"""
Builds the list of NSE stock symbols to scan.

Two modes (set via UNIVERSE_MODE in config.py, or the UNIVERSE_MODE
GitHub Actions env var):

  NIFTY500  -- the ~500 largest/most liquid NSE names (default, faster,
              cleaner signals)
  ALL_NSE   -- every listed NSE equity (~2000 symbols, slower, will
              surface more small/micro-cap setups -- use MIN_AVG_VOLUME
              in config.py to filter out the illiquid ones)

Either way, if the live NSE fetch fails for any reason (NSE blocks the
request, network issue, site change), falls back to the local
universe_fallback.csv so the scan never breaks entirely.
"""

import csv
import io
import requests

from config import NIFTY500_URL, ALL_NSE_EQUITY_URL, UNIVERSE_FALLBACK_FILE, UNIVERSE_MODE


def _load_fallback():
    symbols = []
    with open(UNIVERSE_FALLBACK_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbols.append(row["Symbol"].strip())
    return symbols


def _nse_session():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    session = requests.Session()
    session.headers.update(headers)
    # NSE requires a warm-up request to the homepage first, or it
    # rejects the CSV request with a 401/403.
    session.get("https://www.nseindia.com", timeout=10)
    return session


def _fetch_nifty500():
    session = _nse_session()
    resp = session.get(NIFTY500_URL, timeout=15)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    symbols = [row["Symbol"].strip() for row in reader if row.get("Symbol")]
    if len(symbols) < 100:
        raise ValueError(f"Nifty 500 list looked incomplete ({len(symbols)} symbols)")
    return symbols


def _fetch_all_nse():
    session = _nse_session()
    resp = session.get(ALL_NSE_EQUITY_URL, timeout=20)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    symbols = []
    for row in reader:
        # EQUITY_L.csv lists multiple series (EQ, BE, etc.) -- EQ is the
        # normal, freely-tradable equity series most swing traders want.
        series = (row.get(" SERIES") or row.get("SERIES") or "").strip()
        symbol = (row.get("SYMBOL") or "").strip()
        if symbol and series == "EQ":
            symbols.append(symbol)
    if len(symbols) < 500:
        raise ValueError(f"All-NSE list looked incomplete ({len(symbols)} symbols)")
    return symbols


def get_universe():
    """
    Returns a list of NSE symbols WITHOUT the .NS suffix
    (the suffix is added later when calling yfinance).
    """
    try:
        if UNIVERSE_MODE == "ALL_NSE":
            symbols = _fetch_all_nse()
            print(f"Loaded {len(symbols)} symbols from live ALL_NSE equity list.")
        else:
            symbols = _fetch_nifty500()
            print(f"Loaded {len(symbols)} symbols from live NIFTY500 list.")
        return symbols

    except Exception as e:
        print(f"Could not fetch live NSE universe ({e}). Using local fallback list.")
        symbols = _load_fallback()
        print(f"Loaded {len(symbols)} symbols from fallback list.")
        return symbols
