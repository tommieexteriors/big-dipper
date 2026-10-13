"""Data collection and cleaning: S&P 500 universe, price/volume history, fundamentals."""
from datetime import datetime
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNIVERSE_FILE = DATA_DIR / "sp500_tickers.txt"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def get_universe(refresh: bool = True) -> list[str]:
    """S&P 500 tickers. Tries Wikipedia first, falls back to the copy saved in data/."""
    if refresh:
        try:
            import requests

            html = requests.get(WIKI_URL, headers={"User-Agent": "Mozilla/5.0 (BigDipper student project)"}, timeout=20).text
            table = pd.read_html(StringIO(html))[0]
            tickers = sorted(table["Symbol"].astype(str).str.replace(".", "-", regex=False).unique())
            if len(tickers) > 400:
                DATA_DIR.mkdir(exist_ok=True)
                UNIVERSE_FILE.write_text("\n".join(tickers) + "\n")
                return tickers
        except Exception as exc:  # network or parsing problems are not fatal
            print(f"[data] could not refresh S&P 500 list ({exc}); using saved copy")
    return [t for t in UNIVERSE_FILE.read_text().split() if t]


MARKET_TZ = ZoneInfo("America/New_York")
SESSION_DONE_HOUR, SESSION_DONE_MINUTE = 16, 20  # US close is 16:00 ET; wait a few minutes for the final print


def session_in_progress(last_bar_date, now: datetime | None = None) -> bool:
    """True if the last daily bar is today's session and the US market has not finished it yet."""
    now = (now or datetime.now(MARKET_TZ)).astimezone(MARKET_TZ)
    if last_bar_date != now.date():
        return False
    return (now.hour, now.minute) < (SESSION_DONE_HOUR, SESSION_DONE_MINUTE)


def drop_unfinished_session(df, now: datetime | None = None):
    """The model is built on closing prices, so a half-finished day must not be treated as a close."""
    if len(df) and session_in_progress(df.index[-1].date(), now):
        return df.iloc[:-1]
    return df


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Drop empty rows, forward-fill short gaps (max 3 days), remove non-positive prices."""
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(how="all")
    df = df.ffill(limit=3).dropna(subset=["Close"])
    df = df[df["Close"] > 0]
    df["Volume"] = df["Volume"].fillna(0)
    return df


def download_ohlcv(ticker: str, period: str = "10y", start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Daily split/dividend-adjusted OHLCV for one ticker as a flat DataFrame."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Please enter a ticker symbol.")
    kwargs = dict(start=start, end=end) if start else dict(period=period)
    raw = yf.download(ticker, auto_adjust=True, progress=False, **kwargs)
    if raw is None or raw.empty:
        raise ValueError(f"No price data returned for '{ticker}'. Check the ticker symbol.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return drop_unfinished_session(clean_ohlcv(raw[["Open", "High", "Low", "Close", "Volume"]]))


def download_universe(tickers: list[str], period: str = "2y", batch: int = 100) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Close and Volume for many tickers (columns = tickers), downloaded in batches."""
    closes, volumes = [], []
    for i in range(0, len(tickers), batch):
        chunk = tickers[i : i + batch]
        raw = yf.download(chunk, period=period, auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            continue
        if not isinstance(raw.columns, pd.MultiIndex):  # single-ticker chunk
            raw.columns = pd.MultiIndex.from_product([raw.columns, chunk[:1]])
        closes.append(raw["Close"])
        volumes.append(raw["Volume"])
    close = pd.concat(closes, axis=1).sort_index()
    volume = pd.concat(volumes, axis=1).sort_index()
    close = close.loc[:, ~close.columns.duplicated()].ffill(limit=3)
    volume = volume.loc[:, ~volume.columns.duplicated()].fillna(0)
    if len(close) and session_in_progress(close.index[-1].date()):
        close, volume = close.iloc[:-1], volume.iloc[:-1]
    return close, volume


def _num(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(value) or np.isinf(value) else value


def fetch_fundamentals(ticker: str) -> dict:
    """Current fundamentals from Yahoo Finance. Missing fields come back as None (never guessed)."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    market_cap, fcf = _num(info.get("marketCap")), _num(info.get("freeCashflow"))
    de = _num(info.get("debtToEquity"))  # Yahoo reports this as a percentage (78 = 0.78x)
    peg = _num(info.get("pegRatio")) or _num(info.get("trailingPegRatio"))
    debt, cash, ebitda = _num(info.get("totalDebt")), _num(info.get("totalCash")), _num(info.get("ebitda"))
    book = _num(info.get("bookValue"))
    return {
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector") or "Unknown",
        "market_cap": market_cap,
        "pe": _num(info.get("forwardPE")) or _num(info.get("trailingPE")),
        "peg": peg if peg and peg > 0 else None,
        "roe": _num(info.get("returnOnEquity")),
        "roa": _num(info.get("returnOnAssets")),
        "profit_margin": _num(info.get("profitMargins")),
        "revenue_growth": _num(info.get("revenueGrowth")),
        "earnings_growth": _num(info.get("earningsGrowth")),
        "debt_to_equity": de / 100 if de is not None else None,
        "fcf_yield": fcf / market_cap if fcf is not None and market_cap else None,
        "price_to_book": _num(info.get("priceToBook")),
        # buybacks can push book equity below zero, which makes ROE and debt/equity meaningless
        "negative_equity": book is not None and book < 0,
        "net_debt_to_ebitda": (debt - cash) / ebitda if None not in (debt, cash, ebitda) and ebitda > 0 else None,
    }
