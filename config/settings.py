"""
Proxima Alpha Engine — Global Configuration & Risk Rules
Defines global settings, MT5 terminal paths, risk shield thresholds, and all 6 strategy suite specifications.
"""

from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

STATE_FILE = DATA_DIR / "state.json"

# MT5 Terminal Settings
MT5_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
MT5_SERVER_TIMEZONE_OFFSET_HOURS = 3  # EET (UTC+3 summer offset)

# Risk & Prop Firm Shield Guard
DAILY_DRAWDOWN_LIMIT_PCT = 4.5         # Hard circuit breaker at 4.5% (below FTMO 5% limit)
MAX_SPREAD_PIPS_DEFAULT = 15.0         # 15 pip max spread entry gate
MAX_RETRY_COUNT = 3                     # Execution guard backoff retries
RETRY_DELAY_MS = 15                    # 15ms retry backoff delay

# 6 Core Portfolio Strategies & Fixed Lot Sizing Specs (Auto-Updater 15s Verified)
STRATEGY_SUITE = {
    "tokyo_h0": {
        "name": "Tokyo H0",
        "lot": 1.00,
        "magic": 202630,
        "hold_bars": 12,                # 60m hold (12 M5 bars)
        "lookback_bars": 6,             # 30m lookback
        "sl_pips": 50.0,                # Emergency wide broker SL
        "tp_pips": 60.0,                # Emergency wide broker TP
        "top_n": 5,
        "universe": [
            "EURJPY", "GBPJPY", "USDJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY",
            "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
            "EURAUD", "EURGBP", "EURCAD", "GBPAUD", "GBPCAD"
        ],
        "anchor_pair": "EURUSD",
        "proven_wr": 95.3
    },
    "ultra_monster": {
        "name": "Ultra Monster",
        "lot": 1.20,
        "magic": 202600,
        "hold_bars": 3,                 # 15m hold (3 M5 bars)
        "lookback_bars": 12,            # 60m range lookback
        "min_range_pips": 6.0,          # 6.0 pip minimum range gate
        "sl_pips": 40.0,                # Emergency wide broker SL
        "tp_pips": 50.0,                # Emergency wide broker TP
        "triggers": [0, 30],            # :00 & :30 minute half-hours
        "universe": [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
            "EURJPY", "GBPJPY", "EURAUD"
        ],
        "anchor_pair": "GBPUSD",
        "proven_wr": 76.0
    },
    "cppf_z": {
        "name": "CPPF Z",
        "lot": 1.40,
        "magic": 202650,
        "hold_bars": 18,                # 90m hold (18 M5 bars)
        "rolling_window": 200,          # 200-bar rolling z-score
        "z_threshold": -6.0,            # 6-Sigma dislocation shock
        "sl_pips": 60.0,                # Emergency wide broker SL
        "tp_pips": 90.0,                # Emergency wide broker TP
        "direction": "LONG",
        "universe": ["EURAUD", "GBPAUD"],
        "anchor_pair": "EURAUD",
        "proven_wr": 85.0
    },
    "msv_asian": {
        "name": "MSV Asian",
        "lot": 1.00,
        "magic": 202640,
        "hold_bars": 12,                # 60m hold (12 M5 bars)
        "dispersion_thresh": 0.95,      # 95th percentile network dispersion
        "sl_pips": 45.0,                # Emergency wide broker SL
        "tp_pips": 60.0,                # Emergency wide broker TP
        "universe": ["USDJPY"],
        "anchor_pair": "USDJPY",
        "proven_wr": 88.0
    },
    "ny_h21": {
        "name": "NY H21",
        "lot": 1.50,
        "magic": 202660,
        "hold_bars": 12,                # 60m hold (12 M5 bars)
        "lookback_bars": 12,            # 60m drive lookback
        "sl_pips": 50.0,                # Emergency wide broker SL
        "tp_pips": 70.0,                # Emergency wide broker TP
        "universe": ["EURJPY", "GBPJPY"],
        "anchor_pair": "EURJPY",
        "proven_wr": 65.9
    },
    "cpmc_z": {
        "name": "CPMC Z",
        "lot": 1.40,
        "magic": 202670,
        "hold_bars": 9,                 # 45m hold (9 M5 bars)
        "rolling_window": 200,          # 200-bar rolling z-score
        "z_threshold": 3.5,             # +3.5 Sigma momentum spike
        "sl_pips": 50.0,                # Emergency wide broker SL
        "tp_pips": 70.0,                # Emergency wide broker TP
        "universe": ["GBPAUD", "GBPNZD"],
        "anchor_pair": "GBPAUD",
        "proven_wr": 78.0
    }
}
