# GenAI log (feeds the individual vibe-coding reflections)

Add an entry whenever Claude gets something wrong, suggests something you hadn't thought of, or you make a judgment call. Be specific; the reflections ask for exactly this.

## Prompts that worked
* "Combine ideas #1 and #6 and make sure everything checks the rubric and the project description" (a checklist-style constraint produced a requirement-by-requirement plan).

## Things Claude suggested that we hadn't planned
* Hard **quality gate**: weak fundamentals can veto a Buy regardless of the chart (the core "dip vs falling knife" idea).
* **Naive vs filtered** comparison to test whether the technical filter actually adds value.
* Daily-refreshed JSON so the website needs no Python server.

## Mistakes and corrections
| Date | What happened | How we fixed it | Who decided |
|---|---|---|---|
| 2026-10-13 | Claude first created a project folder in the wrong location (inside another project) | We said to use the FINC 314 school folder; Claude cleaned up the stray folder | team |
| 2026-10-13 | Backtest first computed trade return and exposure with convoluted expressions | Simplified and covered by tests | Claude, reviewed by team |
| 2026-10-13 | Stress test: ETFs, indexes and crypto got a fake fundamental score of ~50 (all metrics missing -> neutral marks) and could have been rated Buy | Added rule: 4+ of 8 fundamentals missing means never Buy, with a visible data warning | Claude found it, team to confirm threshold |
| 2026-10-13 | Stress test: empty ticker gave a cryptic error; JSON had no price date; delisted tickers could slip into the screener | Clear error messages, `as_of` date in JSON, stale-price filter | Claude |
| 2026-10-13 | Claude's own stress-test check for `as_of` passed even though the field was missing (sloppy assertion) | Rewrote the check so it fails when the field is absent | Claude, caught on review |
| 2026-10-13 | Yahoo reports debt-to-equity as a percentage (78 = 0.78x); easy to mis-scale | Divided by 100 in `data.py` | Claude |

## Judgment calls the humans made or must confirm
* [ ] Dip threshold (15%) and screener minimum (10%)
* [ ] 50/50 weighting of fundamentals and technicals
* [ ] Risk-profile budgets, stops and caps
* [ ] Whether to attempt point-in-time fundamentals later

## Honest findings to quote
* Pooled over ~40 large caps (10y), the technical filter raised win rate from 60.1% (buy every dip) to 60.6-62.8% (score cut-off 55-65) and cut the worst trade from -36% to -26%; the gain is modest and the sample is survivorship-biased and bullish.
* NKE example: strategy +2% vs buy-and-hold -31% vs SPY +264%; the tool protects capital in a falling stock but does not beat the index.

## Review of the live Buy list (2026-10-13)
* Claude reviewed the 41 Buys and found the live rule was looser than the tested rule: stocks with technical scores in the 30s (RSI ~45-49) could be a Buy on fundamentals alone, but the backtest only enters at technical >= 55. Fixed by adding the same 55 trigger to the live Buy rule so the historical evidence applies to it.
* Also documented: cyclical-peak valuation trap (cheap forward P/E and huge growth at peak earnings) and sector clustering of Buys. Both are limitations, not fixed.
