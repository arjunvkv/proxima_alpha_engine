"""
MT5 RPyC Server — Runs inside Wine Python to bridge native MT5 C-Extension to Linux Python.
"""
import sys
import rpyc
import MetaTrader5 as mt5
from rpyc.utils.server import ThreadedServer

class MT5Service(rpyc.Service):
    def on_connect(self, conn):
        pass
    def on_disconnect(self, conn):
        pass
    def exposed_get_mt5(self):
        return mt5

if __name__ == '__main__':
    print("🟢 [MT5 RPyC Server] Starting MT5 bridge server on port 18812...")
    server = ThreadedServer(
        MT5Service,
        port=18812,
        protocol_config={'allow_all_attrs': True, 'allow_public_attrs': True, 'allow_getattr': True, 'allow_setattr': True}
    )
    server.start()
