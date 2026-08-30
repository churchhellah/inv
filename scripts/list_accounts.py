"""
Read-only: выводит список брокерских счетов, доступных TINVEST_TOKEN_PROD (или
TINVEST_TOKEN_SANDBOX, если запустить с --sandbox). Не делает ничего, кроме GetAccounts —
безопасно запускать в любой момент, чтобы узнать правильный account_id для .env.

Запуск: python scripts/list_accounts.py [--sandbox]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
from t_tech.invest import Client
from t_tech.invest.sandbox.client import SandboxClient


def main() -> None:
    load_dotenv(override=True)
    use_sandbox = "--sandbox" in sys.argv
    token_env = "TINVEST_TOKEN_SANDBOX" if use_sandbox else "TINVEST_TOKEN_PROD"
    token = os.environ[token_env]
    client_cls = SandboxClient if use_sandbox else Client

    with client_cls(token) as client:
        response = client.users.get_accounts()
        if not response.accounts:
            print(f"У токена {token_env} нет ни одного счёта.")
            return
        for account in response.accounts:
            print(f"account_id={account.id!r}  name={account.name!r}  status={account.status!r}")


if __name__ == "__main__":
    main()
