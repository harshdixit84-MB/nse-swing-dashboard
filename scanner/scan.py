"""
Daily scan entry point.

Run this via `python scan.py` locally, or automatically through the
GitHub Actions workflow (.github/workflows/daily-scan.yml).

Steps:
1. Load the NSE universe (Nifty 500 or all NSE, per UNIVERSE_MODE)
2. Pull daily OHLCV data for each stock (concurrently, small pool)
3. Run the EMA Pullback strategy on each
4. Write today's candidates + append to the running history
5. Send a Telegram alert for any symbol that's newly appeared today
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import yfinance as yf

from config import (
    DATA_DIR,
    CANDIDATES_FILE,
    HISTORY_FILE,
    LOOKBACK_PERIOD,
    DATA_INTERVAL,
    MAX_HOLDING_DAYS,
    MAX_WORKERS,
    UNIVERSE_MODE,
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


def fetch_one(symbol):
    """
    Fetches daily OHLCV history for a single symbol.

    No custom session is passed here deliberately: yfinance 0.2.40+
    auto-detects curl_cffi (listed in requirements.txt) and uses its
    Chrome-impersonating requests internally to get past Yahoo
    Finance's bot-blocking. Manually constructing and passing our own
    curl_cffi session conflicts with yfinance's internal session
    handling and causes silent failures -- that's what caused the
    earlier 'str' object has no attribute 'name' errors.
    """
    ticker = f"{symbol}.NS"
    try:
        df = yf.Ticker(ticker).history(period=LOOKBACK_PERIOD, interval=DATA_INTERVAL)
        if df is None or df.empty:
            return symbol, None
        return symbol, df
    except Exception as e:
        print(f"  Failed to fetch {ticker}: {e}")
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
        print("WARNING: zero symbols returned data. Yahoo Finance is likely "
              "still blocking this run -- check the errors above.")

    if new_symbols:
        header = f"*NSE Swing Scan -- {scan_date}*\n{len(new_symbols)} new setup(s) found:\n"
        send_telegram_message(header)
        for entry in new_symbols:
            send_telegram_message(format_setup_message(entry["symbol"], entry))
    else:
        print("No new setups today -- no Telegram alert sent.")


if __name__ == "__main__":
    main()
