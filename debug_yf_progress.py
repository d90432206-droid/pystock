import yfinance as yf
import pandas as pd
import traceback

symbol = "2330.TW"
print(f"Downloading {symbol} with progress=False...")
try:
    data = yf.download([symbol], period="10mo", interval="1d", auto_adjust=True, progress=False)
    print("Download success")
    print("Data head:", data.head())
except Exception:
    traceback.print_exc()
