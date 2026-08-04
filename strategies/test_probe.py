"""
Temporary Test Probe Strategy — Fires 1 instant test order (0.01 lot) on EURUSD to verify live execution & exit.
"""
_fired = False

def evaluate_test_probe(df_dict, timestamp, cfg):
    global _fired
    if _fired:
        return []

    if "EURUSD" not in df_dict:
        return []

    _fired = True
    print("🧪 [TestProbe] FIRING TEST SIGNAL: 0.01 Lot BUY EURUSD (Hold 1 bar)")
    return [{
        "strategy": "Test Probe",
        "pair": "EURUSD",
        "side": "BUY",
        "lot": 0.01,
        "hold_bars": 1,
        "reason": "LIVE_EXECUTION_TEST"
    }]
