"""
Daily scan entry point.

Run this via `python scan.py` locally, or automatically through the
GitHub Actions workflow (.github/workflows/daily-scan.yml).

Steps:
1. Load the NSE universe
2. Pull daily OHLCV data for each stock
3. Run the EMA Pullback strategy on each
4. Write today's candidates + append to the running history
5. Send a Telegram alert for any symbol that's newly appeared today
"""

import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from config import (
    DATA_DIR,
    CANDIDATES_FILE,
    HISTORY_FILE,
    LOOKBACK_PERIOD,
    DATA_INTERVAL,
    MAX_HOLDING_DAYS,
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


def fetch_history(symbol: str):
    ticker = f"{symbol}.NS"
    try:
        df = yf.Ticker(ticker).history(period=LOOKBACK_PERIOD, interval=DATA_INTERVAL)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print(f"  Failed to fetch {ticker}: {e}")
        return None


def main():
    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Starting scan for {scan_date}")

    universe = get_universe()
    previous_candidates = load_json(CANDIDATES_FILE, {"scan_date": None, "candidates": []})
    previous_symbols = {c["symbol"] for c in previous_candidates.get("candidates", [])}

    history = load_json(HISTORY_FILE, {"entries": []})

    today_candidates = []
    new_symbols = []

    for i, symbol in enumerate(universe):
        print(f"[{i + 1}/{len(universe)}] Checking {symbol}...")
        df = fetch_history(symbol)
        if df is None:
            continue

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

        # Small delay to be polite to Yahoo Finance rate limits
        time.sleep(0.3)

    save_json(CANDIDATES_FILE, {"scan_date": scan_date, "candidates": today_candidates})
    save_json(HISTORY_FILE, history)

    print(f"Scan complete. {len(today_candidates)} candidates found today, "
          f"{len(new_symbols)} are new.")

    if new_symbols:
        header = f"*NSE Swing Scan -- {scan_date}*\n{len(new_symbols)} new setup(s) found:\n"
        send_telegram_message(header)
        for entry in new_symbols:
            send_telegram_message(format_setup_message(entry["symbol"], entry))
    else:
        print("No new setups today -- no Telegram alert sent.")


if __name__ == "__main__":
    main()
