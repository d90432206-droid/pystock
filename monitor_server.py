import requests
import json
import time

def monitor():
    url = "http://localhost:8001/api/check_stock?symbol=2330"
    print(f"🚀 Monitor: Sending GET request to {url}...")
    try:
        t0 = time.time()
        resp = requests.get(url, timeout=30)
        dt = time.time() - t0
        print(f"⏱️ Time taken: {dt:.2f}s")
        print(f"📥 Status Code: {resp.status_code}")
        
        try:
            data = resp.json()
            print("📄 JSON Response:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if "message" in data:
                print("\n⚠️ Message Content (Traceback):")
                print(data["message"])
        except ValueError:
            print("❌ Invalid JSON response. Raw content:")
            print(resp.text[:500])
            
    except Exception as e:
        print(f"❌ Request Failed: {e}")

if __name__ == "__main__":
    monitor()
