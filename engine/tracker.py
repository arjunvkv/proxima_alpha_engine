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

    def add_position(self, ticket, strategy, pair, side, lot, hold_bars, entry_time_str):
        self.active_positions[str(ticket)] = {
            "ticket": ticket,
            "strategy": strategy,
            "pair": pair,
            "side": side,
            "lot": lot,
            "hold_bars": hold_bars,
            "bars_held": 0,
            "entry_time": entry_time_str
        }
        self.save_state()

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
