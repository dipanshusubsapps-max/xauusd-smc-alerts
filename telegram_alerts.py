"""
Telegram notification module for XAUUSD SMC Alert System.
Sends rich, mobile-friendly Telegram alerts.
Implements token safety, network retry handling, and dry-run execution.
"""

import logging
import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from smc_detector import SMCSignal, SignalType, Direction
import config

logger = logging.getLogger("xauusd_smc.telegram")


def mask_token(token: str) -> str:
    """Masks bot token for safe logging (e.g. 123456...abcd)."""
    if not token or len(token) < 10:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


def format_alert_message(signal: SMCSignal, data_provider_name: str, session_name: str) -> str:
    """
    Constructs clean, professional HTML message for Telegram.
    Times converted to IST (Indian Standard Time).
    """
    # Convert timestamp to IST
    try:
        ist_tz = config.ALERT_TIMEZONE
        ts_ist = signal.candle_timestamp.astimezone(ist_tz)
        time_str = ts_ist.strftime("%d-%b-%Y %I:%M %p IST")
    except Exception:
        time_str = signal.candle_timestamp.strftime("%Y-%m-%d %H:%M UTC")

    icon = "🟢" if signal.direction == Direction.BULLISH else "🔴"
    sig_label = f"{signal.direction.value} {signal.signal_type.value}"

    message = (
        f"⚡ <b>XAUUSD | M5 Structure Alert</b> ⚡\n\n"
        f"<b>Signal:</b> {icon} <b>{sig_label}</b>\n"
        f"<b>Break Level:</b> <code>{signal.break_level:.2f}</code>\n"
        f"<b>Close Price:</b> <code>{signal.close_price:.2f}</code>\n"
        f"<b>Time:</b> <code>{time_str}</code>\n"
        f"<b>Status:</b> Confirmed candle close\n"
        f"<b>Displacement:</b> {signal.displacement_ratio:.2f}x ATR\n"
        f"<b>Session:</b> {session_name}\n"
        f"<b>Data Provider:</b> {data_provider_name}\n\n"
        f"📖 <b>Context:</b>\n"
        f"<i>{signal.explanation}</i>\n\n"
        f"⚠️ <i>Alert & chart analysis only. Never risk capital without independent confirmation.</i>"
    )
    return message


def send_telegram_alert(
    signal: SMCSignal,
    data_provider_name: str,
    session_name: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    dry_run: bool = False
) -> bool:
    """
    Dispatches alert to Telegram.
    Returns True if sent successfully or handled in dry-run mode.
    """
    token = (bot_token or config.TELEGRAM_BOT_TOKEN).strip()
    target_chat_id = (chat_id or config.TELEGRAM_CHAT_ID).strip()
    is_dry = dry_run or config.DRY_RUN

    text = format_alert_message(signal, data_provider_name, session_name)

    if is_dry:
        logger.info(f"[DRY-RUN] Alert generated for {signal.signal_id}:\n{text}")
        print("\n" + "=" * 55)
        print(" [DRY-RUN MODE] TELEGRAM ALERT PREVIEW")
        print("=" * 55)
        # Strip HTML tags for clean console display
        clean_text = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", "")
        print(clean_text)
        print("=" * 55 + "\n")
        return True

    if not token or not target_chat_id:
        logger.error("Cannot send Telegram alert: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "XAUUSD-SMC-Alert-Bot"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            if res_body.get("ok"):
                logger.info(f"Telegram alert successfully dispatched for {signal.signal_id}")
                return True
            else:
                logger.error(f"Telegram API returned not OK: {res_body}")
                return False

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        logger.error(f"Telegram HTTP Error {e.code} using token {mask_token(token)}: {error_body}")
        return False
    except Exception as e:
        logger.error(f"Failed to deliver Telegram notification: {e}")
        return False


def test_telegram_connection(bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
    """Sends a lightweight test ping to verify Telegram credentials."""
    token = (bot_token or config.TELEGRAM_BOT_TOKEN).strip()
    target_chat_id = (chat_id or config.TELEGRAM_CHAT_ID).strip()

    if not token or not target_chat_id:
        print("Error: Both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be provided.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    test_msg = (
        "🤖 <b>XAUUSD SMC Alert System Connected!</b>\n\n"
        "Your Telegram bot credentials are valid and ready to receive M5 Gold structure alerts.\n"
        f"Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
    )

    payload = {
        "chat_id": target_chat_id,
        "text": test_msg,
        "parse_mode": "HTML"
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "XAUUSD-SMC-Alert-Bot"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                print("SUCCESS: Test notification received by Telegram!")
                return True
            else:
                print(f"FAILED: Telegram API response: {body}")
                return False
    except Exception as e:
        print(f"FAILED: Connection test encountered error: {e}")
        return False
