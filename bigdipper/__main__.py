"""Command line: python -m bigdipper screen | analyze TICKER | backtest TICKER"""
import argparse

from .backtest import BacktestParams, backtest_ticker
from .config import PROFILES
from .screener import analyze_ticker, run_screen


def main() -> None:
    parser = argparse.ArgumentParser(prog="bigdipper", description="Dip or falling knife?")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("screen", help="scan the S&P 500 and write the JSON the web app reads")
    s.add_argument("--out", default="web/data/dippers.json")
    s.add_argument("--max-stocks", type=int, default=250)

    a = sub.add_parser("analyze", help="score one stock")
    a.add_argument("ticker")
    a.add_argument("--profile", choices=PROFILES, default="balanced")

    b = sub.add_parser("backtest", help="backtest the technical dip rule on one stock")
    b.add_argument("ticker")
    b.add_argument("--period", default="10y")

    args = parser.parse_args()
    if args.cmd == "screen":
        payload = run_screen(args.out, max_stocks=args.max_stocks)
        print(f"Wrote {payload['dip_count']} dipping stocks to {args.out}")
    elif args.cmd == "analyze":
        analysis, _, _ = analyze_ticker(args.ticker.upper(), args.profile)
        print(f"{analysis.ticker} ({analysis.name}): {analysis.verdict}\n")
        print(analysis.explanation)
        for c in analysis.components:
            print(f"  [{c.group[:4]}] {c.name:<26} {c.points:5.1f}/{c.max_points:<5g} {c.value}")
    else:
        r = backtest_ticker(args.ticker.upper(), BacktestParams(), args.period)
        print(r.summary().round(3).to_string())
        print(f"\nTrades: {len(r.trades)}")


if __name__ == "__main__":
    main()
