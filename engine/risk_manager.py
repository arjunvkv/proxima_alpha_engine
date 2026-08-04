"""
Risk Manager — Daily Drawdown Shield (4.5% FTMO Shield) & Cross-Pair Pip Value USD Calculator
"""

import MetaTrader5 as mt5

class RiskManager:
    def __init__(self, daily_drawdown_limit_pct=0.045):
        self.daily_limit_pct = daily_drawdown_limit_pct
        self.initial_day_equity = None

    def update_daily_baseline(self, account_equity):
        if self.initial_day_equity is None:
            self.initial_day_equity = account_equity

    def check_daily_drawdown_shield(self, current_equity):
        """
        Halts new trade entries if daily drawdown exceeds 4.5% limit.
        """
        if self.initial_day_equity is None or self.initial_day_equity <= 0:
            return True, "BASELINE_OK"

        drawdown_pct = (self.initial_day_equity - current_equity) / self.initial_day_equity
        if drawdown_pct >= self.daily_limit_pct:
            return False, f"Daily Drawdown Shield Triggered ({round(drawdown_pct*100, 2)}% >= {round(self.daily_limit_pct*100, 1)}%)"

        return True, "SHIELD_OK"

    def get_pip_value_usd(self, symbol):
        """
        Computes exact USD value per pip for cross pairs dynamically.
        """
        if "USD" in symbol and symbol.endswith("USD"):
            return 10.0  # EURUSD, GBPUSD, AUDUSD, NZDUSD

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return 10.0

        # Extract quote currency (e.g. AUD in EURAUD, JPY in USDJPY)
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
