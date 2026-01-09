import yfinance as yf

symbols = ["TX=F", "WTX=F", "WTX", "TX", "TXF=F"]

print("Checking symbols...")
for s in symbols:
    print(f"--- {s} ---")
    try:
        df = yf.download(s, period="5d", interval="1h", progress=False)
        print(f"Rows: {len(df)}")
        if not df.empty:
            print(f"Last: {df.index[-1]}")
    except Exception as e:
        print(f"Error: {e}")
