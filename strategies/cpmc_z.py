"""
CPMC Z Momentum Engine — +3.5 Sigma Momentum Continuation Spike
Evaluates rolling 200-bar Z-scores on 15m returns for GBPAUD & GBPNZD.
"""

import pandas as pd
import numpy as np

def evaluate_cpmc_z(df_dict, timestamp, config):
    window = config.get("rolling_window", 200)
    z_thresh = config.get("z_threshold", 3.5)
    universe = config.get("universe", ["GBPAUD", "GBPNZD"])
    lot_size = config.get("lot", 1.40)

    signals = []

    for pair in universe:
        df = df_dict.get(pair)
        if df is not None and len(df) >= window + 3:
            try:
                loc = df.index.get_loc(timestamp)
                if loc >= window + 3:
                    sub = df.iloc[loc - window - 3:loc + 1]
                    ret3 = (sub['close'] - sub['open'].shift(2)) / sub['open'].shift(2)
                    m200 = ret3.iloc[-window:].mean()
                    s200 = ret3.iloc[-window:].std()
                    zscore = (ret3.iloc[-1] - m200) / (s200 + 1e-9)

                    if zscore >= z_thresh:
                        signals.append({
                            "strategy": "CPMC Z",
                            "pair": pair,
                            "side": "BUY",
                            "lot": lot_size,
                            "hold_bars": config.get("hold_bars", 9),
                            "timestamp": timestamp,
                            "reason": f"Momentum Spike Continuation (Z={round(zscore,2)})"
                        })
            except Exception:
                continue

    return signals
