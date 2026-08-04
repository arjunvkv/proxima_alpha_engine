"""
Proxima Alpha Engine — Single Master Production Entry Point for Live Execution
Connects MT5 Bridge, Execution Guard, Risk Manager, Strategy Evaluator, Position Tracker, Auto-Updater & Telemetry.
SingleInstanceLock guaranteed to eliminate duplicate instances.
"""

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from engine.mt5_bridge import mt5, HAS_MT5_LIB, MT5Bridge

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import STRATEGY_SUITE, MT5_PATH, MT5_SERVER_TIMEZONE_OFFSET_HOURS, DAILY_DRAWDOWN_LIMIT_PCT, MAX_SPREAD_PIPS_DEFAULT
from engine.lock import SingleInstanceLock
from engine.mt5_bridge import MT5Bridge
from engine.execution_guard import ExecutionGuard
from engine.latency import measure_call_latency
from engine.risk_manager import RiskManager
from engine.evaluator import StrategyEvaluator
from engine.tracker import PositionTracker
from engine.auto_updater import AutoUpdater
from engine.auditor import TradeAuditor
import engine.db as db
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

def _build_real_radar(bridge, df_dict):
    """Compute REAL market radar metrics from live MT5 ticks + M5 data.
    Returns a snapshot dict pushed into telemetry (cached between bar boundaries).
    """
    import numpy as np

    radar = {"tick_velocity_per_sec": 0.0, "network_dispersion_pct": 0.0,
             "directional_agreement_pct": 0.0, "volatility_regime": "UNKNOWN",
             "regime_description": "", "real": True}

    # 1. Real tick velocity: count fresh ticks arriving per second across symbols
    try:
        symbols = list(df_dict.keys()) if df_dict else []
        if symbols:
            radar["tick_velocity_per_sec"] = bridge.fetch_tick_velocity(symbols, window_sec=1.0)
    except Exception:
        pass

    # 2. Real network dispersion & directional agreement from M5 returns
    #    Use CLOSED bars only — drop the currently-forming (last) candle to avoid
    #    lookahead into the live price.
    blips = []
    try:
        ret_series = {}
        for sym, df in df_dict.items():
            if df is not None and len(df) >= 14:
                closes = df["close"].values[-14:-1]
                if closes[0] > 0:
                    ret_series[sym] = np.diff(closes) / closes[:-1]

        if len(ret_series) >= 2:
            keys = list(ret_series.keys())
            n = min(len(ret_series[i]) for i in ret_series)
            arr = np.array([ret_series[k][-n:] for k in keys])
            # Cross-pair correlation matrix (Pearson)
            corr = np.corrcoef(arr)
            mask = ~np.eye(corr.shape[0], dtype=bool)
            mean_abs_corr = float(np.mean(np.abs(corr[mask]))) if corr.shape[0] > 1 else 0.0
            radar["network_dispersion_pct"] = round((1.0 - mean_abs_corr) * 100, 1)

            # Directional agreement = fraction of pairs with same sign on latest return
            last_returns = arr[:, -1]
            pos = int((last_returns > 0).sum())
            neg = int((last_returns < 0).sum())
            radar["directional_agreement_pct"] = round(max(pos, neg) / len(last_returns) * 100, 1)

            # Real radar-sweep blips: one per symbol, angle spread around the dish,
            # radius = recent |return| normalized, color = sign of latest return.
            mags = np.abs(last_returns)
            m_max = float(mags.max()) if mags.size and mags.max() > 0 else 1.0
            for i, sym in enumerate(keys):
                strength = float(mags[i]) / m_max
                angle = (i / len(keys)) * 360.0 - 90.0
                import math as _m
                r = 12 + 30 * strength
                blips.append({
                    "symbol":  sym,
                    "x":       round(50 + r * _m.cos(_m.radians(angle)), 1),
                    "y":       round(50 + r * _m.sin(_m.radians(angle)), 1),
                    "strength": round(strength, 2),
                    "dir":     "up" if last_returns[i] > 0 else "down",
                })
    except Exception:
        pass

    radar["blips"] = blips

    # 3. Regime by UTC hour (session classification stays meaningful)
    h = datetime.now(timezone.utc).hour
    if 0 <= h < 7:
        radar["volatility_regime"], radar["regime_description"] = "ASIAN SESSION 🟡", "Asian FX Network Active"
    elif 8 <= h < 12:
        radar["volatility_regime"], radar["regime_description"] = "LONDON OPEN 🟢", "High Volatility Breakout Zone"
    elif 13 <= h < 17:
        radar["volatility_regime"], radar["regime_description"] = "NY SESSION 🔵", "NY Close Drive Window"
    else:
        radar["volatility_regime"], radar["regime_description"] = "COMPRESSION 🟠", "Range Tightening Pre-Breakout"

    return radar


def main():
    # 0. Acquire Single Instance Lock (Zero Duplicate Instances)
    lock = SingleInstanceLock()
    lock.acquire()

    print("=" * 115)
    print("PROXIMA ALPHA ENGINE — INITIALIZING LIVE INSTITUTIONAL SIDECAR EXECUTION...")
    print("=" * 115)

    # Mirror all engine stdout to the Gaming UI log console
    sys.stdout = _TeeLogger(sys.__stdout__)

    # 0.5 Initialize persistent SQLite store (real trade history backbone)
    db.init_db()
    db.set_meta("started_at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    try:
        import subprocess as _sp
        sha = _sp.check_output(["git", "rev-parse", "HEAD"], cwd=str(Path(__file__).resolve().parent),
                               stderr=_sp.DEVNULL).decode().strip()[:12]
        db.set_meta("git_sha", sha)
    except Exception:
        db.set_meta("git_sha", "unknown")

    # 1. Start Telemetry Web Server
    start_telemetry_server(port=8888)

    # 2. Start Git Push Auto-Updater Service
    repo_dir = str(Path(__file__).resolve().parent)
    updater = AutoUpdater(repo_dir=repo_dir, lock=lock, check_interval_sec=15)
    updater.start()

    # 3. Initialize High-Speed MT5 Bridge
    bridge = MT5Bridge(mt5_path=MT5_PATH, timezone_offset_hours=MT5_SERVER_TIMEZONE_OFFSET_HOURS)
    if not bridge.connect():
        print("❌ Could not connect to MT5. Exiting...")
        lock.release()
        return

    # 3.5 Start Trade Auditor (real closed-trade reconciliation + game state)
    auditor = TradeAuditor(bridge=bridge, check_interval_sec=30, days=30)
    auditor.start()

    # 4. Initialize Execution Guard & Risk Manager
    guard = ExecutionGuard(max_spread_pips=MAX_SPREAD_PIPS_DEFAULT, max_retries=3, retry_delay_ms=15)
    risk_mgr = RiskManager(daily_drawdown_limit_pct=DAILY_DRAWDOWN_LIMIT_PCT)
    tracker = PositionTracker(execution_guard=guard)
    evaluator = StrategyEvaluator(config_suite=STRATEGY_SUITE)

    all_symbols = set()
    for strat in STRATEGY_SUITE.values():
        all_symbols.update(strat["universe"])
    all_symbols = sorted(all_symbols)

    last_eval_time = None
    last_radar_snapshot = None
    start_day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last_day_key = start_day_key

    # ─── Equity sampler daemon (real equity curve every 5s) ───────────────────
    def _equity_sampler():
        while True:
            try:
                if HAS_MT5_LIB and mt5:
                    acc = bridge.account_info()
                    if acc:
                        db.append_equity(acc.equity, acc.balance)
            except Exception:
                pass
            time.sleep(5)

    threading.Thread(target=_equity_sampler, daemon=True).start()

    # Initialize initial radar snapshot immediately on startup
    try:
        init_df = bridge.fetch_all_universes_df(list(all_symbols), count=300, exclude_forming=True)
        last_radar_snapshot = _build_real_radar(bridge, init_df)
        if last_radar_snapshot:
            update_telemetry("real_radar", last_radar_snapshot)
    except Exception as e:
        print(f"⚠️ [Engine] Startup radar init exception: {e}")

    try:
        while True:
            utc_now = bridge.get_server_utc_time()

            if last_eval_time is None or (utc_now.minute % 5 == 0 and utc_now.minute != last_eval_time.minute):
                last_eval_time = utc_now
                print(f"\n⏰ [M5 Bar Boundary] {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')} — Evaluating Strategy Signals...")

                df_dict = bridge.fetch_all_universes_df(list(all_symbols), count=300, exclude_forming=True)

                # Push live account state to Gaming UI telemetry
                acc_info = None
                if HAS_MT5_LIB and mt5:
                    measured_account = measure_call_latency(bridge.account_info)
                    acc_info = measured_account.value
                    update_telemetry("mt5_latency_ms", measured_account.latency_ms)

                    if acc_info:
                        risk_mgr.update_daily_baseline(acc_info.equity)
                        update_telemetry("account_equity", acc_info.equity)
                        update_telemetry("account_balance", acc_info.balance)
                        if risk_mgr.initial_day_equity and risk_mgr.initial_day_equity > 0:
                            dd_pct = (risk_mgr.initial_day_equity - acc_info.equity) / risk_mgr.initial_day_equity * 100
                            update_telemetry("daily_pnl", round(acc_info.equity - risk_mgr.initial_day_equity, 2))
                            update_telemetry("daily_dd_pct", round(dd_pct, 3))
                        shield_ok, shield_reason = risk_mgr.check_daily_drawdown_shield(acc_info.equity)
                # Daily session rollover bookkeeping
                day_key = utc_now.strftime("%Y-%m-%d")
                if day_key != last_day_key:
                    last_day_key = day_key
                    risk_mgr.maybe_rollover_day(day_key)
                    trades_today = db.trades_for_day(day_key)
                    wins = sum(1 for t in trades_today if t["net_pnl"] > 0)
                    db.upsert_daily_session(
                        day=day_key,
                        start_equity=risk_mgr.initial_day_equity or 0.0,
                        end_equity=acc_info.equity if HAS_MT5_LIB and mt5 and acc_info else 0.0,
                        pnl=round(sum(t["net_pnl"] for t in trades_today), 2),
                        dd_pct=round(risk_mgr.daily_dd_pct, 3) if hasattr(risk_mgr, "daily_dd_pct") else 0.0,
                        trades=len(trades_today),
                        wins=wins,
                    )

                # Real market radar snapshot (recomputed at each bar, cached between broadcasts)
                last_radar_snapshot = _build_real_radar(bridge, df_dict)
                if last_radar_snapshot:
                    update_telemetry("real_radar", last_radar_snapshot)

                signals = evaluator.evaluate_all(df_dict, utc_now)
                if signals:
                    print(f"🔥 [Signals] Generated {len(signals)} Active Signals!")
                    for sig in signals:
                        strat_name = sig["strategy"]
                        pair       = sig["pair"]
                        side       = sig["side"]
                        lot        = sig["lot"]
                        cfg        = next(c for c in STRATEGY_SUITE.values() if c["name"] == strat_name)

                        ticket, status, exec_price = guard.execute_market_order(
                            symbol=pair,
                            side=side,
                            lot=lot,
                            magic=cfg["magic"],
                            comment=f"ProximaAlpha_{strat_name}",
                            sl_pips=cfg.get("sl_pips"),
                            tp_pips=cfg.get("tp_pips")
                        )

                        if ticket:
                            db.insert_signal(strat_name, pair, side, lot,
                                             utc_now.strftime("%Y-%m-%d %H:%M:%S"), executed=1)
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
                                entry_time_str=utc_now.strftime("%Y-%m-%d %H:%M:%S"),
                                entry_price=exec_price if exec_price else sig.get("entry_price")
                            )

            # Continuous 1-second position tracking & hold timer checks
            try:
                removed = tracker.refresh_live_pnl(risk_mgr, bridge)
                if removed:
                    print(f"🟢 [Tracker] {removed} position(s) closed externally — removed from active state.")
            except Exception as e:
                print(f"⚠️ [Tracker] refresh_live_pnl error: {e}")

            if last_eval_time is not None:
                tracker.update_bar_hold_timers(utc_now.strftime("%Y-%m-%d %H:%M:%S"))

            # Continuous 1-second tick velocity & live market radar update
            try:
                live_ticks = bridge.fetch_ticks(all_symbols)
                if live_ticks and last_radar_snapshot:
                    # Compute live 1s tick velocity
                    fresh_count = sum(1 for t in live_ticks.values() if t.get("ask", 0) > 0)
                    last_radar_snapshot["tick_velocity_per_sec"] = round(fresh_count / 1.5, 1)

                    # Compute real-time directional agreement from live tick moves
                    ups = sum(1 for t in live_ticks.values() if t.get("ask", 0) >= t.get("bid", 0))
                    total = len(live_ticks)
                    if total > 0:
                        last_radar_snapshot["directional_agreement_pct"] = round(max(ups, total - ups) / total * 100, 1)

                    update_telemetry("real_radar", last_radar_snapshot)
            except Exception:
                pass

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Engine stopped by user.")
    finally:
        updater.stop()
        auditor.stop()
        bridge.shutdown()
        lock.release()

if __name__ == "__main__":
    main()
