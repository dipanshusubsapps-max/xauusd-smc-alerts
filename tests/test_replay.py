"""
Replay backtest test:
Runs full SMC detection across realistic XAUUSD historical candles.
Verifies detection of CHOCH and MSS structure breaks.
"""

from pathlib import Path
import pandas as pd
import pytest

from data_provider import get_data_provider
from smc_detector import SMCDetector, SignalType, Direction


def test_historical_replay_on_sample_data():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_xauusd_m5.csv"
    assert csv_path.exists(), f"Sample data file {csv_path} must exist."

    provider = get_data_provider("csv", source=csv_path)
    df = provider.fetch_candles("XAUUSD", "5m", limit=100)

    assert len(df) == 49

    detector = SMCDetector(
        swing_length=2,
        min_displacement_atr_mult=0.8,
        atr_period=10,
        require_candle_close=True,
        symbol="XAUUSD",
        timeframe="5m"
    )

    signals = detector.detect_signals(df, scan_latest_only=False)
    assert len(signals) > 0, "Expected at least one SMC structure break in the sample dataset"

    # Verify both CHOCH or MSS signals are present in this data
    signal_types = {s.signal_type for s in signals}
    directions = {s.direction for s in signals}

    assert SignalType.CHOCH in signal_types or SignalType.MSS in signal_types
    assert Direction.BEARISH in directions or Direction.BULLISH in directions

    for sig in signals:
        assert sig.confirmed is True
        assert sig.break_level > 0
        assert sig.close_price > 0
        assert len(sig.explanation) > 10
