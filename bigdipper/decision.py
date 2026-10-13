"""Decision engine: combine the two scores, apply the fundamental gate, size the position, explain why."""
from dataclasses import dataclass, field

import pandas as pd

from .config import (
    DEFAULT_SETTINGS,
    PROFILES,
    VERDICT_AVOID,
    VERDICT_BUY,
    VERDICT_NOT_A_DIP,
    VERDICT_WAIT,
    RiskProfile,
    Settings,
)
from .fundamentals import fundamental_components
from .technicals import Component, technical_components


MAX_MISSING_FOR_BUY = 4  # of 8 fundamental metrics; at 4+ missing the score is mostly guesswork


@dataclass
class Analysis:
    ticker: str
    name: str
    sector: str
    price: float
    drawdown: float          # negative, e.g. -0.27 = 27% below the 52-week high
    high_52w: float
    fund_score: float
    tech_score: float
    composite: float
    verdict: str
    position_size: float     # share of the portfolio (0 unless Buy)
    stop_price: float | None
    explanation: str
    components: list[Component] = field(default_factory=list)
    missing_fundamentals: int = 0


def decide(drawdown: float, fund_score: float, tech_score: float, profile: RiskProfile, settings: Settings = DEFAULT_SETTINGS) -> tuple[str, float, float]:
    """Returns (verdict, composite score, position size as a share of the portfolio)."""
    composite = settings.weight_fundamental * fund_score + settings.weight_technical * tech_score
    if -drawdown < settings.dip_threshold:
        return VERDICT_NOT_A_DIP, composite, 0.0
    if fund_score < profile.min_fundamental_score:  # the gate: weak business => never a Buy, however oversold
        return VERDICT_AVOID, composite, 0.0
    if composite >= settings.buy_threshold:
        if tech_score < settings.min_technical_for_buy:  # good business, but the chart has not set up yet
            return VERDICT_WAIT, composite, 0.0
        size = min(profile.max_position, profile.risk_budget / profile.stop_loss)
        return VERDICT_BUY, composite, size
    if composite >= settings.wait_threshold:
        return VERDICT_WAIT, composite, 0.0
    return VERDICT_AVOID, composite, 0.0


def _extremes(comps: list[Component]):
    scored = [c for c in comps if not c.missing]
    if not scored:
        return None, None
    ratio = lambda c: c.points / c.max_points
    return max(scored, key=ratio), min(scored, key=ratio)


def explain(a: "Analysis", profile: RiskProfile, settings: Settings) -> str:
    dd = -a.drawdown
    if a.verdict == VERDICT_NOT_A_DIP:
        return f"{a.ticker} is only {dd:.0%} below its 52-week high, under the {settings.dip_threshold:.0%} dip threshold, so there is no dip to evaluate."
    fund = [c for c in a.components if c.group == "fundamental"]
    tech = [c for c in a.components if c.group == "technical"]
    f_best, f_worst = _extremes(fund)
    t_best, t_worst = _extremes(tech)
    parts = [f"{a.ticker} is {dd:.0%} below its 52-week high."]
    if f_best:
        parts.append(f"Business quality scores {a.fund_score:.0f}/100: strongest on {f_best.name} ({f_best.value}), weakest on {f_worst.name} ({f_worst.value}).")
    if t_best:
        parts.append(f"The price setup scores {a.tech_score:.0f}/100: best signal is {t_best.name} ({t_best.value}), weakest is {t_worst.name} ({t_worst.value}).")
    if a.verdict == VERDICT_AVOID and a.fund_score < profile.min_fundamental_score:
        parts.append(f"Verdict: AVOID. Business quality is below the {profile.min_fundamental_score:.0f}-point minimum for a {profile.name} investor, so this looks more like a falling knife than a discount, however oversold the chart is.")
    elif a.verdict == VERDICT_AVOID:
        parts.append(f"Verdict: AVOID. The combined score of {a.composite:.0f} is below {settings.wait_threshold:.0f}; neither the business nor the chart makes a convincing case.")
    elif a.verdict == VERDICT_WAIT and a.composite >= settings.buy_threshold:
        parts.append(f"Verdict: WAIT. The business looks good, but the price setup score of {a.tech_score:.0f} is below the {settings.min_technical_for_buy:.0f} needed for a buy signal (the same trigger used in our backtest). The chart does not yet show an oversold, stabilising entry.")
    elif a.verdict == VERDICT_WAIT:
        parts.append(f"Verdict: WAIT. The combined score of {a.composite:.0f} is decent but short of the {settings.buy_threshold:.0f} needed to buy; watch for the price setup to improve.")
    else:
        parts.append(f"Verdict: BUY THE DIP. Combined score {a.composite:.0f}. For a {profile.name} investor: position of about {a.position_size:.1%} of the portfolio with a stop-loss at ${a.stop_price:,.2f} ({profile.stop_loss:.0%} below the price).")
    if a.missing_fundamentals >= MAX_MISSING_FOR_BUY:
        parts.append(f"Data warning: {a.missing_fundamentals} of 8 fundamental metrics were unavailable (common for ETFs, indexes and crypto), so the business score is mostly neutral filler and this can never be a Buy.")
    elif a.missing_fundamentals:
        parts.append(f"Note: {a.missing_fundamentals} fundamental metric(s) were unavailable and received neutral marks.")
    return " ".join(parts)


def build_analysis(
    ticker: str,
    ind_row: pd.Series,
    fundamentals: dict,
    profile: RiskProfile | str = "balanced",
    settings: Settings = DEFAULT_SETTINGS,
) -> Analysis:
    """Score one stock as of the last row of its indicator table."""
    profile = PROFILES[profile] if isinstance(profile, str) else profile
    f_comps = fundamental_components(fundamentals)
    t_comps = technical_components(ind_row)
    fund_score = sum(c.points for c in f_comps)
    tech_score = sum(c.points for c in t_comps)
    verdict, composite, size = decide(ind_row["drawdown"], fund_score, tech_score, profile, settings)
    price = float(ind_row["close"])
    a = Analysis(
        ticker=ticker,
        name=fundamentals.get("name", ticker),
        sector=fundamentals.get("sector", "Unknown"),
        price=price,
        drawdown=float(ind_row["drawdown"]),
        high_52w=float(ind_row["high_252"]),
        fund_score=fund_score,
        tech_score=tech_score,
        composite=composite,
        verdict=verdict,
        position_size=size,
        stop_price=price * (1 - profile.stop_loss) if verdict == VERDICT_BUY else None,
        explanation="",
        components=f_comps + t_comps,
        missing_fundamentals=sum(c.missing for c in f_comps),
    )
    if a.verdict == VERDICT_BUY and a.missing_fundamentals >= MAX_MISSING_FOR_BUY:
        # mostly neutral marks is not evidence of quality (ETFs, indexes, crypto, thin coverage): never a Buy
        a.verdict, a.position_size, a.stop_price = VERDICT_WAIT, 0.0, None
    a.explanation = explain(a, profile, settings)
    return a
