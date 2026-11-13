"""
Main entry point and orchestrator for the XAUUSD SMC Alert System.
Integrates data fetching, SMC structure detection, session filtering,
state persistence / deduplication, and Telegram notifications.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import config
from data_provider import get_data_provider, BaseDataProvider
from smc_detector import SMCDetector, SMCSignal
from telegram_alerts import send_telegram_alert, test_telegram_connection, mask_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("xauusd_smc.main")


class StateManager:
    """Manages persistent state between runs to guarantee zero duplicate alerts."""

    def __init__(self, state_file: Path = config.STATE_FILE_PATH):
        self.state_file = state_file
        self.state: Dict[str, Any] = {
            "alerted_signals": [],
            "last_run_timestamp": None,
            "last_candle_timestamp": None
        }
        self.load()

    def load(self) -> None:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                logger.info(f"Loaded existing state with {len(self.state.get('alerted_signals', []))} alerted signals.")
            except Exception as e:
                logger.warning(f"Could not read state file ({e}). Starting with clean state.")

    def save(self) -> None:
        try:
            # Retain maximum 500 recent signal IDs to prevent unbounded growth
            signals = self.state.get("alerted_signals", [])
            if len(signals) > 500:
                self.state["alerted_signals"] = signals[-500:]

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            logger.info("Saved persistent state successfully.")
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def is_already_alerted(self, signal_id: str) -> bool:
        return signal_id in self.state.get("alerted_signals", [])

    def record_signal(self, signal_id: str) -> None:
        if "alerted_signals" not in self.state:
            self.state["alerted_signals"] = []
        if signal_id not in self.state["alerted_signals"]:
            self.state["alerted_signals"].append(signal_id)


def run_pipeline(dry_run: bool = False, force_session: bool = False) -> int:
    """
    Executes a single monitoring cycle:
    1. Fetch latest completed M5 candles.
    2. Check session window.
    3. Detect structure breaks.
    4. Send alerts for new signals.
    5. Update state.
    """
    logger.info("==================================================")
    logger.info(f"Starting SMC Check: {config.INSTRUMENT} {config.TIMEFRAME}")
    logger.info(f"Provider: {config.DATA_PROVIDER} | Mode: {'DRY-RUN' if (dry_run or config.DRY_RUN) else 'LIVE'}")
    logger.info("==================================================")

    # 1. Initialize Data Provider
    if config.DATA_PROVIDER == "yahoo":
        provider = get_data_provider("yahoo", fallback_symbol=config.YAHOO_FALLBACK_SYMBOL)
        target_symbol = config.YAHOO_SYMBOL
    elif config.DATA_PROVIDER == "twelvedata":
        provider = get_data_provider("twelvedata", api_key=config.TWELVEDATA_API_KEY)
        target_symbol = config.TWELVEDATA_SYMBOL
    else:
        logger.error(f"Unsupported data provider: {config.DATA_PROVIDER}")
        return 1

    # 2. Fetch Completed Candles
    try:
        candles_df = provider.fetch_candles(
            symbol=target_symbol,
            timeframe=config.TIMEFRAME,
            limit=config.HISTORY_CANDLE_LIMIT
        )
        logger.info(f"Successfully fetched {len(candles_df)} completed M5 candles from {provider.name}.")
    except Exception as e:
        logger.error(f"Data acquisition error: {e}")
        return 1

    if len(candles_df) < (2 * config.SWING_LENGTH + config.ATR_PERIOD + 5):
        logger.warning("Insufficient historical candles for reliable structure detection.")
        return 0

    latest_candle = candles_df.iloc[-1]
    latest_ts = latest_candle['timestamp']
    latest_close = float(latest_candle['close'])
    logger.info(f"Latest closed candle: {latest_ts.isoformat()} | Close: {latest_close:.2f}")

    # 3. Session Filtering
    is_active_session, session_name = config.get_active_session_name(latest_ts)
    logger.info(f"Active Market Session: {session_name} (Active: {is_active_session})")

    if config.FILTER_SESSIONS and not is_active_session and not force_session:
        logger.info("Session filter is enabled and market is outside London/NY sessions. Skipping alerts.")
        return 0

    # 4. Run SMC Detection Engine
    detector = SMCDetector(
        swing_length=config.SWING_LENGTH,
        min_displacement_atr_mult=config.MIN_DISPLACEMENT_ATR_MULT,
        atr_period=config.ATR_PERIOD,
        require_candle_close=config.REQUIRE_CANDLE_CLOSE,
        symbol=config.INSTRUMENT,
        timeframe=config.TIMEFRAME
    )

    # Scan the most recent completed candle
    signals = detector.detect_signals(candles_df, scan_latest_only=True)
    logger.info(f"Detection completed. Found {len(signals)} new structure event(s) on latest candle.")

    # 5. Process and Deduplicate Signals
    state_mgr = StateManager()
    alerts_dispatched = 0

    for sig in signals:
        sig_id = sig.signal_id
        if state_mgr.is_already_alerted(sig_id):
            logger.info(f"Skipping duplicate signal: {sig_id}")
            continue

        logger.info(f"NEW CONFIRMED SIGNAL: {sig.direction.value} {sig.signal_type.value} at break level {sig.break_level:.2f}")
        sent = send_telegram_alert(
            signal=sig,
            data_provider_name=provider.name,
            session_name=session_name,
            dry_run=dry_run
        )

        if sent:
            state_mgr.record_signal(sig_id)
            alerts_dispatched += 1

    # Update state metadata
    state_mgr.state["last_run_timestamp"] = datetime.now(timezone.utc).isoformat()
    state_mgr.state["last_candle_timestamp"] = latest_ts.isoformat()
    state_mgr.save()

    logger.info(f"Cycle completed successfully. Dispatched {alerts_dispatched} alert(s).")
    return 0


def run_health_check() -> int:
    """Performs deep end-to-end health check of system components."""
    print("\n=======================================================")
    print("      XAUUSD SMC ALERT SYSTEM HEALTH CHECK")
    print("=======================================================")

    print(f"Instrument:        {config.INSTRUMENT}")
    print(f"Timeframe:         {config.TIMEFRAME}")
    print(f"Data Provider:     {config.DATA_PROVIDER}")
    print(f"Swing Lookback:    {config.SWING_LENGTH} bars")
    print(f"Displacement Mult: {config.MIN_DISPLACEMENT_ATR_MULT}x ATR({config.ATR_PERIOD})")
    print(f"Confirmation:      {'Candle Close' if config.REQUIRE_CANDLE_CLOSE else 'Wick'}")
    print(f"Session Filter:    {'Enabled' if config.FILTER_SESSIONS else 'Disabled (Monitors 24/5)'}")
    print(f"Telegram Token:    {mask_token(config.TELEGRAM_BOT_TOKEN)}")
    print(f"Telegram Chat ID:  {config.TELEGRAM_CHAT_ID[:3]}...{config.TELEGRAM_CHAT_ID[-2:] if len(config.TELEGRAM_CHAT_ID) > 5 else '***'}")
    print(f"Dry-Run Active:    {config.DRY_RUN}")
    print("-------------------------------------------------------")

    # Check configuration errors
    errs = config.validate_config(is_dry_run=True)
    if errs:
        print("[!] Configuration Warnings:")
        for e in errs:
            print(f"    - {e}")
    else:
        print("[✓] Core configuration settings are valid.")

    # Check Market Data Connectivity
    print("\n[+] Testing Market Data Provider connectivity...")
    try:
        if config.DATA_PROVIDER == "yahoo":
            prov = get_data_provider("yahoo", fallback_symbol=config.YAHOO_FALLBACK_SYMBOL)
            df = prov.fetch_candles(config.YAHOO_SYMBOL, config.TIMEFRAME, limit=30)
        else:
            prov = get_data_provider("twelvedata", api_key=config.TWELVEDATA_API_KEY)
            df = prov.fetch_candles(config.TWELVEDATA_SYMBOL, "5min", limit=30)

        print(f"[✓] Successfully retrieved {len(df)} candles from {prov.name}.")
        last_c = df.iloc[-1]
        print(f"    Latest Price: Close={last_c['close']:.2f}, High={last_c['high']:.2f}, Low={last_c['low']:.2f}")
        print(f"    Latest Timestamp (UTC): {last_c['timestamp']}")
    except Exception as e:
        print(f"[X] Market data fetch failed: {e}")

    # Check Active Session
    now_utc = datetime.now(timezone.utc)
    active, s_name = config.get_active_session_name(now_utc)
    print(f"\n[+] Current Market Session: {s_name} (Session Active: {active})")
    print("=======================================================\n")
    return 0


def run_replay(csv_file_path: str) -> int:
    """Runs structure detection replay across an entire historical CSV dataset."""
    path = Path(csv_file_path)
    if not path.exists():
        print(f"Error: Historical CSV file '{csv_file_path}' not found.")
        return 1

    print(f"Starting Historical Replay on: {csv_file_path}")
    provider = get_data_provider("csv", source=csv_file_path, name="Historical Replay")
    df = provider.fetch_candles("XAUUSD", "5m", limit=10000)
    print(f"Loaded {len(df)} candles.")

    detector = SMCDetector(
        swing_length=config.SWING_LENGTH,
        min_displacement_atr_mult=config.MIN_DISPLACEMENT_ATR_MULT,
        atr_period=config.ATR_PERIOD,
        require_candle_close=config.REQUIRE_CANDLE_CLOSE,
        symbol="XAUUSD",
        timeframe="5m"
    )

    signals = detector.detect_signals(df, scan_latest_only=False)
    print(f"\nReplay Complete! Found {len(signals)} historical SMC structure signals:")
    print("-" * 75)
    for i, s in enumerate(signals, 1):
        ts_str = s.candle_timestamp.strftime("%Y-%m-%d %H:%M")
        print(f"{i:2d}. [{ts_str}] {s.direction.value:7s} {s.signal_type.value:5s} | Break: {s.break_level:8.2f} | Close: {s.close_price:8.2f} | Disp: {s.displacement_ratio:.2f}x")
    print("-" * 75)
    return 0


def main():
    parser = argparse.ArgumentParser(description="XAUUSD Smart Money Concepts Cloud Alert System")
    parser.add_argument("--dry-run", action="store_true", help="Run without sending live Telegram messages")
    parser.add_argument("--health-check", action="store_true", help="Check component connectivity and exit")
    parser.add_argument("--test-telegram", action="store_true", help="Send test Telegram notification to verify token/chat")
    parser.add_argument("--replay", type=str, metavar="CSV_FILE", help="Run historical replay analysis on CSV file")
    parser.add_argument("--force-session", action="store_true", help="Ignore session window filter for testing")

    args = parser.parse_args()

    if args.health_check:
        sys.exit(run_health_check())

    if args.test_telegram:
        success = test_telegram_connection()
        sys.exit(0 if success else 1)

    if args.replay:
        sys.exit(run_replay(args.replay))

    sys.exit(run_pipeline(dry_run=args.dry_run, force_session=args.force_session))


if __name__ == "__main__":
    main()
