"""
Cryptocurrency data service for fetching crypto market data and news.
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
from pycoingecko import CoinGeckoAPI
import ccxt

from ..models.financial_data import FinancialData, TechnicalIndicators


class CryptoDataService:
    """Service for fetching cryptocurrency data from multiple sources."""

    def __init__(self):
        self.coingecko = CoinGeckoAPI()
        self.exchanges = {}
        self._initialize_exchanges()

    def _initialize_exchanges(self):
        """Initialize cryptocurrency exchanges for data fetching."""
        try:
            # Initialize major exchanges (free tier)
            self.exchanges = {
                'binance': ccxt.binance({'sandbox': False}),
                'coinbase': ccxt.coinbasepro({'sandbox': False}),
                'kraken': ccxt.kraken({'sandbox': False})
            }
            logger.info("Cryptocurrency exchanges initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize some exchanges: {str(e)}")

    def is_crypto_symbol(self, symbol: str) -> bool:
        """Check if a symbol is a cryptocurrency."""
        crypto_indicators = ['-USD', '-BTC', '-ETH', 'USDT', 'USD']
        symbol_upper = symbol.upper()

        # Common crypto symbols
        major_cryptos = [
            'BTC', 'ETH', 'BNB', 'ADA', 'DOT', 'XRP', 'LINK', 'LTC',
            'BCH', 'UNI', 'SOL', 'AVAX', 'MATIC', 'ATOM', 'FTT', 'ALGO'
        ]

        # Check if it's a major crypto
        if symbol_upper in major_cryptos:
            return True

        # Check for crypto trading pairs
        for indicator in crypto_indicators:
            if indicator in symbol_upper:
                return True

        return False

    def normalize_crypto_symbol(self, symbol: str) -> str:
        """Normalize cryptocurrency symbol for different APIs."""
        symbol = symbol.upper()

        # Handle common formats
        if '-USD' in symbol:
            return symbol.replace('-USD', '')
        elif 'USDT' in symbol:
            return symbol.replace('USDT', '')
        elif '/USD' in symbol:
            return symbol.replace('/USD', '')

        return symbol

    async def get_crypto_data(self, symbol: str) -> Optional[FinancialData]:
        """Fetch cryptocurrency financial data."""
        try:
            normalized_symbol = self.normalize_crypto_symbol(symbol)

            # Get data from CoinGecko
            crypto_data = await self._get_coingecko_data(normalized_symbol)
            if not crypto_data:
                return None

            # Convert to FinancialData format
            financial_data = FinancialData(
                symbol=symbol,
                company_name=crypto_data.get('name', symbol),
                market_cap=crypto_data.get('market_cap'),
                pe_ratio=None,  # N/A for crypto
                price_to_book=None,  # N/A for crypto
                dividend_yield=None,  # N/A for crypto
                beta=None,  # N/A for crypto
                fifty_two_week_high=crypto_data.get('ath'),
                fifty_two_week_low=crypto_data.get('atl'),
                current_price=crypto_data.get('current_price'),
                report_date=datetime.now(),
                report_type="crypto_data"
            )

            return financial_data

        except Exception as e:
            logger.error(f"Error fetching crypto data for {symbol}: {str(e)}")
            return None

    async def _get_coingecko_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch data from CoinGecko API."""
        try:
            # Map common symbols to CoinGecko IDs
            symbol_map = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'BNB': 'binancecoin',
                'ADA': 'cardano',
                'DOT': 'polkadot',
                'XRP': 'ripple',
                'LINK': 'chainlink',
                'LTC': 'litecoin',
                'BCH': 'bitcoin-cash',
                'UNI': 'uniswap',
                'SOL': 'solana',
                'AVAX': 'avalanche-2',
                'MATIC': 'matic-network',
                'ATOM': 'cosmos',
                'ALGO': 'algorand'
            }

            coin_id = symbol_map.get(symbol.upper(), symbol.lower())

            # Fetch coin data
            coin_data = self.coingecko.get_coin_by_id(coin_id)

            if not coin_data:
                return None

            market_data = coin_data.get('market_data', {})

            return {
                'name': coin_data.get('name'),
                'symbol': coin_data.get('symbol', '').upper(),
                'current_price': market_data.get('current_price', {}).get('usd'),
                'market_cap': market_data.get('market_cap', {}).get('usd'),
                'total_volume': market_data.get('total_volume', {}).get('usd'),
                'ath': market_data.get('ath', {}).get('usd'),
                'atl': market_data.get('atl', {}).get('usd'),
                'price_change_24h': market_data.get('price_change_24h'),
                'price_change_percentage_24h': market_data.get('price_change_percentage_24h'),
                'price_change_percentage_7d': market_data.get('price_change_percentage_7d'),
                'price_change_percentage_30d': market_data.get('price_change_percentage_30d'),
                'circulating_supply': market_data.get('circulating_supply'),
                'total_supply': market_data.get('total_supply'),
                'last_updated': market_data.get('last_updated')
            }

        except Exception as e:
            logger.error(f"Error fetching CoinGecko data for {symbol}: {str(e)}")
            return None

    async def get_crypto_technical_indicators(self, symbol: str) -> Optional[TechnicalIndicators]:
        """Calculate technical indicators for cryptocurrency."""
        try:
            normalized_symbol = self.normalize_crypto_symbol(symbol)

            # Get historical data from exchange
            historical_data = await self._get_crypto_ohlcv(normalized_symbol)
            if not historical_data or len(historical_data) < 50:
                return None

            df = pd.DataFrame(historical_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Calculate technical indicators
            close_prices = df['close']

            # Simple Moving Averages
            sma_20 = close_prices.rolling(window=20).mean().iloc[-1]
            sma_50 = close_prices.rolling(window=50).mean().iloc[-1]

            # Exponential Moving Averages
            ema_12_series = close_prices.ewm(span=12).mean()
            ema_26_series = close_prices.ewm(span=26).mean()
            ema_12 = ema_12_series.iloc[-1]
            ema_26 = ema_26_series.iloc[-1]

            # RSI
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            # MACD
            macd_line = ema_12_series - ema_26_series
            macd_signal = macd_line.ewm(span=9).mean().iloc[-1]

            # Bollinger Bands
            bb_window = 20
            bb_std = close_prices.rolling(window=bb_window).std().iloc[-1]
            bb_sma = close_prices.rolling(window=bb_window).mean().iloc[-1]
            bb_upper = bb_sma + (bb_std * 2)
            bb_lower = bb_sma - (bb_std * 2)

            # Volume indicators
            volume_sma = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / volume_sma if volume_sma > 0 else 1.0

            technical = TechnicalIndicators(
                symbol=symbol,
                sma_20=float(sma_20),
                sma_50=float(sma_50),
                ema_12=float(ema_12),
                ema_26=float(ema_26),
                rsi=float(rsi),
                macd_signal=float(macd_signal),
                bollinger_upper=float(bb_upper),
                bollinger_lower=float(bb_lower),
                volume_sma=float(volume_sma),
                volume_ratio=float(volume_ratio),
                timestamp=datetime.now()
            )

            return technical

        except Exception as e:
            logger.error(f"Error calculating crypto technical indicators for {symbol}: {str(e)}")
            return None

    async def _get_crypto_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Optional[List]:
        """Fetch OHLCV data from cryptocurrency exchange."""
        try:
            # Try different exchanges
            for exchange_name, exchange in self.exchanges.items():
                try:
                    if exchange.has['fetchOHLCV']:
                        # Common trading pairs
                        pairs = [f"{symbol}/USDT", f"{symbol}/USD", f"{symbol}/BTC"]

                        for pair in pairs:
                            try:
                                ohlcv = exchange.fetch_ohlcv(pair, timeframe, limit=limit)
                                if ohlcv and len(ohlcv) >= 50:
                                    logger.info(f"Fetched {len(ohlcv)} OHLCV records for {pair} from {exchange_name}")
                                    return ohlcv
                            except Exception as e:
                                continue  # Try next pair

                except Exception as e:
                    continue  # Try next exchange

            logger.warning(f"Could not fetch OHLCV data for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error fetching crypto OHLCV for {symbol}: {str(e)}")
            return None

    async def get_crypto_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch cryptocurrency news and sentiment."""
        try:
            normalized_symbol = self.normalize_crypto_symbol(symbol)

            # Use CoinGecko for news (limited in free tier)
            # In production, you might want to use specialized crypto news APIs

            return [
                {
                    'title': f'Crypto Market Analysis for {symbol}',
                    'source': 'crypto_service',
                    'content': f'Technical analysis suggests monitoring {symbol} for market movements',
                    'sentiment': 'neutral',
                    'timestamp': datetime.now().isoformat()
                }
            ]

        except Exception as e:
            logger.error(f"Error fetching crypto news for {symbol}: {str(e)}")
            return []