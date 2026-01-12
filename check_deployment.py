#!/usr/bin/env python3
"""
本地測試腳本 - 驗證前後端整合是否正常
"""

import os
import sys

def check_frontend_build():
    """檢查前端是否已構建"""
    frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    
    print("=" * 60)
    print("檢查前端構建狀態...")
    print("=" * 60)
    
    if not os.path.exists(frontend_dist):
        print("❌ 錯誤: frontend/dist 目錄不存在")
        print("\n📝 解決方法:")
        print("   cd frontend")
        print("   npm install")
        print("   npm run build")
        return False
    
    index_path = os.path.join(frontend_dist, "index.html")
    if not os.path.exists(index_path):
        print(f"❌ 錯誤: {index_path} 不存在")
        return False
    
    assets_path = os.path.join(frontend_dist, "assets")
    if not os.path.exists(assets_path):
        print("⚠️  警告: assets 目錄不存在，可能構建不完整")
    
    print(f"✅ 前端構建正常")
    print(f"   - index.html: {index_path}")
    print(f"   - assets: {assets_path}")
    
    # List assets files
    if os.path.exists(assets_path):
        assets_files = os.listdir(assets_path)
        print(f"   - 資源文件數: {len(assets_files)}")
    
    return True

def check_python_deps():
    """檢查 Python 依賴"""
    print("\n" + "=" * 60)
    print("檢查 Python 依賴...")
    print("=" * 60)
    
    required = [
        'fastapi',
        'uvicorn',
        'yfinance',
        'pandas',
        'numpy',
        'matplotlib',
        'mplfinance'
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} (未安裝)")
            missing.append(pkg)
    
    if missing:
        print("\n📝 解決方法:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True

def check_env_vars():
    """檢查環境變數"""
    print("\n" + "=" * 60)
    print("檢查環境變數...")
    print("=" * 60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("⚠️  警告: GEMINI_API_KEY 環境變數未設置")
        print("   AI 分析功能將無法使用")
        print("\n📝 設置方法:")
        print("   export GEMINI_API_KEY=你的金鑰  # Linux/Mac")
        print("   set GEMINI_API_KEY=你的金鑰     # Windows CMD")
        print("   $env:GEMINI_API_KEY='你的金鑰'  # Windows PowerShell")
    else:
        masked_key = api_key[:10] + "..." if len(api_key) > 10 else "***"
        print(f"✅ GEMINI_API_KEY: {masked_key}")
    
    port = os.getenv("PORT", "8001")
    print(f"✅ PORT: {port}")
    
    return True

def main():
    print("\n🔍 ABC 策略選股系統 - 部署前檢查\n")
    
    results = [
        check_frontend_build(),
        check_python_deps(),
        check_env_vars()
    ]
    
    print("\n" + "=" * 60)
    print("檢查結果")
    print("=" * 60)
    
    if all(results):
        print("✅ 所有檢查通過！可以開始部署")
        print("\n🚀 本地測試:")
        print("   python stock2.py")
        print("   然後訪問: http://localhost:8001")
        print("\n📦 Docker 測試:")
        print("   docker build -t pystock-abc .")
        print("   docker run -p 8001:8001 -e GEMINI_API_KEY=你的金鑰 pystock-abc")
        return 0
    else:
        print("❌ 部分檢查未通過，請先修正上述問題")
        return 1

if __name__ == "__main__":
    sys.exit(main())
