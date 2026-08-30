import pandas as pd

from tinvest_agent.analysis.indicators import compute_signal


def _make_candles(prices: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": prices})


def test_compute_signal_returns_none_with_too_few_candles():
    assert compute_signal("TEST", _make_candles([100.0] * 10)) is None


def test_uptrend_produces_up_trend_and_high_rsi():
    prices = [100 + i for i in range(60)]
    signal = compute_signal("TEST", _make_candles(prices))
    assert signal is not None
    assert signal.trend == "up"
    assert signal.rsi > 70
    assert signal.sma_fast > signal.sma_slow


def test_downtrend_produces_down_trend_and_low_rsi():
    prices = [200 - i for i in range(60)]
    signal = compute_signal("TEST", _make_candles(prices))
    assert signal is not None
    assert signal.trend == "down"
    assert signal.rsi < 30
    assert signal.sma_fast < signal.sma_slow


def test_flat_series_has_zero_volatility():
    prices = [100.0] * 60
    signal = compute_signal("TEST", _make_candles(prices))
    assert signal is not None
    assert signal.volatility_pct == 0.0
