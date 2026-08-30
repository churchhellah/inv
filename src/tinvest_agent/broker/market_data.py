from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
from t_tech.invest import CandleInterval, InstrumentIdType, InstrumentType
from t_tech.invest.utils import now

from tinvest_agent.broker.money import quotation_to_float

logger = logging.getLogger(__name__)

_INTERVAL_MAP = {
    "hour": CandleInterval.CANDLE_INTERVAL_HOUR,
    "day": CandleInterval.CANDLE_INTERVAL_DAY,
}


@dataclass(frozen=True)
class Instrument:
    ticker: str
    uid: str
    figi: str
    lot: int
    currency: str


def resolve_instruments(client, tickers: list[str]) -> dict[str, Instrument]:
    """Резолвит тикеры watchlist в инструменты T-Invest API (uid/figi/lot).

    Инструменты, которые не найдены или недоступны для торгов, пропускаются с
    предупреждением в лог — они просто выпадут из анализа на этот цикл.
    """
    resolved: dict[str, Instrument] = {}
    for ticker in tickers:
        found = client.instruments.find_instrument(
            query=ticker,
            instrument_kind=InstrumentType.INSTRUMENT_TYPE_SHARE,
            api_trade_available_flag=True,
        )
        match = next((item for item in found.instruments if item.ticker == ticker), None)
        if match is None:
            logger.warning("Инструмент %s не найден или недоступен для торгов — пропускаю", ticker)
            continue

        share = client.instruments.share_by(
            id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID, id=match.uid
        ).instrument
        resolved[ticker] = Instrument(
            ticker=ticker,
            uid=share.uid,
            figi=share.figi,
            lot=share.lot,
            currency=share.currency,
        )
    return resolved


def get_candles_df(client, instrument: Instrument, lookback_days: int, interval: str) -> pd.DataFrame:
    rows = []
    for candle in client.get_all_candles(
        instrument_id=instrument.uid,
        from_=now() - timedelta(days=lookback_days),
        interval=_INTERVAL_MAP[interval],
    ):
        rows.append(
            {
                "time": candle.time,
                "open": quotation_to_float(candle.open),
                "high": quotation_to_float(candle.high),
                "low": quotation_to_float(candle.low),
                "close": quotation_to_float(candle.close),
                "volume": candle.volume,
            }
        )
    return pd.DataFrame(rows)


def get_last_prices(client, instruments: list[Instrument]) -> dict[str, float]:
    if not instruments:
        return {}
    response = client.market_data.get_last_prices(instrument_id=[i.uid for i in instruments])
    price_by_uid = {p.instrument_uid: quotation_to_float(p.price) for p in response.last_prices}
    return {i.ticker: price_by_uid.get(i.uid, 0.0) for i in instruments}
