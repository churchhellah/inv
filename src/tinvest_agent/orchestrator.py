from __future__ import annotations

import logging
from dataclasses import dataclass, field

from tinvest_agent.analysis.indicators import compute_signal
from tinvest_agent.broker.client import broker_client
from tinvest_agent.broker.executor import place_market_order
from tinvest_agent.broker.market_data import get_candles_df, get_last_prices, resolve_instruments
from tinvest_agent.broker.portfolio import get_portfolio_context
from tinvest_agent.config import AppConfig
from tinvest_agent.decision.rules import decide_all
from tinvest_agent.risk.journal import Journal, JournalEntry
from tinvest_agent.risk.manager import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    considered: int = 0
    approved: int = 0
    executed: int = 0
    errors: list[str] = field(default_factory=list)


def run_once(cfg: AppConfig, journal: Journal | None = None) -> RunSummary:
    journal = journal or Journal()
    summary = RunSummary()

    if not cfg.trading_enabled:
        logger.info("trading_enabled=false — анализирую и веду журнал, заявки отправляться не будут")
    if cfg.dry_run:
        logger.info("dry_run=true — заявки отправляться не будут")

    with broker_client(cfg) as client:
        instruments = resolve_instruments(client, cfg.watchlist)
        if not instruments:
            logger.warning("Ни один инструмент из watchlist не резолвится — нечего анализировать")
            return summary

        uid_to_ticker = {inst.uid: ticker for ticker, inst in instruments.items()}
        portfolio = get_portfolio_context(client, cfg.tinvest_account_id, uid_to_ticker)
        last_prices = get_last_prices(client, list(instruments.values()))

        signals = []
        for ticker, instrument in instruments.items():
            candles = get_candles_df(
                client, instrument, cfg.indicators.lookback_days, cfg.indicators.candle_interval
            )
            signal = compute_signal(ticker, candles)
            if signal is None:
                logger.warning("Недостаточно свечей для %s — пропускаю", ticker)
                continue
            signals.append(signal)

        if not signals:
            logger.warning("Нет ни одного валидного технического сигнала — анализировать нечего")
            return summary

        risk_manager = RiskManager(cfg, journal)
        batch = decide_all(signals, portfolio, cfg.limits)

        # Сначала обрабатываем решения с наибольшей уверенностью — лимит max_orders_per_run
        # расходуется в порядке приоритета сигнала, а не порядке обхода watchlist.
        ordered_decisions = sorted(batch.decisions, key=lambda d: d.confidence, reverse=True)

        for decision in ordered_decisions:
            summary.considered += 1
            instrument = instruments.get(decision.ticker)
            if instrument is None:
                continue

            price = last_prices.get(decision.ticker, 0.0)
            verdict = risk_manager.evaluate(decision, price, instrument.lot, portfolio)

            entry = JournalEntry(
                ticker=decision.ticker,
                mode=cfg.mode,
                decision_action=decision.action.value,
                decision_confidence=decision.confidence,
                decision_rationale=decision.rationale,
                decision_suggested_value_rub=decision.suggested_value_rub,
                risk_approved=verdict.approved,
                risk_reason=verdict.reason,
                approved_lots=verdict.lots,
                approved_value_rub=verdict.value_rub,
            )

            if not verdict.approved:
                journal.record(entry)
                logger.info(
                    "Отклонено risk-менеджером: %s %s — %s",
                    decision.action.value, decision.ticker, verdict.reason,
                )
                continue

            summary.approved += 1
            logger.info(
                "Одобрено risk-менеджером: %s %s lots=%s value_rub=%.2f",
                decision.action.value, decision.ticker, verdict.lots, verdict.value_rub,
            )

            if cfg.should_execute_orders:
                try:
                    order_result = place_market_order(
                        client, cfg.tinvest_account_id, instrument, decision.action.value, verdict.lots
                    )
                    entry.order_id = order_result.order_id
                    entry.order_status = order_result.status
                    entry.executed = True
                    summary.executed += 1
                except Exception as exc:  # noqa: BLE001 — реальная заявка на бирже, ошибка обязана попасть в журнал
                    logger.exception("Ошибка при отправке заявки %s %s", decision.action.value, decision.ticker)
                    entry.order_status = f"error: {exc}"
                    summary.errors.append(f"{decision.ticker}: {exc}")
            else:
                entry.order_status = "not_sent (dry_run/trading_disabled)"

            journal.record(entry)

    return summary
