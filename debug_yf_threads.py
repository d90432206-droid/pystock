import yfinance as yf
import pandas as pd
import traceback

symbol = "2330.TW"
print(f"Downloading {symbol} with threads=False...")
try:
    data = yf.download([symbol], period="10mo", interval="1d", auto_adjust=True, progress=False, threads=False)
    print("Download success")
    print("Data type:", type(data))
    print("Columns:", data.columns)
    print("Head:", data.head())
except Exception:
    traceback.print_exc()
