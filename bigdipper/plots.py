"""Charts: price with dip shading, score waterfall, equity curves, and trade markers."""
import matplotlib.pyplot as plt
import pandas as pd

GREEN, RED, BLUE, GREY = "#2e8b57", "#c0392b", "#2c6fbb", "#888888"


def plot_price(ind: pd.DataFrame, ticker: str, dip_threshold: float = 0.15, days: int = 500):
    d = ind.tail(days)
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    ax.plot(d.index, d["close"], color=BLUE, lw=1.6, label="Close")
    ax.plot(d.index, d["sma50"], color="#e69f00", lw=1, label="50-day avg")
    ax.plot(d.index, d["sma200"], color=GREY, lw=1, label="200-day avg")
    ax.plot(d.index, d["high_252"], color=GREEN, lw=1, ls="--", label="52-week high")
    ax.fill_between(d.index, d["close"], d["high_252"], where=(-d["drawdown"] >= dip_threshold), color=RED, alpha=0.15, label=f"Dip (>{dip_threshold:.0%} below high)")
    ax.set_title(f"{ticker}: price, trend and dip zones")
    ax.legend(loc="best", ncol=3, fontsize=8)
    ax.grid(alpha=0.2)
    ax2.plot(d.index, d["rsi"], color="#7d3c98", lw=1.2)
    ax2.axhline(30, color=RED, ls=":", lw=1)
    ax2.axhline(70, color=GREEN, ls=":", lw=1)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI (14)")
    ax2.grid(alpha=0.2)
    fig.tight_layout()
    return fig


def plot_waterfall(analysis, group: str | None = None):
    """Horizontal bars: how many points each signal earned out of its maximum."""
    comps = [c for c in analysis.components if group in (None, c.group)]
    comps = sorted(comps, key=lambda c: (c.group, -c.points))
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(comps) + 1.6))
    y = range(len(comps))
    ax.barh(y, [c.max_points for c in comps], color="#e8e8e8")
    ax.barh(y, [c.points for c in comps], color=[GREEN if c.group == "fundamental" else BLUE for c in comps], hatch=None)
    for i, c in enumerate(comps):
        ax.text(c.max_points + 0.3, i, "no data, left out of score" if c.missing else f"{c.points:.1f}/{c.max_points:g}  {c.value}", va="center", fontsize=8)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{c.name}" for c in comps])
    ax.invert_yaxis()
    ax.set_xlim(0, 25)
    ax.set_title(f"{analysis.ticker}: {analysis.verdict}   (business {analysis.fund_score:.0f} | setup {analysis.tech_score:.0f} | combined {analysis.composite:.0f})")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=GREEN), plt.Rectangle((0, 0), 1, 1, color=BLUE)], labels=["Fundamental", "Technical"], loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


def plot_backtest(result):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(result.equity.index, result.equity, color=BLUE, lw=1.8, label="Big Dipper strategy")
    ax.plot(result.buy_hold.index, result.buy_hold, color=GREY, lw=1.3, label=f"Buy & hold {result.ticker}")
    if result.benchmark is not None:
        ax.plot(result.benchmark.index, result.benchmark, color="#e69f00", lw=1.1, label="S&P 500 (SPY)")
    for _, t in result.trades.iterrows():
        win = t["return"] > 0
        ax.axvspan(t["entry_date"], t["exit_date"], color=GREEN if win else RED, alpha=0.12)
    ax.set_title(f"{result.ticker}: growth of $1 (green = winning trades, red = losing trades)")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return fig


def plot_trade_returns(trades: pd.DataFrame, title: str = "Trade returns"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(trades["return"] * 100, bins=25, color=BLUE, alpha=0.8)
    ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("Return per trade (%)")
    ax.set_title(title)
    fig.tight_layout()
    return fig
