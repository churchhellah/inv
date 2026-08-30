from dataclasses import replace

from tinvest_agent.analysis.indicators import TechnicalSignal
from tinvest_agent.decision.rules import decide_one
from tinvest_agent.decision.schema import TradeAction

_BASE_SIGNAL = TechnicalSignal(
    ticker="SBER",
    last_price=250.0,
    sma_fast=100.0,
    sma_slow=100.0,
    trend="flat",
    rsi=50.0,
    macd=0.0,
    macd_signal=0.0,
    macd_hist=0.0,
    bollinger_pct_b=0.5,
    volatility_pct=1.0,
)


def test_aligned_bullish_signals_produce_buy():
    signal = replace(_BASE_SIGNAL, trend="up", macd_hist=0.5, rsi=55.0)
    decision = decide_one(signal, held_value_rub=0.0, max_order_value_rub=5000)
    assert decision.action == TradeAction.BUY
    assert decision.suggested_value_rub == 5000


def test_overbought_uptrend_does_not_buy():
    # тренд вверх, но RSI перекуплен — только 1 бычий голос (trend), недостаточно для покупки
    signal = replace(_BASE_SIGNAL, trend="up", macd_hist=-0.1, rsi=85.0)
    decision = decide_one(signal, held_value_rub=0.0, max_order_value_rub=5000)
    assert decision.action == TradeAction.HOLD


def test_aligned_bearish_signals_sell_when_holding_position():
    signal = replace(_BASE_SIGNAL, trend="down", macd_hist=-0.5, rsi=45.0)
    decision = decide_one(signal, held_value_rub=3000.0, max_order_value_rub=5000)
    assert decision.action == TradeAction.SELL
    assert decision.suggested_value_rub == 3000.0


def test_bearish_signals_without_position_do_not_sell():
    signal = replace(_BASE_SIGNAL, trend="down", macd_hist=-0.5, rsi=45.0)
    decision = decide_one(signal, held_value_rub=0.0, max_order_value_rub=5000)
    assert decision.action == TradeAction.HOLD


def test_sell_value_capped_by_max_order_value():
    signal = replace(_BASE_SIGNAL, trend="down", macd_hist=-0.5, rsi=45.0)
    decision = decide_one(signal, held_value_rub=100_000.0, max_order_value_rub=5000)
    assert decision.action == TradeAction.SELL
    assert decision.suggested_value_rub == 5000


def test_neutral_signals_hold():
    decision = decide_one(_BASE_SIGNAL, held_value_rub=0.0, max_order_value_rub=5000)
    assert decision.action == TradeAction.HOLD
    assert decision.suggested_value_rub == 0
