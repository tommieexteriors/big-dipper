"""Fundamental score (0-100): "is the business behind this dip healthy?"

Four pillars worth 25 points each: valuation, profitability, growth, financial health.
A metric that Yahoo does not report earns half marks and is flagged as missing; it is never guessed.
"""
import numpy as np

from .technicals import Component


def linear(value, bad, good, max_pts):
    """Linear points between a 'bad' value (0 pts) and a 'good' value (max_pts). Works when good < bad."""
    if value is None or np.isnan(value):
        return None
    return max_pts * float(np.clip((value - bad) / (good - bad), 0, 1))


def _comp(name, pts, max_pts, value, note):
    if pts is None:
        return Component("fundamental", name, max_pts / 2, max_pts, "n/a", "Not reported; given neutral half marks.", missing=True)
    return Component("fundamental", name, pts, max_pts, value, note)


def _pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def fundamental_components(f: dict) -> list[Component]:
    unprofitable = f.get("profit_margin") is not None and f["profit_margin"] < 0

    pe = f.get("pe")
    pe_pts = 0.0 if unprofitable else linear(pe, 40, 15, 12.5)  # P/E 15 or lower = full, 40+ = none
    peg = f.get("peg")
    peg_pts = 0.0 if unprofitable else linear(peg, 3, 1, 12.5)  # PEG 1 or lower = full, 3+ = none

    growth_note = lambda g: "Growing." if g is not None and g > 0.05 else "Flat or shrinking."
    de = f.get("debt_to_equity")
    fcf = f.get("fcf_yield")

    return [
        _comp("P/E ratio", pe_pts, 12.5, f"P/E {pe:.1f}" if pe else "n/a", "Loss-making, so no earnings to value." if unprofitable else "Cheap relative to earnings." if pe_pts and pe_pts > 8 else "Priced richly relative to earnings."),
        _comp("PEG ratio", peg_pts, 12.5, f"PEG {peg:.2f}" if peg else "n/a", "Price is reasonable for its growth." if peg_pts and peg_pts > 8 else "Paying a lot for each unit of growth."),
        _comp("Return on equity", linear(f.get("roe"), 0, 0.20, 12.5), 12.5, _pct(f.get("roe")), "Earns strong returns on shareholder capital." if (f.get("roe") or 0) >= 0.15 else "Weak returns on shareholder capital."),
        _comp("Profit margin", linear(f.get("profit_margin"), 0, 0.20, 12.5), 12.5, _pct(f.get("profit_margin")), "Healthy margins." if (f.get("profit_margin") or 0) >= 0.10 else "Thin or negative margins."),
        _comp("Revenue growth", linear(f.get("revenue_growth"), -0.05, 0.15, 12.5), 12.5, _pct(f.get("revenue_growth")), growth_note(f.get("revenue_growth"))),
        _comp("Earnings growth", linear(f.get("earnings_growth"), -0.10, 0.20, 12.5), 12.5, _pct(f.get("earnings_growth")), growth_note(f.get("earnings_growth"))),
        _comp("Debt-to-equity", linear(de, 2.0, 0.5, 12.5), 12.5, f"{de:.2f}x" if de is not None else "n/a", "Manageable debt." if de is not None and de <= 1 else "Heavy debt load."),
        _comp("Free-cash-flow yield", linear(fcf, 0, 0.05, 12.5), 12.5, _pct(fcf), "Generates real cash relative to its price." if (fcf or 0) >= 0.03 else "Little or negative free cash flow."),
    ]
