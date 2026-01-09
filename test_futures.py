import yfinance as yf
import pandas as pd

tickers = {
    "TX=F": "Taiwan Index Futures", # or maybe WTX
    "NQ=F": "Nasdaq 100 Futures",
    "MNQ=F": "Micro Nasdaq 100 Futures",
    "^TWII": "Taiwan Weighted Index"
}

results = {}

for symbol, name in tickers.items():
    print(f"Checking {name} ({symbol})...")
    try:
        # Check 1h
        data_1h = yf.download(symbol, period="1mo", interval="1h", progress=False)
        # Check 5m
        data_5m = yf.download(symbol, period="5d", interval="5m", progress=False)
        
        results[symbol] = {
            "1h_len": len(data_1h),
            "1h_last": str(data_1h.index[-1]) if not data_1h.empty else "N/A",
            "5m_len": len(data_5m),
            "5m_last": str(data_5m.index[-1]) if not data_5m.empty else "N/A"
        }
    except Exception as e:
        results[symbol] = f"Error: {e}"

print("\nResults:")
for s, r in results.items():
    print(f"{s}: {r}")
