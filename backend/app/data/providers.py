import json
import os
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Callable, Iterable, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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
    "sh000688": "000688.SH",
    "sh000300": "000300.SH",
    "sz399330": "399330.SZ",
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
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"-", "--", "None", "null", "NaN"}:
            return default
        value = text.replace(",", "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def tushare_amount_to_yuan(value) -> Optional[float]:
    amount = as_float(value, default=None)
    return amount * 1000 if amount is not None else None


def as_date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _row_value(row, *names: str):
    for name in names:
        if name in row:
            return row[name]
    return None


def normalize_stock_code(value) -> str:
    text = str(value or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")):
        text = text[2:]
    if "." in text:
        text = text.split(".", 1)[0]
    return text.zfill(6) if text else ""


def _strip_jsonp(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped
    if "(" in stripped and stripped.endswith(")"):
        return stripped.split("(", 1)[1].rsplit(")", 1)[0]
    return stripped


def is_plausible_realtime_daily(record: StockDailyRecord) -> bool:
    prices = [record.open, record.high, record.low, record.close, record.pre_close]
    if any(value is None for value in prices):
        return False
    if any(value <= 0 or value >= 100000 for value in prices):
        return False
    if record.low > record.high:
        return False
    if record.open > record.high or record.open < record.low:
        return False
    if record.close > record.high or record.close < record.low:
        return False
    if abs(record.change) >= 100000:
        return False
    if abs(record.pct_chg) >= 200:
        return False
    if record.volume < 0 or record.amount < 0:
        return False
    return True


def valid_realtime_daily(record: Optional[StockDailyRecord]) -> Optional[StockDailyRecord]:
    if record is None:
        return None
    return record if is_plausible_realtime_daily(record) else None


def fetch_eastmoney_limit_snapshot(trade_date: date, source: str = "akshare_eastmoney_limit_pool") -> list[LimitSnapshotRecord]:
    date_text = trade_date.strftime("%Y%m%d")
    records: list[LimitSnapshotRecord] = []
    with without_proxy_env():
        up_frame = ak.stock_zt_pool_em(date=date_text)
        down_frame = ak.stock_zt_pool_dtgc_em(date=date_text)

    for _, row in up_frame.iterrows():
        records.append(_eastmoney_limit_record(row, trade_date, "limit_up", source))
    for _, row in down_frame.iterrows():
        records.append(_eastmoney_limit_record(row, trade_date, "limit_down", source))
    return records


def _eastmoney_limit_record(row, trade_date: date, limit_status: str, source: str) -> LimitSnapshotRecord:
    return LimitSnapshotRecord(
        trade_date=trade_date,
        stock_code=normalize_stock_code(_row_value(row, "代码", "code")),
        stock_name=str(_row_value(row, "名称", "name") or ""),
        close_price=as_float(_row_value(row, "最新价", "close")),
        pct_chg=as_float(_row_value(row, "涨跌幅", "pct_chg")),
        limit_status=limit_status,
        amount=as_float(_row_value(row, "成交额", "amount")),
        source=source,
    )


def infer_limit_snapshot_from_daily(
    stock_daily: Iterable[StockDailyRecord],
    stock_basic: Iterable[StockBasicRecord],
    source: str = "inferred_from_stock_daily",
) -> list[LimitSnapshotRecord]:
    name_by_code = {record.stock_code: record.stock_name for record in stock_basic}
    records: list[LimitSnapshotRecord] = []
    for daily in stock_daily:
        status = _inferred_limit_status(daily)
        if not status:
            continue
        records.append(
            LimitSnapshotRecord(
                trade_date=daily.trade_date,
                stock_code=daily.stock_code,
                stock_name=name_by_code.get(daily.stock_code, daily.stock_code),
                close_price=daily.close,
                pct_chg=daily.pct_chg,
                limit_status=status,
                amount=daily.amount,
                source=source,
            )
        )
    return records


def _inferred_limit_status(record: StockDailyRecord) -> Optional[str]:
    if record.pct_chg >= _limit_threshold(record.stock_code) - 0.2:
        return "limit_up"
    if record.pct_chg <= -(_limit_threshold(record.stock_code) - 0.2):
        return "limit_down"
    return None


def _limit_threshold(stock_code: str) -> float:
    if stock_code.startswith(("30", "68")):
        return 20.0
    if stock_code.startswith(("4", "8", "9")):
        return 30.0
    return 10.0


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
        return fetch_eastmoney_limit_snapshot(trade_date)

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


class AkShareRealtimeQuoteProvider:
    name = "akshare_realtime"

    def __init__(self, spot_fetcher=None):
        self._spot_fetcher = spot_fetcher or ak.stock_zh_a_spot_em

    def fetch_realtime_stock_daily(
        self,
        stock_codes: Iterable[str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        wanted = {normalize_stock_code(code) for code in stock_codes}
        wanted.discard("")
        if not wanted:
            return []

        with without_proxy_env():
            frame = self._spot_fetcher()
        if frame.empty:
            return []

        records: list[StockDailyRecord] = []
        for _, row in frame.iterrows():
            code = normalize_stock_code(_row_value(row, "代码", "code", "symbol"))
            if code not in wanted:
                continue
            record = self._quote_row_to_daily(row, code, trade_date)
            if record is not None:
                records.append(record)
        return records

    def _quote_row_to_daily(self, row, stock_code: str, trade_date: date) -> Optional[StockDailyRecord]:
        close = as_float(_row_value(row, "最新价", "最新", "close", "trade"), default=None)
        open_price = as_float(_row_value(row, "今开", "开盘", "open"), default=None)
        high = as_float(_row_value(row, "最高", "high"), default=None)
        low = as_float(_row_value(row, "最低", "low"), default=None)
        pre_close = as_float(_row_value(row, "昨收", "pre_close", "settlement"), default=None)
        if not close or not open_price or not high or not low:
            return None
        if close <= 0 or open_price <= 0 or high <= 0 or low <= 0:
            return None
        pre_close = pre_close or close
        change = as_float(_row_value(row, "涨跌额", "change", "pricechange"), default=close - pre_close)
        pct_chg = as_float(_row_value(row, "涨跌幅", "pct_chg", "changepercent"), default=0.0)
        return valid_realtime_daily(
            StockDailyRecord(
                stock_code=stock_code,
                trade_date=trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                pre_close=pre_close,
                change=change,
                pct_chg=pct_chg,
                volume=as_float(_row_value(row, "成交量", "volume"), default=0.0),
                amount=as_float(_row_value(row, "成交额", "amount"), default=0.0),
                turnover_rate=as_float(_row_value(row, "换手率", "turnover_rate", "turnoverratio"), default=None),
                source=self.name,
            )
        )


class AkShareSinaRealtimeQuoteProvider(AkShareRealtimeQuoteProvider):
    name = "akshare_sina_realtime"

    def __init__(self, spot_fetcher=None):
        self._spot_fetcher = spot_fetcher or ak.stock_zh_a_spot


SinaQuoteFetcher = Callable[[str, float], str]


class SinaDirectRealtimeQuoteProvider:
    name = "sina_direct_realtime"

    def __init__(self, fetcher: Optional[SinaQuoteFetcher] = None, timeout: float = 5.0):
        self._fetcher = fetcher or self._fetch_sina_quotes
        self.timeout = timeout

    def fetch_realtime_stock_daily(
        self,
        stock_codes: Iterable[str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        symbol_to_code = {
            symbol: code
            for code in (normalize_stock_code(raw_code) for raw_code in stock_codes)
            if code
            for symbol in [self._sina_symbol(code)]
            if symbol
        }
        if not symbol_to_code:
            return []

        records: list[StockDailyRecord] = []
        symbols = list(symbol_to_code)
        for start in range(0, len(symbols), 80):
            batch_symbols = symbols[start : start + 80]
            url = f"https://hq.sinajs.cn/list={','.join(batch_symbols)}"
            text = self._fetcher(url, self.timeout)
            records.extend(self._parse_response(text, symbol_to_code, trade_date))
        return records

    def _sina_symbol(self, stock_code: str) -> Optional[str]:
        market = infer_market(stock_code)
        if market == "SH":
            return f"sh{stock_code}"
        if market == "SZ":
            return f"sz{stock_code}"
        if market == "BJ":
            return f"bj{stock_code}"
        return None

    def _fetch_sina_quotes(self, url: str, timeout: float) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn/",
            },
        )
        with without_proxy_env():
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("gbk", errors="replace")

    def _parse_response(
        self,
        text: str,
        symbol_to_code: dict[str, str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        records: list[StockDailyRecord] = []
        for statement in text.splitlines():
            if "=\"" not in statement:
                continue
            symbol = statement.split("hq_str_", 1)[-1].split("=", 1)[0]
            stock_code = symbol_to_code.get(symbol)
            if not stock_code:
                continue
            raw_fields = statement.split("=\"", 1)[-1].rsplit("\"", 1)[0]
            record = self._fields_to_daily(raw_fields.split(","), stock_code, trade_date)
            if record is not None:
                records.append(record)
        return records

    def _fields_to_daily(
        self,
        fields: list[str],
        stock_code: str,
        trade_date: date,
    ) -> Optional[StockDailyRecord]:
        if len(fields) < 10:
            return None
        open_price = as_float(fields[1], default=None)
        pre_close = as_float(fields[2], default=None)
        close = as_float(fields[3], default=None)
        high = as_float(fields[4], default=None)
        low = as_float(fields[5], default=None)
        volume = as_float(fields[8], default=0.0)
        amount = as_float(fields[9], default=0.0)
        if not close or not open_price or not high or not low:
            return None
        if close <= 0 or open_price <= 0 or high <= 0 or low <= 0:
            return None
        pre_close = pre_close or close
        change = close - pre_close
        pct_chg = (change / pre_close * 100) if pre_close else 0.0
        return valid_realtime_daily(
            StockDailyRecord(
                stock_code=stock_code,
                trade_date=trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                pre_close=pre_close,
                change=change,
                pct_chg=pct_chg,
                volume=volume,
                amount=amount,
                turnover_rate=None,
                source=self.name,
            )
        )


class TencentDirectRealtimeQuoteProvider:
    name = "tencent_direct_realtime"

    def __init__(self, fetcher: Optional[SinaQuoteFetcher] = None, timeout: float = 5.0):
        self._fetcher = fetcher or self._fetch_tencent_quotes
        self.timeout = timeout

    def fetch_realtime_stock_daily(
        self,
        stock_codes: Iterable[str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        symbol_to_code = {
            symbol: code
            for code in (normalize_stock_code(raw_code) for raw_code in stock_codes)
            if code
            for symbol in [self._tencent_symbol(code)]
            if symbol
        }
        if not symbol_to_code:
            return []

        records: list[StockDailyRecord] = []
        symbols = list(symbol_to_code)
        for start in range(0, len(symbols), 80):
            batch_symbols = symbols[start : start + 80]
            url = f"https://qt.gtimg.cn/q={','.join(batch_symbols)}"
            text = self._fetcher(url, self.timeout)
            records.extend(self._parse_response(text, symbol_to_code, trade_date))
        return records

    def _tencent_symbol(self, stock_code: str) -> Optional[str]:
        market = infer_market(stock_code)
        if market == "SH":
            return f"sh{stock_code}"
        if market == "SZ":
            return f"sz{stock_code}"
        if market == "BJ":
            return f"bj{stock_code}"
        return None

    def _fetch_tencent_quotes(self, url: str, timeout: float) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://stockapp.finance.qq.com/",
            },
        )
        with without_proxy_env():
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("gbk", errors="replace")

    def _parse_response(
        self,
        text: str,
        symbol_to_code: dict[str, str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        records: list[StockDailyRecord] = []
        for statement in text.splitlines():
            if "=\"" not in statement:
                continue
            symbol = statement.split("v_", 1)[-1].split("=", 1)[0]
            stock_code = symbol_to_code.get(symbol)
            if not stock_code:
                continue
            raw_fields = statement.split("=\"", 1)[-1].rsplit("\"", 1)[0]
            record = self._fields_to_daily(raw_fields.split("~"), stock_code, trade_date)
            if record is not None:
                records.append(record)
        return records

    def _fields_to_daily(
        self,
        fields: list[str],
        stock_code: str,
        trade_date: date,
    ) -> Optional[StockDailyRecord]:
        if len(fields) < 35:
            return None
        close = as_float(fields[3], default=None)
        pre_close = as_float(fields[4], default=None)
        open_price = as_float(fields[5], default=None)
        volume = as_float(fields[6], default=0.0)
        change = as_float(fields[31] if len(fields) > 31 else None, default=None)
        pct_chg = as_float(fields[32] if len(fields) > 32 else None, default=None)
        high = as_float(fields[33], default=None)
        low = as_float(fields[34], default=None)
        amount = as_float(fields[37] if len(fields) > 37 else None, default=0.0)
        turnover_rate = as_float(fields[38] if len(fields) > 38 else None, default=None)
        if not close or not open_price or not high or not low:
            return None
        if close <= 0 or open_price <= 0 or high <= 0 or low <= 0:
            return None
        pre_close = pre_close or close
        computed_change = close - pre_close
        return valid_realtime_daily(
            StockDailyRecord(
                stock_code=stock_code,
                trade_date=trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                pre_close=pre_close,
                change=change if change is not None else computed_change,
                pct_chg=pct_chg if pct_chg is not None else ((computed_change / pre_close * 100) if pre_close else 0.0),
                volume=volume,
                amount=amount,
                turnover_rate=turnover_rate,
                source=self.name,
            )
        )


class EastmoneyDirectRealtimeQuoteProvider:
    name = "eastmoney_direct_realtime"

    def __init__(self, fetcher: Optional[SinaQuoteFetcher] = None, timeout: float = 5.0):
        self._fetcher = fetcher or self._fetch_eastmoney_quotes
        self.timeout = timeout

    def fetch_realtime_stock_daily(
        self,
        stock_codes: Iterable[str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        secid_to_code = {
            secid: code
            for code in (normalize_stock_code(raw_code) for raw_code in stock_codes)
            if code
            for secid in [self._eastmoney_secid(code)]
            if secid
        }
        if not secid_to_code:
            return []

        records: list[StockDailyRecord] = []
        secids = list(secid_to_code)
        for start in range(0, len(secids), 80):
            batch_secids = secids[start : start + 80]
            query = urlencode(
                {
                    "fltt": "2",
                    "invt": "2",
                    "fields": "f12,f43,f44,f45,f46,f47,f48,f60,f170",
                    "secids": ",".join(batch_secids),
                }
            )
            url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?{query}"
            text = self._fetcher(url, self.timeout)
            records.extend(self._parse_response(text, secid_to_code, trade_date))
        return records

    def _eastmoney_secid(self, stock_code: str) -> Optional[str]:
        market = infer_market(stock_code)
        if market == "SH":
            return f"1.{stock_code}"
        if market in {"SZ", "BJ"}:
            return f"0.{stock_code}"
        return None

    def _fetch_eastmoney_quotes(self, url: str, timeout: float) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/",
            },
        )
        with without_proxy_env():
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")

    def _parse_response(
        self,
        text: str,
        secid_to_code: dict[str, str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        payload = json.loads(_strip_jsonp(text))
        rows = payload.get("data", {}).get("diff") or []
        records: list[StockDailyRecord] = []
        for row in rows:
            code = normalize_stock_code(str(row.get("f12") or ""))
            secid = self._eastmoney_secid(code) if code else None
            stock_code = secid_to_code.get(secid or "")
            if not stock_code:
                continue
            record = self._row_to_daily(row, stock_code, trade_date)
            if record is not None:
                records.append(record)
        return records

    def _row_to_daily(self, row: dict, stock_code: str, trade_date: date) -> Optional[StockDailyRecord]:
        close = as_float(row.get("f43"), default=None)
        high = as_float(row.get("f44"), default=None)
        low = as_float(row.get("f45"), default=None)
        open_price = as_float(row.get("f46"), default=None)
        volume = as_float(row.get("f47"), default=0.0)
        amount = as_float(row.get("f48"), default=0.0)
        pre_close = as_float(row.get("f60"), default=None)
        pct_chg = as_float(row.get("f170"), default=0.0)
        if not close or not open_price or not high or not low:
            return None
        if close <= 0 or open_price <= 0 or high <= 0 or low <= 0:
            return None
        pre_close = pre_close or close
        change = close - pre_close
        return valid_realtime_daily(
            StockDailyRecord(
                stock_code=stock_code,
                trade_date=trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                pre_close=pre_close,
                change=change,
                pct_chg=pct_chg or ((change / pre_close * 100) if pre_close else 0.0),
                volume=volume,
                amount=amount,
                turnover_rate=None,
                source=self.name,
            )
        )


class FallbackRealtimeQuoteProvider:
    name = "auto_realtime"

    def __init__(self, providers: Iterable[object]):
        self.providers = list(providers)
        self.last_provider_name: Optional[str] = None
        self.errors: list[str] = []

    def fetch_realtime_stock_daily(
        self,
        stock_codes: Iterable[str],
        trade_date: date,
    ) -> list[StockDailyRecord]:
        self.last_provider_name = None
        self.errors = []
        for provider in self.providers:
            try:
                records = provider.fetch_realtime_stock_daily(stock_codes, trade_date)
            except Exception as exc:
                self.errors.append(f"{provider.name}: {exc.__class__.__name__}: {exc}")
                continue
            self.last_provider_name = provider.name
            self.name = provider.name
            if records:
                return records
            self.errors.append(f"{provider.name}: 返回 0 行实时行情")
        raise RuntimeError("；".join(self.errors) or "所有实时行情源均未返回数据")


class MissingTushareTokenError(RuntimeError):
    pass


class TushareMarketDataProvider:
    name = "tushare"

    def __init__(self, token: str, pro_client=None, limit_snapshot_fetcher=None):
        self.token = token.strip()
        self._pro_client = pro_client
        self._limit_snapshot_fetcher = limit_snapshot_fetcher or fetch_eastmoney_limit_snapshot

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

        limit_snapshot = self._fetch_limit_snapshot(pro, trade_date_text, stock_daily, stock_basic)

        return MarketDataSnapshot(
            provider=self.name,
            trade_date=actual_trade_date,
            trading_calendar=self._fetch_trading_calendar(pro, actual_trade_date),
            stock_basic=stock_basic,
            index_daily=self._fetch_index_daily(pro, trade_date_text),
            stock_daily=stock_daily,
            limit_snapshot=limit_snapshot,
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
        end_date = pd.to_datetime(trade_date_text).date()
        start_date_text = (end_date - timedelta(days=45)).strftime("%Y%m%d")
        for index_code in INDEX_SYMBOLS.values():
            frame = pro.index_daily(
                ts_code=index_code,
                start_date=start_date_text,
                end_date=trade_date_text,
            )
            for _, row in frame.iterrows():
                records.append(
                    IndexDailyRecord(
                        index_code=str(row["ts_code"]),
                        trade_date=pd.to_datetime(row["trade_date"]).date(),
                        open=as_float(row["open"]),
                        high=as_float(row["high"]),
                        low=as_float(row["low"]),
                        close=as_float(row["close"]),
                        volume=as_float(row["vol"]),
                        amount=tushare_amount_to_yuan(row.get("amount")),
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

    def _fetch_limit_snapshot(
        self,
        pro,
        trade_date_text: str,
        stock_daily: Iterable[StockDailyRecord],
        stock_basic: Iterable[StockBasicRecord],
    ) -> list[LimitSnapshotRecord]:
        # TuShare limit_list_d may require higher privileges than a 3200-point account.
        # Keep TuShare for low-threshold core OHLC/calendar data, but source
        # limit-up/limit-down pools from free Eastmoney via AkShare. If the free
        # Eastmoney endpoint is temporarily unreachable, infer the pool from the
        # already fetched full-market daily pct_chg so startup data completion is
        # not blocked by a non-critical auxiliary endpoint.
        try:
            return self._limit_snapshot_fetcher(pd.to_datetime(trade_date_text).date())
        except Exception:
            return infer_limit_snapshot_from_daily(stock_daily, stock_basic)

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
