"""
Unit tests for Telegram notification formatting, token masking, and dry-run execution.
"""

from datetime import datetime, timezone
import pytest

from smc_detector import SMCSignal, SignalType, Direction
from telegram_alerts import format_alert_message, mask_token, send_telegram_alert


def test_token_masking():
    assert mask_token("") == "***"
    assert mask_token("short") == "***"
    assert mask_token("1234567890:ABCdefGhIjkLmNoPqRsTuVwXyZ") == "123456...wXyZ"


def test_format_alert_message_contains_all_required_fields():
    ts = datetime(2026, 11, 13, 10, 35, tzinfo=timezone.utc)
    signal = SMCSignal(
        signal_type=SignalType.MSS,
        direction=Direction.BULLISH,
        symbol="XAUUSD",
        timeframe="5m",
        candle_timestamp=ts,
        break_level=2735.50,
        close_price=2737.10,
        atr=2.40,
        displacement_ratio=1.45,
        confirmed=True,
        explanation="Impulsive bullish candle broke above swing high with 1.45x ATR displacement."
    )

    msg = format_alert_message(signal, data_provider_name="Yahoo Finance (XAUUSD=X)", session_name="London Session")

    # Verify all mandatory specification fields
    assert "XAUUSD | M5" in msg
    assert "Bullish MSS" in msg
    assert "2735.50" in msg
    assert "2737.10" in msg
    assert "IST" in msg  # Timezone requirement
    assert "Confirmed candle close" in msg
    assert "Yahoo Finance (XAUUSD=X)" in msg
    assert "London Session" in msg
    assert "Impulsive bullish candle" in msg


def test_dry_run_does_not_call_network():
    ts = datetime(2026, 11, 13, 10, 35, tzinfo=timezone.utc)
    signal = SMCSignal(
        signal_type=SignalType.CHOCH,
        direction=Direction.BEARISH,
        symbol="XAUUSD",
        timeframe="5m",
        candle_timestamp=ts,
        break_level=2720.00,
        close_price=2718.50,
        atr=2.0,
        displacement_ratio=1.2,
        confirmed=True,
        explanation="Bearish CHOCH reversal."
    )

    # Dry-run with empty or dummy tokens should succeed gracefully
    result = send_telegram_alert(
        signal=signal,
        data_provider_name="Mock Feed",
        session_name="New York Session",
        bot_token="",
        chat_id="",
        dry_run=True
    )
    assert result is True


def test_live_mode_without_credentials_fails_cleanly():
    ts = datetime(2026, 11, 13, 10, 35, tzinfo=timezone.utc)
    signal = SMCSignal(
        signal_type=SignalType.CHOCH,
        direction=Direction.BEARISH,
        symbol="XAUUSD",
        timeframe="5m",
        candle_timestamp=ts,
        break_level=2720.00,
        close_price=2718.50,
        atr=2.0,
        displacement_ratio=1.2,
        confirmed=True,
        explanation="Bearish CHOCH reversal."
    )

    result = send_telegram_alert(
        signal=signal,
        data_provider_name="Mock Feed",
        session_name="New York Session",
        bot_token="",
        chat_id="",
        dry_run=False
    )
    assert result is False
