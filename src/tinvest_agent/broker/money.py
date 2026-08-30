from __future__ import annotations

from typing import Any


def quotation_to_float(value: Any) -> float:
    """Конвертирует Quotation/MoneyValue T-Invest API (units + nano) во float."""
    if value is None:
        return 0.0
    return value.units + value.nano / 1_000_000_000
