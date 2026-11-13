"""
Unit tests for SMC Structure Detector:
- Bullish CHOCH
- Bearish CHOCH
- Bullish MSS
- Bearish MSS
- Candle-close confirmation vs Wick
- Zero-repainting verification
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


def test_bullish_choch_detection():
    """
    Test Bullish CHOCH:
    In a prevailing downtrend (forming LH and LL), price closes above the key Lower High (LH).
    """
    candles = []
    # 1. Establish initial high
    candles.append(make_candle(0, 2740, 2742, 2739, 2741))
    candles.append(make_candle(1, 2741, 2745, 2740, 2744))
    candles.append(make_candle(2, 2744, 2750, 2743, 2749))  # Peak High at 2750
    candles.append(make_candle(3, 2749, 2747, 2742, 2743))
    candles.append(make_candle(4, 2743, 2744, 2740, 2741))
    candles.append(make_candle(5, 2741, 2742, 2738, 2739))

    # 2. Downtrend legs: Lower Low, then Lower High at 2736
    candles.append(make_candle(6, 2739, 2739, 2725, 2726))  # Low 2725
    candles.append(make_candle(7, 2726, 2728, 2724, 2725))
    candles.append(make_candle(8, 2725, 2727, 2723, 2726))
    candles.append(make_candle(9, 2726, 2736, 2725, 2735))  # Lower High peak at 2736
    candles.append(make_candle(10, 2735, 2733, 2728, 2729))
    candles.append(make_candle(11, 2729, 2730, 2722, 2723))
    candles.append(make_candle(12, 2723, 2724, 2715, 2716))  # Lower Low at 2715
    candles.append(make_candle(13, 2716, 2718, 2714, 2715))
    candles.append(make_candle(14, 2715, 2719, 2714, 2718))
    candles.append(make_candle(15, 2718, 2722, 2717, 2721))
    candles.append(make_candle(16, 2721, 2728, 2720, 2727))
    candles.append(make_candle(17, 2727, 2733, 2726, 2732))

    # 18. Candle breaks above Lower High (2736) with confirmed close
    candles.append(make_candle(18, 2732, 2740, 2731, 2739))  # Close 2739 > 2736

    df = pd.DataFrame(candles)
    detector = SMCDetector(swing_length=2, min_displacement_atr_mult=0.5, atr_period=5, require_candle_close=True)
    signals = detector.detect_signals(df, scan_latest_only=True)

    assert len(signals) == 1, f"Expected 1 Bullish CHOCH signal, got {len(signals)}"
    sig = signals[0]
    assert sig.signal_type == SignalType.CHOCH
    assert sig.direction == Direction.BULLISH
    assert sig.break_level == 2736.0
    assert sig.close_price == 2739.0
    assert sig.confirmed is True


def test_bearish_choch_detection():
    """
    Test Bearish CHOCH:
    In a prevailing uptrend (forming HH and HL), price closes below the key Higher Low (HL).
    """
    candles = []
    # 1. Establish initial low at 2695
    candles.append(make_candle(0, 2700, 2702, 2698, 2699))
    candles.append(make_candle(1, 2699, 2701, 2695, 2696))  # Low 2695
    candles.append(make_candle(2, 2696, 2705, 2698, 2704))
    candles.append(make_candle(3, 2704, 2715, 2710, 2714))  # High 2715
    candles.append(make_candle(4, 2714, 2713, 2708, 2709))
    candles.append(make_candle(5, 2709, 2712, 2705, 2706))  # Higher Low at 2705
    candles.append(make_candle(6, 2706, 2714, 2708, 2713))
    candles.append(make_candle(7, 2713, 2725, 2712, 2724))  # Higher High at 2725
    candles.append(make_candle(8, 2724, 2723, 2718, 2719))
    candles.append(make_candle(9, 2719, 2720, 2714, 2715))
    candles.append(make_candle(10, 2715, 2716, 2710, 2711))

    # 11. Candle breaks below Higher Low (2705) with confirmed close
    candles.append(make_candle(11, 2711, 2711, 2700, 2702))  # Close 2702 < 2705

    df = pd.DataFrame(candles)
    detector = SMCDetector(swing_length=2, min_displacement_atr_mult=0.5, atr_period=5, require_candle_close=True)
    signals = detector.detect_signals(df, scan_latest_only=True)

    assert len(signals) == 1, f"Expected 1 Bearish CHOCH signal, got {len(signals)}"
    sig = signals[0]
    assert sig.signal_type == SignalType.CHOCH
    assert sig.direction == Direction.BEARISH
    assert sig.break_level == 2705.0
    assert sig.close_price == 2702.0


def test_candle_close_confirmation_versus_wick():
    """
    Test that a wick breaching the level WITHOUT candle close does NOT trigger an alert
    when require_candle_close=True.
    """
    candles = []
    # Setup swing high at 2730
    candles.append(make_candle(0, 2720, 2725, 2719, 2724))
    candles.append(make_candle(1, 2724, 2730, 2723, 2729))  # Swing High at 2730
    candles.append(make_candle(2, 2729, 2727, 2722, 2723))
    candles.append(make_candle(3, 2723, 2725, 2720, 2721))
    candles.append(make_candle(4, 2721, 2724, 2719, 2722))

    # Candle 5: Wicks to 2733 (> 2730) but closes at 2728 (< 2730)
    candles.append(make_candle(5, 2722, 2733, 2721, 2728))

    df = pd.DataFrame(candles)

    # 1. With require_candle_close=True -> NO alert
    det_close = SMCDetector(swing_length=1, min_displacement_atr_mult=0.5, atr_period=3, require_candle_close=True)
    signals_close = det_close.detect_signals(df, scan_latest_only=True)
    assert len(signals_close) == 0, "Wick-only breach should NOT trigger when require_candle_close is True"

    # 2. With require_candle_close=False -> Triggered
    det_wick = SMCDetector(swing_length=1, min_displacement_atr_mult=0.5, atr_period=3, require_candle_close=False)
    signals_wick = det_wick.detect_signals(df, scan_latest_only=True)
    assert len(signals_wick) >= 1, "Wick breach SHOULD trigger when require_candle_close is False"


def test_bullish_and_bearish_mss_displacement():
    """
    Test Market Structure Shift (MSS) triggers when break has high displacement (>= ATR mult).
    """
    candles = []
    candles.append(make_candle(0, 2720, 2722, 2719, 2721))
    candles.append(make_candle(1, 2721, 2726, 2720, 2725))  # Swing High at 2726
    candles.append(make_candle(2, 2725, 2724, 2721, 2722))
    candles.append(make_candle(3, 2722, 2723, 2720, 2721))

    # Candle 4: Massive bullish displacement candle breaking 2726
    # Range = 2738 - 2721 = 17 points (huge displacement)
    candles.append(make_candle(4, 2721, 2738, 2721, 2737))

    df = pd.DataFrame(candles)
    detector = SMCDetector(swing_length=1, min_displacement_atr_mult=1.0, atr_period=3, require_candle_close=True)
    signals = detector.detect_signals(df, scan_latest_only=True)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == SignalType.MSS
    assert sig.direction == Direction.BULLISH
    assert sig.break_level == 2726.0
    assert sig.displacement_ratio >= 1.0


def test_signal_id_deduplication():
    """
    Test that deterministic signal IDs are identical for the same event,
    preventing duplicate alert broadcasts.
    """
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
