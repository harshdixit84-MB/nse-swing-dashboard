import json
import os
import sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from nsepython import index_history
import config
from universe import get_universe
from strategy import check_setup
from telegram_alert import send_telegram_alert

def fetch_stock_data(symbol):
    """
    Fetches historical OHLCV daily data for a given NSE ticker using nsepython.
    """
    clean_symbol = symbol.replace(".NS", "").strip()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    start_str = start_date.strftime("%d-%m-%Y")
    end_str = end_date.strftime("%d-%m-%Y")
    
    try:
        df = index_history(clean_symbol, start_str, end_str)
        if df is None or df.empty:
            return symbol, None
            
        # Standardize column names to match expected DataFrame schema
        df = df.rename(columns={
            'EOD_TIMESTAMP': 'Date',
            'EOD_OPEN_INDEX_VAL': 'Open',
            'EOD_HIGH_INDEX_VAL': 'High',
            'EOD_LOW_INDEX_VAL': 'Low',
            'EOD_CLOSE_INDEX_VAL': 'Close',
            'EOD_VOLUME': 'Volume'
        })
        
        # Ensure correct data types
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        df = df.dropna(subset=['Close'])
        if len(df) < 50:
            return symbol, None
            
        return symbol, df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return symbol, None

def run_scanner():
    print("Starting NSE Swing Scanner...")
    universe = get_universe(mode=config.UNIVERSE_MODE)
    print(f"Loaded universe with {len(universe)} symbols.")
    
    candidates = []
    
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        future_to_symbol = {executor.submit(fetch_stock_data, sym): sym for sym in universe}
        
        for future in as_completed(future_to_symbol):
            symbol, df = future.result()
            if df is not None and not df.empty:
                setup = check_setup(symbol, df)
                if setup:
                    candidates.append(setup)
                    print(f"[SETUP FOUND] {symbol}")

    print(f"Scan complete. Found {len(candidates)} candidates.")
    
    # Save candidates.json
    os.makedirs("data", exist_ok=True)
    candidates_file = os.path.join("data", "candidates.json")
    with open(candidates_file, "w") as f:
        json.dump(candidates, f, indent=2)
        
    # Append/Update history.json
    history_file = os.path.join("data", "history.json")
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception:
            history = []
            
    today_str = datetime.now().strftime("%Y-%m-%d")
    for cand in candidates:
        cand_copy = dict(cand)
        cand_copy["scan_date"] = today_str
        history.append(cand_copy)
        
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)

    # Send alerts if new setups found
    if candidates:
        msg = f"<b>NSE Swing Scanner Alerts ({today_str})</b>\n\n"
        for c in candidates:
            msg += f"• <b>{c['symbol']}</b> - SL: {c['stop_loss']} | Target: {c['target']}\n"
        send_telegram_alert(msg)

if __name__ == "__main__":
    run_scanner()
