import numpy as np
import pandas as pd
import pytest

from bigdipper.backtest import BacktestParams, run_backtest
from bigdipper.config import PROFILES, VERDICT_AVOID, VERDICT_BUY, VERDICT_NOT_A_DIP, VERDICT_WAIT
from bigdipper.decision import decide
from bigdipper.fundamentals import fundamental_components, linear
from bigdipper.technicals import indicators, rsi, technical_score_series


def synthetic(n=900, seed=1, drift=0.0004, vol=0.015):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    idx = pd.bdate_range("2018-01-01", periods=n)
    s = pd.Series(close, index=idx)
    return pd.DataFrame({"Open": s.shift(1).fillna(s.iloc[0]), "High": s * 1.01, "Low": s * 0.99, "Close": s, "Volume": rng.integers(1_000_000, 2_000_000, n)}, index=idx)


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 100, dtype=float))
    down = up[::-1].reset_index(drop=True)
    assert rsi(up).iloc[-1] == 100
    assert rsi(down).iloc[-1] < 1
    assert rsi(synthetic()["Close"]).dropna().between(0, 100).all()


def test_indicators_have_no_lookahead():
    """The indicator value on day t must not change if we delete everything after day t."""
    df = synthetic()
    full = indicators(df["Close"], df["Volume"])
    cut = 600
    part = indicators(df["Close"].iloc[: cut + 1], df["Volume"].iloc[: cut + 1])
    pd.testing.assert_series_equal(full.iloc[cut], part.iloc[cut], check_names=False)
    pd.testing.assert_series_equal(technical_score_series(full).iloc[[cut]], technical_score_series(part).iloc[[cut]])


def test_linear_scoring_direction_and_missing():
    assert linear(10, 40, 15, 12.5) == 12.5  # better than 'good' caps at max
    assert linear(50, 40, 15, 12.5) == 0
    assert linear(27.5, 40, 15, 12.5) == pytest.approx(6.25)
    assert linear(None, 0, 1, 10) is None


def test_missing_fundamentals_get_neutral_marks_and_are_flagged():
    comps = fundamental_components({})
    assert all(c.missing for c in comps)
    assert sum(c.points for c in comps) == pytest.approx(50)


def test_unprofitable_company_scores_zero_on_valuation():
    comps = {c.name: c for c in fundamental_components({"profit_margin": -0.2, "pe": None, "peg": None})}
    assert comps["P/E ratio"].points == 0 and not comps["P/E ratio"].missing


def test_fundamental_gate_blocks_buy_even_when_chart_is_perfect():
    p = PROFILES["balanced"]
    verdict, _, size = decide(-0.30, fund_score=30, tech_score=100, profile=p)
    assert verdict == VERDICT_AVOID and size == 0


def test_decision_paths():
    p = PROFILES["balanced"]
    assert decide(-0.05, 90, 90, p)[0] == VERDICT_NOT_A_DIP
    assert decide(-0.25, 80, 70, p)[0] == VERDICT_BUY
    assert decide(-0.25, 60, 40, p)[0] == VERDICT_WAIT
    assert decide(-0.25, 50, 30, p)[0] == VERDICT_AVOID


def test_position_size_respects_risk_profile():
    sizes = {name: decide(-0.25, 90, 90, p)[2] for name, p in PROFILES.items()}
    assert sizes["conservative"] < sizes["balanced"] < sizes["aggressive"]
    assert sizes["conservative"] <= PROFILES["conservative"].max_position


def test_conservative_is_pickier_than_aggressive():
    # fundamental score of 40: aggressive (min 35) can buy, conservative (min 55) cannot
    assert decide(-0.25, 40, 95, PROFILES["aggressive"])[0] == VERDICT_BUY
    assert decide(-0.25, 40, 95, PROFILES["conservative"])[0] == VERDICT_AVOID


def make_crash_and_recovery():
    idx = pd.bdate_range("2018-01-01", periods=700)
    close = np.concatenate([np.linspace(100, 200, 400), np.linspace(200, 150, 40), np.linspace(150, 210, 260)])
    s = pd.Series(close, index=idx)
    vol = pd.Series(1_000_000.0, index=idx)
    vol.iloc[400:440] = 3_000_000
    return pd.DataFrame({"Open": s, "High": s, "Low": s, "Close": s, "Volume": vol}, index=idx)


def test_backtest_trades_and_accounting():
    df = make_crash_and_recovery()
    r = run_backtest(df, BacktestParams(entry_min_tech=None, cost_bps=0, stop_loss=0.5), "SYN")
    assert len(r.trades) >= 1
    t = r.trades.iloc[0]
    assert t["entry_date"] > df.index[400]  # entered only after the dip began
    assert t["exit_date"] > t["entry_date"]
    assert t["return"] == pytest.approx(t["exit"] / t["entry"] - 1)
    assert r.equity.iloc[0] == pytest.approx(1.0)
    assert r.metrics["strategy"]["max_drawdown"] <= 0


def test_backtest_executes_on_next_open_not_signal_close():
    df = make_crash_and_recovery()
    r = run_backtest(df, BacktestParams(entry_min_tech=None, cost_bps=0, stop_loss=0.5))
    first = r.trades.iloc[0]
    pos = df.index.get_loc(first["entry_date"])
    assert first["entry"] == df["Open"].iloc[pos]
    ind = indicators(df["Close"], df["Volume"])
    assert -ind["drawdown"].iloc[pos - 1] >= 0.15  # the signal came from the PREVIOUS day


def test_stricter_filter_never_adds_trades():
    df = synthetic(n=1500, seed=3, vol=0.025)
    naive = run_backtest(df, BacktestParams(entry_min_tech=None)).metrics["strategy"]["trades"]
    filtered = run_backtest(df, BacktestParams(entry_min_tech=70)).metrics["strategy"]["trades"]
    assert filtered <= naive


def test_sparse_fundamentals_never_buy():
    from bigdipper.decision import build_analysis
    ind = indicators(synthetic(n=900)["Close"], synthetic(n=900)["Volume"]).iloc[-1].copy()
    ind["drawdown"], ind["rsi"], ind["pct_b"], ind["vol_ratio"] = -0.3, 20.0, 0.0, 2.0  # perfect chart
    ind["sma200"] = ind["close"]
    a = build_analysis("ETF", ind, {}, "aggressive")  # no fundamentals at all
    assert a.verdict != VERDICT_BUY and a.position_size == 0 and "Data warning" in a.explanation


def test_backtest_rejects_short_history():
    with pytest.raises(ValueError):
        run_backtest(synthetic(n=150), BacktestParams(), "NEW")


def test_empty_ticker_message():
    from bigdipper.data import download_ohlcv
    with pytest.raises(ValueError, match="ticker"):
        download_ohlcv("  ")


def test_buy_requires_technical_trigger_matching_backtest():
    p = PROFILES["balanced"]
    # great business, composite above 60, but chart not set up (tech 40 < 55): Wait, never Buy
    verdict, composite, size = decide(-0.25, fund_score=90, tech_score=40, profile=p)
    assert composite >= 60 and verdict == VERDICT_WAIT and size == 0
    assert decide(-0.25, 90, 55, p)[0] == VERDICT_BUY
    from bigdipper.config import DEFAULT_SETTINGS
    assert BacktestParams().entry_min_tech == DEFAULT_SETTINGS.min_technical_for_buy
