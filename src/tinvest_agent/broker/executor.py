from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from t_tech.invest import OrderDirection, OrderType

from tinvest_agent.broker.market_data import Instrument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderResult:
    ticker: str
    direction: str
    lots: int
    order_id: str
    status: str


def place_market_order(client, account_id: str, instrument: Instrument, direction: str, lots: int) -> OrderResult:
    order_direction = (
        OrderDirection.ORDER_DIRECTION_BUY if direction == "buy" else OrderDirection.ORDER_DIRECTION_SELL
    )
    logger.info("Отправляю заявку: %s %s lots=%s", direction, instrument.ticker, lots)
    response = client.orders.post_order(
        instrument_id=instrument.uid,
        quantity=lots,
        direction=order_direction,
        account_id=account_id,
        order_type=OrderType.ORDER_TYPE_MARKET,
        order_id=str(uuid.uuid4()),
    )
    return OrderResult(
        ticker=instrument.ticker,
        direction=direction,
        lots=lots,
        order_id=response.order_id,
        status=str(response.execution_report_status),
    )
