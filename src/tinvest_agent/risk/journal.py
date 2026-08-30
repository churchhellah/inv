from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    ticker TEXT NOT NULL,
    decision_action TEXT NOT NULL,
    decision_confidence REAL NOT NULL,
    decision_rationale TEXT NOT NULL,
    decision_suggested_value_rub REAL NOT NULL,
    risk_approved INTEGER NOT NULL,
    risk_reason TEXT NOT NULL,
    approved_lots INTEGER NOT NULL DEFAULT 0,
    approved_value_rub REAL NOT NULL DEFAULT 0,
    executed INTEGER NOT NULL DEFAULT 0,
    order_id TEXT,
    order_status TEXT
);
"""


@dataclass
class JournalEntry:
    ticker: str
    mode: str
    decision_action: str
    decision_confidence: float
    decision_rationale: str
    decision_suggested_value_rub: float
    risk_approved: bool
    risk_reason: str
    approved_lots: int = 0
    approved_value_rub: float = 0.0
    # True только если заявка реально ушла на биржу (sandbox или production) и была принята.
    # dry_run/trading_disabled и ошибки исполнения оставляют False — иначе неисполненные
    # "одобренные" решения ошибочно съедали бы дневной лимит оборота в будущих прогонах.
    executed: bool = False
    order_id: str | None = None
    order_status: str | None = None


class Journal:
    """Аудит-лог всех рассмотренных решений (SQLite) + источник дневного оборота
    для риск-менеджера. Пишется каждый цикл независимо от того, была ли сделка
    одобрена и исполнена — это единственное место, где человек может разобрать,
    почему агент сделал (или не сделал) ту или иную сделку.
    """

    def __init__(self, db_path: str | Path = "data/journal.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def record(self, entry: JournalEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    ts, mode, ticker, decision_action, decision_confidence, decision_rationale,
                    decision_suggested_value_rub, risk_approved, risk_reason,
                    approved_lots, approved_value_rub, executed, order_id, order_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    entry.mode,
                    entry.ticker,
                    entry.decision_action,
                    entry.decision_confidence,
                    entry.decision_rationale,
                    entry.decision_suggested_value_rub,
                    int(entry.risk_approved),
                    entry.risk_reason,
                    entry.approved_lots,
                    entry.approved_value_rub,
                    int(entry.executed),
                    entry.order_id,
                    entry.order_status,
                ),
            )

    def today_turnover_rub(self, mode: str, action: str) -> float:
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(approved_value_rub), 0) FROM decisions
                WHERE mode = ? AND decision_action = ? AND executed = 1
                  AND substr(ts, 1, 10) = ?
                """,
                (mode, action, today),
            ).fetchone()
        return float(row[0] or 0.0)

    def recent(self, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
