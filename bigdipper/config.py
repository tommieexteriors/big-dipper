"""Tunable settings for Big Dipper. Every threshold here is explained in docs/METHODOLOGY.md."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskProfile:
    name: str
    min_fundamental_score: float  # gate: below this, the verdict can never be "Buy the Dip"
    risk_budget: float            # share of the portfolio the investor accepts losing on one trade
    stop_loss: float              # stop distance below the entry price
    max_position: float           # hard cap on the share of the portfolio in one stock


PROFILES = {
    "conservative": RiskProfile("conservative", 55, 0.005, 0.08, 0.05),
    "balanced": RiskProfile("balanced", 45, 0.010, 0.12, 0.10),
    "aggressive": RiskProfile("aggressive", 35, 0.020, 0.18, 0.20),
}


@dataclass(frozen=True)
class Settings:
    dip_threshold: float = 0.15      # drawdown from the 52-week high that counts as a "dip"
    screen_min_dip: float = 0.10     # the screener lists anything at least this far down
    weight_fundamental: float = 0.5
    weight_technical: float = 0.5
    buy_threshold: float = 60.0      # composite score needed for "Buy the Dip"
    wait_threshold: float = 45.0     # composite score needed for "Wait" (below it: "Avoid")
    min_technical_for_buy: float = 55.0  # price-setup trigger; same cut-off the backtest tests


DEFAULT_SETTINGS = Settings()

VERDICT_NOT_A_DIP = "Not a Dip"
VERDICT_BUY = "Buy the Dip"
VERDICT_WAIT = "Wait"
VERDICT_AVOID = "Avoid (Falling Knife)"
