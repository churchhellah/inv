from __future__ import annotations

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from tinvest_agent.config import AppConfig
from tinvest_agent.orchestrator import run_once

logger = logging.getLogger(__name__)


def _within_trading_window(cfg: AppConfig) -> bool:
    tz = ZoneInfo(cfg.schedule.timezone)
    now = datetime.now(tz)
    if now.weekday() >= 5:  # суббота/воскресенье
        return False
    start = time.fromisoformat(cfg.schedule.trading_start)
    end = time.fromisoformat(cfg.schedule.trading_end)
    return start <= now.time() <= end


def _job(cfg: AppConfig) -> None:
    if not _within_trading_window(cfg):
        logger.debug("Вне торгового окна MOEX — пропускаю цикл")
        return
    try:
        summary = run_once(cfg)
        logger.info(
            "Цикл завершён: рассмотрено=%s одобрено=%s исполнено=%s ошибок=%s",
            summary.considered, summary.approved, summary.executed, len(summary.errors),
        )
    except Exception:  # noqa: BLE001 — демон обязан пережить единичный сбой цикла и продолжить по расписанию
        logger.exception("Необработанная ошибка в цикле анализа")


def run_daemon(cfg: AppConfig) -> None:
    tz = ZoneInfo(cfg.schedule.timezone)
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        _job,
        trigger=IntervalTrigger(minutes=cfg.schedule.interval_minutes),
        args=[cfg],
        next_run_time=datetime.now(tz),
    )
    logger.info(
        "Демон запущен: интервал=%s мин, торговое окно %s-%s (%s), mode=%s, trading_enabled=%s, dry_run=%s",
        cfg.schedule.interval_minutes,
        cfg.schedule.trading_start,
        cfg.schedule.trading_end,
        cfg.schedule.timezone,
        cfg.mode,
        cfg.trading_enabled,
        cfg.dry_run,
    )
    scheduler.start()
