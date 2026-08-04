"""
MT5 Bridge — Direct C-Extension shared memory connection to MT5 terminal with EET broker offset handling.
Safe cross-platform import guard for Windows & Linux Wine environments.
"""

import time
import pandas as pd
from datetime import datetime, timezone, timedelta

try:
    import MetaTrader5 as mt5
    HAS_MT5_LIB = True
except ImportError:
    mt5 = None
    HAS_MT5_LIB = False

class MT5Bridge:
    def __init__(self, mt5_path=None, timezone_offset_hours=3):
        self.mt5_path = mt5_path
        self.tz_offset = timedelta(hours=timezone_offset_hours)
        self.connected = False

    def connect(self):
        if not HAS_MT5_LIB or mt5 is None:
            print("⚠️ [MT5Bridge] MetaTrader5 package not loaded natively. Running in Simulation / Replay mode.")
            self.connected = True
            return True

        if not mt5.initialize(path=self.mt5_path) if self.mt5_path else not mt5.initialize():
            print(f"❌ [MT5Bridge] Failed to initialize MT5: {mt5.last_error()}")
            return False

        account_info = mt5.account_info()
        if account_info is None:
            print("❌ [MT5Bridge] Failed to fetch account info.")
            return False

        self.connected = True
        print(f"🟢 [MT5Bridge] Connected to MT5 Account #{account_info.login} ({account_info.company}) | Balance: ${account_info.balance:,.2f} | Equity: ${account_info.equity:,.2f}")
        return True

    def get_server_utc_time(self):
        if HAS_MT5_LIB and mt5:
            tick = mt5.symbol_info_tick("EURUSD")
            if tick and tick.time > 0:
                server_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc)
                utc_dt = server_dt - self.tz_offset
                return utc_dt
        return datetime.now(timezone.utc)

    def fetch_m5_rates(self, symbol, count=300):
        if not HAS_MT5_LIB or mt5 is None:
            return None

        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s') - self.tz_offset
        df.set_index('time', inplace=True)
        return df

    def fetch_all_universes_df(self, symbols_list, count=300):
        df_dict = {}
        for sym in symbols_list:
            df = self.fetch_m5_rates(sym, count=count)
            if df is not None:
                df_dict[sym] = df
        return df_dict

    def shutdown(self):
        if HAS_MT5_LIB and mt5:
            mt5.shutdown()
        self.connected = False
        print("🔴 [MT5Bridge] Disconnected from MT5.")
