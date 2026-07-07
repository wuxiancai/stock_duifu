from datetime import date, timedelta
from io import StringIO
from typing import Callable, Optional

import akshare as ak
import pandas as pd
import requests
import tushare as ts

from backend.app.data.providers import as_float, normalize_stock_code, without_proxy_env
from backend.app.sector.service import SectorRawRecord


class MissingSectorDataTokenError(RuntimeError):
    pass


class FallbackSectorDataProvider:
    source = "fallback_sector_data"

    def __init__(self, providers: Optional[list] = None, member_fetch_limit: int = 80):
        self.providers = providers or [
            EastmoneyIndustrySectorDataProvider(member_fetch_limit=member_fetch_limit),
            ThsIndustrySectorDataProvider(member_fetch_limit=member_fetch_limit),
        ]

    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                records = provider.fetch_sector_window(trade_date=trade_date, lookback_days=lookback_days)
            except Exception as exc:
                errors.append(f"{provider.source}: {exc.__class__.__name__}: {exc}")
                continue
            if records:
                return records
            errors.append(f"{provider.source}: empty result")
        raise RuntimeError("所有免费行业数据源均失败：" + "；".join(errors))


class EastmoneyIndustrySectorDataProvider:
    """Free Eastmoney industry-board provider via AkShare."""

    source = "akshare_eastmoney_industry"

    def __init__(
        self,
        member_fetch_limit: int = 80,
        industry_fetcher: Optional[Callable[[], pd.DataFrame]] = None,
        history_fetcher: Optional[Callable[..., pd.DataFrame]] = None,
        member_fetcher: Optional[Callable[..., pd.DataFrame]] = None,
    ):
        self.member_fetch_limit = member_fetch_limit
        self._industry_fetcher = industry_fetcher or ak.stock_board_industry_name_em
        self._history_fetcher = history_fetcher or ak.stock_board_industry_hist_em
        self._member_fetcher = member_fetcher or ak.stock_board_industry_cons_em

    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        with without_proxy_env():
            industry_frame = self._industry_fetcher()
        if industry_frame.empty:
            return []

        records: list[SectorRawRecord] = []
        target_names = self._target_member_names(industry_frame)
        member_map = {name: self._fetch_member_codes(name) for name in target_names}

        start_date = (trade_date - timedelta(days=lookback_days * 2)).strftime("%Y%m%d")
        end_date = trade_date.strftime("%Y%m%d")
        for _, row in industry_frame.iterrows():
            sector_name = str(_row_value(row, "板块名称", "name") or "").strip()
            if not sector_name:
                continue
            sector_code = str(_row_value(row, "板块代码", "代码", "code") or sector_name).strip()
            history = self._fetch_history(sector_name, start_date, end_date)
            if history.empty:
                today_record = self._record_from_name_row(row, sector_code, sector_name, trade_date, member_map)
                if today_record is not None:
                    records.append(today_record)
                continue
            records.extend(self._history_records(history, row, sector_code, sector_name, trade_date, member_map))
        return records

    def _target_member_names(self, industry_frame: pd.DataFrame) -> list[str]:
        ordered = industry_frame.copy()
        if "涨跌幅" in ordered.columns:
            ordered = ordered.sort_values("涨跌幅", ascending=False)
        names = [str(name).strip() for name in ordered.get("板块名称", pd.Series(dtype=str)).dropna().tolist()]
        return [name for name in names if name][: self.member_fetch_limit]

    def _fetch_history(self, sector_name: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            with without_proxy_env():
                return self._history_fetcher(
                    symbol=sector_name,
                    start_date=start_date,
                    end_date=end_date,
                    period="日k",
                    adjust="",
                )
        except TypeError:
            with without_proxy_env():
                return self._history_fetcher(symbol=sector_name, start_date=start_date, end_date=end_date)
        except Exception:
            return pd.DataFrame()

    def _fetch_member_codes(self, sector_name: str) -> list[str]:
        try:
            with without_proxy_env():
                frame = self._member_fetcher(symbol=sector_name)
        except Exception:
            return []
        if frame.empty:
            return []
        return [normalize_stock_code(code) for code in frame.get("代码", pd.Series(dtype=str)).dropna().tolist()]

    def _record_from_name_row(
        self,
        row,
        sector_code: str,
        sector_name: str,
        trade_date: date,
        member_map: dict[str, list[str]],
    ) -> Optional[SectorRawRecord]:
        daily_return = as_float(_row_value(row, "涨跌幅", "pct_change"), default=None)
        if daily_return is None:
            return None
        return SectorRawRecord(
            sector_code=sector_code,
            sector_name=sector_name,
            trade_date=trade_date,
            daily_return=daily_return,
            amount=as_float(_row_value(row, "成交额", "amount"), default=0.0) or 0.0,
            up_num=int(as_float(_row_value(row, "上涨家数", "up_num"), default=0.0) or 0),
            down_num=int(as_float(_row_value(row, "下跌家数", "down_num"), default=0.0) or 0),
            member_codes=member_map.get(sector_name, []),
            source=self.source,
        )

    def _history_records(
        self,
        history: pd.DataFrame,
        today_row,
        sector_code: str,
        sector_name: str,
        trade_date: date,
        member_map: dict[str, list[str]],
    ) -> list[SectorRawRecord]:
        ordered = history.sort_values("日期") if "日期" in history.columns else history
        result: list[SectorRawRecord] = []
        for _, row in ordered.iterrows():
            row_date = pd.to_datetime(_row_value(row, "日期", "date")).date()
            if row_date > trade_date:
                continue
            is_target_day = row_date == trade_date
            result.append(
                SectorRawRecord(
                    sector_code=sector_code,
                    sector_name=sector_name,
                    trade_date=row_date,
                    daily_return=as_float(_row_value(row, "涨跌幅", "pct_change"), default=0.0) or 0.0,
                    amount=as_float(_row_value(row, "成交额", "amount"), default=0.0) or 0.0,
                    up_num=int(as_float(_row_value(today_row, "上涨家数", "up_num"), default=0.0) or 0) if is_target_day else 0,
                    down_num=int(as_float(_row_value(today_row, "下跌家数", "down_num"), default=0.0) or 0) if is_target_day else 0,
                    member_codes=member_map.get(sector_name, []) if is_target_day else [],
                    source=self.source,
                )
            )
        return result


class ThsIndustrySectorDataProvider:
    source = "akshare_ths_industry"

    def __init__(
        self,
        member_fetch_limit: int = 80,
        summary_fetcher: Optional[Callable[[], pd.DataFrame]] = None,
        history_fetcher: Optional[Callable[..., pd.DataFrame]] = None,
        member_fetcher: Optional[Callable[[str], list[str]]] = None,
    ):
        self.member_fetch_limit = member_fetch_limit
        self._summary_fetcher = summary_fetcher or ak.stock_board_industry_summary_ths
        self._history_fetcher = history_fetcher or ak.stock_board_industry_index_ths
        self._member_fetcher = member_fetcher or ThsIndustryMemberFetcher().fetch_member_codes

    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        with without_proxy_env():
            summary_frame = self._summary_fetcher()
        if summary_frame.empty:
            return []
        summary_frame = summary_frame.copy()
        target_names = self._target_member_names(summary_frame)
        member_map = {name: self._safe_member_codes(name) for name in target_names}
        start_date = (trade_date - timedelta(days=lookback_days * 2)).strftime("%Y%m%d")
        end_date = trade_date.strftime("%Y%m%d")

        records: list[SectorRawRecord] = []
        for _, row in summary_frame.iterrows():
            sector_name = str(_row_value(row, "板块", "name", "板块名称") or "").strip()
            if not sector_name:
                continue
            sector_code = str(_row_value(row, "代码", "code") or sector_name)
            history = self._fetch_history(sector_name, start_date, end_date)
            if history.empty:
                record = self._record_from_summary_row(row, sector_code, sector_name, trade_date, member_map)
                if record is not None:
                    records.append(record)
                continue
            records.extend(self._history_records(history, row, sector_code, sector_name, trade_date, member_map))
        return records

    def _target_member_names(self, frame: pd.DataFrame) -> list[str]:
        ordered = frame.copy()
        if "涨跌幅" in ordered.columns:
            ordered = ordered.sort_values("涨跌幅", ascending=False)
        names = [str(name).strip() for name in ordered.get("板块", pd.Series(dtype=str)).dropna().tolist()]
        return [name for name in names if name][: self.member_fetch_limit]

    def _fetch_history(self, sector_name: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            with without_proxy_env():
                return self._history_fetcher(symbol=sector_name, start_date=start_date, end_date=end_date)
        except Exception:
            return pd.DataFrame()

    def _safe_member_codes(self, sector_name: str) -> list[str]:
        try:
            return self._member_fetcher(sector_name)
        except Exception:
            return []

    def _record_from_summary_row(
        self,
        row,
        sector_code: str,
        sector_name: str,
        trade_date: date,
        member_map: dict[str, list[str]],
    ) -> Optional[SectorRawRecord]:
        daily_return = as_float(_row_value(row, "涨跌幅", "pct_change"), default=None)
        if daily_return is None:
            return None
        return SectorRawRecord(
            sector_code=sector_code,
            sector_name=sector_name,
            trade_date=trade_date,
            daily_return=daily_return,
            amount=as_float(_row_value(row, "总成交额", "成交额", "amount"), default=0.0) or 0.0,
            up_num=int(as_float(_row_value(row, "上涨家数", "up_num"), default=0.0) or 0),
            down_num=int(as_float(_row_value(row, "下跌家数", "down_num"), default=0.0) or 0),
            member_codes=member_map.get(sector_name, []),
            source=self.source,
        )

    def _history_records(
        self,
        history: pd.DataFrame,
        today_row,
        sector_code: str,
        sector_name: str,
        trade_date: date,
        member_map: dict[str, list[str]],
    ) -> list[SectorRawRecord]:
        ordered = history.sort_values("日期") if "日期" in history.columns else history
        if "收盘价" in ordered.columns:
            ordered = ordered.copy()
            ordered["_daily_return"] = ordered["收盘价"].pct_change() * 100
        result: list[SectorRawRecord] = []
        for _, row in ordered.iterrows():
            row_date = pd.to_datetime(_row_value(row, "日期", "date")).date()
            if row_date > trade_date:
                continue
            is_target_day = row_date == trade_date
            daily_return = (
                as_float(_row_value(row, "涨跌幅", "pct_change", "_daily_return"), default=None)
            )
            if daily_return is None and is_target_day:
                daily_return = as_float(_row_value(today_row, "涨跌幅", "pct_change"), default=0.0) or 0.0
            result.append(
                SectorRawRecord(
                    sector_code=sector_code,
                    sector_name=sector_name,
                    trade_date=row_date,
                    daily_return=daily_return or 0.0,
                    amount=as_float(_row_value(row, "成交额", "总成交额", "amount"), default=0.0) or 0.0,
                    up_num=int(as_float(_row_value(today_row, "上涨家数", "up_num"), default=0.0) or 0) if is_target_day else 0,
                    down_num=int(as_float(_row_value(today_row, "下跌家数", "down_num"), default=0.0) or 0) if is_target_day else 0,
                    member_codes=member_map.get(sector_name, []) if is_target_day else [],
                    source=self.source,
                )
            )
        return result


class ThsIndustryMemberFetcher:
    def __init__(
        self,
        name_fetcher: Optional[Callable[[], pd.DataFrame]] = None,
        page_fetcher: Optional[Callable[[str], pd.DataFrame]] = None,
    ):
        self._name_fetcher = name_fetcher or ak.stock_board_industry_name_ths
        self._page_fetcher = page_fetcher or fetch_ths_industry_member_frame

    def fetch_member_codes(self, sector_name: str) -> list[str]:
        with without_proxy_env():
            names = self._name_fetcher()
        code = _ths_sector_code(names, sector_name)
        if not code:
            return []
        with without_proxy_env():
            frame = self._page_fetcher(code)
        return _member_codes_from_frame(frame)


def fetch_ths_industry_member_frame(sector_code: str) -> pd.DataFrame:
    url = f"http://q.10jqka.com.cn/thshy/detail/code/{sector_code}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
    for table in tables:
        if any(column in table.columns for column in ["代码", "股票代码"]):
            return table
    return pd.DataFrame()


def _ths_sector_code(names: pd.DataFrame, sector_name: str) -> str:
    if names.empty:
        return ""
    name_column = "name" if "name" in names.columns else "板块"
    code_column = "code" if "code" in names.columns else "代码"
    matched = names[names[name_column].astype(str).str.strip().eq(sector_name)]
    if matched.empty:
        return ""
    return str(matched.iloc[0][code_column]).strip()


def _member_codes_from_frame(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return []
    for column in ["代码", "股票代码", "code", "symbol"]:
        if column in frame.columns:
            return [normalize_stock_code(code) for code in frame[column].dropna().tolist() if normalize_stock_code(code)]
    return []


class TushareDCSectorDataProvider:
    source = "tushare_dc"

    _INDUSTRY_LEVEL = "东财一级行业"
    _EXCLUDED_CONCEPT_NAMES = {
        "昨日首板",
        "昨日炸板",
        "昨日高换手",
        "昨日高振幅",
        "东方财富热股",
        "昨日打二板以上表现",
        "先进制造风格",
        "消费风格",
        "医药医疗风格",
        "科技风格",
        "金融地产风格",
        "趋势股",
        "反转股",
        "题材股",
        "昨日连板_含一字",
        "昨日连板",
        "高换手",
        "高振幅",
    }

    def __init__(self, token: str, pro_client=None, member_fetch_limit: int = 80):
        self.token = token.strip()
        self._pro_client = pro_client
        self.member_fetch_limit = member_fetch_limit

    def fetch_sector_window(self, trade_date: date, lookback_days: int = 5) -> list[SectorRawRecord]:
        if not self.token:
            raise MissingSectorDataTokenError("TUSHARE_TOKEN is required for sector provider=tushare_dc")
        pro = self._pro_client or ts.pro_api(self.token)
        start_date = (trade_date - timedelta(days=lookback_days * 2)).strftime("%Y%m%d")
        end_date = trade_date.strftime("%Y%m%d")
        frame = pro.dc_index(start_date=start_date, end_date=end_date)
        if frame.empty:
            return []
        frame = _filter_industry_sector_universe(frame)
        if frame.empty:
            return []

        target_codes = self._target_member_codes(frame, trade_date)
        member_map = {code: self._fetch_member_codes(pro, code) for code in target_codes}

        records: list[SectorRawRecord] = []
        for _, row in frame.iterrows():
            sector_code = str(row["ts_code"])
            row_date = pd.to_datetime(row["trade_date"]).date()
            records.append(
                SectorRawRecord(
                    sector_code=sector_code,
                    sector_name=str(row["name"]),
                    trade_date=row_date,
                    daily_return=_float(row.get("pct_change")),
                    amount=_amount_proxy(row),
                    up_num=int(_float(row.get("up_num"))),
                    down_num=int(_float(row.get("down_num"))),
                    member_codes=member_map.get(sector_code, []) if row_date == trade_date else [],
                    source=self.source,
                )
            )
        return records

    def _target_member_codes(self, frame, trade_date: date) -> list[str]:
        target = frame[frame["trade_date"].map(lambda value: pd.to_datetime(value).date()) == trade_date]
        if target.empty:
            return []
        ordered = target.sort_values(
            by=["pct_change", "up_num"],
            ascending=[False, False],
        )
        return [str(code) for code in ordered["ts_code"].head(self.member_fetch_limit).tolist()]

    def _fetch_member_codes(self, pro, sector_code: str) -> list[str]:
        frame = pro.dc_member(ts_code=sector_code)
        if frame.empty:
            return []
        return [str(code) for code in frame["con_code"].dropna().tolist()]


def _row_value(row, *names: str):
    for name in names:
        if name in row:
            return row[name]
    return None


def _amount_proxy(row) -> float:
    total_mv = _float(row.get("total_mv"))
    turnover_rate = _float(row.get("turnover_rate"))
    return total_mv * turnover_rate / 100


def _filter_rankable_sector_universe(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the primary sector universe used by the decision dashboard.

    The strong-sector module must rank stable industry sectors. Concept boards are
    useful as thematic/elasticity signals, but they should not compete with
    industry sectors in the main Top 10 ranking.
    """
    return _filter_industry_sector_universe(frame)


def _filter_industry_sector_universe(frame: pd.DataFrame) -> pd.DataFrame:
    if "idx_type" not in frame.columns or "level" not in frame.columns:
        return frame
    return frame[
        frame["idx_type"].eq("行业板块")
        & frame["level"].eq(TushareDCSectorDataProvider._INDUSTRY_LEVEL)
    ].copy()


def _filter_concept_sector_universe(frame: pd.DataFrame) -> pd.DataFrame:
    if "idx_type" not in frame.columns:
        return frame
    return frame[
        frame["idx_type"].eq("概念板块")
        & ~frame["name"].isin(TushareDCSectorDataProvider._EXCLUDED_CONCEPT_NAMES)
    ].copy()


def _float(value, default: Optional[float] = 0.0) -> float:
    if value is None or pd.isna(value):
        return default or 0.0
    return float(value)
