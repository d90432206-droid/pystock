import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import mplfinance as mpf
import numpy as np
import io
import base64
import os
import math
import traceback

# --- Config ---
MANDATORY = ["1513", "6117"]

# --- Helper Functions from stock2.py ---

def analyze_stock_technical(df, symbol):
    """
    通用技術分析函式
    回傳: (is_passed, details_dict)
    """
    try:
        if df.empty or len(df) < 60: return False, {}
        
        # 1. 找出 A 點 (過去 120~40 天的最低點)
        part_A = df.iloc[-120:-40]
        if part_A.empty: return False, {}
        
        val_A = part_A['Low'].min()
        idx_A = part_A['Low'].idxmin()

        # 確保 idx_A 在這之後有數據
        if idx_A not in df.index: return False, {}
        
        # 2. 找出 B 點 (A 點之後 ~ 倒數第二天)
        iloc_idx_A = df.index.get_loc(idx_A)
        if iloc_idx_A >= len(df) - 2: return False, {} 
        
        subset_B = df.iloc[iloc_idx_A+1 : -1]
        if subset_B.empty:
            val_B = val_A * 1.1 
        else:
            val_B = subset_B['Low'].min()

        dist_A = (df['Close'].iloc[-1] - val_A) / val_A
        is_m = any(m in symbol for m in MANDATORY)
        
        # 3. 判斷邏輯
        is_passed = is_m or (val_B < val_A * 1.005 and -0.02 <= dist_A <= 0.15)
        
        info_dict = {
            'symbol': symbol,
            'val_A': val_A,
            'idx_A': idx_A,
            'val_B': val_B,
            'dist': dist_A,
            'is_m': is_m,
            'df': df
        }
        return is_passed, info_dict

    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return False, {}

def generate_chart_base64(df, val_A, idx_A, symbol, dist):
    """將原本的 mpf 圖表轉為 Base64 字串供 React 顯示"""
    print("DEBUG: Generating Chart...")
    df_p = df.iloc[-90:]
    markers = [np.nan] * len(df_p)
    if idx_A in df_p.index:
        markers[df_p.index.get_loc(idx_A)] = val_A * 0.985
    markers[-1] = df_p['Low'].iloc[-1] * 0.985

    buf = io.BytesIO()
    ap = mpf.make_addplot(markers, type='scatter', marker='^', markersize=50, color='green')
    
    # Critical step that might crash
    mpf.plot(df_p, type='candle', style='charles', addplot=ap, 
             hlines=dict(hlines=[val_A], colors=['b'], linestyle='--'),
             savefig=dict(fname=buf, format='png', dpi=100))
    buf.seek(0)
    print("DEBUG: Chart Generated Successfully")
    return base64.b64encode(buf.read()).decode('utf-8')

def sanitize_json(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    return obj

# --- Main Test ---

def run_test(symbol="2330.TW"):
    print(f"🚀 Testing {symbol}...")
    
    # 1. Download
    try:
        yf.set_tz_cache_location("yf_cache")
        data = yf.download(symbol, period="10mo", interval="1d", auto_adjust=True, progress=False, threads=False)
        print(f"✅ Downloaded shape: {data.shape}")
        
        df = data
        if isinstance(data.columns, pd.MultiIndex):
            try:
                df = data.xs(symbol, level=1, axis=1)
            except:
                 if len(data.columns.levels) > 1:
                     single_ticker = data.columns.levels[1][0]
                     df = data.xs(single_ticker, level=1, axis=1)

        # 2. Analyze
        is_passed, info = analyze_stock_technical(df, symbol)
        print(f"✅ Analysis Result: Passed={is_passed}")
        
        if info:
             dist_val = info.get('dist', 0)
             # 3. Generate Chart
             b64 = generate_chart_base64(info['df'], info['val_A'], info['idx_A'], symbol, dist_val)
             print(f"✅ Chart Generated. Length: {len(b64)}")
        
        print("✅ FULL SUCCESS")
        
    except Exception as e:
        print("❌ FAILED:")
        traceback.print_exc()


# --- Futures Analysis ---

def analyze_futures(symbol, interval="1h", period="1y"):
    print(f"\n🌊 Checking Futures: {symbol} [{interval}]...")
    
    # Map valid tickers
    # TX -> TX=F, NQ -> NQ=F
    ticker_map = {"TX": "TX=F", "NQ": "NQ=F", "MNQ": "MNQ=F"}
    yf_symbol = ticker_map.get(symbol, symbol)
    if "=" not in yf_symbol and "TW" not in yf_symbol and "^" not in yf_symbol:
         # Assume it might be one of the keys
         pass

    try:
        data = yf.download(yf_symbol, period=period, interval=interval, auto_adjust=True, progress=False, threads=False)
        df = data
        if isinstance(data.columns, pd.MultiIndex):
             try: df = data.xs(yf_symbol, level=1, axis=1)
             except: 
                 if len(data.columns.levels) > 1:
                     df = data.xs(data.columns.levels[1][0], level=1, axis=1)

        df = df.dropna()
        if df.empty or len(df) < 50:
            print(f"⚠️ No data for {yf_symbol} ({interval})")
            return

        is_passed, info = analyze_stock_technical(df, yf_symbol)
        
        dist_str = f"{info.get('dist', 0):+.1%}" if info else "N/A"
        status = "✅ PASS" if is_passed else f"❌ FAIL ({dist_str})"
        print(f"Result: {status}")
        
        if info:
            # Generate chart to verify it works
            b64 = generate_chart_base64(info['df'], info['val_A'], info['idx_A'], yf_symbol, info.get('dist', 0))
            print(f"Chart generated ({len(b64)} bytes)")

    except Exception as e:
        print(f"Error checking futures {symbol}: {e}")

if __name__ == "__main__":
    # Original test
    # run_test()
    
    # New Futures Test
    print("--- Testing Futures Logic ---")
    analyze_futures("TX", "1h", "1y") # 台指期 1小時
    analyze_futures("TX", "5m", "5d") # 台指期 5分
    
    analyze_futures("NQ", "1h", "1y") # 小那斯達克 1小時
    analyze_futures("NQ", "5m", "5d") # 小那斯達克 5分

