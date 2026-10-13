"""Big Dipper: is this dip a buying opportunity or a falling knife?"""
from .backtest import BacktestParams, backtest_ticker, compare_naive_vs_filtered, run_backtest, sensitivity
from .config import DEFAULT_SETTINGS, PROFILES, Settings
from .screener import analyze_ticker, run_screen

__all__ = [
    "BacktestParams",
    "DEFAULT_SETTINGS",
    "PROFILES",
    "Settings",
    "analyze_ticker",
    "backtest_ticker",
    "compare_naive_vs_filtered",
    "run_backtest",
    "run_screen",
    "sensitivity",
]
