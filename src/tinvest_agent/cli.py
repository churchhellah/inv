from __future__ import annotations

import argparse
import logging

from tinvest_agent.config import AppConfig, load_config
from tinvest_agent.logging_setup import setup_logging
from tinvest_agent.orchestrator import run_once
from tinvest_agent.risk.journal import Journal
from tinvest_agent.scheduler import run_daemon

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tinvest-agent", description="ИИ-агент для управления инвестициями в Т-Инвестициях"
    )
    parser.add_argument("--config", default="config/config.yaml", help="Путь к config.yaml")
    parser.add_argument("--env-file", default=None, help="Путь к .env (по умолчанию ./.env)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Запустить агент")
    mode_group = run_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--once", action="store_true", help="Один проход анализа и (если разрешено) торговли")
    mode_group.add_argument("--daemon", action="store_true", help="Работать непрерывно по расписанию из конфига")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Форсировать dry_run=true независимо от конфига"
    )

    subparsers.add_parser("status", help="Показать портфель, лимиты и последние записи журнала")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup_logging()
    cfg = load_config(args.config, args.env_file)

    if args.command == "run":
        if args.dry_run:
            cfg = cfg.model_copy(update={"dry_run": True})
        if args.once:
            summary = run_once(cfg)
            logger.info(
                "Готово: рассмотрено=%s одобрено=%s исполнено=%s ошибок=%s",
                summary.considered, summary.approved, summary.executed, len(summary.errors),
            )
        else:
            run_daemon(cfg)
    elif args.command == "status":
        _print_status(cfg)


def _print_status(cfg: AppConfig) -> None:
    journal = Journal()
    print(f"mode={cfg.mode} trading_enabled={cfg.trading_enabled} dry_run={cfg.dry_run}")
    print(f"watchlist={', '.join(cfg.watchlist)}")
    print(
        "лимиты: заявка<=%.0f руб, покупки/день<=%.0f, продажи/день<=%.0f, доля<=%.0f%%, резерв кэша>=%.0f"
        % (
            cfg.limits.max_order_value_rub,
            cfg.limits.max_daily_buy_turnover_rub,
            cfg.limits.max_daily_sell_turnover_rub,
            cfg.limits.max_single_stock_exposure_pct * 100,
            cfg.limits.min_cash_reserve_rub,
        )
    )
    print(
        f"использовано сегодня: покупки={journal.today_turnover_rub(cfg.mode, 'buy'):.2f}, "
        f"продажи={journal.today_turnover_rub(cfg.mode, 'sell'):.2f}"
    )
    print("\nПоследние записи журнала:")
    for row in journal.recent(10):
        print(
            f"  {row['ts']} {row['ticker']:<6} {row['decision_action']:<4} "
            f"conf={row['decision_confidence']:.2f} approved={bool(row['risk_approved'])} "
            f"reason={row['risk_reason']!r} order_status={row['order_status']}"
        )


if __name__ == "__main__":
    main()
