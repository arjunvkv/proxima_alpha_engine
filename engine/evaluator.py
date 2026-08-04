"""
Strategy Evaluator — Microsecond strategy evaluation engine with circular ring buffer memory management.
"""

from strategies.tokyo_h0 import evaluate_tokyo_h0
from strategies.ultra_monster import evaluate_ultra_monster
from strategies.cppf_z import evaluate_cppf_z
from strategies.msv_asian import evaluate_msv_asian
from strategies.ny_h21 import evaluate_ny_h21
from strategies.cpmc_z import evaluate_cpmc_z
from strategies.test_probe import evaluate_test_probe

class StrategyEvaluator:
    def __init__(self, config_suite):
        self.suite = config_suite
        self.evaluators = {
            "test_probe": evaluate_test_probe,
            "tokyo_h0": evaluate_tokyo_h0,
            "ultra_monster": evaluate_ultra_monster,
            "cppf_z": evaluate_cppf_z,
            "msv_asian": evaluate_msv_asian,
            "ny_h21": evaluate_ny_h21,
            "cpmc_z": evaluate_cpmc_z
        }

    def evaluate_all(self, df_dict, timestamp):
        """
        Evaluates all 6 active strategies in microsecond time.
        """
        all_signals = []

        for strat_key, eval_fn in self.evaluators.items():
            cfg = self.suite.get(strat_key)
            if cfg:
                try:
                    signals = eval_fn(df_dict, timestamp, cfg)
                    if signals:
                        all_signals.extend(signals)
                except Exception as e:
                    print(f"⚠️ [Evaluator] Error in {strat_key}: {e}")

        return all_signals
