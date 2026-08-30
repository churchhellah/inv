import pytest
from pydantic import ValidationError

from tinvest_agent.decision.schema import DecisionBatch, TradeAction, TradeDecision


def test_valid_buy_decision_parses():
    decision = TradeDecision(
        ticker="SBER", action="buy", confidence=0.7, rationale="momentum", suggested_value_rub=1000
    )
    assert decision.action == TradeAction.BUY


def test_hold_decision_allows_zero_value():
    decision = TradeDecision(
        ticker="SBER", action="hold", confidence=0.5, rationale="no signal", suggested_value_rub=0
    )
    assert decision.action == TradeAction.HOLD


def test_buy_requires_positive_suggested_value():
    with pytest.raises(ValidationError):
        TradeDecision(ticker="SBER", action="buy", confidence=0.7, rationale="x", suggested_value_rub=0)


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        TradeDecision(ticker="SBER", action="hold", confidence=1.5, rationale="x", suggested_value_rub=0)


def test_decision_batch_parses_list():
    batch = DecisionBatch.model_validate(
        {
            "decisions": [
                {"ticker": "SBER", "action": "hold", "confidence": 0.5, "rationale": "x", "suggested_value_rub": 0}
            ]
        }
    )
    assert len(batch.decisions) == 1
