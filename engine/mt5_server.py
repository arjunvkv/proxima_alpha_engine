"""
MT5 RPyC Server — Runs inside Wine Python to bridge native MT5 C-Extension to Linux Python.
Auto-initializes MT5 on startup so clients just call account_info, order_send, etc.
"""
import sys
import rpyc
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
