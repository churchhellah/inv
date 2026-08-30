from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from t_tech.invest import Client
from t_tech.invest.sandbox.client import SandboxClient

from tinvest_agent.config import AppConfig

logger = logging.getLogger(__name__)


@contextmanager
def broker_client(cfg: AppConfig) -> Iterator[object]:
    """Открывает клиент T-Invest API — SandboxClient или боевой Client, по cfg.mode.

    Открывается заново на каждый цикл анализа (orchestrator.run_once), а не держится
    постоянно открытым — это проще и устойчивее к обрывам соединения между запусками демона.
    """
    client_cls = SandboxClient if cfg.mode == "sandbox" else Client
    logger.debug("Открываю T-Invest клиент (mode=%s)", cfg.mode)
    with client_cls(cfg.tinvest_token) as client:
        yield client
