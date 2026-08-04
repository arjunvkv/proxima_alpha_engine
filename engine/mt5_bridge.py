"""
MT5 Bridge — Direct C-Extension shared memory connection to MT5 terminal with EET broker offset handling.
Safe cross-platform import guard for Windows & Linux Wine environments (via RPyC bridge).
"""

import os
import sys
import time
import socket
import subprocess
import pandas as pd
from datetime import datetime, timezone, timedelta

mt5 = None
HAS_MT5_LIB = False

def _ensure_wine_mt5_server():
    if sys.platform == 'win32':
        return
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        res = sock.connect_ex(('127.0.0.1', 18812))
        sock.close()
        if res != 0:
            print("🚀 [MT5Bridge] Launching MT5 RPyC Bridge Server under Wine...")
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            server_script = os.path.join(repo_root, "engine", "mt5_server.py")
            cmd = f"PYTHONIOENCODING=utf-8 DISPLAY=:10 WINEDEBUG=-all nohup wine ~/.wine/drive_c/Python310/python.exe {server_script} > /tmp/mt5_server.log 2>&1 &"
            subprocess.Popen(cmd, shell=True)
            time.sleep(3)
    except Exception as e:
        print(f"⚠️ [MT5Bridge] Auto-start RPyC server exception: {e}")

def get_mt5():
    global mt5, HAS_MT5_LIB
    if HAS_MT5_LIB and mt5 is not None:
        return mt5, True

    # 1. Native MetaTrader5 (Windows)
    try:
        import MetaTrader5 as native_mt5
        mt5 = native_mt5
        HAS_MT5_LIB = True
        return mt5, True
    except ImportError:
        pass

    # 2. RPyC Bridge (Linux / Wine VPS)
    _ensure_wine_mt5_server()
    try:
        import rpyc
        conn = rpyc.connect('127.0.0.1', 18812, config={'allow_all_attrs': True})
        mt5 = conn.root.get_mt5()
        HAS_MT5_LIB = True
        print("🟢 [MT5Bridge] Connected to MT5 via Linux RPyC Bridge!")
        return mt5, True
    except Exception:
        mt5 = None
        HAS_MT5_LIB = False
        return None, False

mt5, HAS_MT5_LIB = get_mt5()

class MT5Bridge:
    def __init__(self, mt5_path=None, timezone_offset_hours=3):
        self.mt5_path = mt5_path
        self.tz_offset = timedelta(hours=timezone_offset_hours)
        self.connected = False

    def connect(self):
        global mt5, HAS_MT5_LIB
        mt5, HAS_MT5_LIB = get_mt5()
        if not HAS_MT5_LIB or mt5 is None:
            print("⚠️ [MT5Bridge] MetaTrader5 package not loaded natively or via bridge. Running in Simulation mode.")
            self.connected = True
            return True

        init_ok = False
        try:
            init_ok = mt5.initialize(path=self.mt5_path) if self.mt5_path else mt5.initialize()
        except Exception as e:
            print(f"⚠️ [MT5Bridge] MT5 initialize exception: {e}")

        if not init_ok:
            print(f"❌ [MT5Bridge] Failed to initialize MT5: {mt5.last_error()}")
            return False

        account_info = mt5.account_info()
        if account_info is None:
            print("❌ [MT5Bridge] Failed to fetch account info.")
            return False

        self.connected = True
        login = getattr(account_info, 'login', 'Unknown')
        company = getattr(account_info, 'company', 'Unknown')
        balance = getattr(account_info, 'balance', 0.0)
        equity = getattr(account_info, 'equity', 0.0)
        print(f"🟢 [MT5Bridge] Connected to MT5 Account #{login} ({company}) | Balance: ${balance:,.2f} | Equity: ${equity:,.2f}")
        return True

    def get_server_utc_time(self):
        if HAS_MT5_LIB and mt5:
            try:
                tick = mt5.symbol_info_tick("EURUSD")
                if tick and getattr(tick, 'time', 0) > 0:
                    server_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc)
                    utc_dt = server_dt - self.tz_offset
                    return utc_dt
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def fetch_m5_rates(self, symbol, count=300):
        if not HAS_MT5_LIB or mt5 is None:
            return None

        try:
            mt5.symbol_select(symbol, True)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
            if rates is None or len(rates) == 0:
                return None

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s') - self.tz_offset
            df.set_index('time', inplace=True)
            return df
        except Exception as e:
            print(f"⚠️ [MT5Bridge] Error fetching M5 rates for {symbol}: {e}")
            return None

    def fetch_all_universes_df(self, symbols_list, count=300):
        df_dict = {}
        for sym in symbols_list:
            df = self.fetch_m5_rates(sym, count=count)
            if df is not None:
                df_dict[sym] = df
        return df_dict

    def shutdown(self):
        if HAS_MT5_LIB and mt5:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self.connected = False
        print("🔴 [MT5Bridge] Disconnected from MT5.")
