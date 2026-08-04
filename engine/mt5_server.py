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

    def exposed_fetch_history_deals(self, from_time=0, days=30):
        """Return closed deals for the last N days as clean list of dicts (zero-pickle RPyC transfer)."""
        import time as _time
        end = int(_time.time())
        start = end - days * 86400
        deals = mt5.history_deals_get(start if from_time == 0 else from_time, end)
        if deals is None or len(deals) == 0:
            return []
        return [
            {
            'ticket': int(d.ticket),
            'order': int(d.order),
            'symbol': d.symbol,
            'type': int(d.type),
            'side': 'BUY' if d.type == 0 else 'SELL',
            'entry': int(d.entry),
            'position_id': int(d.position_id),
            'volume': float(d.volume),
                'price': float(d.price),
                'profit': float(d.profit),
                'fee': float(d.fee),
                'commission': float(d.commission),
                'swap': float(d.swap),
                'time': int(d.time),
                'comment': d.comment,
                'magic': int(d.magic),
            }
            for d in deals
        ]

    def exposed_fetch_history_orders(self, days=30):
        """Return closed orders (entries + exits) for the last N days as clean dicts."""
        import time as _time
        end = int(_time.time())
        start = end - days * 86400
        orders = mt5.history_orders_get(start, end)
        if orders is None or len(orders) == 0:
            return []
        return [
            {
                'ticket': int(o.ticket),
                'symbol': o.symbol,
                'type': int(o.type),
                'state': int(o.state),
                'volume': float(o.volume),
                'price': float(o.price),
                'sl': float(o.sl) if o.sl else 0.0,
                'tp': float(o.tp) if o.tp else 0.0,
                'time_setup': int(o.time_setup),
                'time_done': int(o.time_done),
                'magic': int(o.magic),
                'comment': o.comment,
            }
            for o in orders
        ]

    def exposed_fetch_ticks(self, symbols):
        """Batch-fetch latest bid/ask/time for many symbols in one RPyC round-trip."""
        out = {}
        for sym in symbols:
            mt5.symbol_select(sym, True)
            t = mt5.symbol_info_tick(sym)
            if t:
                out[sym] = {
                    'bid': float(getattr(t, 'bid', 0.0)),
                    'ask': float(getattr(t, 'ask', 0.0)),
                    'last': float(getattr(t, 'last', 0.0)),
                    'time': int(getattr(t, 'time', 0)),
                }
        return out

    def exposed_fetch_tick_velocity(self, symbols, window_sec=1.0):
        """Count how many symbols received fresh ticks during a live window.

        Uses time_msc (ms-granularity) when available for accuracy; falls back to
        whole-second tick time. Returns fresh symbols per second.
        """
        import time as _time
        def _sample():
            snap = {}
            for sym in symbols:
                t = mt5.symbol_info_tick(sym)
                if t:
                    snap[sym] = int(getattr(t, 'time_msc', getattr(t, 'time', 0) * 1000))
            return snap
        a = _sample()
        _time.sleep(window_sec)
        b = _sample()
        fresh = 0
        for sym in symbols:
            if sym in b and sym in a and b[sym] > a[sym]:
                fresh += 1
        return round(fresh / window_sec, 1)

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
