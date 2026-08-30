from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_CANDLES_REQUIRED = 30


@dataclass(frozen=True)
class TechnicalSignal:
    ticker: str
    last_price: float
    sma_fast: float
    sma_slow: float
    trend: str  # "up" | "down" | "flat"
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    bollinger_pct_b: float
    volatility_pct: float


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    # avg_gain == avg_loss == 0 (совсем нет движения цены за период) — RS не определён,
    # берём нейтральное значение вместо NaN.
    return result.mask((avg_gain == 0) & (avg_loss == 0), 50.0)


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_pct_b(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.Series:
    mid = sma(series, window)
    std = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return (series - lower) / (upper - lower)


def compute_signal(ticker: str, candles: pd.DataFrame) -> TechnicalSignal | None:
    """Считает технический сигнал по свечам. None, если данных недостаточно."""
    if candles is None or len(candles) < MIN_CANDLES_REQUIRED:
        return None

    close = candles["close"].reset_index(drop=True)
    sma_fast_series = sma(close, 10)
    sma_slow_series = sma(close, 30)
    rsi_series = rsi(close, 14)
    macd_line, signal_line, histogram = macd(close)
    pct_b_series = bollinger_pct_b(close)
    returns = close.pct_change()

    last_fast = sma_fast_series.iloc[-1]
    last_slow = sma_slow_series.iloc[-1]
    if last_fast > last_slow:
        trend = "up"
    elif last_fast < last_slow:
        trend = "down"
    else:
        trend = "flat"

    return TechnicalSignal(
        ticker=ticker,
        last_price=float(close.iloc[-1]),
        sma_fast=float(last_fast),
        sma_slow=float(last_slow),
        trend=trend,
        rsi=float(rsi_series.iloc[-1]),
        macd=float(macd_line.iloc[-1]),
        macd_signal=float(signal_line.iloc[-1]),
        macd_hist=float(histogram.iloc[-1]),
        bollinger_pct_b=float(pct_b_series.iloc[-1]),
        volatility_pct=float(returns.std() * 100),
    )
