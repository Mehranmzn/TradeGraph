import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import aiohttp
from loguru import logger

from ..config.settings import settings
from ..models.financial_data import NewsArticle


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
            for url in filing_urls[:3]:  # Limit to 3 most recent filings
                try:
                    filing_data = await self.scrape_url(url, {
                        "onlyMainContent": True,
                        "includeTags": ["div", "p", "table", "span"],
                        "excludeTags": ["script", "style", "nav", "header", "footer"]
                    })

                    if "data" in filing_data:
                        filings.append({
                            "url": url,
                            "content": filing_data["data"]["markdown"][:10000],  # Limit content
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
        urls = []
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, 'html.parser')

            # Find filing document links in SEC EDGAR format
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/Archives/edgar/data/' in href and href.endswith('.htm'):
                    if not href.startswith('http'):
                        href = f"https://www.sec.gov{href}"
                    urls.append(href)

        except Exception as e:
            logger.warning(f"Error extracting filing URLs: {str(e)}")

        return urls

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

            for elem in unique_articles[:max_articles]:
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

                    # Extract content preview
                    content_elem = elem.find(['p', 'div'])
                    content = content_elem.get_text(strip=True)[:500] if content_elem else ""

                    # Check if article is relevant to symbols
                    is_relevant = any(
                        symbol.lower() in title.lower() or symbol.lower() in content.lower()
                        for symbol in symbols
                    )

                    if title and (is_relevant or not symbols):
                        article = NewsArticle(
                            title=title,
                            url=url,
                            content=content,
                            source=source,
                            published_at=datetime.now(),
                            symbols=symbols
                        )
                        articles.append(article)

                except Exception as e:
                    logger.warning(f"Error parsing article element: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting articles from {source}: {str(e)}")

        return articles

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