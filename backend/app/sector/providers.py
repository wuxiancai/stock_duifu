from datetime import date, timedelta
from typing import Optional

import pandas as pd
import tushare as ts

from backend.app.sector.service import SectorRawRecord


class MissingSectorDataTokenError(RuntimeError):
    pass


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
        frame = _filter_rankable_sector_universe(frame)
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


def _amount_proxy(row) -> float:
    total_mv = _float(row.get("total_mv"))
    turnover_rate = _float(row.get("turnover_rate"))
    return total_mv * turnover_rate / 100


def _filter_rankable_sector_universe(frame: pd.DataFrame) -> pd.DataFrame:
    if "idx_type" not in frame.columns or "level" not in frame.columns:
        return frame

    concept_mask = frame["idx_type"].eq("概念板块") & ~frame["name"].isin(
        TushareDCSectorDataProvider._EXCLUDED_CONCEPT_NAMES
    )
    first_level_industry_mask = frame["idx_type"].eq("行业板块") & frame["level"].eq(
        TushareDCSectorDataProvider._INDUSTRY_LEVEL
    )
    return frame[concept_mask | first_level_industry_mask].copy()


def _float(value, default: Optional[float] = 0.0) -> float:
    if value is None or pd.isna(value):
        return default or 0.0
    return float(value)
