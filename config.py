"""
Configuration settings for XAUUSD SMC Alert System.
Loads parameters from environment variables with sensible defaults.
"""

import os
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional, Tuple

# Try loading .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# --- Core Trading & Symbol Parameters ---
INSTRUMENT = os.getenv("INSTRUMENT", "XAUUSD")
TIMEFRAME = os.getenv("TIMEFRAME", "5m")
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "yahoo").lower()  # 'yahoo' or 'twelvedata'

# Default symbols per provider
# Yahoo: 'XAUUSD=X' (Gold Spot vs USD currency feed), fallback 'GC=F' (COMEX Gold Futures)
# Twelve Data: 'XAU/USD'
YAHOO_SYMBOL = os.getenv("YAHOO_SYMBOL", "XAUUSD=X")
YAHOO_FALLBACK_SYMBOL = os.getenv("YAHOO_FALLBACK_SYMBOL", "GC=F")
TWELVEDATA_SYMBOL = os.getenv("TWELVEDATA_SYMBOL", "XAU/USD")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")

# --- SMC Engine Configuration ---
# Lookback bars on each side for swing pivot detection (e.g. 3 bars left, 3 bars right)
SWING_LENGTH = int(os.getenv("SWING_LENGTH", "3"))

# Market Structure Shift (MSS) displacement filter
# Ratio of candle body / range against ATR (Average True Range)
MIN_DISPLACEMENT_ATR_MULT = float(os.getenv("MIN_DISPLACEMENT_ATR_MULT", "1.0"))
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))

# Confirmation rule: 'close' requires candle close past break level, 'wick' requires high/low breach
CONFIRMATION_MODE = os.getenv("CONFIRMATION_MODE", "close").lower()
REQUIRE_CANDLE_CLOSE = CONFIRMATION_MODE == "close"

# Number of historical candles to fetch for reliable structure calculation
HISTORY_CANDLE_LIMIT = int(os.getenv("HISTORY_CANDLE_LIMIT", "250"))

# --- Session Filtering ---
# Set to True if alerts should ONLY be fired during London & New York sessions
FILTER_SESSIONS = os.getenv("FILTER_SESSIONS", "false").lower() in ("true", "1", "yes")

# Session UTC Times:
# London: 08:00 - 16:30 UTC
# New York: 13:00 - 21:30 UTC
# Overlap: 13:00 - 16:30 UTC
LONDON_START_UTC = time(8, 0)
LONDON_END_UTC = time(16, 30)
NY_START_UTC = time(13, 0)
NY_END_UTC = time(21, 30)

# Target Alert Timezone
ALERT_TIMEZONE_STR = os.getenv("ALERT_TIMEZONE", "Asia/Kolkata")
try:
    ALERT_TIMEZONE = ZoneInfo(ALERT_TIMEZONE_STR)
except Exception:
    ALERT_TIMEZONE = timezone.utc

# --- Telegram Bot Config ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

# --- State Persistence & Deduplication ---
STATE_FILE_PATH = Path(os.getenv("STATE_FILE_PATH", "state.json"))


def get_active_session_name(dt_utc: datetime) -> Tuple[bool, str]:
    """
    Checks if a given UTC datetime falls within the London or New York sessions.
    Returns (is_active, session_description).
    """
    t = dt_utc.time()
    in_london = LONDON_START_UTC <= t <= LONDON_END_UTC
    in_ny = NY_START_UTC <= t <= NY_END_UTC

    if in_london and in_ny:
        return True, "London / New York Overlap"
    elif in_london:
        return True, "London Session"
    elif in_ny:
        return True, "New York Session"
    else:
        return False, "Asian / Off-Session"


def validate_config(is_dry_run: bool = False) -> list[str]:
    """
    Validates essential configuration parameters.
    Returns list of warning/error messages (empty if completely valid).
    """
    errors = []
    if not is_dry_run and not DRY_RUN:
        if not TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is missing or empty.")
        if not TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is missing or empty.")

    if DATA_PROVIDER == "twelvedata" and not TWELVEDATA_API_KEY:
        errors.append("TWELVEDATA_API_KEY is required when DATA_PROVIDER is 'twelvedata'.")

    return errors
