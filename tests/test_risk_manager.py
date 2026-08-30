import pytest

from tinvest_agent.broker.portfolio import PortfolioContext, Position
from tinvest_agent.config import AppConfig, IndicatorsConfig, Limits, ScheduleConfig
from tinvest_agent.decision.schema import TradeAction, TradeDecision
from tinvest_agent.risk.journal import Journal
from tinvest_agent.risk.manager import RiskManager


def _make_config(**limit_overrides) -> AppConfig:
    defaults = dict(
        max_order_value_rub=5000,
        max_daily_buy_turnover_rub=10000,
        max_daily_sell_turnover_rub=10000,
        max_single_stock_exposure_pct=0.25,
        min_cash_reserve_rub=1000,
        max_orders_per_run=3,
    )
    defaults.update(limit_overrides)
    limits = Limits(**defaults)
    return AppConfig(
        mode="sandbox",
        trading_enabled=True,
        dry_run=True,
        watchlist=["SBER", "GAZP"],
        limits=limits,
        schedule=ScheduleConfig(interval_minutes=60, trading_start="10:00", trading_end="18:40"),
        indicators=IndicatorsConfig(),
    )


@pytest.fixture
def journal(tmp_path) -> Journal:
    return Journal(tmp_path / "journal.db")


def _portfolio(cash=20000.0, total=100000.0, positions=None) -> PortfolioContext:
    return PortfolioContext(total_value_rub=total, cash_rub=cash, positions=positions or {})


def test_buy_clamped_to_max_order_value(journal):
    cfg = _make_config()
    manager = RiskManager(cfg, journal)
    decision = TradeDecision(
        ticker="SBER", action=TradeAction.BUY, confidence=0.8, rationale="test", suggested_value_rub=50000
    )
    verdict = manager.evaluate(decision, last_price=250.0, lot_size=10, portfolio=_portfolio())
    assert verdict.approved
    assert verdict.value_rub <= cfg.limits.max_order_value_rub


def test_buy_rejected_for_ticker_outside_watchlist(journal):
    cfg = _make_config()
    manager = RiskManager(cfg, journal)
    decision = TradeDecision(
        ticker="AAPL", action=TradeAction.BUY, confidence=0.8, rationale="test", suggested_value_rub=1000
    )
    verdict = manager.evaluate(decision, last_price=100.0, lot_size=1, portfolio=_portfolio())
    assert not verdict.approved
    assert "watchlist" in verdict.reason


def test_buy_respects_cash_reserve(journal):
    cfg = _make_config(min_cash_reserve_rub=9500)
    manager = RiskManager(cfg, journal)
    decision = TradeDecision(
        ticker="SBER", action=TradeAction.BUY, confidence=0.8, rationale="test", suggested_value_rub=5000
    )
    verdict = manager.evaluate(decision, last_price=250.0, lot_size=10, portfolio=_portfolio(cash=10000.0))
    # доступно только 10000-9500=500 руб, а один лот стоит 2500 -> должно быть отклонено
    assert not verdict.approved


def test_sell_rejected_without_position(journal):
    cfg = _make_config()
    manager = RiskManager(cfg, journal)
    decision = TradeDecision(
        ticker="SBER", action=TradeAction.SELL, confidence=0.9, rationale="test", suggested_value_rub=1000
    )
    verdict = manager.evaluate(decision, last_price=250.0, lot_size=10, portfolio=_portfolio())
    assert not verdict.approved
    assert "позиции" in verdict.reason


def test_sell_capped_to_held_quantity(journal):
    cfg = _make_config()
    manager = RiskManager(cfg, journal)
    positions = {"SBER": Position(ticker="SBER", quantity=10, value_rub=2500.0)}
    decision = TradeDecision(
        ticker="SBER", action=TradeAction.SELL, confidence=0.9, rationale="test", suggested_value_rub=10000
    )
    verdict = manager.evaluate(
        decision, last_price=250.0, lot_size=10, portfolio=_portfolio(positions=positions)
    )
    assert verdict.approved
    assert verdict.lots == 1


def test_max_orders_per_run_enforced(journal):
    cfg = _make_config(max_orders_per_run=1)
    manager = RiskManager(cfg, journal)
    portfolio = _portfolio()
    first = TradeDecision(
        ticker="SBER", action=TradeAction.BUY, confidence=0.9, rationale="t", suggested_value_rub=1000
    )
    second = TradeDecision(
        ticker="GAZP", action=TradeAction.BUY, confidence=0.8, rationale="t", suggested_value_rub=1000
    )
    assert manager.evaluate(first, last_price=100.0, lot_size=1, portfolio=portfolio).approved
    verdict = manager.evaluate(second, last_price=100.0, lot_size=1, portfolio=portfolio)
    assert not verdict.approved
    assert "max_orders_per_run" in verdict.reason
