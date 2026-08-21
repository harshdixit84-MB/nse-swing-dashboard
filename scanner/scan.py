"""
Daily scan entry point.

Run this via `python scan.py` locally, or automatically through the
GitHub Actions workflow (.github/workflows/daily-scan.yml).

Steps:
1. Load the NSE universe (Nifty 500 or all NSE, per UNIVERSE_MODE)
2. Pull daily OHLCV data for each stock directly from NSE (nsepython)
3. Run the EMA Pullback strategy on each
4. Write today's candidates + append to the running history
5. Send a Telegram alert for any symbol that's newly appeared today

NOTE ON DATA SOURCE: this used to run on yfinance (Yahoo Finance), but
Yahoo began persistently blocking requests from GitHub Actions' shared
IP ranges (empty/error responses on every ticker). Switched to
nsepython, which pulls historical data straight from NSE's own site
using the same cookie-handshake technique already used in universe.py.
NSE tends to rate-limit concurrent scraping harder than sequential
requests, so concurrency here is intentionally kept low (see
MAX_WORKERS / REQUEST_DELAY_SECONDS in config.py) -- expect this scan
to take noticeably longer than the old yfinance version did.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import pandas as pd
from nsepython import equity_history

from config import (
    DATA_DIR,
    CANDIDATES_FILE,
    HISTORY_FILE,
    HISTORY_DAYS_BACK,
    MAX_HOLDING_DAYS,
    MAX_WORKERS,
    REQUEST_DELAY_SECONDS,
    UNIVERSE_MODE,
)
from universe import get_universe
from strategy import evaluate
from telegram_alert import send_telegram_message, format_setup_message

NSE_COLUMN_MAP = {
    "CH_TIMESTAMP": "Date",
    "CH_OPENING_PRICE": "Open",
    "CH_TRADE_HIGH_PRICE": "High",
    "CH_TRADE_LOW_PRICE": "Low",
    "CH_CLOSING_PRICE": "Close",
    "CH_TOT_TRADED_QTY": "Volume",
}
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def fetch_one(symbol):
    """
    Fetches daily OHLCV history for a single symbol directly from NSE.
    """
    try:
        to_date = datetime.now().strftime("%d-%m-%Y")
        from_date = (datetime.now() - timedelta(days=HISTORY_DAYS_BACK)).strftime("%d-%m-%Y")

        raw = equity_history(symbol, "EQ", from_date, to_date)
        time.sleep(REQUEST_DELAY_SECONDS)  # be gentle on NSE's rate limiter

        if raw is None or raw.empty:
            return symbol, None

        raw = raw.rename(columns=NSE_COLUMN_MAP)
        if not all(c in raw.columns for c in REQUIRED_COLUMNS):
            return symbol, None

        raw["Date"] = pd.to_datetime(raw["Date"])
        raw = raw.sort_values("Date").reset_index(drop=True)

        for col in REQUIRED_COLUMNS:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
        raw = raw.dropna(subset=REQUIRED_COLUMNS)

        if raw.empty:
            return symbol, None

        return symbol, raw[REQUIRED_COLUMNS]

    except Exception as e:
        print(f"  Failed to fetch {symbol}: {e}")
        return symbol, None


def main():
    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Starting scan for {scan_date} (universe mode: {UNIVERSE_MODE})")

    universe = get_universe()
    previous_candidates = load_json(CANDIDATES_FILE, {"scan_date": None, "candidates": []})
    previous_symbols = {c["symbol"] for c in previous_candidates.get("candidates", [])}

    history = load_json(HISTORY_FILE, {"entries": []})

    today_candidates = []
    new_symbols = []
    fetched_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_one, s): s for s in universe}
        for i, future in enumerate(as_completed(futures), start=1):
            symbol, df = future.result()
            if i % 50 == 0 or i == len(universe):
                print(f"Progress: {i}/{len(universe)} checked")

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
          f"({failed_count} failed).")
    print(f"Scan complete. {len(today_candidates)} candidates found today, "
          f"{len(new_symbols)} are new.")

    if fetched_count == 0:
        print("WARNING: zero symbols returned data. NSE may be blocking "
              "this run too -- check the errors above.")

    if new_symbols:
        header = f"*NSE Swing Scan -- {scan_date}*\n{len(new_symbols)} new setup(s) found:\n"
        send_telegram_message(header)
        for entry in new_symbols:
            send_telegram_message(format_setup_message(entry["symbol"], entry))
    else:
        print("No new setups today -- no Telegram alert sent.")


if __name__ == "__main__":
    main()
