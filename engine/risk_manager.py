"""
Risk Manager — Daily Drawdown Shield (4.5% FTMO Shield) & Cross-Pair Pip Value USD Calculator.
Safe cross-platform import guard.
"""

from engine.mt5_bridge import mt5, HAS_MT5_LIB, MT5_LOCK
import engine.db as db
from datetime import datetime, timezone

class RiskManager:
    def __init__(self, daily_drawdown_limit_pct=0.045):
        self.daily_limit_pct = daily_drawdown_limit_pct
        self.initial_day_equity = None
        self._baseline_key = None
        self._restore_persisted_baseline()

    def _restore_persisted_baseline(self):
        """Restore the day's opening equity baseline from SQLite so the DD shield
        survives engine restarts mid-day (else a restart silently re-arms the shield
        at the already-drawn-down equity level)."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"dd_baseline_{day}"
        self._baseline_key = key
        try:
            persisted = db.get_meta(key)
            if persisted:
                self.initial_day_equity = float(persisted)
                print(f"🛡️ [RiskManager] Restored daily DD baseline for {day}: ${self.initial_day_equity:,.2f}")
        except Exception as e:
            print(f"⚠️ [RiskManager] Baseline restore error: {e}")

    def update_daily_baseline(self, account_equity):
        if self.initial_day_equity is None:
            self.initial_day_equity = account_equity
            try:
                day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                key = f"dd_baseline_{day}"
                self._baseline_key = key
                db.set_meta(key, str(round(self.initial_day_equity, 2)))
                print(f"🛡️ [RiskManager] Daily DD baseline set: ${self.initial_day_equity:,.2f}")
            except Exception as e:
                print(f"⚠️ [RiskManager] Baseline persist error: {e}")

    def maybe_rollover_day(self, day_key):
        """Reset the baseline when a new UTC day begins."""
        expected_key = f"dd_baseline_{day_key}"
        if self._baseline_key != expected_key:
            self.initial_day_equity = None
            self._baseline_key = expected_key
            print(f"📅 [RiskManager] New day detected ({day_key}) — baseline will re-arm at first account poll.")

    def check_daily_drawdown_shield(self, current_equity):
        if self.initial_day_equity is None or self.initial_day_equity <= 0:
            return True, "BASELINE_OK"

        drawdown_pct = (self.initial_day_equity - current_equity) / self.initial_day_equity
        if drawdown_pct >= self.daily_limit_pct:
            return False, f"Daily Drawdown Shield Triggered ({round(drawdown_pct*100, 2)}% >= {round(self.daily_limit_pct*100, 1)}%)"

        return True, "SHIELD_OK"

    def compute_floating_pnl(self, symbol, side, lot, entry_price, tick):
        """Estimate floating PnL in USD from a live tick {bid, ask}.

        A BUY position is closed at the BID; a SELL position is closed at the ASK.
        Using the wrong side overstates PnL by the full spread.
        """
        if not tick:
            return 0.0
        pip_val = self.get_pip_value_usd(symbol)
        pip_sz = 0.01 if "JPY" in symbol else 0.0001
        price = tick.get("bid") if side.upper() == "BUY" else tick.get("ask")
        if not price or not entry_price:
            return 0.0
        if side.upper() == "BUY":
            pips = (price - entry_price) / pip_sz
        else:
            pips = (entry_price - price) / pip_sz
        return round(pips * pip_val * float(lot), 2)

    def get_pip_value_usd(self, symbol):
        if "USD" in symbol and symbol.endswith("USD"):
            return 10.0

        if not HAS_MT5_LIB or mt5 is None:
            return 10.0

        with MT5_LOCK:
            sym_info = mt5.symbol_info(symbol)
            if sym_info is None:
                return 10.0

            quote_currency = symbol[3:]

            if quote_currency == "USD":
                return 10.0
            elif quote_currency == "JPY":
                usdjpy = mt5.symbol_info("USDJPY")
                if usdjpy and usdjpy.bid > 0:
                    return (1000.0 / usdjpy.bid)
                return 6.5
            elif quote_currency == "AUD":
                audusd = mt5.symbol_info("AUDUSD")
                if audusd and audusd.bid > 0:
                    return 10.0 * audusd.bid
                return 6.7
            elif quote_currency == "NZD":
                nzdusd = mt5.symbol_info("NZDUSD")
                if nzdusd and nzdusd.bid > 0:
                    return 10.0 * nzdusd.bid
                return 6.0
            elif quote_currency == "CAD":
                usdcad = mt5.symbol_info("USDCAD")
                if usdcad and usdcad.bid > 0:
                    return (10.0 / usdcad.bid)
                return 7.5
            elif quote_currency == "CHF":
                usdchf = mt5.symbol_info("USDCHF")
                if usdchf and usdchf.bid > 0:
                    return (10.0 / usdchf.bid)
                return 11.0

            return 10.0
