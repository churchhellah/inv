from __future__ import annotations

from dataclasses import dataclass, field

from tinvest_agent.broker.money import quotation_to_float


@dataclass(frozen=True)
class Position:
    ticker: str
    quantity: float
    value_rub: float


@dataclass(frozen=True)
class PortfolioContext:
    total_value_rub: float
    cash_rub: float
    positions: dict[str, Position] = field(default_factory=dict)

    def position_value(self, ticker: str) -> float:
        position = self.positions.get(ticker)
        return position.value_rub if position else 0.0

    def position_quantity(self, ticker: str) -> float:
        position = self.positions.get(ticker)
        return position.quantity if position else 0.0


def get_portfolio_context(client, account_id: str, uid_to_ticker: dict[str, str]) -> PortfolioContext:
    portfolio = client.operations.get_portfolio(account_id=account_id)

    total_value = quotation_to_float(portfolio.total_amount_portfolio)
    cash = quotation_to_float(portfolio.total_amount_currencies)

    positions: dict[str, Position] = {}
    for pos in portfolio.positions:
        ticker = uid_to_ticker.get(pos.instrument_uid)
        if ticker is None:
            continue
        quantity = quotation_to_float(pos.quantity)
        price = quotation_to_float(pos.current_price)
        positions[ticker] = Position(ticker=ticker, quantity=quantity, value_rub=quantity * price)

    return PortfolioContext(total_value_rub=total_value, cash_rub=cash, positions=positions)
