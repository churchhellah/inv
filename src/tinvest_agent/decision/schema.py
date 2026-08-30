from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradeDecision(BaseModel):
    ticker: str
    action: TradeAction
    confidence: float = Field(ge=0, le=1)
    rationale: str
    suggested_value_rub: float = Field(ge=0, default=0)

    @model_validator(mode="after")
    def _require_value_when_trading(self) -> "TradeDecision":
        if self.action != TradeAction.HOLD and self.suggested_value_rub <= 0:
            raise ValueError("suggested_value_rub должен быть > 0 для buy/sell")
        return self


class DecisionBatch(BaseModel):
    decisions: list[TradeDecision] = Field(default_factory=list)
