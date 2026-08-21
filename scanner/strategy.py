import pandas as pd
import numpy as np
import config

def check_setup(symbol, df):
    """
    Evaluates the Trend Pullback to 20/50 EMA strategy on daily price data.
    Returns setup dictionary if valid, else None.
    """
    if df is None or len(df) < 50:
        return None

    # Calculate indicators
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Vol20SMA'] = df['Volume'].rolling(window=20).mean()
    df['High20'] = df['High'].rolling(window=20).max()

    # Get latest bar and prior bar data
    curr = df.iloc[-1]
    prev = df.iloc[-2]

    close = curr['Close']
    open_price = curr['Open']
    high = curr['High']
    low = curr['Low']
    volume = curr['Volume']

    ema20 = curr['EMA20']
    ema50 = curr['EMA50']
    vol_sma20 = curr['Vol20SMA']
    swing_high20 = curr['High20']

    # 1. Uptrend filter: Close > EMA20 > EMA50, and Close > EMA50
    if not (close > ema20 > ema50 and close > ema50):
        return None

    # 2. Pullback filter: Price pulled back 5-15% from 20-day high
    if pd.isna(swing_high20) or swing_high20 == 0:
        return None
    pullback_pct = ((swing_high20 - close) / swing_high20) * 100
    if not (5.0 <= pullback_pct <= 15.0):
        return None

    # 3. Near EMA filter: Price within 2% of EMA20 or EMA50
    near_ema20 = abs(close - ema20) / ema20 <= 0.02
    near_ema50 = abs(close - ema50) / ema50 <= 0.02
    if not (near_ema20 or near_ema50):
        return None

    # 4. Liquidity filter: 20-day average volume >= 500,000
    if pd.isna(vol_sma20) or vol_sma20 < 500000:
        return None

    # 5. Bullish reversal candle check (Hammer or Bullish Engulfing)
    body = abs(close - open_price)
    candle_range = high - low
    if candle_range == 0:
        return None

    lower_wick = min(open_price, close) - low
    upper_wick = high - max(open_price, close)

    is_hammer = (lower_wick >= 2 * body) and (upper_wick <= 0.2 * body)
    
    prev_close = prev['Close']
    prev_open = prev['Open']
    is_bullish_engulfing = (prev_close < prev_open) and (close > open_price) and (close >= prev_open) and (open_price <= prev_close)

    if not (is_hammer or is_bullish_engulfing):
        return None

    # 6. Volume confirmation: Reversal volume >= 20-day average
    if volume < vol_sma20:
        return None

    # Risk management calculations
    pullback_5d_low = df['Low'].tail(5).min()
    sl_base = max(pullback_5d_low, ema50)
    stop_loss = round(sl_base * 0.995, 2)  # 0.5% buffer

    risk = close - stop_loss
    if risk <= 0:
        return None

    target_2r = close + (2 * risk)
    target = round(max(target_2r, swing_high20), 2)

    return {
        "symbol": symbol,
        "close": round(close, 2),
        "stop_loss": stop_loss,
        "target": target,
        "pattern": "Hammer" if is_hammer else "Bullish Engulfing",
        "pullback_pct": round(pullback_pct, 2)
    }
