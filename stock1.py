import yfinance as yf
import pandas as pd
import mplfinance as mpf
import numpy as np
import matplotlib.pyplot as plt
import re
import logging
import os
import google.generativeai as genai
from datetime import datetime
import time  # 新增：用於延遲
from google.api_core import exceptions # 新增：用於補捉 API 特定錯誤

# 1. 環境設定與 AI 配置
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False

# ==========================================
# 修正後的配置區
# ==========================================
API_KEY = "AIzaSyCIDQLQiEhRuW_aXaQ5RCxfahn3wuiUEZY"
genai.configure(api_key=API_KEY)

# 1. 執行這段來檢查您到底能用哪些模型 (除錯用)
print("--- 您目前的 API Key 支援的模型清單 ---")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
print("---------------------------------------")

# 2. 根據測試結果，請嘗試修改這裡：
MODEL_NAME = 'gemini-2.5-flash-lite' 
model = genai.GenerativeModel(MODEL_NAME)

MANDATORY = ["1513", "6117"]

def get_gemini_advice(symbol, info, dist_A):
    """ 呼叫 Gemini 進行診斷，並加入 429 自動重試機制 """
    # 準備數據摘要
    summary = (
        f"股票代碼: {symbol}\n"
        f"技術位階: 離支撐 A 點目前 {dist_A:+.1%}\n"
        f"營收成長率: {info.get('revenueGrowth', 0)*100:.1f}%\n"
        f"毛利率: {info.get('grossMargins', 0)*100:.1f}%\n"
        f"ROE: {info.get('returnOnEquity', 0)*100:.1f}%\n"
        f"本益比: {info.get('trailingPE', 'N/A')}\n"
    )
    
    prompt = (
        f"你是一位精通台股的專業分析師，請針對以下數據給予該標的 50 字內的精準投資建議，"
        f"並必須在開頭標註評等為『強烈推薦』、『穩健』或『觀察』：\n{summary}"
    )

    # 無限迴圈直到成功或遇到非額度的錯誤
    while True:
        try:
            response = model.generate_content(prompt)
            if response and hasattr(response, 'text'):
                return response.text.strip()
            else:
                return "AI 診斷未回傳有效文字。"
                
        except exceptions.ResourceExhausted:
            # 這是關鍵：當遇到 429 錯誤時執行的動作
            print(f"⚠️ {symbol}: 觸發 API 每分鐘次數限制 (429)，等待 15 秒後重試...")
            time.sleep(15) 
            continue # 重新跑一次 try 區塊
            
        except Exception as e:
            # 其他類型的錯誤（如網路斷線、模型名稱錯誤等）
            return f"AI 診斷暫時不可用 ({str(e)})"

def run_v30_gemini_radar(file_path):
    # A. 建立資料夾
    today_str = datetime.now().strftime('%Y-%m-%d')
    if not os.path.exists(today_str): os.makedirs(today_str)

    # B. 下載數據
    codes_set = set(MANDATORY)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.findall(r'\d{4}', line)
                for c in m: codes_set.add(c)
    
    ticker_list = [f"{c}.TW" for c in codes_set]
    print(f"🚀 V30 AI 智勝雷達 (Gemini) 啟動 | 分析標的: {len(ticker_list)} 檔")
    
    all_data = yf.download(ticker_list, period="10mo", interval="1d", group_by='ticker', auto_adjust=True, progress=True)

    results = []
    report_list = []

    # C. 分析結構
    for symbol in ticker_list:
        try:
            df = all_data[symbol].dropna()
            if df.empty or len(df) < 60: continue

            val_A = df.iloc[-120:-40]['Low'].min()
            idx_A = df.iloc[-120:-40]['Low'].idxmin()
            val_B = df.loc[idx_A : df.index[-2]]['Low'].min()
            dist_A = (df['Close'].iloc[-1] - val_A) / val_A
            
            is_m = any(m in symbol for m in MANDATORY)
            if is_m or (val_B < val_A * 1.005 and -0.02 <= dist_A <= 0.15):
                results.append({'symbol': symbol, 'df': df, 'val_A': val_A, 'idx_A': idx_A, 'dist': dist_A, 'is_m': is_m})
        except: continue

    # D. 挑選前 20 檔並呼叫 AI
    picks = sorted(results, key=lambda x: abs(x['dist']))[:20]
    print(f"🤖 正在為 {len(picks)} 檔潛力股進行診斷 (已開啟自動避開限流機制)...")

    for item in picks:
        try:
            tk = yf.Ticker(item['symbol'])
            info = tk.info
            # 這裡會呼叫帶有重試機制的函式
            ai_advice = get_gemini_advice(item['symbol'], info, item['dist'])
            
            report_list.append({
                '代碼': item['symbol'],
                '位階距離': f"{item['dist']:+.1%}",
                'AI 專家診斷 (3.0 Flash)': ai_advice
            })
            # 為了降低觸發頻率，每筆之間主動微休 1 秒
            time.sleep(1)
            
        except Exception as e:
            report_list.append({'代碼': item['symbol'], '位階距離': 'N/A', 'AI 專家診斷 (3.0 Flash)': f'獲取失敗: {str(e)}'})

    # E. 儲存 CSV 報表
    df_report = pd.DataFrame(report_list)
    report_path = os.path.join(today_str, f"AI_Smart_Report_3.0_{datetime.now().strftime('%H%M%S')}.csv")
    df_report.to_csv(report_path, index=False, encoding='utf-8-sig')
    print(f"📄 AI 診斷報表已生成: {report_path}")

    # F. 繪製 20 宮格
    if picks:
        fig = mpf.figure(style='charles', figsize=(25, 18), facecolor='white')
        for i, item in enumerate(picks):
            ax = fig.add_subplot(4, 5, i+1)
            df_p = item['df'].iloc[-90:]
            v_A = item['val_A']
            
            markers = [np.nan] * len(df_p)
            if item['idx_A'] in df_p.index: 
                markers[df_p.index.get_loc(item['idx_A'])] = v_A * 0.985
            markers[-1] = df_p['Low'].iloc[-1] * 0.985
            
            ap = mpf.make_addplot(markers, type='scatter', marker='^', markersize=40, color='green', ax=ax)
            mpf.plot(df_p, type='candle', ax=ax, addplot=ap, hlines=dict(hlines=[v_A], colors=['b'], linestyle='--'))
            ax.set_title(f"{item['symbol']} ({item['dist']:+.1%})", fontsize=10, fontweight='bold', loc='left')

        fig.tight_layout(pad=4.0)
        img_path = os.path.join(today_str, f"AI_Visual_Radar_3.0_{datetime.now().strftime('%H%M%S')}.png")
        fig.savefig(img_path, dpi=120)
        print(f"🖼️ 20 宮格圖檔已儲存: {img_path}")
        plt.show()
    else:
        print("⚠️ 未發現符合條件的標的，跳過繪圖。")

if __name__ == "__main__":
    run_v30_gemini_radar('tickers.txt')