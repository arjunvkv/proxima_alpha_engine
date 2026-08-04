"""
MT5 RPyC Server — Runs inside Wine Python to bridge native MT5 C-Extension to Linux Python.
Auto-initializes MT5 on startup and exposes clean data structures over RPyC socket.
"""
import sys
import rpyc
import rpyc.core.protocol

# Globally enable pickling in RPyC protocol
rpyc.core.protocol.DEFAULT_CONFIG['allow_pickle'] = True
rpyc.core.protocol.DEFAULT_CONFIG['allow_all_attrs'] = True

import MetaTrader5 as mt5
from rpyc.utils.server import ThreadedServer

# Auto-init MT5 when server starts (connects to already-running FTMO terminal)
_init_ok = mt5.initialize()
if _init_ok:
    acc = mt5.account_info()
    login = acc.login if acc else "unknown"
    balance = acc.balance if acc else 0
    print(f"[MT5 RPyC Server] MT5 initialized! Account #{login} | Balance: ${balance:,.2f}")
else:
    print(f"[MT5 RPyC Server] MT5 init failed: {mt5.last_error()}")

class MT5Service(rpyc.Service):
    def on_connect(self, conn):
        pass
    def on_disconnect(self, conn):
        pass
    def exposed_get_mt5(self):
        return mt5
    def exposed_is_initialized(self):
        return _init_ok

    def exposed_fetch_m5_rates(self, symbol, count=300):
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
        if rates is None or len(rates) == 0:
            return None
        # Convert numpy structured array to clean list of dicts for instant RPyC transfer
        return [
            {
                'time': int(r[0]),
                'open': float(r[1]),
                'high': float(r[2]),
                'low': float(r[3]),
                'close': float(r[4]),
                'tick_volume': int(r[5]),
                'spread': int(r[6]),
                'real_volume': int(r[7])
            }
            for r in rates
        ]

    def exposed_order_send(self, request_dict):
        # Unpack RPyC netref dict into native local Wine Python dict
        native_req = {k: v for k, v in request_dict.items()}
        res = mt5.order_send(native_req)
        if res is None:
            print(f"[MT5 RPyC Server] order_send returned None. Last error: {mt5.last_error()}")
            return None
        # Convert OrderResult namedtuple to dict for clean RPyC return
        return {
            'retcode': res.retcode,
            'deal': res.deal,
            'order': res.order,
            'volume': res.volume,
            'price': res.price,
            'bid': res.bid,
            'ask': res.ask,
            'comment': res.comment,
            'request_id': res.request_id,
            'retcode_external': res.retcode_external
        }

if __name__ == '__main__':
    print("[MT5 RPyC Server] Starting bridge server on port 18812...")
    server = ThreadedServer(
        MT5Service,
        port=18812,
        protocol_config={
            'allow_all_attrs': True,
            'allow_public_attrs': True,
            'allow_getattr': True,
            'allow_setattr': True,
            'allow_pickle': True
        }
    )
    server.start()
