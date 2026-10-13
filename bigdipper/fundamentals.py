"""Fundamental score (0-100): "is the business behind this dip healthy?"

Eight metrics, 12.5 points each, across four pillars: valuation, profitability, growth, financial health.
Two kinds of company need different measures because the usual ones are meaningless for them:

* Negative shareholders' equity (heavy buybacks, e.g. MCD, LOW): ROE and debt-to-equity are undefined, so we use
  return on assets and net debt / EBITDA instead.
* Financials (banks, brokers, insurers): free cash flow and debt-to-equity do not apply, so we use price-to-book
  and return on assets instead.

A metric that Yahoo does not report is left OUT of the score (never guessed): the score is points earned divided by
points available, scaled to 100, and the stock is flagged with how many metrics were scored. With fewer than 5 metrics
the score is pulled toward neutral (50) so it can never rest on a couple of numbers.
"""
import numpy as np

from .technicals import Component

NO_DATA_NOTE = "Yahoo has no figure for this company; left out of the score."


def linear(value, bad, good, max_pts):
    """Linear points between a 'bad' value (0 pts) and a 'good' value (max_pts). Works when good < bad."""
    if value is None or np.isnan(value):
        return None
    return max_pts * float(np.clip((value - bad) / (good - bad), 0, 1))


def _comp(name, pts, max_pts, value, note):
    if pts is None:
        return Component("fundamental", name, 0.0, max_pts, "n/a", NO_DATA_NOTE, missing=True)
    return Component("fundamental", name, pts, max_pts, value, note)


def _pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def fundamental_components(f: dict) -> list[Component]:
    financial = f.get("sector") == "Financial Services"
    neg_equity = bool(f.get("negative_equity")) and not financial
    unprofitable = f.get("profit_margin") is not None and f["profit_margin"] < 0

    pe = f.get("pe")
    pe_pts = 0.0 if unprofitable else linear(pe, 40, 15, 12.5)  # P/E 15 or lower = full, 40+ = none
    peg = f.get("peg")
    peg_pts = 0.0 if unprofitable else linear(peg, 3, 1, 12.5)  # PEG 1 or lower = full, 3+ = none
    growth_note = lambda g: "Growing." if g is not None and g > 0.05 else "Flat or shrinking."

    comps = [
        _comp("P/E ratio", pe_pts, 12.5, f"P/E {pe:.1f}" if pe else "n/a", "Loss-making, so no earnings to value." if unprofitable else "Cheap relative to earnings." if pe_pts and pe_pts > 8 else "Priced richly relative to earnings."),
        _comp("PEG ratio", peg_pts, 12.5, f"PEG {peg:.2f}" if peg else "n/a", "Price is reasonable for its growth." if peg_pts and peg_pts > 8 else "Paying a lot for each unit of growth."),
    ]

    roa = f.get("roa")
    if neg_equity:
        comps.append(_comp("Return on assets", linear(roa, 0, 0.10, 12.5), 12.5, _pct(roa), "Earns good returns on its assets. (Return on equity is not meaningful: shareholder equity is negative after buybacks.)" if (roa or 0) >= 0.06 else "Modest returns on its assets. (Return on equity is not meaningful: shareholder equity is negative after buybacks.)"))
    else:
        comps.append(_comp("Return on equity", linear(f.get("roe"), 0, 0.20, 12.5), 12.5, _pct(f.get("roe")), "Earns strong returns on shareholder capital." if (f.get("roe") or 0) >= 0.15 else "Weak returns on shareholder capital."))
    comps += [
        _comp("Profit margin", linear(f.get("profit_margin"), 0, 0.20, 12.5), 12.5, _pct(f.get("profit_margin")), "Healthy margins." if (f.get("profit_margin") or 0) >= 0.10 else "Thin or negative margins."),
        _comp("Revenue growth", linear(f.get("revenue_growth"), -0.05, 0.15, 12.5), 12.5, _pct(f.get("revenue_growth")), growth_note(f.get("revenue_growth"))),
        _comp("Earnings growth", linear(f.get("earnings_growth"), -0.10, 0.20, 12.5), 12.5, _pct(f.get("earnings_growth")), growth_note(f.get("earnings_growth"))),
    ]

    if financial:  # debt IS a bank's raw material and free cash flow is distorted by deposits and loans
        pb = f.get("price_to_book")
        comps.append(_comp("Price-to-book", linear(pb, 3.0, 1.0, 12.5), 12.5, f"{pb:.2f}x" if pb is not None else "n/a", "Trades near or below book value." if pb is not None and pb <= 1.5 else "Trades at a premium to book value."))
        comps.append(_comp("Return on assets", linear(roa, 0, 0.012, 12.5), 12.5, _pct(roa) if roa is None else f"{roa:.1%}", "Earns solid returns on its assets for a financial firm." if (roa or 0) >= 0.008 else "Weak returns on assets for a financial firm."))
    else:
        if neg_equity:
            nd = f.get("net_debt_to_ebitda")
            comps.append(_comp("Net debt / EBITDA", linear(nd, 4.0, 1.0, 12.5), 12.5, f"{nd:.1f}x" if nd is not None else "n/a", "Debt is small relative to earnings. (Debt-to-equity is not meaningful with negative equity.)" if nd is not None and nd <= 2.5 else "Debt is large relative to earnings. (Debt-to-equity is not meaningful with negative equity.)"))
        else:
            de = f.get("debt_to_equity")
            comps.append(_comp("Debt-to-equity", linear(de, 2.0, 0.5, 12.5), 12.5, f"{de:.2f}x" if de is not None else "n/a", "Manageable debt." if de is not None and de <= 1 else "Heavy debt load."))
        fcf = f.get("fcf_yield")
        comps.append(_comp("Free-cash-flow yield", linear(fcf, 0, 0.05, 12.5), 12.5, _pct(fcf), "Generates real cash relative to its price." if (fcf or 0) >= 0.03 else "Little or negative free cash flow."))
    return comps


MIN_METRICS = 5  # fewer scored metrics than this and the score is pulled toward neutral


def fundamental_score(comps: list[Component]) -> tuple[float, int]:
    """(score 0-100, number of metrics scored).

    The score is points earned / points available, scaled to 100. With fewer than MIN_METRICS metrics it is pulled
    toward a neutral 50 in proportion to how little data there is, so a great-looking score can never rest on two numbers.
    """
    avail = [c for c in comps if not c.missing]
    if not avail:
        return 50.0, 0
    scaled = 100 * sum(c.points for c in avail) / sum(c.max_points for c in avail)
    if len(avail) < MIN_METRICS:
        scaled = 50 + (scaled - 50) * len(avail) / MIN_METRICS
    return scaled, len(avail)
