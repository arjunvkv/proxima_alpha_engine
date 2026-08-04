"""
Institutional Execution Guard — Zero-Failure Order Placement & Exit Retry Engine
Safe cross-platform import guard for Windows & Linux environments (via RPyC bridge).
"""

import time
import engine.mt5_bridge as bridge_mod
from engine.mt5_bridge import mt5, HAS_MT5_LIB

class ExecutionGuard:
    def __init__(self, max_spread_pips=15.0, max_retries=3, retry_delay_ms=15):
        self.max_spread_pips = max_spread_pips
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms

    def _pip_size(self, symbol):
        return 0.01 if "JPY" in symbol else 0.0001

    def resolve_filling_mode(self, symbol):
        if not HAS_MT5_LIB or mt5 is None:
            return 0
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return mt5.ORDER_FILLING_IOC

        filling_mode = sym_info.filling_mode
        if filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        elif filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        else:
            return mt5.ORDER_FILLING_RETURN

    def check_spread_gate(self, symbol):
        if not HAS_MT5_LIB or mt5 is None:
            return True, "SPREAD_OK"
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return False, "Symbol info unavailable"

        pip_sz = self._pip_size(symbol)
        spread_pips = (sym_info.ask - sym_info.bid) / pip_sz

        if spread_pips > self.max_spread_pips:
            return False, f"Spread {round(spread_pips, 1)}p > Max {self.max_spread_pips}p"
        return True, "SPREAD_OK"

    def _do_order_send(self, request):
        conn = getattr(bridge_mod, 'rpyc_conn', None)
        if conn is not None and hasattr(conn.root, 'order_send'):
            return conn.root.order_send(request)
        else:
            res = mt5.order_send(request)
            if res is None:
                return None
            return {
                'retcode': getattr(res, 'retcode', 0),
                'order': getattr(res, 'order', 0),
                'price': getattr(res, 'price', 0.0),
                'comment': getattr(res, 'comment', '')
            }

    def execute_market_order(self, symbol, side, lot, magic, comment=""):
        if not HAS_MT5_LIB or mt5 is None:
            print(f"🟢 [SimMode] Simulated Order: {symbol} {side} {lot}L")
            return 99999, "SIM_SUCCESS"

        spread_ok, reason = self.check_spread_gate(symbol)
        if not spread_ok:
            print(f"🛑 [ExecutionGuard] Order rejected for {symbol}: {reason}")
            return None, reason

        filling_mode = self.resolve_filling_mode(symbol)
        order_type = mt5.ORDER_TYPE_BUY if side.upper() == "BUY" else mt5.ORDER_TYPE_SELL

        for attempt in range(1, self.max_retries + 1):
            sym_info = mt5.symbol_info(symbol)
            if sym_info is None:
                mt5.symbol_select(symbol, True)
                sym_info = mt5.symbol_info(symbol)

            price = sym_info.ask if order_type == mt5.ORDER_TYPE_BUY else sym_info.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(lot),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": int(magic),
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }

            res = self._do_order_send(request)
            if res is not None and res.get('retcode') == 10009:  # 10009 == TRADE_RETCODE_DONE
                ticket = res.get('order', 0)
                exec_price = res.get('price', price)
                print(f"🟢 [ExecutionGuard] Order Executed! Ticket #{ticket} | {symbol} {side} {lot}L @ {exec_price}")
                return ticket, "SUCCESS"

            err_code = res.get('retcode') if res else "UNKNOWN"
            err_msg = res.get('comment') if res else ""
            print(f"⚠️ [ExecutionGuard] Attempt {attempt}/{self.max_retries} failed for {symbol}: Code {err_code} ({err_msg}). Retrying in {self.retry_delay_ms}ms...")
            time.sleep(self.retry_delay_ms / 1000.0)

        return None, f"Failed after {self.max_retries} retries"

    def hard_exit_position(self, ticket, symbol, side, lot):
        if not HAS_MT5_LIB or mt5 is None:
            print(f"🟢 [SimMode] Simulated Hard Exit Ticket #{ticket}")
            return True

        filling_mode = self.resolve_filling_mode(symbol)
        close_type = mt5.ORDER_TYPE_SELL if side.upper() == "BUY" else mt5.ORDER_TYPE_BUY

        for attempt in range(1, 5):
            positions = mt5.positions_get(ticket=int(ticket))
            if not positions:
                print(f"🟢 [ExecutionGuard] Position #{ticket} confirmed 100% closed!")
                return True

            sym_info = mt5.symbol_info(symbol)
            price = sym_info.bid if close_type == mt5.ORDER_TYPE_SELL else sym_info.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(lot),
                "type": close_type,
                "position": int(ticket),
                "price": price,
                "deviation": 20,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }

            self._do_order_send(request)
            time.sleep(0.1)

            positions_after = mt5.positions_get(ticket=int(ticket))
            if not positions_after:
                print(f"🟢 [ExecutionGuard] Exit Executed & Confirmed! Ticket #{ticket} closed @ {price}")
                return True

        return False
