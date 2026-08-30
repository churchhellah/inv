from __future__ import annotations

from tinvest_agent.analysis.indicators import TechnicalSignal
from tinvest_agent.broker.portfolio import PortfolioContext
from tinvest_agent.config import Limits
from tinvest_agent.decision.schema import DecisionBatch, TradeAction, TradeDecision

RSI_OVERBOUGHT = 70.0
RSI_EXTREME_OVERBOUGHT = 75.0

# Минимум голосов индикаторов "за", нужный чтобы решиться на сделку — отсекает
# слабые/противоречивые сигналы, когда индикаторы не согласны друг с другом.
MIN_VOTES_TO_ACT = 2


def _bullish_votes(signal: TechnicalSignal) -> int:
    votes = 0
    if signal.trend == "up":
        votes += 1
    if signal.macd_hist > 0:
        votes += 1
    if signal.rsi < RSI_OVERBOUGHT:
        votes += 1
    return votes


def _bearish_votes(signal: TechnicalSignal) -> int:
    votes = 0
    if signal.trend == "down":
        votes += 1
    if signal.macd_hist < 0:
        votes += 1
    if signal.rsi > RSI_EXTREME_OVERBOUGHT:
        votes += 1
    return votes


def decide_one(signal: TechnicalSignal, held_value_rub: float, max_order_value_rub: float) -> TradeDecision:
    """Чисто детерминированная стратегия по индикаторам, без обращения к какому-либо
    внешнему LLM/API. Покупка требует согласия тренда, MACD и RSI (не в перекупленности);
    продажа — только если позиция реально есть — либо на явном развороте тренда вниз,
    либо на экстремальной перекупленности (фиксация прибыли).
    """
    bullish = _bullish_votes(signal)
    bearish = _bearish_votes(signal)

    if bullish >= MIN_VOTES_TO_ACT and bullish > bearish:
        return TradeDecision(
            ticker=signal.ticker,
            action=TradeAction.BUY,
            confidence=bullish / 3,
            rationale=(
                f"Бычьи сигналы ({bullish}/3): trend={signal.trend}, "
                f"MACD_hist={signal.macd_hist:.4f}, RSI={signal.rsi:.1f}"
            ),
            suggested_value_rub=max_order_value_rub,
        )

    if held_value_rub > 0 and bearish >= MIN_VOTES_TO_ACT and bearish > bullish:
        return TradeDecision(
            ticker=signal.ticker,
            action=TradeAction.SELL,
            confidence=bearish / 3,
            rationale=(
                f"Медвежьи сигналы ({bearish}/3): trend={signal.trend}, "
                f"MACD_hist={signal.macd_hist:.4f}, RSI={signal.rsi:.1f}"
            ),
            suggested_value_rub=min(held_value_rub, max_order_value_rub),
        )

    return TradeDecision(
        ticker=signal.ticker,
        action=TradeAction.HOLD,
        confidence=0.5,
        rationale=f"Недостаточно согласованный сигнал: trend={signal.trend}, RSI={signal.rsi:.1f}",
        suggested_value_rub=0,
    )


def decide_all(signals: list[TechnicalSignal], portfolio: PortfolioContext, limits: Limits) -> DecisionBatch:
    decisions = [
        decide_one(signal, portfolio.position_value(signal.ticker), limits.max_order_value_rub)
        for signal in signals
    ]
    return DecisionBatch(decisions=decisions)
