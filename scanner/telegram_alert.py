"""
Sends Telegram alerts for newly-found setups.
"""

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured (missing secrets) -- skipping alert.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"Telegram alert failed: {e}")


def format_setup_message(symbol: str, setup: dict) -> str:
    return (
        f"*New Setup: {symbol}*\n"
        f"Pattern: {setup['pattern']}\n"
        f"Entry: ₹{setup['entry_price']}\n"
        f"Stop-loss: ₹{setup['stop_loss']}\n"
        f"Target: ₹{setup['target']}\n"
        f"Reward:Risk: {setup['reward_risk_ratio']}:1\n"
        f"Pullback: {setup['pullback_pct']}% from swing high"
    )
