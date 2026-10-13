"""Technical indicators and the 0-100 technical score ("is the price setup a good dip entry?").

Everything here is point-in-time: each indicator value on day t uses only data up to and including day t,
so the same functions are safe to use in the backtest (no look-ahead bias).
"""
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass
class Component:
    group: str       # "fundamental" or "technical"
    name: str
    points: float
    max_points: float
    value: str       # human-readable raw value, e.g. "RSI 27.4"
    note: str        # one-line reason
    missing: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["points"] = round(float(self.points), 1)
        return d


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    out = 100 - 100 / (1 + gain / loss)
    return out.where(loss != 0, 100.0).where(gain.notna())


def indicators(close: pd.Series, volume: pd.Series) -> pd.DataFrame:
    """All indicators used by the score, aligned to the input index."""
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    high_252 = close.rolling(252, min_periods=200).max()
    return pd.DataFrame(
        {
            "close": close,
            "rsi": rsi(close),
            "pct_b": (close - (mid - 2 * std)) / (4 * std),  # 0 = lower Bollinger band, 1 = upper band
            "sma50": close.rolling(50).mean(),
            "sma200": close.rolling(200).mean(),
            "vol_ratio": volume.rolling(5).mean() / volume.rolling(50).mean(),
            "high_252": high_252,
            "drawdown": close / high_252 - 1,
        }
    )


# --- point formulas (each worth up to 25 points; work on scalars and Series) -------------------------
def pts_rsi(rsi_value):
    return 25 * np.clip((50 - rsi_value) / 20, 0, 1)  # full marks at RSI <= 30, none at RSI >= 50


def pts_bollinger(pct_b):
    return 25 * np.clip((0.5 - pct_b) / 0.5, 0, 1)  # full marks at/below the lower band, none at/above the middle


def pts_trend(close, sma200):
    below = np.clip((sma200 - close) / sma200, 0, None)
    return 25 * np.clip(1 - below / 0.30, 0, 1)  # full marks if above the 200-day average, none if 30%+ below


def pts_volume(vol_ratio):
    return 25 * np.clip(vol_ratio - 1, 0, 1)  # full marks if the last 5 days trade at 2x+ the 50-day average


def technical_score_series(ind: pd.DataFrame) -> pd.Series:
    """Vectorised technical score for every day (NaN until all indicators have enough history)."""
    return (
        pts_rsi(ind["rsi"]) + pts_bollinger(ind["pct_b"]) + pts_trend(ind["close"], ind["sma200"]) + pts_volume(ind["vol_ratio"])
    )


def technical_components(row: pd.Series) -> list[Component]:
    """Itemised technical score for one day, for the explanation / waterfall chart."""
    def comp(name, pts, value, note):
        missing = bool(pd.isna(pts))
        return Component("technical", name, 0.0 if missing else float(pts), 25, value, note, missing)

    r, b, v = row["rsi"], row["pct_b"], row["vol_ratio"]
    gap = (row["close"] / row["sma200"] - 1) if pd.notna(row["sma200"]) else np.nan
    return [
        comp("RSI (14)", pts_rsi(r), f"RSI {r:.0f}", "Oversold (RSI near/below 30) is what a dip entry wants." if r <= 35 else "Not oversold yet; the selling may not be exhausted."),
        comp("Bollinger Bands", pts_bollinger(b), f"%B {b:.2f}", "Price is stretched at/below the lower band." if b <= 0.1 else "Price is still inside its normal 20-day range."),
        comp("Long-term trend (200-day)", pts_trend(row["close"], row["sma200"]), f"{gap:+.0%} vs 200-day avg", "Long-term uptrend still intact." if gap >= 0 else "Price is below its 200-day average; the trend is damaged."),
        comp("Volume (capitulation)", pts_volume(v), f"{v:.1f}x normal volume", "Heavy volume suggests panic selling that may be washing out." if v >= 1.5 else "No volume spike; the decline is quiet drift."),
    ]
