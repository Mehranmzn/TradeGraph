import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import aiohttp
from loguru import logger
import re
from dateutil import parser as date_parser

from ..config.settings import settings
from ..models.financial_data import NewsArticle
from ..utils.helpers import generate_summary


class FirecrawlService:
    def __init__(self):
        self.api_key = settings.firecrawl_api_key
        self.base_url = "https://api.firecrawl.dev"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=settings.analysis_timeout_seconds)
        )

    async def stop(self) -> None:
        if self.session:
            await self.session.close()

    async def scrape_url(self, url: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("FirecrawlService not started")

        payload = {
            "url": url,
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
            "includeTags": ["article", "main", "div"],
            "excludeTags": ["nav", "footer", "aside", "script", "style"],
            "waitFor": 2000,
            "timeout": 30000
        }

        if options:
            payload.update(options)

        try:
            async with self.session.post(f"{self.base_url}/v1/scrape", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Firecrawl scrape failed for {url}: {response.status} - {error_text}")
                    raise Exception(f"Firecrawl API error: {response.status}")

        except Exception as e:
            logger.error(f"Error scraping {url} with Firecrawl: {str(e)}")
            raise

    async def scrape_multiple_urls(
        self,
        urls: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not urls:
            return []

        # Limit concurrent requests to avoid overwhelming the API
        semaphore = asyncio.Semaphore(3)

        async def scrape_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.scrape_url(url, options)
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {str(e)}")
                    return {"url": url, "error": str(e)}

        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return valid results
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception scraping {urls[i]}: {str(result)}")
            elif isinstance(result, dict) and "error" not in result:
                valid_results.append(result)

        return valid_results

    async def scrape_financial_reports(
        self,
        company_symbol: str,
        report_type: str = "10-K"
    ) -> List[Dict[str, Any]]:
        try:
            # SEC EDGAR search URL
            edgar_search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={company_symbol}&type={report_type}&dateb=&owner=include&count=10"

            # First, scrape the search results page
            search_results = await self.scrape_url(edgar_search_url, {
                "includeTags": ["table", "tr", "td", "a"],
                "waitFor": 3000
            })

            if "data" not in search_results:
                return []

            # Extract filing URLs from the search results
            filing_urls = self._extract_filing_urls(search_results["data"])

            # Scrape the actual filing documents
            filings = []
            if isinstance(filing_urls, list) and len(filing_urls) > 0:
                urls_to_process = filing_urls[:3]  # Limit to 3 most recent filings
            else:
                urls_to_process = []

            for url in urls_to_process:
                try:
                    filing_data = await self.scrape_url(url, {
                        "onlyMainContent": True,
                        "includeTags": ["div", "p", "table", "span"],
                        "excludeTags": ["script", "style", "nav", "header", "footer"]
                    })

                    if "data" in filing_data:
                        markdown_content = filing_data["data"].get("markdown", "")
                        if isinstance(markdown_content, str):
                            content = markdown_content[:10000]
                        else:
                            content = str(markdown_content)[:10000]

                        filings.append({
                            "url": url,
                            "content": content,
                            "scraped_at": datetime.now().isoformat(),
                            "report_type": report_type
                        })

                except Exception as e:
                    logger.warning(f"Failed to scrape filing {url}: {str(e)}")

            return filings

        except Exception as e:
            logger.error(f"Error scraping financial reports for {company_symbol}: {str(e)}")
            return []

    def _extract_filing_urls(self, html_content: str) -> List[str]:
        """Extract SEC filing URLs, prioritizing the most recent filings."""
        filing_data = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, 'html.parser')

            # Look for filing tables (SEC EDGAR format)
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')[1:]  # Skip header row

                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:  # Typical SEC filing table has multiple columns
                        try:
                            # Extract filing date (usually in first few columns)
                            filing_date_text = None
                            for i in range(min(3, len(cells))):
                                cell_text = cells[i].get_text(strip=True)
                                if re.match(r'\d{4}-\d{2}-\d{2}', cell_text):
                                    filing_date_text = cell_text
                                    break

                            # Extract filing URL
                            link = row.find('a', href=True)
                            if link and '/Archives/edgar/data/' in link.get('href', ''):
                                href = link['href']
                                if not href.startswith('http'):
                                    href = f"https://www.sec.gov{href}"

                                # Parse filing date
                                filing_date = datetime.now()
                                if filing_date_text:
                                    try:
                                        filing_date = date_parser.parse(filing_date_text)
                                    except:
                                        pass

                                filing_data.append({
                                    'url': href,
                                    'date': filing_date,
                                    'date_text': filing_date_text
                                })

                        except Exception as e:
                            continue

            # If table parsing failed, fall back to simple link extraction
            if not filing_data:
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    if '/Archives/edgar/data/' in href and href.endswith('.htm'):
                        if not href.startswith('http'):
                            href = f"https://www.sec.gov{href}"

                        # Try to extract date from link text or nearby elements
                        link_text = link.get_text(strip=True)
                        parent_text = link.parent.get_text(strip=True) if link.parent else ""

                        filing_date = datetime.now()
                        for text in [link_text, parent_text]:
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                            if date_match:
                                try:
                                    filing_date = date_parser.parse(date_match.group(1))
                                    break
                                except:
                                    pass

                        filing_data.append({
                            'url': href,
                            'date': filing_date,
                            'date_text': None
                        })

            # Sort by date (newest first) and remove duplicates
            filing_data.sort(key=lambda x: x['date'], reverse=True)

            # Remove duplicate URLs, keeping the newest
            seen_urls = set()
            unique_filings = []

            for filing in filing_data:
                url = filing['url']
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_filings.append(filing)

            # Only keep filings from the last 2 years for relevance
            cutoff_date = datetime.now() - timedelta(days=730)
            recent_filings = [f for f in unique_filings if f['date'] >= cutoff_date]

            # Return only URLs of recent, unique filings (up to 5 most recent)
            return [filing['url'] for filing in recent_filings[:5]]

        except Exception as e:
            logger.warning(f"Error extracting filing URLs: {str(e)}")
            return []

    async def scrape_news_websites(
        self,
        symbols: List[str],
        max_articles_per_source: int = 10
    ) -> List[NewsArticle]:
        news_sources = {
            "marketwatch": f"https://www.marketwatch.com/search?q={'+'.join(symbols)}",
            "yahoo_finance": f"https://finance.yahoo.com/lookup?s={symbols[0]}" if symbols else "",
            "seeking_alpha": f"https://seekingalpha.com/search?q={'+'.join(symbols)}",
            "bloomberg": f"https://www.bloomberg.com/search?query={'+'.join(symbols)}"
        }

        all_articles = []

        for source, search_url in news_sources.items():
            try:
                if not search_url:
                    continue

                logger.info(f"Scraping {source} for symbols: {symbols}")

                search_results = await self.scrape_url(search_url, {
                    "includeTags": ["article", "div", "h1", "h2", "h3", "p", "a", "time"],
                    "excludeTags": ["script", "style", "nav", "footer", "aside", "advertisement"],
                    "waitFor": 3000
                })

                if "data" in search_results:
                    articles = self._extract_articles_from_html(
                        search_results["data"],
                        source,
                        symbols,
                        max_articles_per_source
                    )
                    all_articles.extend(articles)

            except Exception as e:
                logger.warning(f"Failed to scrape {source}: {str(e)}")

        return all_articles

    def _extract_articles_from_html(
        self,
        scraped_data: Dict[str, Any],
        source: str,
        symbols: List[str],
        max_articles: int
    ) -> List[NewsArticle]:
        articles = []

        try:
            markdown_content = scraped_data.get("markdown", "")
            html_content = scraped_data.get("html", "")

            from bs4 import BeautifulSoup

            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
            else:
                # Fallback to markdown parsing
                soup = BeautifulSoup(markdown_content, 'html.parser')

            # Extract article elements based on common patterns
            article_selectors = [
                'article',
                '.story-card',
                '.news-item',
                '.article-card',
                '[data-testid*="article"]',
                '.headline'
            ]

            found_articles = []
            for selector in article_selectors:
                elements = soup.select(selector)
                found_articles.extend(elements)

            # Remove duplicates and limit results
            unique_articles = list({str(elem): elem for elem in found_articles}.values())

            # Sort by extractable publication dates first
            article_data = []

            for elem in unique_articles:
                try:
                    # Extract title
                    title_elem = (
                        elem.find(['h1', 'h2', 'h3']) or
                        elem.find('a') or
                        elem.find(class_=['title', 'headline'])
                    )

                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    # Extract URL
                    link_elem = elem.find('a')
                    url = link_elem.get('href', '') if link_elem else ''

                    if url and not url.startswith('http'):
                        if source == "marketwatch":
                            url = f"https://www.marketwatch.com{url}"
                        elif source == "yahoo_finance":
                            url = f"https://finance.yahoo.com{url}"
                        elif source == "seeking_alpha":
                            url = f"https://seekingalpha.com{url}"
                        elif source == "bloomberg":
                            url = f"https://www.bloomberg.com{url}"

                    # Extract publication date
                    published_at = self._extract_publication_date(elem, source)

                    # Extract content preview
                    content_elem = elem.find(['p', 'div'])
                    content = content_elem.get_text(strip=True)[:500] if content_elem else ""

                    # Check if article is relevant to symbols
                    is_relevant = any(
                        symbol.lower() in title.lower() or symbol.lower() in content.lower()
                        for symbol in symbols
                    )

                    if title and (is_relevant or not symbols):
                        article_data.append({
                            'title': title,
                            'url': url,
                            'content': content,
                            'published_at': published_at,
                            'source': source,
                            'symbols': symbols
                        })

                except Exception as e:
                    logger.warning(f"Error parsing article element: {str(e)}")
                    continue

            # Sort by publication date (newest first) and filter recent articles
            cutoff_date = datetime.now() - timedelta(days=90)  # Extend to 90 days for better coverage
            article_data.sort(key=lambda x: x['published_at'], reverse=True)

            logger.info(f"Found {len(article_data)} articles before filtering for {source}")

            # Remove duplicates based on title similarity and keep newest
            filtered_articles = self._remove_duplicate_articles(article_data)

            logger.info(f"After duplicate removal: {len(filtered_articles)} articles for {source}")

            # Take recent articles (be more lenient with date filtering)
            added_count = 0
            for article_info in filtered_articles[:max_articles * 2]:  # Check more candidates
                try:
                    # Be more lenient with date filtering - include articles even if slightly older
                    if article_info['published_at'] >= cutoff_date or added_count < 3:
                        article = NewsArticle(
                            title=article_info['title'],
                            url=article_info['url'],
                            content=article_info['content'],
                            summary=generate_summary(article_info['content'] or article_info['title']),
                            source=article_info['source'],
                            published_at=article_info['published_at'],
                            symbols=article_info['symbols']
                        )
                        articles.append(article)
                        added_count += 1

                    if added_count >= max_articles:
                        break

                except Exception as e:
                    logger.warning(f"Error creating article object: {str(e)}")
                    continue

            logger.info(f"Final article count for {source}: {len(articles)}")

        except Exception as e:
            logger.error(f"Error extracting articles from {source}: {str(e)}")

        return articles

    def _extract_publication_date(self, elem, source: str) -> datetime:
        """Extract publication date from article element."""
        try:
            # Try various date element selectors
            date_selectors = [
                'time',
                '.timestamp', '.date', '.published-date',
                '[datetime]', '[data-timestamp]',
                '.article-date', '.post-date'
            ]

            date_text = None

            for selector in date_selectors:
                date_elem = elem.select_one(selector)
                if date_elem:
                    # Try datetime attribute first
                    if date_elem.has_attr('datetime'):
                        date_text = date_elem['datetime']
                    elif date_elem.has_attr('data-timestamp'):
                        date_text = date_elem['data-timestamp']
                    else:
                        date_text = date_elem.get_text(strip=True)
                    break

            # If no dedicated date element, look for date patterns in text
            if not date_text:
                text_content = elem.get_text()
                # Common date patterns
                date_patterns = [
                    r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
                    r'(\d{4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD
                    r'(\w+ \d{1,2}, \d{4})',     # Month DD, YYYY
                    r'(\d{1,2} \w+ \d{4})',      # DD Month YYYY
                    r'(\d+ hours? ago)',          # X hours ago
                    r'(\d+ days? ago)',           # X days ago
                ]

                for pattern in date_patterns:
                    match = re.search(pattern, text_content, re.IGNORECASE)
                    if match:
                        date_text = match.group(1)
                        break

            if date_text:
                # Handle relative dates
                if 'ago' in date_text.lower():
                    if 'hour' in date_text:
                        hours = int(re.search(r'(\d+)', date_text).group(1))
                        return datetime.now() - timedelta(hours=hours)
                    elif 'day' in date_text:
                        days = int(re.search(r'(\d+)', date_text).group(1))
                        return datetime.now() - timedelta(days=days)

                # Try to parse the date
                return date_parser.parse(date_text, fuzzy=True)

        except Exception as e:
            logger.debug(f"Could not extract date from {source} article: {str(e)}")

        # Fallback: return current time minus a small random offset to maintain some ordering
        import random
        return datetime.now() - timedelta(minutes=random.randint(0, 60))

    def _remove_duplicate_articles(self, article_data: List[Dict]) -> List[Dict]:
        """Remove duplicate articles based on title similarity, keeping the newest."""
        from difflib import SequenceMatcher

        def title_similarity(title1: str, title2: str) -> float:
            """Calculate similarity between two titles."""
            return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()

        unique_articles = []
        similarity_threshold = 0.85  # 85% similarity threshold

        for article in article_data:
            is_duplicate = False

            for existing in unique_articles:
                if title_similarity(article['title'], existing['title']) > similarity_threshold:
                    # Found a duplicate - keep the newer one
                    if article['published_at'] > existing['published_at']:
                        unique_articles.remove(existing)
                        break
                    else:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_articles.append(article)

        return unique_articles

    async def health_check(self) -> bool:
        try:
            if not self.session:
                await self.start()

            # Test with a simple URL
            test_result = await self.scrape_url(
                "https://httpbin.org/json",
                {"formats": ["markdown"]}
            )

            return "data" in test_result

        except Exception as e:
            logger.error(f"Firecrawl health check failed: {str(e)}")
            return False
