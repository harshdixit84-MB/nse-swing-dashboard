"""
Daily scan entry point.

Run this via `python scan.py` locally, or automatically through the
GitHub Actions workflow (.github/workflows/daily-scan.yml).

Steps:
1. Log into Angel One SmartAPI (key-based, not scraping)
2. Load the NSE universe (Nifty 500 or all NSE, per UNIVERSE_MODE)
3. Load Angel's instrument master to map symbol -> numeric token
4. Pull daily OHLCV data for each stock sequentially (rate-limit safe)
5. Run the EMA Pullback strategy on each
6. Write today's candidates + append to the running history
7. Send a Telegram alert for any symbol that's newly appeared today

NOTE ON DATA SOURCE HISTORY: this project first used yfinance (Yahoo
Finance), then nsepython (direct NSE scraping) -- both got blocked at
the IP level by GitHub Actions' shared datacenter IP ranges. Switched
to Angel One SmartAPI because it's a real authenticated API (using an
existing Angel One account's credentials), not scraping, so it isn't
subject to the same IP-reputation blocking.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import pyotp
import requests
from SmartApi import SmartConnect

from config import (
    DATA_DIR,
    CANDIDATES_FILE,
    HISTORY_FILE,
    HISTORY_DAYS_BACK,
    MAX_HOLDING_DAYS,
    UNIVERSE_MODE,
    ANGEL_API_KEY,
    ANGEL_CLIENT_ID,
    ANGEL_PASSWORD,
    ANGEL_TOTP_SECRET,
    ANGEL_REQUEST_DELAY_SECONDS,
    INSTRUMENT_MASTER_URL,
)
from universe import get_universe
from strategy import evaluate
from telegram_alert import send_telegram_message, format_setup_message


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def angel_login():
    """
    Logs into SmartAPI using the TOTP secret to generate a fresh 2FA
    code automatically -- no manual OTP entry needed.
    """
    smart_api = SmartConnect(api_key=ANGEL_API_KEY)
    totp_code = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
    session = smart_api.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp_code)

    if not session or not session.get("status"):
        raise RuntimeError(f"Angel One login failed: {session}")

    return smart_api


def build_symbol_token_map(universe):
    """
    Downloads Angel's instrument master (all exchanges/segments) and
    builds {symbol: token} for the NSE equity ("-EQ") instruments we
    actually need, so we don't keep the full multi-MB list in memory.
    """
    wanted = set(universe)
    resp = requests.get(INSTRUMENT_MASTER_URL, timeout=60)
    resp.raise_for_status()
    instruments = resp.json()

    token_map = {}
    for inst in instruments:
        if inst.get("exch_seg") != "NSE":
            continue
        if not inst.get("symbol", "").endswith("-EQ"):
            continue
        name = inst.get("name", "")
        if name in wanted and name not in token_map:
            token_map[name] = inst.get("token")

    return token_map


def fetch_one(smart_api, symbol, token):
    """
    Fetches daily OHLCV history for a single symbol via SmartAPI.
    """
    try:
        to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        from_date = (datetime.now() - timedelta(days=HISTORY_DAYS_BACK)).strftime("%Y-%m-%d %H:%M")

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_DAY",
            "fromdate": from_date,
            "todate": to_date,
        }
        resp = smart_api.getCandleData(params)
        time.sleep(ANGEL_REQUEST_DELAY_SECONDS)  # respect SmartAPI's rate limit

        if not resp or not resp.get("status") or not resp.get("data"):
            return symbol, None

        # Each candle: [timestamp, open, high, low, close, volume]
        rows = resp["data"]
        df = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])

        if df.empty:
            return symbol, None

        return symbol, df[["Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        print(f"  Failed to fetch {symbol}: {e}")
        time.sleep(ANGEL_REQUEST_DELAY_SECONDS)
        return symbol, None


def main():
    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Starting scan for {scan_date} (universe mode: {UNIVERSE_MODE})")

    print("Logging into Angel One SmartAPI...")
    smart_api = angel_login()
    print("Login successful.")

    universe = get_universe()

    print("Loading Angel instrument master and mapping symbols to tokens...")
    token_map = build_symbol_token_map(universe)
    print(f"Matched {len(token_map)}/{len(universe)} symbols to Angel instrument tokens.")

    previous_candidates = load_json(CANDIDATES_FILE, {"scan_date": None, "candidates": []})
    previous_symbols = {c["symbol"] for c in previous_candidates.get("candidates", [])}

    history = load_json(HISTORY_FILE, {"entries": []})

    today_candidates = []
    new_symbols = []
    fetched_count = 0
    failed_count = 0

    for i, symbol in enumerate(universe, start=1):
        if i % 50 == 0 or i == len(universe):
            print(f"Progress: {i}/{len(universe)} checked")

        token = token_map.get(symbol)
        if not token:
            failed_count += 1
            continue

        symbol, df = fetch_one(smart_api, symbol, token)
        if df is None:
            failed_count += 1
            continue
        fetched_count += 1

        setup = evaluate(df)
        if setup is None:
            continue

        entry = {
            "symbol": symbol,
            "date_found": scan_date,
            "max_holding_days": MAX_HOLDING_DAYS,
            **setup,
        }
        today_candidates.append(entry)
        history["entries"].append(entry)

        if symbol not in previous_symbols:
            new_symbols.append(entry)

    save_json(CANDIDATES_FILE, {"scan_date": scan_date, "candidates": today_candidates})
    save_json(HISTORY_FILE, history)

    print(f"Data fetched for {fetched_count}/{len(universe)} symbols "
          f"({failed_count} failed/unmatched).")
    print(f"Scan complete. {len(today_candidates)} candidates found today, "
          f"{len(new_symbols)} are new.")

    if fetched_count == 0:
        print("WARNING: zero symbols returned data. Check Angel One "
              "login/credentials and the errors above.")

    if new_symbols:
        header = f"*NSE Swing Scan -- {scan_date}*\n{len(new_symbols)} new setup(s) found:\n"
        send_telegram_message(header)
        for entry in new_symbols:
            send_telegram_message(format_setup_message(entry["symbol"], entry))
    else:
        print("No new setups today -- no Telegram alert sent.")


if __name__ == "__main__":
    main()
