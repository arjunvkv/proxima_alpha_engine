"""
Proxima Alpha Engine — Trade Auditor & Game State Manager
Reconciles MT5 deal history into the SQLite trades table so the dashboard shows
REAL closed trades (PnL, exit reason, R-multiple). Also drives the gamification
layer: win-streaks, XP/levels and achievements. Runs as a daemon thread.
"""

import time
import threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import engine.db as db
from engine.mt5_bridge import mt5, HAS_MT5_LIB, rpyc_conn

# Exit reason heuristics
def _classify_exit_reason(pair, side, entry_price, exit_price):
    """Best-effort: our engine uses hold-timer hard exits; SL/TP are wide emergency guards.
    Categorize by which emergency boundary the exit price is closest to."""
    if entry_price <= 0:
        return "HOLD_TIMER"
    pip_sz = 0.01 if "JPY" in pair else 0.0001
    # Config emergency SL/TP pips (must stay in sync with config/settings.py)
    sl_pips, tp_pips = 50.0, 60.0  # Tokyo H0 default; approximate for classification
    if side == "BUY":
        sl_price = entry_price - sl_pips * pip_sz
        tp_price = entry_price + tp_pips * pip_sz
    else:
        sl_price = entry_price + sl_pips * pip_sz
        tp_price = entry_price - tp_pips * pip_sz

    if exit_price <= 0:
        return "UNKNOWN"
    d_sl = abs(exit_price - sl_price)
    d_tp = abs(exit_price - tp_price)
    if d_tp < d_sl and d_tp < pip_sz * 5:
        return "TAKE_PROFIT"
    if d_sl < d_tp and d_sl < pip_sz * 5:
        return "STOP_LOSS"
    return "HOLD_TIMER"

class TradeAuditor:
    def __init__(self, bridge, check_interval_sec=30, days=30):
        self.bridge = bridge
        self.interval = check_interval_sec
        self.days = days
        self.running = False
        self._thread = None
        self._last_scan_time = None
        self._last_seen_ticket = 0
        # Per-strategy win streaks, persisted
        self._daily_streak_key = None
        self._daily_trades = 0
        self._daily_wins = 0

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"🟢 [Auditor] Trade reconciliation started ({self.interval}s interval, {self.days} days history).")

    def stop(self):
        self.running = False

    # ─── Main loop ────────────────────────────────────────────────────────────
    def _loop(self):
        # Backfill once at startup
        try:
            backfilled = self._reconcile(backfill=True)
            print(f"🟢 [Auditor] Backfill complete. {backfilled} new closed trades stored.")
        except Exception as e:
            print(f"⚠️ [Auditor] Backfill error: {e}")

        while self.running:
            time.sleep(self.interval)
            try:
                self._reconcile(backfill=False)
            except Exception as e:
                print(f"⚠️ [Auditor] Reconcile error: {e}")

    # ─── Reconcile ────────────────────────────────────────────────────────────
    def _reconcile(self, backfill=False):
        if not HAS_MT5_LIB or mt5 is None:
            return 0

        deals = self.bridge.fetch_history_deals(from_time=0, days=self.days)
        if not deals:
            return 0

        # Group deals by position_id → (entry deal, exit deals, side, symbol, magic)
        positions = defaultdict(list)
        for d in deals:
            pid = d.get("position_id", 0)
            if pid:
                positions[pid].append(d)

        # Only consider deals with our magic numbers (Proxima strategies)
        from config.settings import STRATEGY_SUITE
        magic_to_strat = {cfg["magic"]: key for key, cfg in STRATEGY_SUITE.items()}
        magic_to_lot = {cfg["magic"]: cfg["lot"] for key, cfg in STRATEGY_SUITE.items()}

        new_count = 0
        for pid, pdeals in positions.items():
            magic = next((d.get("magic", 0) for d in pdeals if d.get("magic", 0) in magic_to_strat), 0)
            if not magic:
                continue
            strategy_key = magic_to_strat[magic]
            strategy_name = STRATEGY_SUITE[strategy_key]["name"]

            entries = [d for d in pdeals if d.get("entry", 0) == 0]  # DEAL_ENTRY_IN
            exits   = [d for d in pdeals if d.get("entry", 0) == 1]  # DEAL_ENTRY_OUT
            if not entries or not exits:
                continue

            entry = min(entries, key=lambda d: d["time"])
            exit_  = max(exits,   key=lambda d: d["time"])
            symbol = entry["symbol"]
            side   = entry["side"]

            net_pnl = sum(d.get("profit", 0.0) for d in pdeals)

            # Total closed volume on the exit side (for lot)
            exit_vol = sum(d.get("volume", 0.0) for d in exits)
            lot = exit_vol or magic_to_lot.get(magic, 1.0)

            # Pips — volume-weighted average exit price (handles partial closes:
            # each exit deal is a separate fill at its own price).
            pip_sz = 0.01 if "JPY" in symbol else 0.0001
            eprice = entry["price"]
            wsum, wvol = 0.0, 0.0
            for d in exits:
                wsum += d.get("price", 0.0) * d.get("volume", 0.0)
                wvol += d.get("volume", 0.0)
            xprice = (wsum / wvol) if wvol > 0 else exit_["price"]
            if eprice > 0 and xprice > 0:
                if side == "BUY":
                    pips = (xprice - eprice) / pip_sz
                else:
                    pips = (eprice - xprice) / pip_sz
            else:
                pips = 0.0

            # R-multiple: risk approximated by wide emergency SL distance (50 pips standard)
            risk_per_lot_usd = 50.0 * 10.0  # ~$50 risk per lot at 1:50 pips ($10/pip)
            r_multiple = net_pnl / (risk_per_lot_usd * lot) if lot else 0.0

            entry_time = datetime.fromtimestamp(entry["time"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            exit_time  = datetime.fromtimestamp(exit_["time"],  tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            trade = {
                "position_id": int(pid),
                "ticket": int(pid),
                "strategy": strategy_name,
                "pair": symbol,
                "side": side,
                "lot": round(lot, 2),
                "magic": int(magic),
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": round(eprice, 5),
                "exit_price": round(xprice, 5),
                "pips": round(pips, 1),
                "net_pnl": round(net_pnl, 2),
                "r_multiple": round(r_multiple, 2),
                "exit_reason": _classify_exit_reason(symbol, side, eprice, xprice),
                "is_live": 1,
            }

            db.upsert_trade(trade)
            if backfill or (self._last_scan_time is not None and exit_["time"] > self._last_scan_time):
                new_count += 1
                # Only track game state for freshly-closed trades (skip backfilled history
                # so streaks reflect consecutive live closes, not the entire past).
                if not backfill:
                    self._on_trade_closed(trade)

        self._last_scan_time = time.time()
        # Always keep last-seen ticket high-water for change detection
        if deals:
            self._last_seen_ticket = max(d.get("ticket", 0) for d in deals)
        return new_count

    # ─── Game state transitions ───────────────────────────────────────────────
    def _today_key(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _on_trade_closed(self, trade):
        """Update streaks / XP / achievements when a trade closes."""
        strategy = trade["strategy"]
        won = trade["net_pnl"] > 0
        today = self._today_key()

        # Per-strategy win streak
        streak_key = f"streak_{strategy}"
        if won:
            db.set_streak(streak_key, db.get_streak(streak_key) + 1)
        else:
            db.set_streak(streak_key, 0)

        # Overall win streak (consecutive wins across all strategies)
        if won:
            db.set_streak("streak_overall", db.get_streak("streak_overall") + 1)
        else:
            db.set_streak("streak_overall", 0)

        # XP: 10 per win, 4 per loss, +5 bonus per pip>0 handled below
        xp = db.get_streak("xp") + (10 if won else 4)
        db.set_streak("xp", xp)

        # Achievements
        if db.get_streak(f"streak_{strategy}") >= 5:
            db.unlock_achievement(f"streak5_{strategy}")
        if db.get_streak("streak_overall") >= 10:
            db.unlock_achievement("streak10_overall")
        if trade["net_pnl"] >= 500:
            db.unlock_achievement("single_500_day_trade")

        total_trades = db.closed_trade_count()
        if total_trades >= 10:
            db.unlock_achievement("trades_10")
        if total_trades >= 100:
            db.unlock_achievement("trades_100")

        # Daily session tally
        if self._daily_streak_key != today:
            self._daily_streak_key = today
            self._daily_trades = 0
            self._daily_wins = 0
        self._daily_trades += 1
        if won:
            self._daily_wins += 1
        if self._daily_wins >= 5:
            db.unlock_achievement("daily_5wins")

        print(f"🎮 [Auditor] {strategy} {trade['pair']} closed {'WIN' if won else 'LOSS'} "
              f"${trade['net_pnl']:+,.2f} | Streak={db.get_streak('streak_overall')} XP={xp}")
