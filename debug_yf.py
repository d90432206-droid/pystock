import yfinance as yf
import pandas as pd
import mplfinance as mpf

def analyze_stock_technical(df, symbol):
    print(f"Analyze: Lines={len(df)}")
    if df.empty or len(df) < 40: 
        print("Too short < 40")
        return False, {}
    
    lookback_start = -120
    lookback_end = -40
    
    if len(df) < 130:
        lookback_start = -len(df) + 10 
        lookback_end = -(len(df) // 3) 
    
    print(f"Window: {lookback_start} to {lookback_end}")

    if lookback_end >= -5: 
         print("Lookback end too close")
         return False, {}

    part_A = df.iloc[lookback_start : lookback_end]
    if part_A.empty: 
        print("Part A empty")
        return False, {}
    
    val_A = part_A['Low'].min()
    print(f"Val A: {val_A}")
    
    return True, {'df': df, 'val_A': val_A}

def check(symbol, interval):
    print(f"--- Checking {symbol} {interval} ---")
    period = "10mo"
    if interval == "5m":
        period = "5d"
    elif interval == "60m":
        period = "1mo"
        
    print(f"Downloading period={period}")
    data = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False, threads=False)
    
    df = pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
            if symbol in data.columns.get_level_values(0):
                df = data.xs(symbol, level=0, axis=1, drop_level=True)
            else:
                df = data
    else:
            df = data
            
    df = df.dropna()
    print(f"Downloaded Rows: {len(df)}")
    if not df.empty:
        print(df.tail())
        
    analyze_stock_technical(df, symbol)

if __name__ == "__main__":
    check("2330.TW", "5m")
    check("NQ=F", "5m")
