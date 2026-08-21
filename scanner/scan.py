"""
Daily scan entry point.

Run this via `python scan.py` locally, or automatically through the
GitHub Actions workflow (.github/workflows/daily-scan.yml).

Steps:
1. Load the NSE universe (Nifty 500 or all NSE, per UNIVERSE_MODE)
2. Pull daily OHLCV data for each stock, in batches
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
from curl_cffi import requests as cffi_requests

from config import (
    DATA_DIR,
    CANDIDATES_FILE,
    HISTORY_FILE,
    LOOKBACK_PERIOD,
    DATA_INTERVAL,
    MAX_HOLDING_DAYS,
    BATCH_SIZE,
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


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_batch(symbols, session):
    """
    Downloads daily OHLCV for a batch of symbols in one request.
    Returns {symbol: DataFrame} for symbols that returned usable data.

    Uses a curl_cffi session that impersonates a real Chrome browser's
    TLS fingerprint -- Yahoo Finance increasingly blocks plain
    requests-library traffic (which is what GitHub Actions runners look
    like by default), returning empty responses instead of data.

    threads=False is deliberate: yfinance's internal sqlite cache can
    throw "database is locked" errors under heavy parallel access,
    which gets worse when Yahoo is already stressing the connection.
    """
    tickers = [f"{s}.NS" for s in symbols]
    try:
        raw = yf.download(
            tickers=tickers,
            period=LOOKBACK_PERIOD,
            interval=DATA_INTERVAL,
            group_by="ticker",
            threads=False,
            progress=False,
            auto_adjust=False,
            session=session,
        )
    except Exception as e:
        print(f"  Batch download failed: {e}")
        return {}

    result = {}
    for symbol in symbols:
        ticker = f"{symbol}.NS"
        try:
            if len(tickers) == 1:
                df = raw
            else:
                df = raw[ticker]
            df = df.dropna(how="all")
            if not df.empty and "Close" in df.columns:
                result[symbol] = df
        except (KeyError, Exception):
            continue
    return result


def main():
    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Starting scan for {scan_date} (universe mode: {UNIVERSE_MODE})")

    universe = get_universe()
    previous_candidates = load_json(CANDIDATES_FILE, {"scan_date": None, "candidates": []})
    previous_symbols = {c["symbol"] for c in previous_candidates.get("candidates", [])}

    history = load_json(HISTORY_FILE, {"entries": []})

    # Browser-impersonating session -- see fetch_batch() docstring.
    session = cffi_requests.Session(impersonate="chrome")

    today_candidates = []
    new_symbols = []
    batches = list(chunked(universe, BATCH_SIZE))

    for batch_num, batch in enumerate(batches, start=1):
        print(f"Batch {batch_num}/{len(batches)} -- {len(batch)} symbols")
        batch_data = fetch_batch(batch, session)
        if not batch_data and batch_num == 1:
            print("  WARNING: entire first batch returned no data. "
                  "Yahoo Finance may be blocking this run -- check the "
                  "error text above for 'Expecting value' or 'database "
                  "is locked' errors.")
        # Small pause between batches so we don't look like a flood of
        # requests to Yahoo's rate limiter.
        time.sleep(2)

        for symbol, df in batch_data.items():
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
