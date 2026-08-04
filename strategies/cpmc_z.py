"""
CPMC Z Momentum Engine — +3.5 Sigma Momentum Continuation Spike
Evaluates rolling 200-bar Z-scores on 15m returns for GBPAUD & GBPNZD on completed M5 candle close.
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

def evaluate_cpmc_z(df_dict, timestamp, config):
    window = config.get("rolling_window", 200)
    z_thresh = config.get("z_threshold", 3.5)
    universe = config.get("universe", ["GBPAUD", "GBPNZD"])
    lot_size = config.get("lot", 1.40)

    signals = []

    for pair in universe:
        df = df_dict.get(pair)
        if df is not None and len(df) >= window + 4:
            try:
                loc = _get_bar_loc(df, timestamp)
                if loc is not None and loc >= window + 3:
                    # Evaluate up to loc (loc - 1 completed bar)
                    sub = df.iloc[loc - window - 3:loc]
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
