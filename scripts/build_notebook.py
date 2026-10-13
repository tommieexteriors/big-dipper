"""Builds BigDipper.ipynb (the Colab/Jupyter deliverable). Run: python scripts/build_notebook.py"""
from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = []

cells.append(md("""# Big Dipper
### Is this dip a buying opportunity, or a falling knife?

**Customer:** self-directed, long-term retail investors who see a stock fall and ask *"should I buy this?"*
**What it does:** scores the **business** (fundamentals) and the **price setup** (technicals) from 0-100, combines them with a
*quality gate* so a weak business can never be a "Buy", sizes the position for the investor's risk profile, explains every point, and
backtests the price-based rule honestly.

**How to use:** change the settings in section 1, then **Runtime > Run all** (Colab) or **Run All** (Jupyter). No other code needs editing.

*Educational project, not investment advice.*"""))

cells.append(code("""# --- Setup (works locally and in Google Colab) ---
import os, subprocess, sys
REPO_URL = "https://github.com/tommieexteriors/big-dipper.git"   # <- set this once the GitHub repo exists

if "google.colab" in sys.modules and not os.path.exists("bigdipper"):
    subprocess.run(["git", "clone", REPO_URL, "big-dipper"], check=True)
    os.chdir("big-dipper")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)
elif os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
sys.path.insert(0, os.getcwd())

import warnings; warnings.filterwarnings("ignore")
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
from bigdipper import analyze_ticker, backtest_ticker, run_backtest, compare_naive_vs_filtered, sensitivity, BacktestParams, PROFILES, DEFAULT_SETTINGS
from bigdipper.data import download_ohlcv
from bigdipper.plots import plot_price, plot_waterfall, plot_backtest, plot_trade_returns
pd.options.display.float_format = "{:,.3f}".format
plt.rcParams["figure.dpi"] = 110"""))

cells.append(md("## 1. Settings (the only cell you need to edit)"))
cells.append(code("""TICKER = "NKE"                 # any US stock symbol
PROFILE = "balanced"           # "conservative", "balanced" or "aggressive"
PERIOD = "10y"                 # how much price history to download (backtest uses all of it)
DIP_THRESHOLD = 0.15           # a 'dip' = this far below the 52-week high (0.15 = 15%)

SETTINGS = type(DEFAULT_SETTINGS)(dip_threshold=DIP_THRESHOLD)
print(f"Risk profile '{PROFILE}':", PROFILES[PROFILE])"""))

cells.append(md("""## 2. Data collection and cleaning
Prices and volume come from Yahoo Finance (`yfinance`), adjusted for splits and dividends. Cleaning drops empty rows and duplicate dates,
forward-fills gaps of up to 3 days, and removes non-positive prices. Fundamentals are the *current* figures Yahoo reports; anything missing is
flagged and given neutral marks rather than guessed."""))
cells.append(code("""analysis, ohlcv, ind = analyze_ticker(TICKER, PROFILE, SETTINGS, period=PERIOD)
print(f"{analysis.name} ({analysis.ticker}), sector: {analysis.sector}")
print(f"{len(ohlcv):,} trading days from {ohlcv.index[0].date()} to {ohlcv.index[-1].date()}")
print("Missing values after cleaning:", int(ohlcv.isna().sum().sum()))
display(ohlcv.tail())"""))

cells.append(md("## 3. Where is the stock relative to its high?"))
cells.append(code("""print(f"Price ${analysis.price:,.2f}  |  52-week high ${analysis.high_52w:,.2f}  |  {analysis.drawdown:.1%} from the high")
fig = plot_price(ind, TICKER, DIP_THRESHOLD); plt.show()"""))

cells.append(md("""## 4. Fundamental analysis: is the business healthy? (0-100)
Four pillars, 25 points each: **valuation** (P/E, PEG), **profitability** (ROE, profit margin), **growth** (revenue, earnings),
**financial health** (debt-to-equity, free-cash-flow yield). Companies with negative equity (heavy buybacks) and financials (banks) get substitute metrics because the usual ones are meaningless for them; metrics Yahoo does not report are left out of the score, not guessed. Thresholds are in `bigdipper/fundamentals.py` and justified in `docs/METHODOLOGY.md`."""))
cells.append(code("""fund = pd.DataFrame([c.to_dict() for c in analysis.components if c.group == "fundamental"])
display(fund[["name", "value", "points", "max_points", "note"]])
print(f"Fundamental score: {analysis.fund_score:.0f} / 100")"""))

cells.append(md("""## 5. Technical analysis: is the price setup a good entry? (0-100)
Four methods, 25 points each: **RSI** (oversold?), **Bollinger Bands** (stretched below normal range?), **200-day trend** (is the long-term
uptrend intact or broken?), and **volume** (is there a capitulation spike, or quiet drift?)."""))
cells.append(code("""tech = pd.DataFrame([c.to_dict() for c in analysis.components if c.group == "technical"])
display(tech[["name", "value", "points", "max_points", "note"]])
print(f"Technical score: {analysis.tech_score:.0f} / 100")"""))

cells.append(md("""## 6. The decision
`combined = 50% business + 50% setup`. **Gate:** if the business score is below the risk profile's minimum, the answer is *Avoid* no matter how
oversold the chart looks. Otherwise: **60+ = Buy the Dip**, **45-60 = Wait**, **below 45 = Avoid**. A buy comes with a position size and stop-loss
derived from the investor's risk budget."""))
cells.append(code("""display(Markdown(f"### {analysis.ticker}: **{analysis.verdict}**"))
print(analysis.explanation)
fig = plot_waterfall(analysis); plt.show()

from bigdipper.data import fetch_fundamentals
from bigdipper.decision import build_analysis
fundamentals = fetch_fundamentals(TICKER)
rows = []
for name in PROFILES:
    a = build_analysis(TICKER, ind.iloc[-1], fundamentals, name, SETTINGS)
    rows.append({"profile": name, "verdict": a.verdict, "position (% of portfolio)": a.position_size * 100, "stop price": a.stop_price})
display(pd.DataFrame(rows).set_index("profile"))"""))

cells.append(md("""## 7. Strategy testing (price-based rule)
**Rule:** enter when the stock is at least `dip_threshold` below its 52-week high *and* the technical score is at least 55. Exit at a recovery target
(half the drop from the high), a stop-loss, or after 60 trading days. Signals use only data up to that day's close and trades execute at the **next day's open**
(no look-ahead bias). Costs: 5 bps per side.

> **Honest limitation:** Yahoo only provides *current* fundamentals, so the fundamental gate cannot be backtested without look-ahead bias.
> The backtest tests the technical half of Big Dipper; the fundamental score is a live overlay."""))
cells.append(code("""PARAMS = BacktestParams(dip_threshold=DIP_THRESHOLD)
result = backtest_ticker(TICKER, PARAMS, period=PERIOD)
display(result.summary())
fig = plot_backtest(result); plt.show()
display(result.trades.tail(10))"""))

cells.append(md("""## 8. Does the technical filter actually help?
Single stocks have too few trades to judge. Here we pool trades across a basket of large companies and compare **"buy every dip"** against **Big Dipper's filter**.
(Survivorship bias warning: the basket is today's large caps, so companies that collapsed are missing, which flatters both versions.)"""))
cells.append(code("""BASKET = "AAPL MSFT NVDA AMZN GOOGL META TSLA NKE DIS INTC PFE KO PEP WMT HD JPM BAC XOM CVX BA CAT MMM T VZ CSCO ORCL ADBE CRM AMD QCOM TXN MCD SBUX TGT COST LOW UNH JNJ MRK".split()
basket_data = {t: download_ohlcv(t, PERIOD) for t in BASKET}
comparison = compare_naive_vs_filtered(basket_data, PARAMS)
display(comparison)"""))
cells.append(code("""# Higher technical-score cut-offs: fewer trades, and (in this sample) a higher win rate and smaller worst loss
rows = {}
for m in [None, 45, 55, 65, 75]:
    from dataclasses import replace
    c = compare_naive_vs_filtered(basket_data, replace(PARAMS, entry_min_tech=m)).iloc[1 if m is not None else 0]
    rows["no filter" if m is None else f"score >= {m}"] = c
display(pd.DataFrame(rows).T)"""))

cells.append(md("## 9. Sensitivity: how fragile are the results to our assumptions?"))
cells.append(code("""grid = sensitivity(ohlcv, PARAMS)
display(grid)
display(grid.pivot(index="dip_threshold", columns="min_tech_score", values="total_return").style.format("{:.1%}").set_caption(f"{TICKER}: strategy total return by dip threshold and technical cut-off"))"""))

cells.append(md("""## 10. Today's biggest dippers (market screener)
The same engine run across the whole S&P 500. This is what feeds the Big Dipper website: a list of every stock that is down, each clickable
to its score and explanation. Set `RUN_SCREEN = True` to scan (about 30 seconds)."""))
cells.append(code("""RUN_SCREEN = False
if RUN_SCREEN:
    from bigdipper import run_screen
    payload = run_screen("web/data/dippers.json")
    s = pd.DataFrame([{"ticker": x["ticker"], "name": x["name"], "from high": x["drawdown"], "1-day": x["day_change"],
                       "business": x["fund_score"], "setup": x["tech_score"], "verdict": x["verdicts"][PROFILE]["verdict"]} for x in payload["stocks"]])
    display(s.head(25))
    print(s["verdict"].value_counts())"""))

cells.append(md("""## 11. Limitations and risks
* **Fundamentals are not backtested.** Only current fundamentals are available; the backtest covers the technical rule only.
* **Survivorship bias.** Basket and screener use today's index members.
* **Bull-market sample.** Ten years of mostly rising markets flatter any buy-the-dip rule. Dips in 2008 or 2000-02 looked very different.
* **Thresholds are judgment calls.** See the sensitivity tables; results move when the thresholds move.
* **Yahoo data quality.** Free data can be delayed, restated, or missing; missing fundamentals get neutral marks and a warning.
* **Not advice.** The tool ranks and explains; the investor decides."""))

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
Path(__file__).resolve().parent.parent.joinpath("BigDipper.ipynb").write_text(nbf.writes(nb))
print("wrote BigDipper.ipynb")
