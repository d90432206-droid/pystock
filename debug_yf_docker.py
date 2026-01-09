
import yfinance as yf
import sys
import requests

print("Testing yfinance download for 2330.TW with custom session...")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
})

try:
    # Try using Ticker.history which is sometimes more robust
    ticker = yf.Ticker("2330.TW", session=session)
    data = ticker.history(period="1mo")
    
    if data.empty:
        print("FAIL: Ticker.history returned empty data")
    else:
        print(f"SUCCESS: Ticker.history downloaded {len(data)} rows")
        print(data.head())
        sys.exit(0)

    # If that failed, try download with session (though yf.download deprecated session arg in some versions, need to check)
    print("Retrying with yf.download...")
    # yfinance >= 0.2.x uses requests_cache or internal session handling usually
    # forcing it via Ticker is safer.
    
    sys.exit(1)

except Exception as e:
    print(f"ERROR: {e}")
    # Print more info on the 'Expecting value' error if possible?
    sys.exit(1)
