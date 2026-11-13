"""
Unit tests for SMC Structure Detector:
Matching 1:1 with TradingView Pine Script:
'SMC Market Structure (HH/HL/LH/LL + BOS/CHoCH/MSS)'
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from smc_detector import SMCDetector, SignalType, Direction, SMCSignal


def make_candle(ts_idx: int, o: float, h: float, l: float, c: float, v: float = 1000.0) -> dict:
    base_time = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)
    return {
        "timestamp": base_time + timedelta(minutes=5 * ts_idx),
        "open": float(o),
        "high": float(h),
        "low": float(l),
        "close": float(c),
        "volume": float(v)
    }


def test_bullish_choch_and_mss_pine_logic():
    """
    Pine Script Logic Test:
    1. Trend is established as Bearish (trend = -1) by a breakDown.
    2. A swing high is established.
    3. Reversal breakUp occurs:
       - If body <= 1.5 * ATR -> Bullish CHoCH
       - If body > 1.5 * ATR and candle closes past high -> Bullish MSS
    """
    candles = []
    # 0, 1, 2: establish initial swing low at bar 1 (low = 2700)
    candles.append(make_candle(0, 2710, 2712, 2708, 2711))
    candles.append(make_candle(1, 2711, 2713, 2700, 2705))  # Swing Low at 2700
    candles.append(make_candle(2, 2705, 2715, 2704, 2714))  # Swing High at 2715
    candles.append(make_candle(3, 2714, 2712, 2706, 2707))

    # Bar 4: Breaks below 2700 -> establishes trend = -1 (downtrend)
    candles.append(make_candle(4, 2707, 2707, 2690, 2692))

    # Bar 5, 6, 7: Pullback establishing a new Swing High at bar 6 (high = 2710)
    candles.append(make_candle(5, 2692, 2705, 2691, 2704))
    candles.append(make_candle(6, 2704, 2710, 2702, 2708))  # Swing High at 2710
    candles.append(make_candle(7, 2708, 2706, 2698, 2699))
    candles.append(make_candle(8, 2699, 2701, 2695, 2697))

    # Case A: Bar 9 breaks above 2710 with modest body (CHoCH)
    # ATR is approx 8-10 points. Body = 2711 - 2705 = 6 points (< 1.5 * ATR)
    candles_choch = candles.copy()
    candles_choch.append(make_candle(9, 2705, 2712, 2704, 2711))  # Closes at 2711 > 2710

    df_choch = pd.DataFrame(candles_choch)
    detector_choch = SMCDetector(swing_length=1, confirmation_mode="close", min_displacement_atr_mult=1.5, atr_period=5)
    signals_choch = detector_choch.detect_signals(df_choch, scan_latest_only=True)

    assert len(signals_choch) == 1, f"Expected 1 CHoCH, got {len(signals_choch)}"
    assert signals_choch[0].signal_type == SignalType.CHOCH
    assert signals_choch[0].direction == Direction.BULLISH
    assert signals_choch[0].break_level == 2710.0

    # Case B: Bar 9 breaks above 2710 with massive displacement body (MSS)
    # Body = 2730 - 2700 = 30 points (>> 1.5 * ATR)
    candles_mss = candles.copy()
    candles_mss.append(make_candle(9, 2700, 2732, 2699, 2730))

    df_mss = pd.DataFrame(candles_mss)
    detector_mss = SMCDetector(swing_length=1, confirmation_mode="close", min_displacement_atr_mult=1.5, atr_period=5)
    signals_mss = detector_mss.detect_signals(df_mss, scan_latest_only=True)

    assert len(signals_mss) == 1, f"Expected 1 MSS, got {len(signals_mss)}"
    assert signals_mss[0].signal_type == SignalType.MSS
    assert signals_mss[0].direction == Direction.BULLISH
    assert signals_mss[0].break_level == 2710.0


def test_bearish_choch_and_mss_pine_logic():
    """
    Pine Script Logic Test:
    1. Trend is established as Bullish (trend = 1) by a breakUp.
    2. A swing low is established.
    3. Reversal breakDown occurs:
       - If body <= 1.5 * ATR -> Bearish CHoCH
       - If body > 1.5 * ATR and candle closes past low -> Bearish MSS
    """
    candles = []
    # 0, 1, 2: establish initial swing high at bar 1 (high = 2720)
    candles.append(make_candle(0, 2710, 2712, 2708, 2711))
    candles.append(make_candle(1, 2711, 2720, 2710, 2718))  # Swing High at 2720
    candles.append(make_candle(2, 2718, 2716, 2708, 2710))
    candles.append(make_candle(3, 2710, 2712, 2707, 2709))

    # Bar 4: Breaks above 2720 -> establishes trend = 1 (uptrend)
    candles.append(make_candle(4, 2709, 2730, 2708, 2728))

    # Bar 5, 6, 7: Pullback establishing a new Swing Low at bar 6 (low = 2715)
    candles.append(make_candle(5, 2728, 2729, 2720, 2722))
    candles.append(make_candle(6, 2722, 2725, 2715, 2723))  # Swing Low at 2715
    candles.append(make_candle(7, 2723, 2728, 2720, 2727))
    candles.append(make_candle(8, 2727, 2732, 2725, 2731))

    # Case A: Bar 9 breaks below 2715 with modest body (CHoCH)
    candles_choch = candles.copy()
    candles_choch.append(make_candle(9, 2718, 2719, 2713, 2714))  # Closes at 2714 < 2715

    df_choch = pd.DataFrame(candles_choch)
    detector_choch = SMCDetector(swing_length=1, confirmation_mode="close", min_displacement_atr_mult=1.5, atr_period=5)
    signals_choch = detector_choch.detect_signals(df_choch, scan_latest_only=True)

    assert len(signals_choch) == 1, f"Expected 1 Bearish CHoCH, got {len(signals_choch)}"
    assert signals_choch[0].signal_type == SignalType.CHOCH
    assert signals_choch[0].direction == Direction.BEARISH
    assert signals_choch[0].break_level == 2715.0

    # Case B: Bar 9 breaks below 2715 with massive displacement body (MSS)
    candles_mss = candles.copy()
    candles_mss.append(make_candle(9, 2730, 2731, 2695, 2698))  # Giant drop

    df_mss = pd.DataFrame(candles_mss)
    detector_mss = SMCDetector(swing_length=1, confirmation_mode="close", min_displacement_atr_mult=1.5, atr_period=5)
    signals_mss = detector_mss.detect_signals(df_mss, scan_latest_only=True)

    assert len(signals_mss) == 1, f"Expected 1 Bearish MSS, got {len(signals_mss)}"
    assert signals_mss[0].signal_type == SignalType.MSS
    assert signals_mss[0].direction == Direction.BEARISH
    assert signals_mss[0].break_level == 2715.0


def test_wick_versus_close_break_confirmation():
    """
    Test Pine Script 'Wick' vs 'Close' break confirmation setting.
    """
    candles = []
    # Trend = -1
    candles.append(make_candle(0, 2710, 2712, 2708, 2711))
    candles.append(make_candle(1, 2711, 2713, 2700, 2705))
    candles.append(make_candle(2, 2705, 2715, 2704, 2714))
    candles.append(make_candle(3, 2714, 2712, 2706, 2707))
    candles.append(make_candle(4, 2707, 2707, 2690, 2692))  # trend = -1

    candles.append(make_candle(5, 2692, 2705, 2691, 2704))
    candles.append(make_candle(6, 2704, 2710, 2702, 2708))  # Swing High at 2710
    candles.append(make_candle(7, 2708, 2706, 2698, 2699))

    # Bar 8: Wicks above 2710 to 2713, but closes below at 2708
    candles.append(make_candle(8, 2700, 2713, 2699, 2708))

    df = pd.DataFrame(candles)

    # 1. With confirmation_mode="close" -> NO signal
    det_close = SMCDetector(swing_length=1, confirmation_mode="close", atr_period=5)
    sigs_close = det_close.detect_signals(df, scan_latest_only=True)
    assert len(sigs_close) == 0

    # 2. With confirmation_mode="wick" -> Triggers CHoCH
    det_wick = SMCDetector(swing_length=1, confirmation_mode="wick", atr_period=5)
    sigs_wick = det_wick.detect_signals(df, scan_latest_only=True)
    assert len(sigs_wick) == 1
    assert sigs_wick[0].signal_type == SignalType.CHOCH
    assert sigs_wick[0].direction == Direction.BULLISH


def test_signal_id_deduplication():
    ts = datetime(2026, 11, 13, 10, 35, tzinfo=timezone.utc)
    sig1 = SMCSignal(
        signal_type=SignalType.MSS,
        direction=Direction.BULLISH,
        symbol="XAUUSD",
        timeframe="5m",
        candle_timestamp=ts,
        break_level=2735.45,
        close_price=2737.10,
        atr=2.5,
        displacement_ratio=1.6,
        confirmed=True,
        explanation="Test explanation"
    )

    sig2 = SMCSignal(
        signal_type=SignalType.MSS,
        direction=Direction.BULLISH,
        symbol="XAUUSD",
        timeframe="5m",
        candle_timestamp=ts,
        break_level=2735.45,
        close_price=2737.10,
        atr=2.5,
        displacement_ratio=1.6,
        confirmed=True,
        explanation="Duplicate instance"
    )

    assert sig1.signal_id == sig2.signal_id
    assert "XAUUSD_5m_MSS_Bullish" in sig1.signal_id
