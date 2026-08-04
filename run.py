"""
Proxima Alpha Engine — Single Master Production Entry Point for Live Execution
Connects MT5 Bridge, Execution Guard, Risk Manager, Strategy Evaluator, Position Tracker, Auto-Updater & Telemetry.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
    HAS_MT5_LIB = True
except ImportError:
    mt5 = None
    HAS_MT5_LIB = False

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import STRATEGY_SUITE, MT5_PATH, MT5_SERVER_TIMEZONE_OFFSET_HOURS, DAILY_DRAWDOWN_LIMIT_PCT, MAX_SPREAD_PIPS_DEFAULT
from engine.mt5_bridge import MT5Bridge
from engine.execution_guard import ExecutionGuard
from engine.risk_manager import RiskManager
from engine.evaluator import StrategyEvaluator
from engine.tracker import PositionTracker
from engine.auto_updater import AutoUpdater
from telemetry.server import start_telemetry_server

def main():
    print("=" * 115)
    print("PROXIMA ALPHA ENGINE — INITIALIZING LIVE INSTITUTIONAL SIDECAR EXECUTION...")
    print("=" * 115)

    # 1. Start Telemetry Web Server
    start_telemetry_server(port=8888)

    # 2. Start Git Push Auto-Updater Service
    repo_dir = str(Path(__file__).resolve().parent)
    updater = AutoUpdater(repo_dir=repo_dir, check_interval_sec=15)
    updater.start()

    # 3. Initialize High-Speed MT5 Bridge
    bridge = MT5Bridge(mt5_path=MT5_PATH, timezone_offset_hours=MT5_SERVER_TIMEZONE_OFFSET_HOURS)
    if not bridge.connect():
        print("❌ Could not connect to MT5. Exiting...")
        return

    # 4. Initialize Execution Guard & Risk Manager
    guard = ExecutionGuard(max_spread_pips=MAX_SPREAD_PIPS_DEFAULT, max_retries=3, retry_delay_ms=15)
    risk_mgr = RiskManager(daily_drawdown_limit_pct=DAILY_DRAWDOWN_LIMIT_PCT)
    tracker = PositionTracker(execution_guard=guard)
    evaluator = StrategyEvaluator(config_suite=STRATEGY_SUITE)

    all_symbols = set()
    for strat in STRATEGY_SUITE.values():
        all_symbols.update(strat["universe"])

    print(f"🟢 [Engine] Monitoring {len(all_symbols)} Symbols across 6 Active Strategies...")
    print("=" * 115)

    last_eval_time = None

    try:
        while True:
            utc_now = bridge.get_server_utc_time()

            if last_eval_time is None or (utc_now.minute % 5 == 0 and utc_now.minute != last_eval_time.minute):
                last_eval_time = utc_now
                print(f"\n⏰ [M5 Bar Boundary] {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')} — Evaluating Strategy Signals...")

                df_dict = bridge.fetch_all_universes_df(list(all_symbols), count=300)

                if HAS_MT5_LIB and mt5:
                    acc_info = mt5.account_info()
                    if acc_info:
                        risk_mgr.update_daily_baseline(acc_info.equity)
                        shield_ok, shield_reason = risk_mgr.check_daily_drawdown_shield(acc_info.equity)
                        if not shield_ok:
                            print(f"🛑 [RiskShield] {shield_reason}. Skipping new entries.")
                            time.sleep(5)
                            continue

                tracker.update_bar_hold_timers(utc_now.strftime("%Y-%m-%d %H:%M:%S"))

                signals = evaluator.evaluate_all(df_dict, utc_now)
                if signals:
                    print(f"🔥 [Signals] Generated {len(signals)} Active Signals!")
                    for sig in signals:
                        strat_name = sig["strategy"]
                        pair       = sig["pair"]
                        side       = sig["side"]
                        lot        = sig["lot"]
                        cfg        = next(c for c in STRATEGY_SUITE.values() if c["name"] == strat_name)

                        ticket, status = guard.execute_market_order(
                            symbol=pair,
                            side=side,
                            lot=lot,
                            magic=cfg["magic"],
                            comment=f"ProximaAlpha_{strat_name}"
                        )

                        if ticket:
                            tracker.add_position(
                                ticket=ticket,
                                strategy=strat_name,
                                pair=pair,
                                side=side,
                                lot=lot,
                                hold_bars=sig["hold_bars"],
                                entry_time_str=utc_now.strftime("%Y-%m-%d %H:%M:%S")
                            )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Engine stopped by user.")
    finally:
        updater.stop()
        bridge.shutdown()

if __name__ == "__main__":
    main()
