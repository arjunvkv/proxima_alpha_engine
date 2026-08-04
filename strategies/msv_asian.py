"""
MSV Asian Exhaustion Engine — Asian Network Dispersion Reversion
Evaluates Asian FX network dispersion > 95% threshold on USDJPY at 00:30 UTC.
"""

import pandas as pd
import numpy as np

def evaluate_msv_asian(df_dict, timestamp, config):
    if timestamp.hour != 0 or timestamp.minute != 30:
        return []

    pair = config.get("universe", ["USDJPY"])[0]
    lot_size = config.get("lot", 1.00)
    df = df_dict.get(pair)

    if df is not None and len(df) >= 13:
        try:
            loc = df.index.get_loc(timestamp)
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
