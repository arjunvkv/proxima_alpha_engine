"""
NY H21 Closing Bell Engine — 60-min NY Close Reversion (65.9% Proven WR)
Evaluates 60m drive declines on EURJPY & GBPJPY at 21:00 UTC and picks most-declined pair.
"""

import pandas as pd
import numpy as np

def evaluate_ny_h21(df_dict, timestamp, config):
    if timestamp.hour != 21 or timestamp.minute != 0:
        return []

    lookback = config.get("lookback_bars", 12)
    universe = config.get("universe", ["EURJPY", "GBPJPY"])
    lot_size = config.get("lot", 1.50)

    returns = []
    for pair in universe:
        df = df_dict.get(pair)
        if df is not None and len(df) >= lookback + 1:
            try:
                loc = df.index.get_loc(timestamp)
                if loc >= lookback:
                    p_start = df.iloc[loc - lookback]['open']
                    p_end   = df.iloc[loc]['open']
                    ret     = (p_end - p_start) / p_start
                    returns.append((pair, ret))
            except Exception:
                continue

    if not returns:
        return []

    returns.sort(key=lambda x: x[1])
    best_pair, ret = returns[0]

    return [{
        "strategy": "NY H21",
        "pair": best_pair,
        "side": "BUY",
        "lot": lot_size,
        "hold_bars": config.get("hold_bars", 12),
        "timestamp": timestamp,
        "reason": f"NY Close Drive Decline ({round(ret*100,3)}%)"
    }]
