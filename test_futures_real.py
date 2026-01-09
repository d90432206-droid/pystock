import yfinance as yf
import pandas as pd
import mplfinance as mpf
import numpy as np
import io
import base64
import math

# --- Reuse Logic ---
def analyze_stock_technical_custom(df, symbol):
    # Same logic as stock2.py but adapted if needed
    try:
        # Check if enough data
        if df.empty or len(df) < 60:
            return False, {}
            
        # 1. Logic A: Find Low in window [-120:-40]
        # For 5m/1h, we might want to check relative to 'bars'
        window_start = -120
        window_end = -40
        
        # Guard against short dataframes
        if len(df) < abs(window_start):
             # If not enough data for full window, try a smaller recent window or fail
             # For 5d 5m data, we have ~300-400 bars usually. So 120 is fine.
             pass
        
        part_A = df.iloc[window_start:window_end]
        if part_A.empty: return False, {}
        
        val_A = part_A['Low'].min()
        idx_A = part_A['Low'].idxmin()
        
        if idx_A not in df.index: return False, {}
        
        iloc_idx_A = df.index.get_loc(idx_A)
        if iloc_idx_A >= len(df) - 2: return False, {}
        
        subset_B = df.iloc[iloc_idx_A+1 : -1]
        val_B = subset_B['Low'].min() if not subset_B.empty else val_A * 1.1

        dist_A = (df['Close'].iloc[-1] - val_A) / val_A
        
        # 2. Logic Condition
        # "Bottom Support": val_B (second low) shoud NOT be much lower than val_A (0.5% tolerance)
        # And price must be close to A (-2% to +15%)
        
        is_passed = (val_B < val_A * 1.005 and -0.02 <= dist_A <= 0.15)
        
        info_dict = {'symbol': symbol, 'val_A': val_A, 'idx_A': idx_A, 'val_B': val_B, 'dist': dist_A, 'df': df}
        return is_passed, info_dict
    except Exception as e:
        print(f"Analysis error: {e}")
        return False, {}

def fetch_and_analyze(symbol, interval, period):
    print(f"\n--- Checking {symbol} ({interval}) ---")
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        # Handle MultiIndex if necessary
        if isinstance(df.columns, pd.MultiIndex):
             # Try to get the specific symbol level
             try: df = df.xs(symbol, level=1, axis=1)
             except: pass
        
        df = df.dropna()
        print(f"Data shape: {df.shape}")
        if df.empty:
            print("Empty dataframe.")
            return

        is_passed, info = analyze_stock_technical_custom(df, symbol)
        
        dist_str = f"{info.get('dist', 0):+.2%}" if info else "N/A"
        print(f"Passed: {is_passed}")
        print(f"Distance to A: {dist_str}")
        if info:
            print(f"Point A: {info['val_A']} at {info['idx_A']}")
            print(f"Last Close: {df['Close'].iloc[-1]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Check TX (Taiwan)
    # Note: TX=F might need .TW or just TX=F. Yahoo uses TX=F for Index Futures.
    fetch_and_analyze("TX=F", "1h", "1y") 
    fetch_and_analyze("TX=F", "5m", "5d")
    
    # Check NQ (Nasdaq)
    fetch_and_analyze("NQ=F", "1h", "1y")
    fetch_and_analyze("NQ=F", "5m", "5d")
