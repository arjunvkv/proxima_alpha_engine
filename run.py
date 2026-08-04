"""
Proxima Alpha Engine — Single Master Production Entry Point for Live Execution
Connects MT5 Bridge, Execution Guard, Risk Manager, Strategy Evaluator, Position Tracker, Auto-Updater & Telemetry.
SingleInstanceLock guaranteed to eliminate duplicate instances.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from engine.mt5_bridge import mt5, HAS_MT5_LIB, MT5Bridge

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import STRATEGY_SUITE, MT5_PATH, MT5_SERVER_TIMEZONE_OFFSET_HOURS, DAILY_DRAWDOWN_LIMIT_PCT, MAX_SPREAD_PIPS_DEFAULT
from engine.lock import SingleInstanceLock
from engine.mt5_bridge import MT5Bridge
from engine.execution_guard import ExecutionGuard
from engine.risk_manager import RiskManager
from engine.evaluator import StrategyEvaluator
from engine.tracker import PositionTracker
from engine.auto_updater import AutoUpdater
from telemetry.server import start_telemetry_server, update_telemetry, _telemetry_state, push_engine_log

class _TeeLogger:
    """Mirrors all engine print() output to the Gaming UI console panel."""
    def __init__(self, original):
        self._orig = original
    def write(self, msg):
        self._orig.write(msg)
        self._orig.flush()
        if msg.strip():
            push_engine_log(msg)
    def flush(self):
        self._orig.flush()
    def fileno(self):
        return self._orig.fileno()

def main():
    # 0. Acquire Single Instance Lock (Zero Duplicate Instances)
    lock = SingleInstanceLock()
    lock.acquire()

    print("=" * 115)
    print("PROXIMA ALPHA ENGINE — INITIALIZING LIVE INSTITUTIONAL SIDECAR EXECUTION...")
    print("=" * 115)

    # Mirror all engine stdout to the Gaming UI log console
    sys.stdout = _TeeLogger(sys.__stdout__)

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
        lock.release()
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
    update_telemetry("engine_status", "ONLINE")
    update_telemetry("connected", HAS_MT5_LIB)
    print("=" * 115)

    last_eval_time = None

    try:
        while True:
            utc_now = bridge.get_server_utc_time()

            if last_eval_time is None or (utc_now.minute % 5 == 0 and utc_now.minute != last_eval_time.minute):
                last_eval_time = utc_now
                print(f"\n⏰ [M5 Bar Boundary] {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')} — Evaluating Strategy Signals...")

                df_dict = bridge.fetch_all_universes_df(list(all_symbols), count=300)

                # Push live account state to Gaming UI telemetry
                update_telemetry("mt5_latency_ms", 15)

                if HAS_MT5_LIB and mt5:
                    acc_info = mt5.account_info()
                    if acc_info:
                        risk_mgr.update_daily_baseline(acc_info.equity)
                        update_telemetry("account_equity", acc_info.equity)
                        update_telemetry("account_balance", acc_info.balance)
                        if risk_mgr.initial_day_equity and risk_mgr.initial_day_equity > 0:
                            dd_pct = (risk_mgr.initial_day_equity - acc_info.equity) / risk_mgr.initial_day_equity * 100
                            update_telemetry("daily_pnl", round(acc_info.equity - risk_mgr.initial_day_equity, 2))
                            update_telemetry("daily_dd_pct", round(dd_pct, 3))
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
                            # Update active positions in telemetry
                            cur_positions = list(tracker.active_positions.values())
                            update_telemetry("active_positions", cur_positions)
                            sigs_today = list(_telemetry_state["signals_today"])
                            sigs_today.append({"strategy": strat_name, "pair": pair, "side": side, "lot": lot, "time": utc_now.strftime("%H:%M")})
                            update_telemetry("signals_today", sigs_today[-50:])
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
        lock.release()

if __name__ == "__main__":
    main()
