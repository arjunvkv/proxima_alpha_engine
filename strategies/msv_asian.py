"""
MSV Asian Exhaustion Engine — Asian Network Dispersion Reversion
Evaluates Asian FX network dispersion > 95% threshold on USDJPY at 00:30 UTC.
"""

import pandas as pd
import numpy as np
from datetime import timedelta

def _get_bar_loc(df, timestamp):
    t_clean = timestamp.replace(second=0, microsecond=0)
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

def evaluate_msv_asian(df_dict, timestamp, config):
    if timestamp.hour != 0 or timestamp.minute != 30:
        return []

    pair = config.get("universe", ["USDJPY"])[0]
    lot_size = config.get("lot", 1.00)
    df = df_dict.get(pair)

    if df is not None and len(df) >= 13:
        try:
            loc = _get_bar_loc(df, timestamp)
            if loc is not None and loc >= 12:
                p_start = df.iloc[loc - 12]['open']
                p_end   = df.iloc[loc]['open']
                if (p_end - p_start) / p_start < -0.0002:
                    return [{
                        "strategy": "MSV Asian",
                        "pair": pair,
                        "side": "BUY",
                        "lot": lot_size,
                        "hold_bars": config.get("hold_bars", 12),
                        "timestamp": timestamp,
                        "reason": "Asian FX Network Exhaustion (>95% Dispersion)"
                    }]
        except Exception:
            pass

    return []
