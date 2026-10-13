"""Daily dip screener: scan the S&P 500, score every stock that is down, export JSON for the web app."""
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEFAULT_SETTINGS, PROFILES, Settings
from .data import download_ohlcv, download_universe, fetch_fundamentals, get_universe
from .decision import Analysis, build_analysis
from .technicals import indicators


def _clean(obj):
    """Make an object JSON-safe (NaN/inf -> None, numpy -> python)."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if (math.isnan(obj) or math.isinf(obj)) else round(float(obj), 4)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def scan(universe: list[str] | None = None, settings: Settings = DEFAULT_SETTINGS) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Technical pass over the whole universe. Returns (table of dippers, indicator tables by ticker)."""
    universe = universe or get_universe()
    close, volume = download_universe(universe)
    rows, tables = [], {}
    latest = close.index[-1]
    for t in close.columns:
        c = close[t].dropna()
        if len(c) < 210 or c.index[-1] != latest:  # too new, or delisted / no recent price
            continue
        ind = indicators(c, volume[t].reindex(c.index).fillna(0))
        last = ind.iloc[-1]
        if pd.isna(last["drawdown"]) or -last["drawdown"] < settings.screen_min_dip:
            continue
        rows.append({"ticker": t, "day_change": c.iloc[-1] / c.iloc[-2] - 1, "drawdown": last["drawdown"], "rsi": last["rsi"]})
        tables[t] = ind
    table = pd.DataFrame(rows).sort_values("drawdown").reset_index(drop=True)
    return table, tables


def analyze_ticker(ticker: str, profile="balanced", settings: Settings = DEFAULT_SETTINGS, period: str = "10y") -> tuple[Analysis, pd.DataFrame, pd.DataFrame]:
    """Full analysis of one stock. Returns (Analysis, OHLCV, indicator table)."""
    ohlcv = download_ohlcv(ticker, period=period)
    ind = indicators(ohlcv["Close"], ohlcv["Volume"])
    if ind.iloc[-1][["rsi", "sma200", "high_252"]].isna().any():
        raise ValueError(f"Not enough price history for '{ticker}' (needs about 1 year).")
    analysis = build_analysis(ticker, ind.iloc[-1], fetch_fundamentals(ticker), profile, settings)
    return analysis, ohlcv, ind


def run_screen(out_path: str | Path = "web/data/dippers.json", universe: list[str] | None = None, settings: Settings = DEFAULT_SETTINGS, max_stocks: int = 250) -> dict:
    """Scan, score every dipper under all three risk profiles, and write the JSON the web app reads."""
    table, tables = scan(universe, settings)
    as_of = max(ind.index[-1] for ind in tables.values()).date().isoformat() if tables else None
    total_dippers = len(table)
    table = table.head(max_stocks)
    with ThreadPoolExecutor(max_workers=8) as pool:
        fundamentals = dict(zip(table["ticker"], pool.map(fetch_fundamentals, table["ticker"])))

    stocks = []
    for _, r in table.iterrows():
        t = r["ticker"]
        ind, f = tables[t], fundamentals[t]
        per_profile = {name: build_analysis(t, ind.iloc[-1], f, name, settings) for name in PROFILES}
        base = per_profile["balanced"]
        stocks.append(
            {
                "ticker": t,
                "name": base.name,
                "sector": base.sector,
                "price": base.price,
                "day_change": r["day_change"],
                "drawdown": base.drawdown,
                "high_52w": base.high_52w,
                "rsi": r["rsi"],
                "fund_score": base.fund_score,
                "tech_score": base.tech_score,
                "composite": base.composite,
                "verdicts": {
                    name: {"verdict": a.verdict, "position_size": a.position_size, "stop_price": a.stop_price, "explanation": a.explanation}
                    for name, a in per_profile.items()
                },
                "components": [c.to_dict() for c in base.components],
                "missing_fundamentals": base.missing_fundamentals,
                "metrics_scored": 8 - base.missing_fundamentals,
                "sparkline": ind["close"].tail(120).round(2).tolist(),
            }
        )

    payload = _clean(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "universe_size": len(universe or get_universe(refresh=False)),
            "as_of": as_of,
            "dip_count": len(stocks),
            "total_dippers": total_dippers,
            "settings": settings.__dict__,
            "profiles": {k: v.__dict__ for k, v in PROFILES.items()},
            "disclaimer": "Educational project. Not investment advice.",
            "stocks": stocks,
        }
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=1))
    return payload
