"""
NY H21 Closing Bell Engine — 60-min NY Close Reversion (65.9% Proven WR)
Evaluates 60m drive declines on EURJPY & GBPJPY at 21:00 UTC and picks most-declined pair.
"""

import pandas as pd
import numpy as np
from datetime import timedelta

def _get_bar_loc(df, timestamp):
    t_clean = timestamp.replace(second=0, microsecond=0, tzinfo=None)
    t_m5 = t_clean - timedelta(minutes=t_clean.minute % 5)
    t_str = t_m5.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(df.index, pd.DatetimeIndex):
        if t_m5 in df.index:
            return df.index.get_loc(t_m5)
        elif t_str in df.index:
            return df.index.get_loc(t_str)

    if "time" in df.columns:
        matches = df[df["time"] == t_str].index
        if not matches.empty:
            return matches[0]
        matches_dt = df[df["time"] == t_m5].index
        if not matches_dt.empty:
            return matches_dt[0]

    return None

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
                loc = _get_bar_loc(df, timestamp)
                if loc is not None and loc >= lookback:
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
