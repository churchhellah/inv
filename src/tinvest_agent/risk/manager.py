from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from tinvest_agent.broker.portfolio import PortfolioContext
from tinvest_agent.config import AppConfig
from tinvest_agent.decision.schema import TradeAction, TradeDecision
from tinvest_agent.risk.journal import Journal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskVerdict:
    approved: bool
    reason: str
    lots: int = 0
    value_rub: float = 0.0


class RiskManager:
    """Единственная точка, разрешающая сделку. Клампит/отклоняет предложения торговой
    стратегии (decision/rules.py) по жёстким лимитам из config.yaml — они применяются
    после решения стратегии, независимо от того, что она предложила.
    """

    def __init__(self, cfg: AppConfig, journal: Journal):
        self.cfg = cfg
        self.journal = journal
        self._run_buy_used_rub = 0.0
        self._run_sell_used_rub = 0.0
        self._orders_this_run = 0

    def evaluate(
        self,
        decision: TradeDecision,
        last_price: float,
        lot_size: int,
        portfolio: PortfolioContext,
    ) -> RiskVerdict:
        if decision.action == TradeAction.HOLD:
            return RiskVerdict(approved=False, reason="hold")

        if decision.ticker not in self.cfg.watchlist_set:
            return RiskVerdict(approved=False, reason="тикер вне watchlist — отклонено")

        if self._orders_this_run >= self.cfg.limits.max_orders_per_run:
            return RiskVerdict(approved=False, reason="достигнут max_orders_per_run для этого прохода")

        if last_price <= 0 or lot_size <= 0:
            return RiskVerdict(approved=False, reason="некорректная цена или размер лота")

        if decision.action == TradeAction.BUY:
            verdict = self._evaluate_buy(decision, last_price, lot_size, portfolio)
        else:
            verdict = self._evaluate_sell(decision, last_price, lot_size, portfolio)

        if verdict.approved:
            self._orders_this_run += 1
            if decision.action == TradeAction.BUY:
                self._run_buy_used_rub += verdict.value_rub
            else:
                self._run_sell_used_rub += verdict.value_rub

        return verdict

    def _evaluate_buy(
        self, decision: TradeDecision, price: float, lot_size: int, portfolio: PortfolioContext
    ) -> RiskVerdict:
        limits = self.cfg.limits

        already_used_today = self.journal.today_turnover_rub(self.cfg.mode, "buy")
        remaining_daily = limits.max_daily_buy_turnover_rub - already_used_today - self._run_buy_used_rub
        if remaining_daily <= 0:
            return RiskVerdict(approved=False, reason="дневной лимит покупок исчерпан")

        available_cash = portfolio.cash_rub - limits.min_cash_reserve_rub - self._run_buy_used_rub
        if available_cash <= 0:
            return RiskVerdict(approved=False, reason="недостаточно свободного кэша с учётом резерва")

        allowed_position_value = limits.max_single_stock_exposure_pct * portfolio.total_value_rub
        current_position_value = portfolio.position_value(decision.ticker)
        exposure_room = allowed_position_value - current_position_value
        if exposure_room <= 0:
            return RiskVerdict(approved=False, reason="лимит доли портфеля по инструменту исчерпан")

        value_cap = min(
            decision.suggested_value_rub,
            limits.max_order_value_rub,
            remaining_daily,
            available_cash,
            exposure_room,
        )

        lot_cost = price * lot_size
        lots = math.floor(value_cap / lot_cost)
        if lots < 1:
            return RiskVerdict(approved=False, reason="сумма после клампинга меньше стоимости одного лота")

        return RiskVerdict(approved=True, reason="ok", lots=lots, value_rub=lots * lot_cost)

    def _evaluate_sell(
        self, decision: TradeDecision, price: float, lot_size: int, portfolio: PortfolioContext
    ) -> RiskVerdict:
        limits = self.cfg.limits

        held_value = portfolio.position_value(decision.ticker)
        if held_value <= 0:
            return RiskVerdict(approved=False, reason="нет позиции для продажи")

        already_used_today = self.journal.today_turnover_rub(self.cfg.mode, "sell")
        remaining_daily = limits.max_daily_sell_turnover_rub - already_used_today - self._run_sell_used_rub
        if remaining_daily <= 0:
            return RiskVerdict(approved=False, reason="дневной лимит продаж исчерпан")

        value_cap = min(decision.suggested_value_rub, limits.max_order_value_rub, remaining_daily, held_value)

        lot_cost = price * lot_size
        held_lots = math.floor(portfolio.position_quantity(decision.ticker) / lot_size)
        lots = min(math.floor(value_cap / lot_cost), held_lots)
        if lots < 1:
            return RiskVerdict(approved=False, reason="сумма после клампинга меньше стоимости одного лота")

        return RiskVerdict(approved=True, reason="ok", lots=lots, value_rub=lots * lot_cost)
