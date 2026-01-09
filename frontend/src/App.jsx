import React, { useState, useEffect, useRef } from 'react';
import { RefreshCw, Activity, TrendingUp, AlertCircle, X, Filter, FileDown } from 'lucide-react';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { createChart } from 'lightweight-charts';

// TradingView Chart Component
const TradingViewChart = ({ data, valA, valB, valC, idxA, idxB, idxC }) => {
  const chartContainerRef = useRef();

  useEffect(() => {
    if (!data || data.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: { background: { type: 'solid', color: '#0f172a' }, textColor: '#cbd5e1' },
      grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#334155', rightOffset: 20 },
      rightPriceScale: { borderColor: '#334155' }
    });

    const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });
    candlestickSeries.setData(data);
    
    // Prediction Line (Dashed Purple Path)
    const predictionSeries = chart.addLineSeries({
        color: '#a855f7', // purple-500
        lineWidth: 2,
        lineStyle: 2, // Dashed
        title: '預測路徑',
        lastValueVisible: false,
        priceLineVisible: false,
    });

    if (valA) {
        // Generate a 6-point extended projection path (Scenario Simulation)
        const lastCandle = data[data.length - 1];
        const step = (data[1].time - data[0].time); // interval in seconds
        
        const depth = valB ? (valA - valB) : (valA * 0.015);
        const targetHigh = valA + depth;
        
        const projection = [
           { time: lastCandle.time, value: lastCandle.close },
           { time: lastCandle.time + step * 8, value: targetHigh },      // 1. Symmetrical Peak
           { time: lastCandle.time + step * 16, value: valA },           // 2. Initial Retest
           { time: lastCandle.time + step * 22, value: valA * 1.006 },   // 3. Minor Bounce
           { time: lastCandle.time + step * 28, value: valA - depth * 0.5 }, // 4. Shakeout (Long Lower Shadow point)
           { time: lastCandle.time + step * 36, value: valA * 1.002 }    // 5. Final Stabilization
        ];
        predictionSeries.setData(projection);

       // Neckline Support (A)
       candlestickSeries.createPriceLine({
            price: valA,
            color: '#34d399', 
            lineWidth: 2,
            lineStyle: 0, 
            axisLabelVisible: true,
            title: 'Neckline (A)',
       });
    }

    // Add Markers for A, B, and C
    const markers = [];
    const findTime = (targetIdx) => {
        if (!targetIdx || targetIdx === 'None' || targetIdx === 'null') return null;
        const targetDate = new Date(targetIdx);
        if (isNaN(targetDate)) return null;
        const targetTs = Math.floor(targetDate.getTime() / 1000);
        const match = data.find(d => Math.abs(d.time - targetTs) < 3600); 
        return match ? match.time : null;
    };

    const timeA = findTime(idxA);
    if (timeA) markers.push({ time: timeA, position: 'belowBar', color: '#34d399', shape: 'arrowUp', text: 'A: 頸線' });
    const timeB = findTime(idxB);
    if (timeB) markers.push({ time: timeB, position: 'belowBar', color: '#f87171', shape: 'arrowUp', text: 'B: 破位' });
    const timeC = findTime(idxC);
    if (timeC) markers.push({ time: timeC, position: 'belowBar', color: '#fbbf24', shape: 'arrowUp', text: 'C: 買點/回測' });

    if (markers.length > 0) candlestickSeries.setMarkers(markers.sort((a,b) => a.time - b.time));

    chart.timeScale().fitContent();

    const handleResize = () => {
        if(chartContainerRef.current) chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, valA, valB, valC, idxA, idxB, idxC]);

  return <div ref={chartContainerRef} className="w-full h-[400px]" />;
};

const App = () => {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [manualResult, setManualResult] = useState(null);
  const [filterStatus, setFilterStatus] = useState("ALL"); 
  const [lookback, setLookback] = useState(120); 
  const [showHelp, setShowHelp] = useState(false);

  const [quotes, setQuotes] = useState({});
  const [lastUpdated, setLastUpdated] = useState("");
  const [quoteSymbols, setQuoteSymbols] = useState("^TWII,NQ=F,2330.TW");

  useEffect(() => {
    const fetchQuotes = async () => {
      try {
        const res = await fetch(`/api/quote?symbols=${quoteSymbols}`);
        const data = await res.json();
        
        if (data && !data.error) {
          setQuotes(data);
          const now = new Date();
          setLastUpdated(now.toLocaleTimeString());
        } else if (data.error) {
          console.error("API error:", data.error);
          setQuotes({ error: "API 回傳錯誤" });
        }
      } catch (e) {
        console.error("Quote fetch error", e);
        setQuotes({ error: "連線失敗" });
      }
    };

    fetchQuotes();
    const interval = setInterval(fetchQuotes, 5000);
    return () => clearInterval(interval);
  }, [quoteSymbols]);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);
    setProgress("Initiating analysis job...");
    setManualResult(null);

    try {
      const startRes = await fetch('/api/analyze?force=true', { method: 'POST' });
      if (!startRes.ok) throw new Error('Failed to start analysis');

      const intervalId = setInterval(async () => {
        try {
          const statusRes = await fetch('/api/status');
          const statusData = await statusRes.json();

          if (statusData.status === 'running') {
            setProgress(statusData.progress || 'Processing...');
          } else if (statusData.status === 'completed') {
            clearInterval(intervalId);
            setStocks(statusData.data || []);
            setLoading(false);
          } else if (statusData.status === 'error') {
            clearInterval(intervalId);
            setError(`Analysis Failed: ${statusData.error}`);
            setLoading(false);
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 2000); 
    } catch (err) {
      console.error(err);
      setError("Unable to connect to V30 AI Backend. Please ensure the analysis server is running.");
      setLoading(false);
    }
  };

  const handleManualCheck = async (e) => {
    e.preventDefault();
    if (!searchQuery) return;

    setLoading(true);
    setManualResult(null);
    setError(null);

    try {
      const res = await fetch(`/api/check_stock?symbol=${searchQuery}&lookback=${lookback}`);
      const data = await res.json();

      if (data.symbol) {
        setManualResult({
          symbol: data.symbol,
          dist: data.dist,
          status: data.is_passed ? "符合買點" : (data.status || "未符合"),
          advice: data.message,
          chart: data.chart,
          candles: data.candles,
          val_A: data.val_A,
          idx_A: data.idx_A,
          val_B: data.val_B,
          idx_B: data.idx_B,
          val_C: data.val_C,
          idx_C: data.idx_C,
          interval: data.interval,
          is_passed: data.is_passed
        });
      }
    } catch (err) {
      console.error("Manual Check Error:", err);
      setError(`查詢失敗: ${err.message}`);
    } finally {
      setLoading(false);
      setSearchQuery("");
    }
  };

  const handleStrategyCheck = async (symbol, interval, customLookback = null) => {
    const activeLookback = customLookback !== null ? customLookback : lookback;
    setLoading(true);
    setManualResult(null);
    setError(null);
    try {
      const res = await fetch(`/api/check_stock?symbol=${encodeURIComponent(symbol)}&interval=${interval}&lookback=${activeLookback}`);
      const data = await res.json();

      if (data.symbol) {
        setManualResult({
          symbol: data.symbol,
          dist: data.dist,
          status: data.status,
          advice: data.message,
          chart: data.chart,
          candles: data.candles,
          val_A: data.val_A,
          idx_A: data.idx_A,
          val_B: data.val_B,
          idx_B: data.idx_B,
          val_C: data.val_C,
          idx_C: data.idx_C,
          interval: data.interval,
          is_passed: data.is_passed
        });
      } else {
        setError(data.message || "查詢失敗");
      }
    } catch (err) {
      console.error("Strategy Check Error:", err);
      setError(`查詢失敗: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const filteredStocks = stocks.filter(stock => {
    if (filterStatus === "ALL") return true;
    if (filterStatus === "STRONG") return stock.status?.includes("強烈");
    if (filterStatus === "STABLE") return stock.status?.includes("穩健") || stock.status?.includes("中");
    if (filterStatus === "OBSERVE") return stock.status?.includes("觀察");
    return true;
  });

  const handleExportPDF = () => {
    window.print();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white print:bg-white print:text-black">
      <nav className="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-md border-b border-slate-800 print:hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">
            <div className="flex items-center gap-2 shrink-0">
              <Activity className="text-indigo-400 w-6 h-6" />
              <h1 className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent hidden md:block">
                ABC策略選股
              </h1>
            </div>

            <form onSubmit={handleManualCheck} className="flex-1 max-w-md flex items-center gap-2">
              <input
                type="text"
                placeholder="輸入代碼 (2330)..."
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-1.5 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700 transition-colors">
                查詢
              </button>
              <button 
                type="button"
                onClick={() => setShowHelp(true)}
                className="p-1.5 text-slate-400 hover:text-indigo-400 transition-colors"
                title="代碼參考"
              >
                <Filter className="w-5 h-5" />
              </button>
            </form>

            <button
              onClick={fetchAnalysis}
              disabled={loading}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20 shrink-0"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">{loading ? 'Analyzing...' : '開始診斷'}</span>
            </button>
          </div>
        </div>
      </nav>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 print:hidden">
        <div className="bg-slate-900/60 border border-indigo-500/30 rounded-xl p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <TrendingUp className="text-emerald-400" /> 市場即時行情 (Yahoo Finance)
            </h2>
            <div className="text-xs text-slate-500 font-mono">
              上次更新: {lastUpdated}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.keys(quotes).length > 0 ? (
              quotes.error ? (
                <div className="col-span-full text-center py-6 text-red-400 bg-red-950/20 rounded-lg border border-red-900/30">
                   無法讀取行情資料 (請確認後端網址是否正確)
                </div>
              ) : (
                Object.entries(quotes).map(([symbol, data]) => {
                  if (symbol === "error") return null;
                  const isPositive = data.change > 0;
                  const isZero = data.change === 0;
                  const colorClass = isPositive ? "text-red-400" : (isZero ? "text-slate-200" : "text-green-400");
                  const displaySymbol = symbol === 'TX=F' ? '台指期 (TX)' : 
                                        symbol === 'NQ=F' ? '那斯達克 (NQ)' : 
                                        symbol === '^TWII' ? '加權指數' : symbol;
                  
                  return (
                  <div key={symbol} className="bg-slate-800/50 rounded-lg p-4 border border-slate-700 hover:border-indigo-500/50 transition-all">
                     <div className="text-xs text-slate-400 mb-1">{displaySymbol}</div>
                     {data.error ? (
                        <div className="text-xs text-red-400">{data.error === "No Valid Rows" ? "暫無資料" : "讀取錯誤"}</div>
                     ) : (
                       <>
                         <div className={`text-2xl font-bold font-mono ${colorClass}`}>
                           {data.price?.toLocaleString()}
                         </div>
                         <div className={`flex items-center gap-2 text-sm font-mono ${colorClass}`}>
                           <span>{data.change > 0 ? "+" : ""}{data.change?.toFixed(2)}</span>
                           <span className="opacity-70">({(data.pct_change * 100)?.toFixed(2)}%)</span>
                         </div>
                         <div className="text-[10px] text-slate-600 mt-2 text-right">
                            {data.time?.split(" ")[1]?.substring(0,5) || ""}
                         </div>
                         
                         <div className="flex gap-2 mt-3 pt-3 border-t border-slate-700/50">
                            <button 
                               onClick={() => handleStrategyCheck(symbol, '5m')}
                               className="flex-1 px-2 py-1 text-xs bg-indigo-900/40 hover:bg-indigo-800/60 text-indigo-200 rounded border border-indigo-500/30 transition-colors"
                            >
                               5分位階
                            </button>
                            <button 
                               onClick={() => handleStrategyCheck(symbol, '60m')}
                               className="flex-1 px-2 py-1 text-xs bg-indigo-900/40 hover:bg-indigo-800/60 text-indigo-200 rounded border border-indigo-500/30 transition-colors"
                            >
                               60分位階
                            </button>
                         </div>
                       </>
                     )}
                  </div>
                  );
                })
              )
            ) : (
               <div className="col-span-full text-center py-4 text-slate-500 animate-pulse">載入行情中...</div>
            )}
            
            <div className="col-span-full md:col-span-4 mt-2 flex justify-end">
               <div className="flex gap-2 items-center text-xs">
                  <span className="text-slate-500">自訂代碼:</span>
                  <input 
                    type="text" 
                    value={quoteSymbols} 
                    onChange={(e) => setQuoteSymbols(e.target.value)}
                    className="bg-slate-800 border-slate-700 rounded px-2 py-1 w-64 text-slate-300 focus:outline-none focus:border-indigo-500"
                    placeholder="TX=F,NQ=F..."
                  />
               </div>
            </div>
          </div>
        </div>
      </section>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 print:p-0 print:max-w-none">
        {loading && (
          <div className="mb-8 print:hidden">
            <div className="flex flex-col items-center justify-center py-12 text-slate-400 space-y-4">
              <div className="relative w-16 h-16">
                <div className="absolute inset-0 border-4 border-slate-800 rounded-full"></div>
                <div className="absolute inset-0 border-4 border-indigo-500 rounded-full border-t-transparent animate-spin"></div>
              </div>
              <p className="animate-pulse">{progress || "Processing..."}</p>
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="mb-8 p-4 rounded-lg bg-red-950/30 border border-red-900/50 flex items-center gap-3 text-red-200 print:hidden">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {!loading && manualResult && (
          <div className="mb-12 flex flex-col items-center animate-in fade-in slide-in-from-bottom-4 duration-500 print:block print:w-full print:mb-4">
            <div className="w-full max-w-5xl bg-slate-900/80 border border-indigo-500/50 rounded-2xl overflow-hidden shadow-2xl shadow-indigo-500/20 print:bg-white print:border-2 print:border-black print:shadow-none">

              <div className="p-6 border-b border-indigo-500/20 flex justify-between items-center bg-indigo-950/20 print:bg-gray-100 print:border-black">
                <div className="flex flex-col md:flex-row md:items-center gap-4">
                  <div>
                    <h2 className="text-3xl font-bold text-white print:text-black flex items-center gap-3">
                      {manualResult.symbol}
                      <span className={`px-3 py-1 rounded-full text-base font-semibold border ${manualResult.is_passed
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30 print:text-black print:border-black'
                        : 'bg-slate-700/50 text-slate-300 border-slate-600 print:text-black print:border-black'
                        }`}>
                        {manualResult.status}
                      </span>
                    </h2>
                    <p className="text-indigo-300 mt-1 text-lg print:text-black">位階距離: {manualResult.dist}</p>
                  </div>

                  {/* Interval Switcher inside Modal */}
                  <div className="flex bg-slate-950/50 p-1 rounded-lg border border-slate-700 h-10 print:hidden ml-0 md:ml-4">
                    {[
                      { label: '日線', val: '1d' },
                      { label: '1HR', val: '60m' },
                      { label: '5分K', val: '5m' }
                    ].map((item) => (
                      <button
                        key={item.val}
                        onClick={() => handleStrategyCheck(manualResult.symbol, item.val)}
                        className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                          (manualResult.interval || '1d') === item.val
                          ? 'bg-indigo-600 text-white shadow-lg'
                          : 'text-slate-400 hover:text-white hover:bg-slate-800'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>

                  {/* Lookback Range Selector */}
                  <div className="flex items-center gap-2 bg-slate-950/50 px-3 py-1 rounded-lg border border-slate-700 h-10 ml-0 md:ml-4 print:hidden">
                    <span className="text-[10px] text-slate-500 font-bold whitespace-nowrap">偵測範圍:</span>
                    <select 
                      value={lookback}
                      onChange={(e) => {
                        const val = parseInt(e.target.value);
                        setLookback(val);
                        handleStrategyCheck(manualResult.symbol, manualResult.interval || '1d', val);
                      }}
                      className="bg-transparent text-xs text-indigo-300 font-bold focus:outline-none cursor-pointer"
                    >
                      <option value="60">近期 (60根)</option>
                      <option value="120">標準 (120根)</option>
                      <option value="200">長期 (200根)</option>
                      <option value="500">超長期 (500根)</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                   <button
                    onClick={() => setManualResult(null)}
                    className="p-2 hover:bg-white/10 rounded-full transition-colors print:hidden"
                  >
                    <X className="w-6 h-6 text-slate-400" />
                  </button>
                </div>
              </div>

              <div className="relative w-full bg-slate-950 p-4 print:bg-white min-h-[400px]">
                {manualResult.candles && manualResult.candles.length > 0 ? (
                  <TradingViewChart 
                     data={manualResult.candles} 
                     valA={manualResult.val_A} 
                     valB={manualResult.val_B}
                     valC={manualResult.val_C}
                     idxA={manualResult.idx_A}
                     idxB={manualResult.idx_B}
                     idxC={manualResult.idx_C}
                  />
                ) : manualResult.chart ? (
                  <img
                    src={`data:image/png;base64,${manualResult.chart}`}
                    alt={manualResult.symbol}
                    className="w-full h-auto max-h-[70vh] object-contain mx-auto"
                  />
                ) : (
                  <div className="h-64 flex items-center justify-center text-slate-600">無圖表數據</div>
                )}
              </div>

              <div className="p-8 bg-gradient-to-b from-slate-900 via-slate-900 to-indigo-950/20 print:bg-white print:text-black">
                <h3 className="text-lg font-semibold text-indigo-400 mb-2 print:text-black border-b print:border-black pb-1">分析建議</h3>
                <p className="text-xl text-slate-200 leading-relaxed font-light print:text-black">
                  {manualResult.advice}
                </p>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && stocks.length > 0 && (
          <div className="mt-8">
            {manualResult && <div className="border-t border-slate-800 my-12 print:hidden" />}

            <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-4 print:mb-4">
              <h2 className="text-3xl font-bold text-white print:text-black flex items-center gap-2">
                <Activity className="w-8 h-8 text-indigo-500 print:text-black" />
                <span>診斷結果 <span className="text-lg font-normal text-slate-400 print:text-black">({filteredStocks.length})</span></span>
              </h2>

              <div className="flex items-center gap-2 print:hidden">
                <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800">
                  {["ALL", "STRONG", "STABLE", "OBSERVE"].map((status) => (
                    <button
                      key={status}
                      onClick={() => setFilterStatus(status)}
                      className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${filterStatus === status
                        ? 'bg-indigo-600 text-white shadow-lg'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800'
                        }`}
                    >
                      {status === "ALL" && "全部"}
                      {status === "STRONG" && "強烈推薦"}
                      {status === "STABLE" && "穩健"}
                      {status === "OBSERVE" && "觀察"}
                    </button>
                  ))}
                </div>

                <div className="w-px h-8 bg-slate-800 mx-2"></div>

                <button
                  onClick={handleExportPDF}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg flex items-center gap-2 transition-colors"
                  title="列印 / 另存為 PDF"
                >
                  <FileDown className="w-4 h-4" />
                  <span>匯出 PDF</span>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 print:grid-cols-2 print:gap-4 print:block">
              {filteredStocks.map((stock, idx) => (
                <div key={idx} className="print:break-inside-avoid print:mb-8">
                  <StockCard stock={stock} />
                </div>
              ))}

              {filteredStocks.length === 0 && (
                <div className="col-span-full py-12 text-center text-slate-500 bg-slate-900/30 rounded-xl border border-dashed border-slate-800">
                  <p className="text-lg">在此篩選條件下無符合標的。</p>
                </div>
              )}
            </div>
          </div>
        )}

      </main>

      <TickerHelpModal isOpen={showHelp} onClose={() => setShowHelp(false)} />

      <style>{`
        @media print {
          body { background-color: white !important; color: black !important; }
          .print-hidden { display: none !important; }
          .no-break { break-inside: avoid; }
        }
      `}</style>
    </div >
  );
};

const TickerHelpModal = ({ isOpen, onClose }) => {
  if (!isOpen) return null;
  const categories = [
    {
      title: "常用指數 & 期貨",
      items: [
        { name: "加權指數", code: "^TWII", note: "搜尋「大盤」也可" },
        { name: "台指期貨", code: "TX=F", note: "搜尋「台指期」也可" },
        { name: "那斯達克100", code: "NQ=F", note: "搜尋「小那」也可" },
        { name: "標普500", code: "ES=F", note: "美股大盤期貨" },
        { name: "道瓊工業期貨", code: "YM=F", note: "道瓊期貨" },
        { name: "黃金期貨", code: "GC=F", note: "搜尋「黃金」也可" }
      ]
    },
    {
      title: "熱門權值股 (台股)",
      items: [
        { name: "台積電", code: "2330", note: "" },
        { name: "鴻海", code: "2317", note: "" },
        { name: "聯發科", code: "2454", note: "" },
        { name: "廣達", code: "2382", note: "" }
      ]
    },
    {
        title: "美股熱門標的",
        items: [
          { name: "輝達 (NVIDIA)", code: "NVDA", note: "" },
          { name: "特斯拉 (Tesla)", code: "TSLA", note: "" },
          { name: "蘋果 (Apple)", code: "AAPL", note: "" },
          { name: "超微 (AMD)", code: "AMD", note: "" }
        ]
      }
  ];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col max-h-[80vh]">
        <div className="p-6 border-b border-slate-800 flex justify-between items-center">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Filter className="w-5 h-5 text-indigo-400" />
            Yahoo Finance 代碼參考
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-full transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 overflow-y-auto space-y-8">
          {categories.map((cat, i) => (
            <div key={i}>
              <h3 className="text-indigo-400 font-bold mb-3 flex items-center gap-2">
                <span className="w-1 h-4 bg-indigo-500 rounded-full"></span>
                {cat.title}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {cat.items.map((item, j) => (
                  <div key={j} className="bg-slate-950/50 border border-slate-800 p-3 rounded-lg flex justify-between items-center hover:border-slate-600 transition-colors">
                    <div>
                      <div className="text-slate-200 font-medium">{item.name}</div>
                      <div className="text-xs text-slate-500">{item.note}</div>
                    </div>
                    <div className="bg-slate-800 px-2 py-1 rounded text-xs font-mono text-indigo-300 border border-slate-700">
                      {item.code}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="bg-indigo-950/20 border border-indigo-900/30 p-4 rounded-xl">
             <p className="text-xs text-indigo-300 leading-relaxed">
               💡 提示：本系統已內建中文辨識，您可以直接在搜尋框輸入名稱（例如：台指期、台積電），系統會自動轉換為正確的 Yahoo Finance 代碼。
             </p>
          </div>
        </div>
      </div>
    </div>
  );
};

const StockCard = ({ stock }) => {
  const getBadgeStyle = (status) => {
    if (status?.includes('強烈推薦')) return 'bg-red-950/60 text-red-200 border-red-900/50 ring-red-900/30 print:border-black print:text-black print:bg-transparent';
    if (status?.includes('穩健') || status?.includes('中')) return 'bg-emerald-950/60 text-emerald-200 border-emerald-900/50 ring-emerald-900/30 print:border-black print:text-black print:bg-transparent';
    return 'bg-slate-800/60 text-slate-300 border-slate-700/50 ring-slate-700/30 print:border-black print:text-black print:bg-transparent';
  };

  return (
    <div className="group relative bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden hover:border-indigo-500/30 hover:shadow-2xl hover:shadow-indigo-500/10 transition-all duration-300 hover:-translate-y-1 print:bg-white print:border-black print:shadow-none print:transform-none">
      <div className="relative aspect-video bg-slate-950 overflow-hidden print:bg-white print:border-b print:border-black">
        {stock.chart ? (
          <img
            src={`data:image/png;base64,${stock.chart}`}
            alt={stock.symbol}
            className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-500 print:transform-none"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-slate-700">
            <TrendingUp className="w-12 h-12 opacity-20" />
          </div>
        )}
        <div className="absolute top-2 right-2">
          <span className={`px-2 py-1 rounded-md text-sm font-bold border backdrop-blur-sm ring-1 ${getBadgeStyle(stock.status)}`}>
            {stock.status || '觀察'}
          </span>
        </div>
      </div>

      <div className="p-6 space-y-4 print:p-4">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-3xl font-extrabold text-white tracking-tight print:text-black">{stock.symbol}</h3>
            <p className="text-base text-slate-400 mt-1 print:text-black">位階距離: <span className="text-indigo-300 ml-1 font-mono text-lg print:text-black">{stock.dist || 'N/A'}</span></p>
          </div>
        </div>
        <div className="relative pl-4 border-l-4 border-indigo-500/30 py-1 print:border-black">
          <p className="text-lg text-slate-200 leading-relaxed italic opacity-90 print:text-black print:not-italic font-medium">
            "{stock.advice || '暫無 AI 分析'}"
          </p>
        </div>
      </div>
    </div>
  );
};

export default App;
