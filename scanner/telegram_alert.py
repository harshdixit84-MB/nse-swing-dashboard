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
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"Telegram alert failed: {e}")


def rr_dot(reward_risk_ratio):
    "Quick visual read of setup quality, based on reward:risk -- the main quality metric this strategy already produces for every setup."
    if reward_risk_ratio is None:
        return "⚪"
    if reward_risk_ratio >= 2.5:
        return "🟢"
    if reward_risk_ratio >= 1.5:
        return "🟡"
    return "🔴"


def format_setup_block(symbol: str, setup: dict) -> str:
    "One readable card per stock -- the decision numbers (entry/target/stop, R:R) grouped together, trend context (EMAs, volume) kept separate underneath."
    tv_url = f"https://www.tradingview.com/chart/?symbol=NSE:{symbol}"
    symbol_link = f'<a href="{tv_url}"><b>{symbol}</b></a>'
    rr = setup.get("reward_risk_ratio")

    lines = [f"{rr_dot(rr)} {symbol_link}  <i>{setup['pattern']}</i>"]
    lines.append(f"💰 ₹{setup['entry_price']}  ·  🎯 ₹{setup['target']}  ·  🛑 ₹{setup['stop_loss']}")
    lines.append(f"⚖️ R:R {rr}:1  ·  📉 Pullback {setup['pullback_pct']}% from swing high (₹{setup['swing_high']})")
    lines.append(f"📊 EMA20 ₹{setup['ema20']}  ·  EMA50 ₹{setup['ema50']}  ·  Vol(20d) {setup['avg_volume_20d']:,}")

    return "\n".join(lines)


def format_scan_message(scan_date: str, entries: list) -> str:
    "One grouped message for the whole scan, instead of a separate ping per stock -- same pattern as the Monthly Breakout dashboard's alerts."
    header = (
        f"🚀 <b>NSE Swing Scan</b>  •  {scan_date}  •  {len(entries)} new setup{'s' if len(entries) != 1 else ''}\n"
        + "─" * 24
    )
    blocks = [format_setup_block(entry["symbol"], entry) for entry in entries]
    return header + "\n\n" + "\n\n".join(blocks)
