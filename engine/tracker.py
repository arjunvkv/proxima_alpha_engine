"""
Position Tracker — Manages position hold timers and persists state to data/state.json for reboot survival.
"""

import os
import json
import time
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "state.json"

class PositionTracker:
    def __init__(self, execution_guard):
        self.guard = execution_guard
        self.active_positions = {}
        self.last_active_snapshot = {}
        self.load_state()

    def load_state(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.active_positions = json.load(f)
                print(f"🟢 [Tracker] Loaded {len(self.active_positions)} active position states from disk.")
            except Exception as e:
                print(f"⚠️ [Tracker] Error loading state.json: {e}")

    def save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.active_positions, f, indent=2)
        except Exception as e:
            print(f"⚠️ [Tracker] Error saving state.json: {e}")

    def add_position(self, ticket, strategy, pair, side, lot, hold_bars, entry_time_str, entry_price=None):
        self.active_positions[str(ticket)] = {
            "ticket": ticket,
            "strategy": strategy,
            "pair": pair,
            "side": side,
            "lot": lot,
            "hold_bars": hold_bars,
            "bars_held": 0,
            "entry_time": entry_time_str,
            "entry_price": entry_price or 0.0,
            "exit_price": 0.0,
            "pips": 0.0,
            "net_pnl": 0.0,
        }
        self.save_state()

    def refresh_live_pnl(self, risk_mgr, bridge):
        """Update floating PnL + current entry price for all active positions from live ticks.
        Returns number of positions that are no longer on MT5 (closed/removed)."""
        if not self.active_positions:
            return 0
        symbols = list({p["pair"] for p in self.active_positions.values()})
        ticks = {}
        try:
            ticks = bridge.fetch_ticks(symbols)
        except Exception as e:
            print(f"⚠️ [Tracker] refresh_live_pnl tick fetch error: {e}")
            return 0

        removed = 0
        for ticket_str, pos in list(self.active_positions.items()):
            pair = pos["pair"]
            tick = ticks.get(pair)
            try:
                from engine.mt5_bridge import mt5, HAS_MT5_LIB, MT5_LOCK
                if HAS_MT5_LIB and mt5:
                    with MT5_LOCK:
                        posns = mt5.positions_get(ticket=int(pos["ticket"]))
                    if not posns:
                        # Position no longer open on MT5 (TP/SL hit externally)
                        del self.active_positions[ticket_str]
                        removed += 1
                        continue
            except Exception:
                pass

            if tick and pos["entry_price"]:
                pos["net_pnl"] = risk_mgr.compute_floating_pnl(
                    pair, pos["side"], pos["lot"], pos["entry_price"], tick)
                pip_sz = 0.01 if "JPY" in pair else 0.0001
                price = tick.get("bid") if pos["side"].upper() == "BUY" else tick.get("ask")
                if price and pos["entry_price"]:
                    pos["pips"] = round(
                        ((price - pos["entry_price"]) if pos["side"].upper() == "BUY"
                         else (pos["entry_price"] - price)) / pip_sz, 1)
            # Update telemetry reference so UI sees fresh data
            self.last_active_snapshot = dict(self.active_positions)

        self.save_state()
        return removed

    def update_bar_hold_timers(self, current_time_str):
        """
        Updates bar hold timers on every M5 bar close and hard exits expired positions.
        """
        expired_tickets = []

        for ticket_str, pos in list(self.active_positions.items()):
            pos["bars_held"] += 1
            print(f"⏱️ [Tracker] Ticket #{pos['ticket']} ({pos['strategy']} {pos['pair']}) Held: {pos['bars_held']}/{pos['hold_bars']} M5 bars")

            if pos["bars_held"] >= pos["hold_bars"]:
                expired_tickets.append(ticket_str)

        self.save_state()

        # Execute hard exits for expired positions
        for ticket_str in expired_tickets:
            pos = self.active_positions.get(ticket_str)
            if pos:
                print(f"⌛ [Tracker] Hold time expired for Ticket #{pos['ticket']}. Hard exiting...")
                success = self.guard.hard_exit_position(
                    ticket=pos["ticket"],
                    symbol=pos["pair"],
                    side=pos["side"],
                    lot=pos["lot"]
                )
                if success or True:  # Remove state once exit attempt completes
                    del self.active_positions[ticket_str]

        self.save_state()
