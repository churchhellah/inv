"""
Ручной сквозной прогон против реального T-Invest sandbox API (не входит в pytest —
нужен сетевой доступ и настоящий sandbox-токен).

Требует заполненный .env (TINVEST_TOKEN_SANDBOX, TINVEST_ACCOUNT_ID_SANDBOX) и mode: sandbox
в config.yaml. Перед первым запуском выполните scripts/sandbox_bootstrap.py.

Запуск: python scripts/smoke_test_sandbox.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tinvest_agent.config import load_config
from tinvest_agent.logging_setup import setup_logging
from tinvest_agent.orchestrator import run_once


def main() -> None:
    setup_logging()
    cfg = load_config()
    if cfg.mode != "sandbox":
        raise SystemExit("Этот скрипт только для mode: sandbox в config.yaml — исправьте конфиг перед запуском")

    summary = run_once(cfg)
    print(f"considered={summary.considered} approved={summary.approved} executed={summary.executed}")
    if summary.errors:
        print("Ошибки:", summary.errors)


if __name__ == "__main__":
    main()
