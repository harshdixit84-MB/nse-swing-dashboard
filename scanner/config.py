"""
All strategy thresholds and settings live here.
Tune these without touching the scanning logic.
"""

import os

# ---- Trend / EMA settings ----
EMA_FAST = 20
EMA_SLOW = 50

# ---- Pullback settings ----
SWING_LOOKBACK_DAYS = 20       # bars used to find the recent swing high
PULLBACK_MIN_PCT = 5.0         # minimum pullback from swing high
PULLBACK_MAX_PCT = 15.0        # maximum pullback from swing high
EMA_TOLERANCE_PCT = 2.0        # how close price must be to EMA20/EMA50

# ---- Volume / liquidity settings ----
VOLUME_CONFIRM_MULT = 1.0      # reversal-day volume vs 20-day avg volume
MIN_AVG_VOLUME = 500_000       # 20-day average volume floor (liquidity filter)

# ---- Risk management ----
RISK_REWARD_MULT = 2.0         # fallback target = entry + risk * this
STOP_BUFFER_PCT = 0.5          # extra cushion below the calculated stop
MAX_HOLDING_DAYS = 15          # informational -- shown on the dashboard

# ---- Data settings ----
LOOKBACK_PERIOD = "6mo"        # how much daily history to pull per stock
DATA_INTERVAL = "1d"           # daily candles -- change to "1wk" for weekly swings

# ---- File paths ----
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CANDIDATES_FILE = os.path.join(DATA_DIR, "candidates.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
UNIVERSE_FALLBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe_fallback.csv")

# ---- NSE universe source ----
# UNIVERSE_MODE: "NIFTY500" scans ~500 large/mid-cap names (faster, more liquid).
# "ALL_NSE" scans every listed NSE equity (~2000 symbols, slower, includes
# small/micro caps -- expect more false signals from thinly-traded names).
UNIVERSE_MODE = os.environ.get("UNIVERSE_MODE", "NIFTY500")

NIFTY500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
ALL_NSE_EQUITY_URL = "https://archives.nseindia.com/content/equity/EQUITY_L.csv"

# How many tickers to request from Yahoo Finance per batch download.
# Larger batches = fewer requests but bigger payloads; 50-100 is a safe range.
BATCH_SIZE = 75

# ---- Telegram ----
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
