import os
from contextlib import contextmanager
from datetime import date
from typing import Iterable, Optional

import akshare as ak
import pandas as pd
import tushare as ts

from backend.app.data.types import (
    IndexDailyRecord,
    LimitSnapshotRecord,
    MarketDataSnapshot,
    StockBasicRecord,
    StockDailyRecord,
    TradingCalendarRecord,
)


INDEX_SYMBOLS = {
    "sh000001": "000001.SH",
    "sz399001": "399001.SZ",
    "sz399006": "399006.SZ",
}


@contextmanager
def without_proxy_env():
    proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
    previous = {key: os.environ.get(key) for key in proxy_keys}
    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def infer_market(stock_code: str) -> str:
    if stock_code.startswith("6"):
        return "SH"
    if stock_code.startswith(("0", "3")):
        return "SZ"
    if stock_code.startswith(("4", "8", "9")):
        return "BJ"
    return "UNKNOWN"


def akshare_daily_symbol(stock_code: str) -> Optional[str]:
    market = infer_market(stock_code)
    if market == "SH":
        return f"sh{stock_code}"
    if market == "SZ":
        return f"sz{stock_code}"
    return None


def as_float(value, default: Optional[float] = 0.0) -> Optional[float]:
    if value is None or pd.isna(value):
        return default
    return float(value)


def as_date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


class AkShareSinaMarketDataProvider:
    name = "akshare_sina"

    def fetch_snapshot(
        self,
        trade_date: Optional[date] = None,
        sample_size: int = 30,
        stock_codes: Optional[Iterable[str]] = None,
    ) -> MarketDataSnapshot:
        calendar_frame = ak.tool_trade_date_hist_sina()
        calendar_dates = sorted(as_date(value) for value in calendar_frame["trade_date"].tolist())

        index_records = self._fetch_index_daily(trade_date)
        actual_trade_date = trade_date or max(record.trade_date for record in index_records)
        calendar_records = [
            TradingCalendarRecord(trade_date=day, is_open=True, source=self.name)
            for day in calendar_dates
            if day.year == actual_trade_date.year and day <= actual_trade_date
        ]

        selected_codes = list(stock_codes) if stock_codes else self._select_stock_codes(sample_size)
        stock_basic = self._fetch_stock_basic(selected_codes)
        stock_daily = self._fetch_stock_daily(selected_codes, actual_trade_date)
        limit_snapshot = self._fetch_limit_snapshot(actual_trade_date)

        return MarketDataSnapshot(
            provider=self.name,
            trade_date=actual_trade_date,
            trading_calendar=calendar_records,
            stock_basic=stock_basic,
            index_daily=index_records,
            stock_daily=stock_daily,
            limit_snapshot=limit_snapshot,
        )

    def _select_stock_codes(self, sample_size: int) -> list[str]:
        frame = ak.stock_info_a_code_name()
        codes = [str(code).zfill(6) for code in frame["code"].tolist()]
        supported = [code for code in codes if akshare_daily_symbol(code)]
        anchors = ["000001", "600519", "300750"]
        ordered = anchors + [code for code in supported if code not in anchors]
        return ordered[:sample_size]

    def _fetch_stock_basic(self, stock_codes: list[str]) -> list[StockBasicRecord]:
        frame = ak.stock_info_a_code_name()
        names = {
            str(row["code"]).zfill(6): str(row["name"])
            for _, row in frame.iterrows()
        }
        records: list[StockBasicRecord] = []
        for code in stock_codes:
            name = names.get(code, code)
            records.append(
                StockBasicRecord(
                    stock_code=code,
                    stock_name=name,
                    market=infer_market(code),
                    list_date=None,
                    is_st="ST" in name.upper() or "退" in name,
                    status="active",
                    source=self.name,
                )
            )
        return records

    def _fetch_index_daily(self, trade_date: Optional[date]) -> list[IndexDailyRecord]:
        records: list[IndexDailyRecord] = []
        for ak_symbol, index_code in INDEX_SYMBOLS.items():
            frame = ak.stock_zh_index_daily(symbol=ak_symbol)
            row = self._last_row_on_or_before(frame, trade_date)
            records.append(
                IndexDailyRecord(
                    index_code=index_code,
                    trade_date=as_date(row["date"]),
                    open=as_float(row["open"]),
                    high=as_float(row["high"]),
                    low=as_float(row["low"]),
                    close=as_float(row["close"]),
                    volume=as_float(row["volume"]),
                    amount=None,
                    source=self.name,
                )
            )
        return records

    def _fetch_stock_daily(self, stock_codes: list[str], trade_date: date) -> list[StockDailyRecord]:
        records: list[StockDailyRecord] = []
        for code in stock_codes:
            symbol = akshare_daily_symbol(code)
            if not symbol:
                continue
            frame = ak.stock_zh_a_daily(symbol=symbol)
            frame = frame.sort_values("date").reset_index(drop=True)
            row_index = self._last_index_on_or_before(frame, trade_date)
            if row_index is None:
                continue
            row = frame.iloc[row_index]
            if as_date(row["date"]) != trade_date:
                continue
            previous = frame.iloc[row_index - 1] if row_index > 0 else row
            close = as_float(row["close"])
            pre_close = as_float(previous["close"])
            change = close - pre_close
            pct_chg = (change / pre_close * 100) if pre_close else 0.0
            records.append(
                StockDailyRecord(
                    stock_code=code,
                    trade_date=as_date(row["date"]),
                    open=as_float(row["open"]),
                    high=as_float(row["high"]),
                    low=as_float(row["low"]),
                    close=close,
                    pre_close=pre_close,
                    change=change,
                    pct_chg=pct_chg,
                    volume=as_float(row["volume"]),
                    amount=as_float(row["amount"]),
                    turnover_rate=as_float(row.get("turnover"), default=None),
                    source=self.name,
                )
            )
        return records

    def _fetch_limit_snapshot(self, trade_date: date) -> list[LimitSnapshotRecord]:
        date_text = trade_date.strftime("%Y%m%d")
        records: list[LimitSnapshotRecord] = []
        with without_proxy_env():
            up_frame = ak.stock_zt_pool_em(date=date_text)
            down_frame = ak.stock_zt_pool_dtgc_em(date=date_text)

        for _, row in up_frame.iterrows():
            records.append(self._limit_record(row, trade_date, "limit_up"))
        for _, row in down_frame.iterrows():
            records.append(self._limit_record(row, trade_date, "limit_down"))
        return records

    def _limit_record(self, row, trade_date: date, limit_status: str) -> LimitSnapshotRecord:
        return LimitSnapshotRecord(
            trade_date=trade_date,
            stock_code=str(row["代码"]).zfill(6),
            stock_name=str(row["名称"]),
            close_price=as_float(row["最新价"]),
            pct_chg=as_float(row["涨跌幅"]),
            limit_status=limit_status,
            amount=as_float(row["成交额"]),
            source="akshare_eastmoney_limit_pool",
        )

    def _last_row_on_or_before(self, frame, trade_date: Optional[date]):
        index = self._last_index_on_or_before(frame, trade_date)
        if index is None:
            raise RuntimeError("No market data row found")
        return frame.sort_values("date").reset_index(drop=True).iloc[index]

    def _last_index_on_or_before(self, frame, trade_date: Optional[date]) -> Optional[int]:
        ordered = frame.sort_values("date").reset_index(drop=True)
        if trade_date is None:
            return len(ordered) - 1
        eligible = ordered[ordered["date"].map(as_date) <= trade_date]
        if eligible.empty:
            return None
        return int(eligible.index[-1])


class MissingTushareTokenError(RuntimeError):
    pass


class TushareMarketDataProvider:
    name = "tushare"

    def __init__(self, token: str, pro_client=None):
        self.token = token.strip()
        self._pro_client = pro_client

    def fetch_snapshot(
        self,
        trade_date: Optional[date] = None,
        sample_size: int = 30,
        stock_codes: Optional[Iterable[str]] = None,
    ) -> MarketDataSnapshot:
        if not self.token:
            raise MissingTushareTokenError("TUSHARE_TOKEN is required for provider=tushare")
        pro = self._pro_client or ts.pro_api(self.token)
        actual_trade_date = trade_date or self._latest_open_trade_date(pro)
        trade_date_text = actual_trade_date.strftime("%Y%m%d")
        stock_basic = self._fetch_stock_basic(pro, stock_codes, sample_size)
        selected_ts_codes = [self._to_ts_code(record.stock_code) for record in stock_basic]
        stock_daily = (
            self._fetch_all_stock_daily(pro, trade_date_text)
            if not stock_codes and sample_size <= 0
            else self._fetch_stock_daily(pro, selected_ts_codes, trade_date_text)
        )

        return MarketDataSnapshot(
            provider=self.name,
            trade_date=actual_trade_date,
            trading_calendar=self._fetch_trading_calendar(pro, actual_trade_date),
            stock_basic=stock_basic,
            index_daily=self._fetch_index_daily(pro, trade_date_text),
            stock_daily=stock_daily,
            limit_snapshot=self._fetch_limit_snapshot(pro, trade_date_text),
        )

    def _latest_open_trade_date(self, pro) -> date:
        frame = pro.trade_cal(exchange="", start_date="20200101", end_date=date.today().strftime("%Y%m%d"))
        open_days = frame[frame["is_open"] == 1].sort_values("cal_date")
        if open_days.empty:
            raise RuntimeError("TuShare trade calendar returned no open days")
        return pd.to_datetime(open_days.iloc[-1]["cal_date"]).date()

    def _fetch_trading_calendar(self, pro, trade_date: date) -> list[TradingCalendarRecord]:
        frame = pro.trade_cal(
            exchange="",
            start_date=f"{trade_date.year}0101",
            end_date=trade_date.strftime("%Y%m%d"),
        )
        records: list[TradingCalendarRecord] = []
        for _, row in frame.iterrows():
            records.append(
                TradingCalendarRecord(
                    trade_date=pd.to_datetime(row["cal_date"]).date(),
                    is_open=int(row["is_open"]) == 1,
                    source=self.name,
                )
            )
        return records

    def _fetch_stock_basic(
        self,
        pro,
        stock_codes: Optional[Iterable[str]],
        sample_size: int,
    ) -> list[StockBasicRecord]:
        frame = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,market,list_date",
        )
        if stock_codes:
            wanted = {code.zfill(6) for code in stock_codes}
            frame = frame[frame["symbol"].astype(str).str.zfill(6).isin(wanted)]
        elif sample_size > 0:
            frame = frame.head(sample_size)

        records: list[StockBasicRecord] = []
        for _, row in frame.iterrows():
            code = str(row["symbol"]).zfill(6)
            name = str(row["name"])
            records.append(
                StockBasicRecord(
                    stock_code=code,
                    stock_name=name,
                    market=str(row.get("market") or infer_market(code)),
                    list_date=self._parse_optional_date(row.get("list_date")),
                    is_st="ST" in name.upper() or "退" in name,
                    status="active",
                    source=self.name,
                )
            )
        return records

    def _fetch_index_daily(self, pro, trade_date_text: str) -> list[IndexDailyRecord]:
        records: list[IndexDailyRecord] = []
        for index_code in INDEX_SYMBOLS.values():
            frame = pro.index_daily(
                ts_code=index_code,
                start_date=trade_date_text,
                end_date=trade_date_text,
            )
            if frame.empty:
                continue
            row = frame.iloc[0]
            records.append(
                IndexDailyRecord(
                    index_code=str(row["ts_code"]),
                    trade_date=pd.to_datetime(row["trade_date"]).date(),
                    open=as_float(row["open"]),
                    high=as_float(row["high"]),
                    low=as_float(row["low"]),
                    close=as_float(row["close"]),
                    volume=as_float(row["vol"]),
                    amount=as_float(row.get("amount"), default=None),
                    source=self.name,
                )
            )
        return records

    def _fetch_stock_daily(self, pro, ts_codes: list[str], trade_date_text: str) -> list[StockDailyRecord]:
        records: list[StockDailyRecord] = []
        for ts_code in ts_codes:
            frame = pro.daily(ts_code=ts_code, start_date=trade_date_text, end_date=trade_date_text)
            if frame.empty:
                continue
            row = frame.iloc[0]
            records.append(self._stock_daily_record(row))
        return records

    def _fetch_all_stock_daily(self, pro, trade_date_text: str) -> list[StockDailyRecord]:
        frame = pro.daily(trade_date=trade_date_text)
        return [self._stock_daily_record(row) for _, row in frame.iterrows()]

    def _stock_daily_record(self, row) -> StockDailyRecord:
        return StockDailyRecord(
            stock_code=str(row["ts_code"]).split(".")[0],
            trade_date=pd.to_datetime(row["trade_date"]).date(),
            open=as_float(row["open"]),
            high=as_float(row["high"]),
            low=as_float(row["low"]),
            close=as_float(row["close"]),
            pre_close=as_float(row["pre_close"]),
            change=as_float(row["change"]),
            pct_chg=as_float(row["pct_chg"]),
            volume=as_float(row["vol"]),
            amount=as_float(row["amount"]) * 1000,
            turnover_rate=None,
            source=self.name,
        )

    def _fetch_limit_snapshot(self, pro, trade_date_text: str) -> list[LimitSnapshotRecord]:
        frame = pro.limit_list_d(trade_date=trade_date_text)
        records: list[LimitSnapshotRecord] = []
        for _, row in frame.iterrows():
            status = self._limit_status(row.get("limit"))
            if not status:
                continue
            records.append(
                LimitSnapshotRecord(
                    trade_date=pd.to_datetime(row["trade_date"]).date(),
                    stock_code=str(row["ts_code"]).split(".")[0],
                    stock_name=str(row["name"]),
                    close_price=as_float(row["close"]),
                    pct_chg=as_float(row["pct_chg"]),
                    limit_status=status,
                    amount=as_float(row["amount"]),
                    source=self.name,
                )
            )
        return records

    def _to_ts_code(self, stock_code: str) -> str:
        market = infer_market(stock_code)
        suffix = "SH" if market == "SH" else "SZ"
        return f"{stock_code}.{suffix}"

    def _parse_optional_date(self, value) -> Optional[date]:
        if value is None or pd.isna(value) or value == "":
            return None
        return pd.to_datetime(str(value)).date()

    def _limit_status(self, value) -> Optional[str]:
        if value == "U":
            return "limit_up"
        if value == "D":
            return "limit_down"
        return None
