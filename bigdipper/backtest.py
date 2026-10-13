"""Walk-forward backtest of the price-based half of Big Dipper.

Honesty notes (also in docs/METHODOLOGY.md):
* Signals on day t use only data up to the close of day t; trades execute at the NEXT day's open.
* Yahoo only provides CURRENT fundamentals, so the fundamental gate cannot be tested historically without
  look-ahead bias. This backtest therefore tests the technical dip rule only; the fundamental score is a live overlay.
* Pooled tests over today's S&P 500 members carry survivorship bias (stocks that collapsed and left the index are missing).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .config import DEFAULT_SETTINGS
from .data import download_ohlcv
from .technicals import indicators, technical_score_series

TRADING_DAYS = 252


@dataclass(frozen=True)
class BacktestParams:
    dip_threshold: float = 0.15          # enter only when this far below the 52-week high
    entry_min_tech: float | None = DEFAULT_SETTINGS.min_technical_for_buy  # technical score needed to enter; None = "naive": buy every dip
    stop_loss: float = 0.12
    time_stop: int = 60                  # trading days
    recovery_fraction: float = 0.5       # take profit after recovering this share of the drop from the high
    position_fraction: float = 1.0       # share of equity invested per trade
    cost_bps: float = 5.0                # commission/slippage per side, in basis points


@dataclass
class BacktestResult:
    ticker: str
    params: BacktestParams
    equity: pd.Series
    buy_hold: pd.Series
    benchmark: pd.Series | None
    trades: pd.DataFrame
    metrics: dict

    def summary(self) -> pd.DataFrame:
        cols = {"Strategy": self.metrics["strategy"], "Buy & hold": self.metrics["buy_hold"]}
        if self.metrics.get("benchmark"):
            cols["S&P 500 (SPY)"] = self.metrics["benchmark"]
        return pd.DataFrame(cols)


def _curve_metrics(curve: pd.Series) -> dict:
    daily = curve.pct_change().dropna()
    return {
        "total_return": curve.iloc[-1] / curve.iloc[0] - 1,
        "annual_volatility": daily.std() * np.sqrt(TRADING_DAYS),
        "max_drawdown": (curve / curve.cummax() - 1).min(),
    }


def run_backtest(ohlcv: pd.DataFrame, params: BacktestParams = BacktestParams(), ticker: str = "", benchmark_close: pd.Series | None = None) -> BacktestResult:
    ind = indicators(ohlcv["Close"], ohlcv["Volume"])
    tech = technical_score_series(ind)
    valid = ind[["rsi", "sma200", "high_252", "vol_ratio", "pct_b"]].notna().all(axis=1)
    if valid.sum() < 60:
        raise ValueError(f"Not enough price history to backtest {ticker or 'this stock'} (needs about 1 year plus 3 months of data).")
    start = valid.idxmax()
    dates = ohlcv.index[ohlcv.index >= start]
    open_, close = ohlcv["Open"], ohlcv["Close"]
    cost = params.cost_bps / 10_000

    cash, shares, equity = 1.0, 0.0, []
    entry_px = entry_date = target = None
    held = 0
    pending = None  # "enter" / ("exit", reason), executed at the next open
    trades = []

    for i, d in enumerate(dates):
        if pending == "enter":
            budget = params.position_fraction * cash
            shares = budget * (1 - cost) / open_[d]
            cash -= budget
            entry_px, entry_date, held = open_[d], d, 0
            high = ind["high_252"].shift(1)[d]
            target = entry_px + params.recovery_fraction * max(high - entry_px, 0)
        elif isinstance(pending, tuple):
            proceeds = shares * open_[d] * (1 - cost)
            cash += proceeds
            trades.append({"entry_date": entry_date, "exit_date": d, "entry": entry_px, "exit": open_[d], "return": open_[d] / entry_px * (1 - cost) ** 2 - 1, "days": held, "reason": pending[1]})
            shares, entry_px = 0.0, None
        pending = None

        equity.append(cash + shares * close[d])

        if shares > 0:
            held += 1
            if close[d] <= entry_px * (1 - params.stop_loss):
                pending = ("exit", "stop-loss")
            elif close[d] >= target:
                pending = ("exit", "recovery target")
            elif held >= params.time_stop:
                pending = ("exit", "time stop")
        else:
            dip_ok = -ind["drawdown"][d] >= params.dip_threshold
            tech_ok = params.entry_min_tech is None or tech[d] >= params.entry_min_tech
            if dip_ok and tech_ok:
                pending = "enter"
        if pending and i == len(dates) - 1:
            pending = None  # no next open to trade at

    # close any open trade at the last close so it is counted
    if shares > 0:
        last = dates[-1]
        trades.append({"entry_date": entry_date, "exit_date": last, "entry": entry_px, "exit": close[last], "return": close[last] / entry_px * (1 - cost) ** 2 - 1, "days": held, "reason": "open at end"})

    equity = pd.Series(equity, index=dates, name="Strategy")
    buy_hold = (close[dates] / close[dates[0]]).rename("Buy & hold")
    bench = None
    if benchmark_close is not None:
        b = benchmark_close.reindex(dates).ffill()
        bench = (b / b.iloc[0]).rename("S&P 500 (SPY)")

    trades = pd.DataFrame(trades, columns=["entry_date", "exit_date", "entry", "exit", "return", "days", "reason"])
    strat = _curve_metrics(equity)
    strat.update(
        trades=len(trades),
        win_rate=float((trades["return"] > 0).mean()) if len(trades) else np.nan,
        avg_trade_return=float(trades["return"].mean()) if len(trades) else np.nan,
        exposure=float(trades_in_market(trades, dates).mean()) if len(trades) else 0.0,
    )
    metrics = {"strategy": strat, "buy_hold": _curve_metrics(buy_hold), "benchmark": _curve_metrics(bench) if bench is not None else None}
    return BacktestResult(ticker, params, equity, buy_hold, bench, trades, metrics)


def trades_in_market(trades: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    """Boolean series: was the strategy holding a position on each date?"""
    flag = pd.Series(False, index=dates)
    for _, t in trades.iterrows():
        flag[(dates >= t["entry_date"]) & (dates <= t["exit_date"])] = True
    return flag


def backtest_ticker(ticker: str, params: BacktestParams = BacktestParams(), period: str = "10y", benchmark: str = "SPY") -> BacktestResult:
    ohlcv = download_ohlcv(ticker, period=period)
    bench = download_ohlcv(benchmark, period=period)["Close"] if benchmark else None
    return run_backtest(ohlcv, params, ticker, bench)


def compare_naive_vs_filtered(ohlcv_by_ticker: dict[str, pd.DataFrame], params: BacktestParams = BacktestParams()) -> pd.DataFrame:
    """Pooled trades across many stocks: does the technical filter beat buying every dip?"""
    rows = {}
    for label, p in {"Naive: buy every dip": replace(params, entry_min_tech=None), "Big Dipper technical filter": params}.items():
        trades = []
        for t, df in ohlcv_by_ticker.items():
            try:
                r = run_backtest(df, p, t)
            except Exception:
                continue
            trades.append(r.trades.assign(ticker=t))
        all_trades = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(columns=["return", "days"])
        rows[label] = {
            "trades": len(all_trades),
            "win_rate": (all_trades["return"] > 0).mean(),
            "avg_return_per_trade": all_trades["return"].mean(),
            "median_return_per_trade": all_trades["return"].median(),
            "worst_trade": all_trades["return"].min(),
            "avg_days_held": all_trades["days"].mean(),
        }
    return pd.DataFrame(rows).T


def sensitivity(ohlcv: pd.DataFrame, params: BacktestParams = BacktestParams(), dips=(0.10, 0.15, 0.20, 0.25), tech_mins=(None, 45, 55, 65)) -> pd.DataFrame:
    """Re-run the backtest over a grid of dip thresholds and technical-score cut-offs."""
    out = []
    for dip in dips:
        for tm in tech_mins:
            r = run_backtest(ohlcv, replace(params, dip_threshold=dip, entry_min_tech=tm))
            out.append({"dip_threshold": dip, "min_tech_score": "none" if tm is None else tm, "trades": r.metrics["strategy"]["trades"], "win_rate": r.metrics["strategy"]["win_rate"], "total_return": r.metrics["strategy"]["total_return"], "max_drawdown": r.metrics["strategy"]["max_drawdown"]})
    return pd.DataFrame(out)
