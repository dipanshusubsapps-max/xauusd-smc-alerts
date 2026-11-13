"""
Unit tests for Data Providers:
- Completed candle filtering (anti-repainting)
- Mock / CSV Provider
- Yahoo / TwelveData fallback behavior
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from data_provider import CSVReplayProvider, BaseDataProvider, get_data_provider


class DummyProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Dummy"

    def fetch_candles(self, symbol: str, timeframe: str = "5m", limit: int = 100) -> pd.DataFrame:
        return pd.DataFrame()


def test_completed_candle_filtering():
    """
    Ensures an in-progress/forming candle whose interval has not fully elapsed
    is dropped to eliminate repainting.
    """
    provider = DummyProvider()
    now_utc = datetime.now(timezone.utc)

    # 1. Closed candle: started 10 mins ago (elapsed > 5m)
    c1_ts = now_utc - timedelta(minutes=10)
    # 2. In-progress candle: started 1 minute ago (elapsed < 5m)
    c2_ts = now_utc - timedelta(minutes=1)

    df = pd.DataFrame([
        {"timestamp": c1_ts, "open": 2700, "high": 2705, "low": 2699, "close": 2704, "volume": 100},
        {"timestamp": c2_ts, "open": 2704, "high": 2708, "low": 2703, "close": 2707, "volume": 50}
    ])

    filtered = provider.filter_completed_candles(df, timeframe_minutes=5)

    # c2_ts must be dropped because it has only elapsed 1 minute
    assert len(filtered) == 1
    assert filtered.iloc[0]['timestamp'] == c1_ts


def test_csv_replay_provider():
    """Verifies that the CSVReplayProvider loads and formats data properly."""
    raw_data = pd.DataFrame([
        {"timestamp": "2026-11-13T08:00:00Z", "open": 2700, "high": 2702, "low": 2698, "close": 2701, "volume": 500},
        {"timestamp": "2026-11-13T08:05:00Z", "open": 2701, "high": 2704, "low": 2700, "close": 2703, "volume": 600},
        {"timestamp": "2026-11-13T08:10:00Z", "open": 2703, "high": 2706, "low": 2702, "close": 2705, "volume": 700}
    ])

    provider = get_data_provider("csv", source=raw_data)
    candles = provider.fetch_candles("XAUUSD", "5m", limit=2)

    assert len(candles) == 2
    assert "timestamp" in candles.columns
    assert candles.iloc[-1]['close'] == 2705.0


def test_unknown_provider_raises_error():
    """Verifies that an unsupported provider name raises a descriptive error."""
    with pytest.raises(ValueError, match="Unknown data provider type"):
        get_data_provider("non_existent_provider")
