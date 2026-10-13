# Methodology

Use this to defend every choice in the presentation. Items marked **JUDGMENT** are our own calls and should be revisited by the team.

## Thesis
A price drop is only an opportunity if the **business** is still sound. Big Dipper separates *dips* (healthy company, temporary selling)
from *falling knives* (deteriorating company) by scoring fundamentals and price action separately, then letting weak fundamentals veto any buy.

## Dip definition
A stock is in a dip when its close is at least **15% below its trailing 52-week high** (`dip_threshold`). The screener lists anything 10%+ down.
**JUDGMENT:** 15% is a common "correction-sized" move for a single stock (the S&P 500 itself uses 10% for a correction). The sensitivity table tests 10-25%.

## Fundamental score (0-100)
Eight metrics, 12.5 points each, scored linearly between a "zero points" value and a "full points" value.

| Pillar | Metric | 0 pts at | Full pts at | Why |
|---|---|---|---|---|
| Valuation | P/E (forward, else trailing) | 40 or more | 15 or less | Cheap vs earnings = more margin of safety. Loss-making firms get 0. |
| Valuation | PEG | 3 or more | 1 or less | Adjusts P/E for growth; PEG near 1 is the classic "fair" mark. |
| Profitability | Return on equity | 0% | 20% | 15-20%+ ROE is typical of high-quality franchises. |
| Profitability | Profit margin | 0% | 20% | Margin = pricing power and cushion in a downturn. |
| Growth | Revenue growth | -5% | +15% | A real dip in a growing business is more likely temporary. |
| Growth | Earnings growth | -10% | +20% | Same logic, more volatile so wider band. |
| Health | Debt-to-equity | 2.0x | 0.5x | Leverage turns a dip into insolvency risk. |
| Health | Free-cash-flow yield | 0% | 5% | Cash generation funds the recovery; FCF yield compares it to price. |

Missing metrics get neutral half marks and are flagged (never guessed). **JUDGMENT:** equal weights, and the bands above; sector-relative bands
(banks have high leverage, software has high P/E) are a known improvement.

## Technical score (0-100)
Four signals, 25 points each, built for the question *"is the selling exhausted and the longer-term trend still intact?"*

| Signal | Full points | Zero points | Why |
|---|---|---|---|
| RSI (14, Wilder) | RSI 30 or below | RSI 50 or above | Oversold readings mark stretched selling. |
| Bollinger %B (20, 2σ) | at/below lower band | at/above the middle | Price statistically stretched below its recent range. |
| 200-day trend | price above 200-day avg | 30% or more below it | A dip inside an uptrend is different from a broken trend. |
| Volume ratio (5-day / 50-day avg) | 2x or more | 1x or less | Heavy-volume selling often marks capitulation; quiet drift does not. |

**JUDGMENT:** these four are plausible, standard and explainable, but they are not the proven best; the backtest checks whether the combination helps.

## Decision rule
`combined = 0.5 × fundamental + 0.5 × technical`

1. Drop under 15%: **Not a Dip**.
2. Fundamental score below the profile's minimum (conservative 55, balanced 45, aggressive 35): **Avoid (Falling Knife)**. *The gate.*
3. Combined ≥ 60 **and technical score ≥ 55**: **Buy the Dip**. (The 55 trigger is exactly the entry rule in the backtest, so the historical evidence applies to the live signal. A strong business with a weak chart is a **Wait**.) Combined ≥ 60 with technical < 55 is also **Wait**. 45-60: **Wait**. Below 45: **Avoid**.

Position size (Buy only) = `min(max_position, risk_budget / stop_loss)`:

| Profile | Risk budget per trade | Stop-loss | Max position | Result |
|---|---|---|---|---|
| Conservative | 0.5% of portfolio | 8% | 5% | 5.0% |
| Balanced | 1.0% | 12% | 10% | 8.3% |
| Aggressive | 2.0% | 18% | 20% | 11.1% |

The logic: if the stop is hit you lose `position × stop`, which equals the risk budget. **JUDGMENT:** the budgets and stops.

## Backtest design
* Signal at the close of day *t* uses only data through day *t*; the trade executes at day *t+1*'s open. Indicators are tested for no look-ahead (`tests/`).
* Entry: dip ≥ threshold **and** technical score ≥ 55. Exit: recover half the drop from the high, 12% stop-loss, or 60 trading days.
* Costs: 5 bps per side. One position at a time, fully invested during a trade.
* Reported: strategy return, buy-and-hold, S&P 500, annualised volatility, max drawdown, number of trades, win rate, average trade, exposure.
* Pooled across ~40 large caps to get enough trades, comparing "buy every dip" vs the technical filter, plus a sensitivity grid.

### What we can and cannot claim
* **The fundamental score is not backtested.** Yahoo gives only today's fundamentals; using them on past dates would leak the future. The backtest tests the technical rule only. Fixing this properly needs point-in-time statements aligned to filing dates.
* Pooled results suffer **survivorship bias** (today's index members) and a **bull-market sample**.
* The technical filter's improvement over "buy every dip" is modest; report it as modest.

## Known weaknesses (say these before the class does)
0. **Cyclical-peak trap:** valuation uses forward P/E and growth uses trailing revenue growth. For cyclicals (memory chips, chemicals, energy) at peak earnings, P/E looks very cheap and growth very high exactly when risk is greatest (e.g. MU P/E 4.5, +379% revenue). A sector-aware or through-the-cycle valuation is the fix.
0b. **Sector clustering:** many Buys can come from one sector (about a third were tech on 2026-10-13). Position sizing does not account for correlation; an investor should cap exposure per sector.
1. Equal weights and thresholds are judgment, not optimised; optimising them on the same data would overfit.
2. Sector effects: P/E and leverage mean different things for banks, utilities and tech.
3. Free data: delays, restatements, missing fields.
4. A strong score is not a prediction; the tool ranks and explains, the investor decides.
