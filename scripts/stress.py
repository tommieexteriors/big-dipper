"""Live stress test: odd tickers, bad input, determinism, score bounds. Run: python scripts/stress.py"""
import json, math, random, sys, traceback, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np, pandas as pd
from bigdipper import analyze_ticker, backtest_ticker, BacktestParams, PROFILES
from bigdipper.data import get_universe

fails = []
def check(name, fn):
    try:
        out = fn(); print(f"PASS  {name}" + (f"  -> {out}" if out else ""))
    except Exception as e:
        fails.append(name); print(f"FAIL  {name}: {type(e).__name__}: {str(e)[:150]}")

def expect_error(ticker):
    try: analyze_ticker(ticker)
    except ValueError as e: return f"clean ValueError: {str(e)[:60]}"
    raise AssertionError("no error raised")

check("invalid ticker -> clean error", lambda: expect_error("ZZZZNOTREAL"))
check("empty ticker -> clean error", lambda: expect_error(""))
for t in ["SPY", "BRK-B", "TSLA", "GME", "COIN", "RIVN", "ARM", "SMCI", "BTC-USD", "^GSPC", "AAPL"]:
    def f(t=t):
        a, o, i = analyze_ticker(t)
        assert 0 <= a.fund_score <= 100 and 0 <= a.tech_score <= 100, (a.fund_score, a.tech_score)
        assert not math.isnan(a.composite)
        return f"{a.verdict}, F={a.fund_score:.0f} T={a.tech_score:.0f} missing={a.missing_fundamentals}"
    check(f"analyze {t}", f)

def determinism():
    a1 = analyze_ticker("MSFT")[0]; a2 = analyze_ticker("MSFT")[0]
    assert (a1.fund_score, a1.tech_score, a1.verdict) == (a2.fund_score, a2.tech_score, a2.verdict)
check("deterministic repeat run (MSFT)", determinism)

for t in ["NVDA", "INTC", "SPY", "PYPL", "META"]:
    def f(t=t):
        r = backtest_ticker(t, BacktestParams())
        s = r.metrics["strategy"]
        assert s["max_drawdown"] <= 0 and -1 < s["total_return"] < 50
        assert (r.trades["exit_date"] >= r.trades["entry_date"]).all()
        assert (r.trades["return"] > -1).all()
        return f"trades={s['trades']} ret={s['total_return']:.1%} bh={r.metrics['buy_hold']['total_return']:.1%}"
    check(f"backtest {t}", f)

def short_history():
    try: backtest_ticker("ARM", BacktestParams(), period="1y")
    except Exception as e: return f"{type(e).__name__}: {str(e)[:70]}"
    return "ran"
check("backtest with <1y history", short_history)

def random_sample():
    random.seed(7); u = random.sample(get_universe(refresh=False), 25); bad = []
    for t in u:
        try:
            a = analyze_ticker(t)[0]
            assert 0 <= a.fund_score <= 100 and 0 <= a.tech_score <= 100
        except Exception as e: bad.append(f"{t}:{type(e).__name__}")
    assert not bad, bad
    return "25 random S&P names ok"
check("random 25-stock sample", random_sample)

def json_valid():
    d = json.load(open("web/data/dippers.json"))
    txt = open("web/data/dippers.json").read(); assert "NaN" not in txt and "Infinity" not in txt
    for s in d["stocks"]:
        assert -1 < s["drawdown"] < 0 and 0 <= s["fund_score"] <= 100 and 0 <= s["tech_score"] <= 100
        assert len(s["components"]) == 12 and len(s["sparkline"]) > 50
        assert set(s["verdicts"]) == set(PROFILES)
        for v in s["verdicts"].values(): assert v["explanation"]
    ds = [s["drawdown"] for s in d["stocks"]]; assert ds == sorted(ds)
    return f"{len(d['stocks'])} stocks valid"
check("screener JSON schema + sanity", json_valid)

def as_of_check():
    d = json.load(open("web/data/dippers.json"))
    assert d.get("as_of"), "missing as_of"
    latest_bar = pd.Timestamp(d["as_of"]); gap = (pd.Timestamp.now().normalize() - latest_bar).days
    assert gap <= 5, f"data is {gap} days old"
    return f"as_of={d['as_of']}"
check("JSON has fresh as_of price date", as_of_check)

def sparse_never_buy():
    for t in ["SPY", "QQQ", "BTC-USD"]:
        for p in PROFILES:
            a = analyze_ticker(t, p)[0]
            assert a.verdict != "Buy the Dip" and a.position_size == 0, (t, p)
    return "ETF/crypto never Buy"
check("sparse fundamentals can never be Buy", sparse_never_buy)

check("empty ticker message", lambda: expect_error("  "))

print("\nFAILED:", fails if fails else "none"); sys.exit(1 if fails else 0)
