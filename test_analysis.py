import yfinance as yf
import pandas as pd
import traceback
import math
import os

# --- Mocking parts of stock2.py ---

def sanitize_json(obj):
    """Recursively replace NaN/Infinity with None for JSON compliance"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    return obj

def analyze_stock_technical(df, symbol):
    """
    Mock of the function in stock2.py
    """
    print("DEBUG: analyzing data with shape:", df.shape)
    try:
        if df.empty or len(df) < 60: return False, {}
        
        part_A = df.iloc[-120:-40]
        if part_A.empty: return False, {}
        
        val_A = part_A['Low'].min()
        idx_A = part_A['Low'].idxmin()
        
        # ... simplified logic just to check if it crashes ...
        
        info_dict = {
            'symbol': symbol,
            'val_A': val_A,
            'idx_A': idx_A,
            'dist': 0.1, # Fake return
            'df': df
        }
        return False, info_dict
    except Exception as e:
        print(f"Error in analyze: {e}")
        traceback.print_exc()
        return False, {}

def generate_chart_base64(df, val_A, idx_A, symbol, dist_A):
    return "fake_base64_string"

# --- Main Test Logic ---

def check_stock_logic(symbol: str):
    print(f"🔎 Testing symbol: {symbol}")
    
    # Cache setup same as stock2.py
    try:
        if not os.path.exists("yf_cache"):
            os.makedirs("yf_cache")
        yf.set_tz_cache_location("yf_cache")
    except Exception as e:
        print(f"Cache setup failed: {e}")

    try:
        # Match stock2.py call EXACTLY
        data = yf.download(symbol, period="10mo", interval="1d", auto_adjust=True, progress=False, threads=False)
        
        print(f"Download Data Type: {type(data)}")
        print(f"Download Data Columns: {data.columns}")
        
        df = data
        # Logic from stock2.py
        result_is_multiindex = isinstance(data.columns, pd.MultiIndex)
        if result_is_multiindex:
            try:
                df = data.xs(symbol, level=1, axis=1)
            except:
                if len(data.columns.levels) > 1:
                     single_ticker = data.columns.levels[1][0]
                     df = data.xs(single_ticker, level=1, axis=1)
        
        if df.empty:
            raise ValueError("取得數據為空")
            
        df = df.dropna()
        if len(df) < 5:
             raise ValueError("數據過少")

        is_passed, info = analyze_stock_technical(df, symbol)
        
        # 準備結果，處理 NaN
        dist_val = info.get('dist', 0)
        dist_str = f"{dist_val:+.1%}" if not pd.isna(dist_val) else "N/A"

        result = {
            "symbol": symbol,
            "is_passed": is_passed,
            "dist": dist_str,
            "message": "Test Message",
            "chart": "...",
            "status": "觀察"
        }
        
        cleaned = sanitize_json(result)
        print("✅ Success! Result:", cleaned)

    except Exception as e:
        print("❌ Failed inside logic:")
        traceback.print_exc()

if __name__ == "__main__":
    check_stock_logic("2330.TW")
