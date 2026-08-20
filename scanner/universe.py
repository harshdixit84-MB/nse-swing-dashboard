"""
Builds the list of NSE stock symbols to scan.

Tries to pull the live Nifty 500 constituent list from NSE. If that
fetch fails for any reason (NSE blocks the request, network issue, site
change), falls back to the local universe_fallback.csv so the scan
never breaks entirely.
"""

import csv
import io
import requests

from config import NIFTY500_URL, UNIVERSE_FALLBACK_FILE


def _load_fallback():
    symbols = []
    with open(UNIVERSE_FALLBACK_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbols.append(row["Symbol"].strip())
    return symbols


def get_universe():
    """
    Returns a list of NSE symbols WITHOUT the .NS suffix
    (the suffix is added later when calling yfinance).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    try:
        # NSE requires a warm-up request to the homepage first, or it
        # rejects the CSV request with a 401/403.
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10)

        resp = session.get(NIFTY500_URL, timeout=15)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        symbols = [row["Symbol"].strip() for row in reader if row.get("Symbol")]

        if len(symbols) < 100:
            # Unexpectedly short list -- treat as a failed fetch
            raise ValueError(f"NSE list looked incomplete ({len(symbols)} symbols)")

        print(f"Loaded {len(symbols)} symbols from live NSE Nifty 500 list.")
        return symbols

    except Exception as e:
        print(f"Could not fetch live NSE universe ({e}). Using local fallback list.")
        symbols = _load_fallback()
        print(f"Loaded {len(symbols)} symbols from fallback list.")
        return symbols
