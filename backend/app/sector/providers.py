from datetime import date, timedelta
from typing import Callable, Optional

import akshare as ak
import pandas as pd
import tushare as ts

from backend.app.data.providers import as_float, normalize_stock_code, without_proxy_env
from backend.app.sector.service import SectorRawRecord


class MissingSectorDataTokenError(RuntimeError):
    pass


class EastmoneyIndustrySectorDataProvider:
    """Free Eastmoney industry-board provider via AkShare.

    This replaces the TuShare dc_index/dc_member default path so accounts with
    about 3200 points do not depend on higher/unclear privilege endpoints for
    the daily strong-industry workflow.
    """

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
