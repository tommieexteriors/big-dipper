# Big Dipper

**Is this dip a buying opportunity, or a falling knife?**

Big Dipper scans the S&P 500 for stocks that are down, scores each one on **business quality** (fundamentals) and
**price setup** (technicals), and tells an investor whether the dip looks like a bargain, a wait, or a trap, with a
position size and stop-loss matched to their risk profile and a plain-English explanation of every point.

FINC 314 Stock Trading Vibe Coding Project. *Educational only, not investment advice.*

## How it works

| Step | What happens | Code |
|---|---|---|
| 1. Data | S&P 500 universe, adjusted prices and volume, current fundamentals; cleaned | `bigdipper/data.py` |
| 2. Fundamental score (0-100) | Valuation (P/E, PEG), profitability (ROE, margin), growth (revenue, earnings), health (debt/equity, FCF yield) | `bigdipper/fundamentals.py` |
| 3. Technical score (0-100) | RSI, Bollinger Bands, 200-day trend, volume capitulation | `bigdipper/technicals.py` |
| 4. Decision | 50/50 blend, **quality gate** (weak business can never be a Buy), position sizing by risk profile | `bigdipper/decision.py` |
| 5. Backtest | Walk-forward, next-open execution, costs, naive-vs-filtered comparison, sensitivity grid | `bigdipper/backtest.py` |
| 6. Screener | Scores every dipping S&P 500 stock, writes `web/data/dippers.json` for the web app | `bigdipper/screener.py` |

Verdicts: **Buy the Dip**, **Wait**, **Avoid (Falling Knife)**, or **Not a Dip**.
Risk profiles: **conservative**, **balanced**, **aggressive** (different quality gates, stop-losses and position caps).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m bigdipper analyze NKE --profile balanced   # score one stock
python -m bigdipper backtest NKE                     # backtest the technical rule
python -m bigdipper screen                           # scan the S&P 500 -> web/data/dippers.json
pytest                                               # unit tests (offline, fast)
python scripts/stress.py                             # live stress test: odd tickers, bad input, data checks
```

The graded deliverable is **`BigDipper.ipynb`** (open in Jupyter or Google Colab and Run All; edit only the settings cell).
Regenerate it with `python scripts/build_notebook.py`.

## Web app

`web/` is a static site (plain HTML, CSS and JavaScript, no build step) with a galaxy theme: a field of drifting `$` stars and the
Big Dipper constellation drawn as seven gold dollar signs. It reads `web/data/dippers.json`, which a GitHub Action refreshes every weekday
after the market closes (`.github/workflows/refresh.yml`). Each refresh is a commit, so Vercel redeploys the site with fresh data automatically.

Features: risk-profile toggle (conservative / balanced / aggressive), verdict filters, search, sector filter, sorting, and a detail view per stock
with the plain-English explanation, every scored component, position size, stop-loss and price chart.

```bash
python3 -m http.server 8765 --directory web    # then open http://localhost:8765
```

**Deploy (Vercel):** import the GitHub repo, set **Root Directory** to `web`, framework preset **Other**, no build command. Done.

## Documentation

* [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md): every threshold and why we chose it, plus limitations
* [`docs/AI_LOG.md`](docs/AI_LOG.md): running log of what GenAI got wrong and how we corrected it (feeds the reflections)
