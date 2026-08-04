"""
MT5 Bridge — Direct C-Extension shared memory connection to MT5 terminal with EET broker offset handling.
Safe cross-platform import guard for Windows & Linux Wine environments (via RPyC bridge).
"""

import os
import sys
import time
import socket
import threading
import subprocess
import pandas as pd
from datetime import datetime, timezone, timedelta

mt5 = None
HAS_MT5_LIB = False
rpyc_conn = None

# RPyC / MT5 shared connection is NOT thread-safe. All cross-thread MT5 access
# (equity sampler, auditor, main loop) must go through this lock.
MT5_LOCK = threading.RLock()

def locked_mt5_call(fn, *args, **kwargs):
    with MT5_LOCK:
        return fn(*args, **kwargs)

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
    global mt5, HAS_MT5_LIB, rpyc_conn
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
        import rpyc.core.protocol
        rpyc.core.protocol.DEFAULT_CONFIG['allow_pickle'] = True
        rpyc.core.protocol.DEFAULT_CONFIG['allow_all_attrs'] = True

        rpyc_conn = rpyc.connect('127.0.0.1', 18812, config={'allow_all_attrs': True, 'allow_pickle': True})
        mt5 = rpyc_conn.root.get_mt5()
        HAS_MT5_LIB = True
        print("🟢 [MT5Bridge] Connected to MT5 via Linux RPyC Bridge!")
        return mt5, True
    except ImportError:
        print("⚠️ [MT5Bridge] RPyC not installed — cannot connect to Wine MT5 server. Install with: pip install rpyc")
        mt5 = None
        HAS_MT5_LIB = False
        return None, False
    except ConnectionRefusedError:
        print("⚠️ [MT5Bridge] RPyC connection refused on port 18812 — Wine MT5 server not ready. Engine in sim mode.")
        mt5 = None
        HAS_MT5_LIB = False
        return None, False
    except Exception as e:
        print(f"⚠️ [MT5Bridge] RPyC bridge connection failed: {e}. Engine in sim mode.")
        mt5 = None
        HAS_MT5_LIB = False
        return None, False

mt5, HAS_MT5_LIB = get_mt5()
if not HAS_MT5_LIB:
    print("⚠️ [MT5Bridge] Module-level MT5 init failed — will retry in bridge.connect()")

class MT5Bridge:
    def __init__(self, mt5_path=None, timezone_offset_hours=3):
        self.mt5_path = mt5_path
        self.tz_offset = timedelta(hours=timezone_offset_hours)
        self.connected = False

    def connect(self):
        global mt5, HAS_MT5_LIB
        mt5, HAS_MT5_LIB = get_mt5()
        if not HAS_MT5_LIB or mt5 is None:
            print("⚠️ [MT5Bridge] MetaTrader5 not loaded. Running in Simulation mode.")
            self.connected = True
            return True

        # RPyC bridge: MT5 already initialized server-side — skip initialize()
        try:
            account_info = None
            for attempt in range(3):
                with MT5_LOCK:
                    account_info = mt5.account_info()
                if account_info is not None:
                    break
                time.sleep(0.5)

            if account_info is not None:
                self.connected = True
                login = getattr(account_info, 'login', 'Unknown')
                company = getattr(account_info, 'company', 'Unknown')
                balance = getattr(account_info, 'balance', 0.0)
                equity = getattr(account_info, 'equity', 0.0)
                print(f"🟢 [MT5Bridge] Connected to MT5 Account #{login} ({company}) | Balance: ${balance:,.2f} | Equity: ${equity:,.2f}")
                return True
            else:
                print("⚠️ [MT5Bridge] account_info() returned None after 3 retries — MT5 terminal may not be logged in.")
        except Exception as e:
            print(f"⚠️ [MT5Bridge] account_info() probe failed: {e}")

        # Native mode: call initialize() with path
        try:
            init_ok = mt5.initialize(path=self.mt5_path) if self.mt5_path else mt5.initialize()
        except Exception as e:
            print(f"⚠️ [MT5Bridge] MT5 initialize exception: {e}")
            init_ok = False

        if not init_ok:
            print(f"❌ [MT5Bridge] Failed to initialize MT5: {mt5.last_error()}")
            return False

        account_info = mt5.account_info()
        if account_info is None:
            print("❌ [MT5Bridge] Failed to fetch account info after initialize.")
            return False

        self.connected = True
        login = getattr(account_info, 'login', 'Unknown')
        company = getattr(account_info, 'company', 'Unknown')
        balance = getattr(account_info, 'balance', 0.0)
        equity = getattr(account_info, 'equity', 0.0)
        print(f"🟢 [MT5Bridge] Connected to MT5 Account #{login} ({company}) | Balance: ${balance:,.2f} | Equity: ${equity:,.2f}")
        return True

    def account_info(self):
        """Thread-safe account info fetch."""
        if not HAS_MT5_LIB or mt5 is None:
            return None
        try:
            with MT5_LOCK:
                return mt5.account_info()
        except Exception as e:
            print(f"⚠️ [MT5Bridge] Error fetching account info: {e}")
            return None

    def get_server_utc_time(self):
        if HAS_MT5_LIB and mt5:
            try:
                with MT5_LOCK:
                    tick = mt5.symbol_info_tick("EURUSD")
                if tick and getattr(tick, 'time', 0) > 0:
                    server_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc)
                    utc_dt = server_dt - self.tz_offset
                    return utc_dt
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def fetch_m5_rates(self, symbol, count=300, exclude_forming=False):
        if not HAS_MT5_LIB or mt5 is None:
            return None

        try:
            if rpyc_conn is not None and hasattr(rpyc_conn.root, 'fetch_m5_rates'):
                with MT5_LOCK:
                    rates = rpyc_conn.root.fetch_m5_rates(symbol, count)
            else:
                with MT5_LOCK:
                    mt5.symbol_select(symbol, True)
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)

            if rates is None or len(rates) == 0:
                return None

            df = pd.DataFrame(list(rates))
            df['time'] = pd.to_datetime(df['time'], unit='s') - self.tz_offset

            if exclude_forming and len(df) > 1:
                try:
                    last_bar_dt = pd.to_datetime(df['time'].iloc[-1]).tz_localize(None)
                    server_utc_dt = self.get_server_utc_time().replace(tzinfo=None)
                    if (server_utc_dt - last_bar_dt).total_seconds() < 300:
                        df = df.iloc[:-1]
                except Exception as ex:
                    print(f"⚠️ [MT5Bridge] exclude_forming check exception: {ex}")

            df.set_index('time', inplace=True)
            return df
        except Exception as e:
            print(f"⚠️ [MT5Bridge] Error fetching M5 rates for {symbol}: {e}")
            return None

    def fetch_ticks(self, symbols):
        """Batch-fetch latest ticks for a list of symbols (returns {sym: {bid, ask, last, time}})."""
        if not HAS_MT5_LIB or mt5 is None:
            return {}
        try:
            if rpyc_conn is not None and hasattr(rpyc_conn.root, 'fetch_ticks'):
                with MT5_LOCK:
                    return rpyc_conn.root.fetch_ticks(list(symbols))
            out = {}
            with MT5_LOCK:
                for sym in symbols:
                    t = mt5.symbol_info_tick(sym)
                    if t:
                        out[sym] = {
                            'bid': float(getattr(t, 'bid', 0.0)),
                            'ask': float(getattr(t, 'ask', 0.0)),
                            'last': float(getattr(t, 'last', 0.0)),
                            'time': int(getattr(t, 'time', 0)),
                        }
            return out
        except Exception as e:
            print(f"⚠️ [MT5Bridge] Error fetching ticks: {e}")
            return {}

    def fetch_tick_velocity(self, symbols, window_sec=1.0):
        if not HAS_MT5_LIB or mt5 is None:
            return 0.0
        try:
            if rpyc_conn is not None and hasattr(rpyc_conn.root, 'fetch_tick_velocity'):
                with MT5_LOCK:
                    return rpyc_conn.root.fetch_tick_velocity(list(symbols), window_sec)
            import time as _t
            def _sample():
                snap = {}
                with MT5_LOCK:
                    for sym in symbols:
                        t = mt5.symbol_info_tick(sym)
                        if t:
                            snap[sym] = int(getattr(t, 'time_msc', getattr(t, 'time', 0) * 1000))
                return snap
            a = _sample()
            _t.sleep(window_sec)
            b = _sample()
            fresh = 0
            for sym in symbols:
                if sym in b and sym in a and b[sym] > a[sym]:
                    fresh += 1
            return round(fresh / window_sec, 1)
        except Exception as e:
            print(f"⚠️ [MT5Bridge] Error fetching tick velocity: {e}")
            return 0.0

    def fetch_history_deals(self, from_time=0, days=30):
        """Fetch closed deals from MT5 (via RPyC bridge or native)."""
        if not HAS_MT5_LIB or mt5 is None:
            return []
        try:
            if rpyc_conn is not None and hasattr(rpyc_conn.root, 'fetch_history_deals'):
                with MT5_LOCK:
                    return rpyc_conn.root.fetch_history_deals(from_time, days)
            import time as _time
            end = int(_time.time())
            start = end - days * 86400
            deals = mt5.history_deals_get(start if from_time == 0 else from_time, end)
            if deals is None:
                return []
            return [
                {
                    'ticket': int(getattr(d, 'ticket', 0)),
                    'order': int(getattr(d, 'order', 0)),
                    'symbol': d.symbol,
                    'type': int(getattr(d, 'type', 0)),
                    'side': 'BUY' if getattr(d, 'type', 0) == 0 else 'SELL',
                    'entry': int(getattr(d, 'entry', 0)),
                    'position_id': int(getattr(d, 'position_id', 0)),
                    'volume': float(getattr(d, 'volume', 0.0)),
                    'price': float(getattr(d, 'price', 0.0)),
                    'profit': float(getattr(d, 'profit', 0.0)),
                    'fee': float(getattr(d, 'fee', 0.0)),
                    'commission': float(getattr(d, 'commission', 0.0)),
                    'swap': float(getattr(d, 'swap', 0.0)),
                    'time': int(getattr(d, 'time', 0)),
                    'comment': getattr(d, 'comment', ''),
                    'magic': int(getattr(d, 'magic', 0)),
                }
                for d in deals
            ]
        except Exception as e:
            print(f"⚠️ [MT5Bridge] Error fetching history deals: {e}")
            return []

    def fetch_all_universes_df(self, symbols_list, count=300, exclude_forming=False):
        df_dict = {}
        for sym in symbols_list:
            df = self.fetch_m5_rates(sym, count=count, exclude_forming=exclude_forming)
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
