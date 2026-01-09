import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import mplfinance as mpf
import numpy as np
import io
import base64
import re
import os
import time
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import traceback
import math
import logging
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import logging

# --- Silence yfinance logging ---
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- Dynamic Taiwan Stock Mapping ---
TAIWAN_STOCK_MAP = {}

def load_tickers():
    """
    Load ticker to name mapping from tickers.txt.
    Supports formats:
    2330 台積電
    2330 (only ticker)
    """
    global TAIWAN_STOCK_MAP
    new_map = {}
    tickers_path = os.path.join(os.path.dirname(__file__), 'tickers.txt')
    if os.path.exists(tickers_path):
        try:
            with open(tickers_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ticker = parts[0]
                        name = parts[1]
                        new_map[name] = ticker
                    elif len(parts) == 1:
                        # Skip if it's just a placeholder or empty
                        pass
        except Exception as e:
            print(f"Error loading tickers.txt: {e}")
    
    # Merge or replace. Here we replace to keep it clean.
    TAIWAN_STOCK_MAP.update(new_map)

# Initial load
load_tickers()

def resolve_symbol(name: str) -> str:
    # Refresh map in case user updated file
    load_tickers()
    
    # Handle mixed input like "台積電" or "2330"
    name = name.strip()
    
    # Special cases for Index/Futures
    special_map = {
        "台指期": "TX",
        "台指": "TX",
        "台指期貨": "TX",
        "加權指數": "^TWII",
        "大盤": "^TWII",
        "那斯達克": "NQ",
        "小那斯達克": "NQ",
        "黃金": "GC=F"
    }
    if name in special_map:
        return special_map[name]
        
    if name in TAIWAN_STOCK_MAP:
        return TAIWAN_STOCK_MAP[name]
    
    # Check partial match if it's more than 1 char
    if len(name) >= 2:
        for k, v in TAIWAN_STOCK_MAP.items():
            if name in k: return v
            
    return name

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sanitize_json(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj): return None
        return obj
    elif isinstance(obj, np.generic): return obj.item()
    elif isinstance(obj, dict): return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [sanitize_json(v) for v in obj]
    return obj

try:
    if not os.path.exists("yf_cache"): os.makedirs("yf_cache")
    yf.set_tz_cache_location("yf_cache")
except Exception: pass

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AI & Charting logic ---

@app.get("/api/quote")
def get_quotes(symbols: str = "^TWII,NQ=F,2330.TW"):
    """
    Get latest price data for a list of symbols (comma separated).
    Fetches each ticker individually for maximum stability.
    """
    raw_symbols = [s.strip() for s in symbols.split(",") if s.strip()]
    results = {}
    
    if not raw_symbols:
        return {}

    for raw_sym in raw_symbols:
        sym = resolve_symbol(raw_sym).upper()
        if sym.isdigit():
            sym += ".TW"
            
        try:
            # Try 1m data first (for real-time-ish price)
            df = yf.download(sym, period="3d", interval="1m", auto_adjust=True, progress=False, threads=False)
            
            # If 1m failed or empty, try 1d data
            if df.empty:
                df = yf.download(sym, period="5d", interval="1d", auto_adjust=True, progress=False, threads=False)
            
            if df.empty:
                results[raw_sym] = {"error": "No Data"}
                continue

            # Flatten columns if MultiIndex (sometimes happens even with single ticker)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

            valid_df = df.dropna(subset=['Close'])
            if valid_df.empty:
                results[raw_sym] = {"error": "No Valid Prices"}
                continue

            last_row = valid_df.iloc[-1]
            prev_row = valid_df.iloc[-2] if len(valid_df) > 1 else last_row
            
            price = float(last_row['Close'])
            prev_price = float(prev_row['Close'])
            change = price - prev_price
            pct_change = (change / prev_price) if prev_price != 0 else 0.0

            results[raw_sym] = {
                "price": price,
                "change": change,
                "pct_change": pct_change,
                "time": str(last_row.name)
            }
        except Exception as e:
            results[raw_sym] = {"error": str(e)}
            
    return results


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCzAvYgcX1rXftIRdMrcWiuAxweXadRLFQ")
genai.configure(api_key=API_KEY)
# Switch to user-specified model version
MODEL_NAME = 'gemini-2.5-flash'

model = genai.GenerativeModel(MODEL_NAME)
MANDATORY = ["1513", "6117"]

# --- GLOBAL STATE ---
# In a real app, use Redis/Database. For this single-user Docker, global var is fine.
job_state = {
    "status": "idle", # idle, running, completed, error
    "progress": "",
    "data": [],
    "error": None,
    "last_updated": None
}

def get_gemini_advice(symbol, info, dist_A):
    summary = (
        f"股票代碼: {symbol}\n"
        f"技術位階: 離支撐 A 點目前 {dist_A:+.1%}\n"
        f"營收成長率: {info.get('revenueGrowth', 0)*100:.1f}%\n"
        f"毛利率: {info.get('grossMargins', 0)*100:.1f}%\n"
        f"ROE: {info.get('returnOnEquity', 0)*100:.1f}%\n"
        f"本益比: {info.get('trailingPE', 'N/A')}\n"
    )
    prompt = f"你是一位精通台股的專業分析師，請針對數據給予該標的 50 字內建議，開頭標註評等（強烈推薦/穩健/觀察）：\n{summary}"

    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            response = model.generate_content(prompt)
            return response.text.strip() if response and hasattr(response, 'text') else "無回傳文字"
        except exceptions.ResourceExhausted:
            retries += 1
            logger.warning(f"⚠️ {symbol} 限流，等待 20 秒... (重試 {retries}/{max_retries})")
            time.sleep(20)
        except Exception as e:
            logger.error(f"AI Error for {symbol}: {e}")
            return f"AI 錯誤: {str(e)}"
    
    return "AI 分析暫時無法使用 (限流/額度已滿)"


def analyze_stock_technical(df, symbol, lookback=120):
    try:
        if df.empty or len(df) < 30: return False, {}
        
        # Strictly bound the search to the lookback provided by user
        lookback = min(len(df) - 5, lookback)
        window = df.iloc[-lookback:]
        
        # 1. Identify a potential Neckline Floor (A) in the first 65% of the window
        # We look for a plateau, not just a single spike
        split_idx = int(lookback * 0.65)
        part_A = window.iloc[:split_idx]
        
        # A is the 35th percentile of Lows (the "floor" of the plateau)
        val_A = part_A['Low'].quantile(0.35)
        # Find a prominent candle in part_A that actually touched/approached val_A
        # This makes the "A: 頸線" label sit on the actual horizontal line correctly
        idx_A = (part_A['Low'] - val_A).abs().idxmin() 
        
        # 2. Look for the BREAKDOWN (B) in the remaining window
        part_B_C = window.iloc[split_idx:]
        if part_B_C.empty:
             return False, {'val_A': val_A, 'idx_A': idx_A}
             
        # B is the deep spike below A
        val_B = part_B_C['Low'].min()
        idx_B = part_B_C['Low'].idxmin()
        iloc_idx_B = df.index.get_loc(idx_B)
        
        # STRICT RULE: B must break A (at least slightly lower)
        # If not lower, we reject B and C entirely to keep the chart clean
        if val_B >= val_A * 0.9995:
             return False, {'val_A': val_A, 'idx_A': idx_A, 'message': '未見明顯破位'}

        # 3. Reclaim Check: Must cross back above A
        subset_after_B = df.iloc[iloc_idx_B + 1 :]
        cross_above_A = subset_after_B[subset_after_B['High'] > val_A * 1.001]
        
        if cross_above_A.empty:
             # Just show A and B, but no C because it never stood back
             return False, {'val_A': val_A, 'idx_A': idx_A, 'val_B': val_B, 'idx_B': idx_B, 'message': '破位後未站回'}
             
        reclaim_idx = cross_above_A.index[0]
        iloc_reclaim = df.index.get_loc(reclaim_idx)

        # 4. Find FIRST C (The Retest) after Reclaim
        subset_after_reclaim = df.iloc[iloc_reclaim:]
        idx_C = None
        val_C = None
        for i in range(len(subset_after_reclaim)):
            row = subset_after_reclaim.iloc[i]
            # C is when Low touches A plateau
            if row['Low'] <= val_A * 1.01 and row['Low'] >= val_A * 0.99:
                idx_C = subset_after_reclaim.index[i]
                val_C = row['Low']
                break
        
        # 5. Result Determination
        current_price = float(df['Close'].iloc[-1])
        dist_A = (current_price - val_A) / val_A
        
        is_passed = False
        if idx_C is not None:
            # If C is recent (within 20 bars) or currently retesting
            bars_since_C = len(df) - 1 - df.index.get_loc(idx_C)
            if bars_since_C <= 20 or (-0.008 <= dist_A <= 0.012):
                is_passed = True

        return is_passed, {
            'val_A': val_A, 'idx_A': idx_A, 
            'val_B': val_B, 'idx_B': idx_B, 
            'val_C': val_C, 'idx_C': idx_C, 
            'dist': dist_A, 'df': df
        }
    except Exception as e:
        print(f"Analyze Error: {e}")
        return False, {}

def generate_chart_base64(df, val_A, idx_A, symbol, dist):
    try:
        df_p = df.iloc[-90:]
        markers = [np.nan] * len(df_p)
        if idx_A in df_p.index:
            markers[df_p.index.get_loc(idx_A)] = val_A * 0.985
        markers[-1] = df_p['Low'].iloc[-1] * 0.985

        buf = io.BytesIO()
        ap = mpf.make_addplot(markers, type='scatter', marker='^', markersize=50, color='green')
        mpf.plot(df_p, type='candle', style='charles', addplot=ap, 
                 hlines=dict(hlines=[val_A], colors=['b'], linestyle='--'),
                 savefig=dict(fname=buf, format='png', dpi=100))
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Chart gen error: {e}")
        return None

@app.get("/api/check_stock")
def check_stock(symbol: str, interval: str = "1d", lookback: int = 120):
    # Resolve Chinese name to ticker
    symbol = resolve_symbol(symbol).strip().upper()
    
    # Auto-append .TW only if it's purely numeric (e.g. 2330)
    if symbol.isdigit():
         symbol += ".TW"
    
    # Determine Period based on Interval
    period = "10mo"
    if interval == "5m":
        period = "5d" # Last 5 days of 5m data
    elif interval == "60m" or interval == "1h":
        interval = "60m"
        period = "1mo" # Last 1 month of 1h data
    elif interval == "1d":
        period = "10mo"

    try:
        data = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False, threads=False)
        
        # Handle MultiIndex - Robust Flattening
        df = data
        if isinstance(df.columns, pd.MultiIndex):
             # Case 1: Level 0 is Symbol (e.g. grouped by ticker)
             if symbol in df.columns.get_level_values(0):
                  df = df.xs(symbol, level=0, axis=1, drop_level=True)
             # Case 2: Level 1 is Symbol (e.g. grouped by column default)
             elif len(df.columns.levels) > 1 and symbol in df.columns.get_level_values(1):
                  df = df.xs(symbol, level=1, axis=1, drop_level=True)
             
             # Fallback: Just drop the header causing issues if we have 'Close' hidden
             if 'Close' not in df.columns and isinstance(df.columns, pd.MultiIndex):
                  # Try dropping the symbol level (usually level 1 in recent yf)
                  try:
                       temp_df = df.copy()
                       temp_df.columns = temp_df.columns.droplevel(1)
                       if 'Close' in temp_df.columns:
                           df = temp_df
                  except: pass

        # Ensure we have a flat DataFrame with 'Close'
        # Ensure we have a flat DataFrame with 'Close'
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = ["_".join(col).strip() for col in df.columns.values]

        df = df.dropna()
        
        # Fallback for OTC (.TWO) if .TW returned empty
        if (df.empty or len(df) < 5) and symbol.endswith(".TW"):
             print(f"Retry with .TWO for {symbol}")
             alt_symbol = symbol.replace(".TW", ".TWO")
             # Recursive call? No, simplest to just try download again
             try:
                data_two = yf.download(alt_symbol, period=period, interval=interval, auto_adjust=True, progress=False, threads=False)
                df_two = data_two
                if isinstance(data_two.columns, pd.MultiIndex):
                     # Quick flat check for single symbol
                     if alt_symbol in data_two.columns.get_level_values(0):
                          df_two = data_two.xs(alt_symbol, level=0, axis=1, drop_level=True)
                     elif len(data_two.columns.levels) > 1 and alt_symbol in data_two.columns.get_level_values(1):
                          df_two = data_two.xs(alt_symbol, level=1, axis=1, drop_level=True)
                     elif 'Close' not in df_two.columns and len(df_two.columns.levels) > 1:
                            # Try dropping level 1
                            try:
                                temp_df = df_two.copy()
                                temp_df.columns = temp_df.columns.droplevel(1)
                                if 'Close' in temp_df.columns:
                                    df_two = temp_df
                            except: pass
                
                if isinstance(df_two.columns, pd.MultiIndex):
                    df_two.columns = ["_".join(col).strip() for col in df_two.columns.values]
                
                df_two = df_two.dropna()
                if not df_two.empty and len(df_two) >= 5:
                    df = df_two
                    symbol = alt_symbol # Update symbol to .TWO
             except Exception as e_two:
                print(f"TWO Retry failed: {e_two}")

        if df.empty or len(df) < 5: 
             raise ValueError("數據不足 (Not enough data)")

        is_passed, info = analyze_stock_technical(df, symbol, lookback=lookback)
        dist_val = info.get('dist', 0)
        dist_str = f"{dist_val:+.1%}" if not pd.isna(dist_val) else "N/A"
        
        # Prepare Interactive Chart Data
        candles = []
        try:
            temp = df.copy()
            # Convert index (datetime) to unix timestamp (seconds)
            if hasattr(temp.index, 'astype'):
                temp['time'] = temp.index.astype('int64') // 10**9
            
            if 'Open' in temp.columns:
                candles = temp[['time', 'Open', 'High', 'Low', 'Close']].rename(columns={
                    'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'
                }).to_dict(orient='records')
        except Exception as e:
            print(f"Candle Data Error: {e}")

        msg_text = "未符合條件"
        status_text = f"檢查({interval})"

        if info and 'df' in info:
            if is_passed:
                status_text = "符合買點"
                msg_text = f"標準 ABC 圖形：頸線回測中 ({interval})"
            else:
                msg_text = info.get('message', f"未符合條件 (距離 A 點 {dist_str})")

        # Build clean response
        resp = {
            "symbol": symbol, "is_passed": is_passed, "dist": dist_str,
            "message": msg_text, "chart": None, "candles": candles, "status": status_text,
            "interval": interval,
            "val_A": info.get('val_A'),
            "idx_A": str(info.get('idx_A')) if (info.get('idx_A') and info.get('idx_A') != 'nan') else None,
            "version": "4.2-VISUAL-SYNC"
        }
        
        # Suppress B/C if they are not part of a valid pattern or logic
        if is_passed or (info.get('val_B') and info.get('val_B') < info.get('val_A', 999999)):
             # Only show B if it's logically valid (B < A)
             if info.get('idx_B') and info.get('val_B') < info.get('val_A', 999999):
                 resp["val_B"] = info.get('val_B')
                 resp["idx_B"] = str(info.get('idx_B'))
             
             # Only show C if B was valid and C was found
             if info.get('idx_C') and resp.get("val_B"):
                 resp["val_C"] = info.get('val_C')
                 resp["idx_C"] = str(info.get('idx_C'))

        return sanitize_json(resp)
    except Exception as e:
        logger.error(f"Check error: {e}")
        return {"symbol": symbol, "is_passed": False, "message": str(e), "chart": None, "candles": [], "dist": "N/A"}

@app.get("/")
def read_root():
    return {"status": "pystock backend alive", "time": datetime.now().isoformat()}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "4.1-STRICT-ABC", "time": datetime.now().isoformat()}



FUTURES_MAP = {
    "TX": ["TX=F", "^TWII"], # Try Future first, then Index
    "NQ": ["NQ=F", "MNQ=F"],
    "MNQ": ["MNQ=F"],
    "WTX": ["TX=F", "^TWII"]
}

@app.get("/api/check_futures")
def check_futures(symbol: str = "TX"):
    """
    Check 1h and 5m k-line for futures.
    Returns analysis for both timeframes.
    Supports fallback symbols if primary lacks data.
    """
    symbol_upper = symbol.upper()
    candidates = FUTURES_MAP.get(symbol_upper, [symbol_upper])
    
    # If single string (old usage), make it a list
    if isinstance(candidates, str): candidates = [candidates]
    
    results = {"symbol": symbol_upper}
    
    # Define timeframes
    timeframes = [
        {"label": "1h", "interval": "1h", "period": "1y"},
        {"label": "5m", "interval": "5m", "period": "5d"}
    ]
    
    for tf in timeframes:
        label = tf["label"]
        best_df = pd.DataFrame()
        used_symbol = ""
        
        # Try candidates in order until one works
        for yf_symbol in candidates:
            try:
                # Download data
                data = yf.download(yf_symbol, period=tf["period"], interval=tf["interval"], 
                                   auto_adjust=True, progress=False, threads=False)
                
                # Handle MultiIndex / Data cleanup
                df = data
                if isinstance(data.columns, pd.MultiIndex):
                    try: df = data.xs(yf_symbol, level=1, axis=1)
                    except:
                         if len(data.columns.levels) > 1:
                             df = data.xs(data.columns.levels[1][0], level=1, axis=1)

                df = df.dropna()
                
                if not df.empty and len(df) >= 50:
                    best_df = df
                    used_symbol = yf_symbol
                    break # Found valid data
            except Exception: continue
        
        if best_df.empty:
            results[label] = {"status": "No Data", "message": f"無法取得數據 (嘗試: {candidates})"}
            continue
            
        try:
            # Run existing analysis logic
            is_passed, info = analyze_stock_technical(best_df, used_symbol)
            
            dist_val = info.get('dist', 0)
            dist_str = f"{dist_val:+.1%}" if info else "N/A"
            status_text = "觀察"
            if is_passed: status_text = "符合支撐"
            
            chart_b64 = None
            if info:
                # Generate chart for the specific timeframe
                chart_b64 = generate_chart_base64(info['df'], info['val_A'], info['idx_A'], used_symbol, dist_val)
            
            results[label] = {
                "used_symbol": used_symbol,
                "is_passed": is_passed,
                "dist": dist_str,
                "status": status_text,
                "val_A": info.get('val_A'),
                "val_B": info.get('val_B'),
                "message": "符合條件" if is_passed else f"未符合 (距離 {dist_str})",
                "chart": chart_b64
            }
            
        except Exception as e:
            logger.error(f"Futures check error {label}: {e}")
            results[label] = {"error": str(e)}
            
    return sanitize_json(results)
# --- AI & Charting logic below ---
def run_analysis_task(force=False):
    global job_state
    job_state["status"] = "running"
    job_state["error"] = None
    job_state["data"] = []
    
    try:
        # 0. Check Cache
        today_str = datetime.now().strftime('%Y-%m-%d')
        cache_file = f"cache_{today_str}.json"
        
        if not force and os.path.exists(cache_file):
            job_state["progress"] = "Reading from cache..."
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    job_state["data"] = json.load(f)
                job_state["status"] = "completed"
                return
            except Exception:
                pass # If read fails, ignore cache and re-download

        # 1. Tickers
        job_state["progress"] = "Loading tickers..."
        codes_set = set(MANDATORY)
        if os.path.exists('tickers.txt'):
            with open('tickers.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    # Extract the first column as ticker
                    parts = line.strip().split()
                    if parts:
                        ticker_id = parts[0]
                        if ticker_id.isdigit() and len(ticker_id) == 4:
                            codes_set.add(ticker_id)
        ticker_list = [f"{c}.TW" for c in codes_set]
        
        # 2. Download (Chunked for progress & stability)
        job_state["progress"] = f"Starting download for {len(ticker_list)} stocks..."
        print(job_state["progress"], flush=True)
        
        all_data = {}
        chunk_size = 50 # Smaller chunks to update progress more often
        total_tickers = len(ticker_list)
        
        for i in range(0, total_tickers, chunk_size):
            chunk = ticker_list[i : i + chunk_size]
            batch_num = (i // chunk_size) + 1
            total_batches = (total_tickers + chunk_size - 1) // chunk_size
            
            job_state["progress"] = f"Downloading batch {batch_num}/{total_batches} ({len(chunk)} stocks)..."
            logger.info(job_state["progress"])
            
            try:
                # Use threads=False for stability in background tasks if hanging occurs
                data_chunk = yf.download(chunk, period="10mo", interval="1d", group_by='ticker', auto_adjust=True, progress=False, threads=False)
                
                if data_chunk is not None and not data_chunk.empty:
                    if len(chunk) == 1:
                        all_data[chunk[0]] = data_chunk
                    else:
                        for symbol in chunk:
                            try:
                                if symbol in data_chunk.columns.get_level_values(0):
                                    stock_df = data_chunk.xs(symbol, level=0, axis=1, drop_level=True).dropna()
                                    if not stock_df.empty:
                                        all_data[symbol] = stock_df
                            except Exception: continue
                logger.info(f"Batch {batch_num} processed. Total data keys: {len(all_data)}")
            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                continue
                
        candidates = []
        
        # 3. Filter Loop
        total = len(ticker_list)
        for i, symbol in enumerate(ticker_list):
            # Update progress less frequently for analysis as it is fast
            if i % 50 == 0:
                job_state["progress"] = f"Processing technical analysis: {i}/{total}"
                print(job_state["progress"], flush=True)

            try:
                # all_data is now a dict, so we can access directly
                df = all_data.get(symbol)
                
                if df is None or df.empty:
                    continue
                    
                df = df.dropna()
                
                is_passed, info = analyze_stock_technical(df, symbol)
                if is_passed:
                    candidates.append({
                        'symbol': symbol, 'df': df, 
                        'val_A': info['val_A'], 'idx_A': info['idx_A'], 'dist': info['dist']
                    })
            except Exception: continue

        # 4. AI Analysis
        picks = sorted(candidates, key=lambda x: abs(x['dist']))[:20]
        job_state["progress"] = f"AI Diagnosis for top {len(picks)} candidates..."
        
        results = []
        for i, item in enumerate(picks):
            job_state["progress"] = f"AI Analyzing {i+1}/{len(picks)}: {item['symbol']}"
            try:
                symbol = item['symbol']
                tk = yf.Ticker(symbol)
                advice = get_gemini_advice(symbol, tk.info, item['dist'])
                chart_b64 = generate_chart_base64(item['df'], item['val_A'], item['idx_A'], symbol, item['dist'])
                
                results.append(sanitize_json({
                    "symbol": symbol,
                    "dist": f"{item['dist']:+.1%}",
                    "advice": advice,
                    "chart": chart_b64,
                    "status": "強烈推薦" if "強烈推薦" in advice else ("穩健" if "穩健" in advice else "觀察")
                }))
                time.sleep(1)
            except: continue
            
        # 5. Save Cache
        if results:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        job_state["data"] = results
        job_state["status"] = "completed"

    except Exception as e:
        job_state["status"] = "error"
        job_state["error"] = str(e)
        logger.error(f"Analysis Failed: {e}")

@app.post("/api/analyze")
def start_analysis(background_tasks: BackgroundTasks, force: bool = False):
    if job_state["status"] == "running":
        return {"status": "running", "message": "Job already running"}
    
    # Reset state
    job_state["status"] = "idle" 
    job_state["data"] = []
    
    background_tasks.add_task(run_analysis_task, force)
    return {"status": "started"}

@app.get("/api/status")
def get_status():
    return job_state

if __name__ == "__main__":
    import uvicorn
    # Use environment variable PORT for Render deployment, default to 8001
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)