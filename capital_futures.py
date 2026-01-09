import sys
import os
import asyncio
import logging
from queue import Queue, Empty
from datetime import datetime
import json
import threading
import ctypes
try:
    from ctypes import wintypes
except ImportError:
    wintypes = None
import time
import concurrent.futures

# Ensure we can import SKDLLPython
current_dir = os.path.dirname(os.path.abspath(__file__))
sk_path = os.path.join(current_dir, "SKDLLPythonTester")
if sk_path not in sys.path:
    sys.path.append(sk_path)

try:
    from SKDLLPython import SK
except ImportError:
    print("Warning: Could not import SKDLLPython. Capital API features will not work.")
    SK = None

logger = logging.getLogger("CapitalFutures")


import concurrent.futures

class CapitalFuturesClient:
    _instance = None
    
    def __init__(self):
        self.is_connected = False
        self.quote_queue = Queue()
        self.latest_quotes = {}
        self.cmd_queue = Queue()
        self.running = True
        
        # Worker thread for API calls + Message Pump
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def write_log(self, msg):
        try:
            with open("capital_robust.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} {msg}\n")
        except:
            pass

    def _worker_loop(self):
        self.write_log("Starting Capital Worker Loop")
        
        is_windows = (os.name == 'nt')
        user32 = None
        msg = None
        PM_REMOVE = 0x0001
        
        if is_windows:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                self.write_log("CoInitialize successful")
            except Exception as e:
                self.write_log(f"CoInitialize error: {e}")

            # Initialize User32 for pump
            try:
                user32 = ctypes.windll.user32
                msg = wintypes.MSG()
            except Exception as e:
                self.write_log(f"Windows API init failed: {e}")
                
            # Register Callbacks IN THIS THREAD
            if SK:
                self.write_log("Registering callbacks...")
                try:
                    SK.OnNotifyTicksLONG(self._on_notify_ticks)
                    SK.OnReplyMessage(self._on_reply_message)
                    SK.OnConnection(self._on_connection)
                    self.write_log("Callbacks registered")
                except Exception as e:
                    self.write_log(f"Callback registration failed: {e}")
        else:
            self.write_log("Non-Windows env detected. Running in mock/bypass mode.")

        self.write_log("Entering main loop")
        try:
            while self.running:
                # 1. Process Queue
                try:
                    # Non-blocking get
                    while not self.cmd_queue.empty():
                        task = self.cmd_queue.get_nowait()
                        action, args, future = task
                        self.write_log(f"Processing task: {action}")
                        try:
                            # Handle actions
                            res = None
                            if action == 'login':
                                if is_windows:
                                    res = self._do_login(*args)
                                else:
                                    # Mock success for testing in Docker
                                    res = {"status": "success", "message": "Login Simulated (Non-Windows)"}
                            elif action == 'subscribe':
                                if is_windows:
                                    res = self._do_subscribe(*args)
                                else:
                                    res = {"status": "success", "message": f"Subscribe {args[0]} Simulated"}
                            
                            self.write_log(f"Task {action} completed: {res}")
                            if future:
                                future.set_result(res)
                        except Exception as e:
                            self.write_log(f"Task {action} failed execution: {e}")
                            if future: future.set_exception(e)
                except Exception as e:
                    self.write_log(f"Queue/Task Error: {e}")

                # 2. Windows Message Pump (PeekMessage)
                if is_windows and user32 is not None:
                    try:
                        msg_count = 0
                        while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, PM_REMOVE) != 0:
                            user32.TranslateMessage(ctypes.byref(msg))
                            user32.DispatchMessageW(ctypes.byref(msg))
                            msg_count += 1
                            if msg_count > 100: break
                    except Exception as e:
                        self.write_log(f"Pump Error: {e}")
                
                time.sleep(0.01)
        except Exception as e:
            self.write_log(f"Worker Loop CRASHED: {e}")
            import traceback
            self.write_log(traceback.format_exc())

    def _do_login(self, user_id, password, flag=0, cert="", path=""):
        if not SK: return {"status": "error", "message": "DLL missing"}
        self.write_log(f"Worker: Calling SK.Login for {user_id}...")
        try:
            # Pass extra args if provided
            res = SK.Login(user_id, password, flag, cert, path)
            code = res.Code if hasattr(res, 'Code') else res
            self.write_log(f"Worker: Login code: {code}")
            
            if code == 0:
                self.is_connected = True
                self.write_log("Worker: Login success. Calling SKQuoteLib_EnterMonitorLONG...")
                # Correct Connection Method for v2 API
                # Connect to Quote Server (0:Connect, 1:Domestic Quote)
                res_quote = SK.ManageServerConnection(user_id, 0, 1)
                self.write_log(f"Worker: ManageServerConnection(Quote) result: {res_quote}")
                
                if res_quote != 0:
                        self.write_log(f"Worker: Quote Connection Failed: {SK.GetMessage(res_quote)}")
                
                # Connect to Report Server (Optional but good, 0:Connect, 0:Report)
                # res_report = SK.ManageServerConnection(user_id, 0, 0) 
                # self.write_log(f"Worker: ManageServerConnection(Report) result: {res_report}")

                return {"status": "success", "message": "Login & Connection successful"}
            return {"status": "error", "message": f"Login failed: {SK.GetMessage(code)}"}
        except Exception as e:
            self.write_log(f"Worker: SK.Login exception: {e}")
            raise e

    def _do_subscribe(self, symbol):
        if not SK: return {"status": "error"}
        self.write_log(f"Worker: Subscribe {symbol}")
        # Use Page 1
        res = SK.SKQuoteLib_RequestTicks(1, symbol)
        self.write_log(f"Worker: RequestTicks Result: {res}")
        if res == 0:
            return {"status": "success", "message": f"Subscribed {symbol}"}
        return {"status": "error", "message": f"Failed: {SK.GetMessage(res)}"}

    # --- Public Methods ---
    def login(self, user_id, password, flag=0, cert="", path=""):
        future = concurrent.futures.Future()
        self.cmd_queue.put(('login', (user_id, password, flag, cert, path), future))
        return future.result(timeout=10)

    def subscribe(self, symbol):
        future = concurrent.futures.Future()
        self.cmd_queue.put(('subscribe', (symbol,), future))
        return future.result(timeout=5)

    # Callbacks
    def _on_reply_message(self, login_id, message):
        self.write_log(f"[Capital] Reply: {login_id} - {message}")

    def _on_connection(self, login_id, code):
        self.write_log(f"[Capital] Connection: {login_id} Status: {code}")

    def _on_notify_ticks(self, marketNo, strStockNo, ptr, date, timeHMS, timeMicro, bid, ask, close, qty, simulate):
        try:
            symbol_str = strStockNo.decode('ansi') if isinstance(strStockNo, bytes) else strStockNo
            # self.write_log(f"[Tick] {symbol_str} {close}") # Verbose but useful
            
            quote_data = {
                "symbol": symbol_str,
                "date": date,
                "time": timeHMS,
                "bid": bid,
                "ask": ask,
                "price": close,
                "qty": qty,
                "vol": qty
            }
            self.latest_quotes[quote_data["symbol"]] = quote_data
            self.quote_queue.put(quote_data)
        except Exception as e:
            self.write_log(f"Tick error: {e}")

    def get_quote_stream(self):
        while True:
            try:
                item = self.quote_queue.get(timeout=1)
                yield item
            except Empty:
                yield None
            except Exception:
                break


client = CapitalFuturesClient.get_instance()
