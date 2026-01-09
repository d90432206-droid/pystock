import yfinance as yf
import requests
import traceback

def test_connection():
    print("----- Test 1: Direct HTTP Request to Yahoo Finance -----")
    url = "https://query1.finance.yahoo.com/v7/finance/chart/2330.TW?range=1d&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("HTTP Request Successful. Content length:", len(response.content))
        elif response.status_code == 429:
            print("❌ BLOCKED: Rate Limit Exceeded (HTTP 429)")
            return
        elif response.status_code == 403:
            print("❌ BLOCKED: Forbidden (HTTP 403) - IP might be banned")
            return
        else:
            print(f"HTTP Failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

    print("\n----- Test 2: yfinance Library Download (2330.TW) -----")
    try:
        # 建立一個 Ticker 重置 cache
        yf.set_tz_cache_location("yf_test_temp_cache")
        data = yf.download("2330.TW", period="1mo", progress=False)
        if data.empty:
             print("❌ yfinance returned empty data.")
        else:
             print("✅ yfinance download successful!")
             print(data.head())
    except Exception as e:
        print(f"❌ yfinance Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
