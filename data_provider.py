"""
Market data provider layer for XAUUSD M5 data.
Supports:
1. Yahoo Finance (Spot 'XAUUSD=X' with fallback to COMEX Gold Futures 'GC=F')
2. Twelve Data API (Free tier 'XAU/USD')
3. CSV Replay Provider (Deterministic historical testing & unit tests)
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd

logger = logging.getLogger("xauusd_smc.data_provider")


class BaseDataProvider(ABC):
    """Abstract base class for all market data providers."""

    @abstractmethod
    def fetch_candles(self, symbol: str, timeframe: str = "5m", limit: int = 250) -> pd.DataFrame:
        """
        Fetch completed OHLCV candle data.
        Returns DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        indexed by integer with 'timestamp' as UTC datetime.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the data provider."""
        pass

    def filter_completed_candles(self, df: pd.DataFrame, timeframe_minutes: int = 5) -> pd.DataFrame:
        """
        Ensures only closed/completed candles are passed downstream.
        Discards the currently forming/unclosed candle to prevent repainting.
        """
        if df.empty:
            return df

        now_utc = datetime.now(timezone.utc)
        candle_delta = timedelta(minutes=timeframe_minutes)

        valid_rows = []
        for idx, row in df.iterrows():
            ts = row['timestamp']
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if now_utc >= (ts + candle_delta):
                valid_rows.append(row)

        if not valid_rows:
            logger.warning("Clock check yielded empty completed set; dropping last candle conservatively.")
            return df.iloc[:-1].copy()

        result_df = pd.DataFrame(valid_rows)
        result_df = result_df.reset_index(drop=True)
        return result_df


class YahooFinanceProvider(BaseDataProvider):
    """
    Yahoo Finance market data provider.
    Free, no API key required.
    Symbols:
    - 'XAUUSD=X': Gold Spot price against US Dollar.
    - 'GC=F': Gold Futures (COMEX). Note: Futures prices carry contango/backwardation spread.
    """

    def __init__(self, fallback_symbol: Optional[str] = "GC=F"):
        self.fallback_symbol = fallback_symbol
        self._last_used_symbol = ""

    @property
    def name(self) -> str:
        return f"Yahoo Finance ({self._last_used_symbol or 'XAUUSD=X'})"

    def fetch_candles(self, symbol: str = "XAUUSD=X", timeframe: str = "5m", limit: int = 250) -> pd.DataFrame:
        """Fetches candles using yfinance with automated fallback."""
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance is required for YahooFinanceProvider. Install with: pip install yfinance")

        symbols_to_try = [symbol]
        if self.fallback_symbol and self.fallback_symbol != symbol:
            symbols_to_try.append(self.fallback_symbol)

        last_error = None
        for sym in symbols_to_try:
            try:
                logger.info(f"Fetching M5 data for {sym} from Yahoo Finance...")
                ticker = yf.Ticker(sym)
                hist = ticker.history(period="5d", interval=timeframe)

                if hist is None or hist.empty:
                    logger.warning(f"No data returned from Yahoo Finance for symbol {sym}")
                    continue

                hist = hist.reset_index()
                time_col = "Datetime" if "Datetime" in hist.columns else "Date"
                if time_col not in hist.columns:
                    raise ValueError(f"Expected time column not found in: {hist.columns.tolist()}")

                df = pd.DataFrame({
                    "timestamp": pd.to_datetime(hist[time_col], utc=True),
                    "open": hist["Open"].astype(float),
                    "high": hist["High"].astype(float),
                    "low": hist["Low"].astype(float),
                    "close": hist["Close"].astype(float),
                    "volume": hist["Volume"].astype(float) if "Volume" in hist.columns else 0.0
                })

                df = df.dropna().sort_values("timestamp").reset_index(drop=True)

                if len(df) < 20:
                    logger.warning(f"Insufficient candle count ({len(df)}) for {sym}")
                    continue

                self._last_used_symbol = sym
                if sym != symbol:
                    logger.warning(
                        f"NOTE: Primary symbol '{symbol}' was unavailable. Using fallback '{sym}'. "
                        "Futures prices may differ from broker CFD spot prices."
                    )

                completed = self.filter_completed_candles(df, timeframe_minutes=5)
                if len(completed) > limit:
                    completed = completed.iloc[-limit:].reset_index(drop=True)

                return completed

            except Exception as e:
                logger.error(f"Error fetching from Yahoo Finance for {sym}: {e}")
                last_error = e

        raise RuntimeError(f"Failed to fetch market data from Yahoo Finance: {last_error}")


class TwelveDataProvider(BaseDataProvider):
    """
    Twelve Data API provider.
    Free tier offers 800 API credits/day (8 credits/minute).
    Symbol: 'XAU/USD'
    Requires TWELVEDATA_API_KEY.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("TWELVEDATA_API_KEY must be provided for TwelveDataProvider.")
        self.api_key = api_key
        self._symbol = "XAU/USD"

    @property
    def name(self) -> str:
        return f"Twelve Data ({self._symbol})"

    # Map common timeframe aliases to Twelve Data format
    _TF_MAP = {
        "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
        "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day",
    }

    def fetch_candles(self, symbol: str = "XAU/USD", timeframe: str = "5min", limit: int = 150) -> pd.DataFrame:
        import urllib.request
        import json

        self._symbol = symbol
        # Normalize timeframe to Twelve Data format (e.g. "5m" → "5min")
        td_interval = self._TF_MAP.get(timeframe, timeframe)
        url = (
            f"https://api.twelvedata.com/time_series?"
            f"symbol={symbol}&interval={td_interval}&outputsize={min(limit, 200)}&apikey={self.api_key}"
        )

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if "values" not in payload:
                error_msg = payload.get("message", "Unknown error from Twelve Data API")
                code = payload.get("code", "N/A")
                raise RuntimeError(f"Twelve Data error [{code}]: {error_msg}")

            values = payload["values"]
            if not values:
                raise ValueError("Twelve Data returned empty candle list.")

            rows = []
            for item in values:
                rows.append({
                    "timestamp": pd.to_datetime(item["datetime"], utc=True),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item.get("volume", 0.0))
                })

            df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
            completed = self.filter_completed_candles(df, timeframe_minutes=5)
            return completed

        except Exception as e:
            logger.error(f"Failed to fetch data from Twelve Data: {e}")
            raise


class CSVReplayProvider(BaseDataProvider):
    """
    Historical / Mock CSV data provider for backtesting, dry-runs, and deterministic tests.
    Does not require internet or API keys.
    """

    def __init__(self, file_path_or_df, name: str = "CSV Replay Feed"):
        self._name = name
        if isinstance(file_path_or_df, pd.DataFrame):
            self._df = file_path_or_df.copy()
        else:
            self._df = pd.read_csv(file_path_or_df)

        self._df.columns = [c.lower() for c in self._df.columns]
        self._df["timestamp"] = pd.to_datetime(self._df["timestamp"], utc=True)
        self._df = self._df.sort_values("timestamp").reset_index(drop=True)

    @property
    def name(self) -> str:
        return self._name

    def fetch_candles(self, symbol: str = "XAUUSD", timeframe: str = "5m", limit: int = 250) -> pd.DataFrame:
        df = self._df.copy()
        if len(df) > limit:
            df = df.iloc[-limit:].reset_index(drop=True)
        return df


def get_data_provider(provider_type: str = "yahoo", **kwargs) -> BaseDataProvider:
    """Factory helper to obtain the requested data provider instance."""
    provider_type = provider_type.lower()
    if provider_type == "yahoo":
        fallback = kwargs.get("fallback_symbol", "GC=F")
        return YahooFinanceProvider(fallback_symbol=fallback)
    elif provider_type == "twelvedata":
        api_key = kwargs.get("api_key", "")
        return TwelveDataProvider(api_key=api_key)
    elif provider_type in ("csv", "mock", "replay"):
        source = kwargs.get("source")
        return CSVReplayProvider(source, name=kwargs.get("name", "Mock Replay Provider"))
    else:
        raise ValueError(f"Unknown data provider type: '{provider_type}'. Choose 'yahoo', 'twelvedata', or 'csv'.")
