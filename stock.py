import yfinance as yf
import pandas as pd
import mplfinance as mpf
import numpy as np
import matplotlib.pyplot as plt
import re
import logging
import os
from datetime import datetime

# 1. 環境與靜音設定
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False

# 強制一定要追蹤的標的 (確保一定會出現在報表首位)
MANDATORY = ["1513", "6117"]

def run_v27_bulk_auto_report(file_path):
    # A. 建立日期資料夾
    today_str = datetime.now().strftime('%Y-%m-%d')
    if not os.path.exists(today_str):
        os.makedirs(today_str)
        print(f"📂 已建立今日資料夾: {today_str}")

    # B. 讀取並處理代碼
    codes_set = set(MANDATORY)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 抓取 4 位數字代碼
                m = re.findall(r'\d{4}', line)
                for c in m: codes_set.add(c)
    except Exception as e:
        print(f"⚠️ 讀取檔案失敗: {e}")
    
    # 加上後綴，優先嘗試 .TW
    ticker_list = [f"{c}.TW" for c in codes_set]
    
    print(f"🚀 V27 批量雷達啟動 | 目標: {len(ticker_list)} 檔")
    print("📦 正在執行 Bulk Download (大批量一鍵下載)，請稍候...")

    # C. 一次性整包下載 (避開 404/Failed 封鎖)
    try:
        all_data = yf.download(ticker_list, period="10mo", interval="1d", group_by='ticker', auto_adjust=True, progress=True, timeout=30)
    except Exception as e:
        print(f"❌ 下載失敗: {e}")
        return

    # D. 分析潛力結構
    all_picks = []
    print("\n🔍 正在分析 500 檔結構位階...")

    for symbol in ticker_list:
        try:
            # 提取單檔數據並清除空值
            df = all_data[symbol].dropna()
            if df.empty or len(df) < 60: continue

            # 定義 A 點：2025 年底支撐區 (1513/6117 老家)
            part_A = df.loc["2025-10-01":"2025-12-30"]
            if part_A.empty: part_A = df.iloc[-120:-40]
            val_A = part_A['Low'].min()
            idx_A = part_A['Low'].idxmin()

            # 定義 B 點：洗盤動作 (A 點之後)
            search_B = df.loc[idx_A : df.index[-2]]
            val_B = search_B['Low'].min()
            idx_B = search_B['Low'].idxmin()

            # 定義 C 點：現價位階
            today = df.iloc[-1]
            dist_A = (today['Close'] - val_A) / val_A
            
            # 是否為強制追蹤標的
            is_m = any(m in symbol for m in MANDATORY)

            # 過濾邏輯：B 點有洗盤 (<= A * 1.005) 且位階在 -2% ~ +15% 內
            if is_m or (val_B < val_A * 1.005 and -0.02 <= dist_A <= 0.15):
                all_picks.append({
                    'symbol': symbol, 'df': df, 'val_A': val_A, 'idx_A': idx_A, 'idx_B': idx_B, 'dist': dist_A, 'is_m': is_m
                })
        except: continue

    # E. 篩選前 20 檔 (強制標的優先，其餘按離 A 點近度排序)
    m_ones = [r for r in all_picks if r['is_m']]
    others = sorted([r for r in all_picks if not r['is_m']], key=lambda x: abs(x['dist']))
    final_picks = (m_ones + others)[:20]

    if not final_picks:
        print("❌ 本次掃描無符合結構之標的。")
        return

    # F. 繪製 4x5 二十宮格報表
    fig = mpf.figure(style='charles', figsize=(25, 18), facecolor='white')
    print(f"📊 正在產出 20 宮格規劃圖 (目標 {len(final_picks)} 檔)...")

    for i, item in enumerate(final_picks):
        ax = fig.add_subplot(4, 5, i+1)
        df_p = item['df'].iloc[-90:] # 顯示 90 天
        v_A = item['val_A']
        
        # 標註點 (A 點、B 點、今日)
        markers = [np.nan] * len(df_p)
        for target in [item['idx_A'], item['idx_B']]:
            if target in df_p.index:
                markers[df_p.index.get_loc(target)] = df_p.loc[target, 'Low'] * 0.985
        markers[-1] = df_p['Low'].iloc[-1] * 0.985
        
        ap = mpf.make_addplot(markers, type='scatter', marker='^', markersize=45, color='green', ax=ax)
        
        # 繪圖
        mpf.plot(df_p, type='candle', ax=ax, addplot=ap, 
                 hlines=dict(hlines=[v_A, v_A*0.995], colors=['blue', 'red'], linestyle='--', linewidths=0.8),
                 datetime_format='%m-%d', xrotation=20)
        
        # 標題優化：代碼與位階
        ax.set_title(f"{item['symbol']} ({item['dist']:+.1%})", fontsize=10, fontweight='bold', loc='left', pad=8)
        ax.tick_params(labelsize=7)

    fig.tight_layout(pad=4.0)
    
    # G. 自動儲存圖檔
    save_name = f"Potential_ABC_{datetime.now().strftime('%H%M%S')}.png"
    save_path = os.path.join(today_str, save_name)
    fig.savefig(save_path, dpi=150)
    
    print(f"✅ 報表已儲存至: {save_path}")
    mpf.show()

if __name__ == "__main__":
    run_v27_bulk_auto_report('tickers.txt')