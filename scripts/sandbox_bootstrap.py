"""
Одноразовый скрипт: создаёт sandbox-аккаунт T-Invest API и пополняет его тестовым
балансом. Нужен один раз перед первым запуском агента в режиме sandbox — orchestrator
только читает/торгует на уже существующем счёте, а не создаёт его.

Запуск: python scripts/sandbox_bootstrap.py [сумма_пополнения_руб]
Требует TINVEST_TOKEN_SANDBOX в .env. Выведет account_id — пропишите его в .env
как TINVEST_ACCOUNT_ID_SANDBOX.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
from t_tech.invest import MoneyValue
from t_tech.invest.sandbox.client import SandboxClient


def main() -> None:
    load_dotenv()
    token = os.environ["TINVEST_TOKEN_SANDBOX"]
    amount_rub = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000

    with SandboxClient(token) as client:
        account = client.sandbox.open_sandbox_account()
        client.sandbox.sandbox_pay_in(
            account_id=account.account_id,
            amount=MoneyValue(currency="rub", units=amount_rub, nano=0),
        )
        print(f"Создан sandbox-аккаунт: {account.account_id}")
        print(f"Баланс пополнен на {amount_rub} руб.")
        print("Пропишите этот account_id в .env как TINVEST_ACCOUNT_ID_SANDBOX")


if __name__ == "__main__":
    main()
