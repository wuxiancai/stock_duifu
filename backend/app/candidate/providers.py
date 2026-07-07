from datetime import date
from typing import Callable, Optional

import akshare as ak
import pandas as pd
import tushare as ts

from backend.app.data.providers import normalize_stock_code, without_proxy_env
from backend.app.sector.providers import _filter_industry_sector_universe


class MissingCandidateDataTokenError(RuntimeError):
    pass


class EastmoneyIndustrySectorMembershipProvider:
    source = "akshare_eastmoney_industry_membership"

    def __init__(
        self,
        trade_date: date,
        member_fetcher: Optional[Callable[..., pd.DataFrame]] = None,
    ):
        self.trade_date = trade_date
        self._member_fetcher = member_fetcher or ak.stock_board_industry_cons_em

    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for sector_name in sector_names:
            try:
                with without_proxy_env():
                    member_frame = self._member_fetcher(symbol=sector_name)
            except Exception:
                result[sector_name] = []
                continue
            result[sector_name] = [
                normalize_stock_code(code)
                for code in member_frame.get("代码", pd.Series(dtype=str)).dropna().tolist()
                if normalize_stock_code(code)
            ]
        return result


class TushareDCSectorMembershipProvider:
    def __init__(self, token: str, trade_date: date, pro_client=None):
        self.token = token.strip()
        self.trade_date = trade_date
        self._pro_client = pro_client

    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        if not self.token:
            raise MissingCandidateDataTokenError("TUSHARE_TOKEN is required for candidate sector membership")
        pro = self._pro_client or ts.pro_api(self.token)
        index_frame = pro.dc_index(trade_date=self.trade_date.strftime("%Y%m%d"))
        index_frame = _filter_industry_sector_universe(index_frame)
        code_by_name = {
            str(row["name"]): str(row["ts_code"])
            for _, row in index_frame.iterrows()
        }
        result: dict[str, list[str]] = {}
        for sector_name in sector_names:
            sector_code = code_by_name.get(sector_name)
            if not sector_code:
                result[sector_name] = []
                continue
            member_frame = pro.dc_member(ts_code=sector_code)
            result[sector_name] = [_normalize_code(code) for code in member_frame["con_code"].dropna().tolist()]
        return result


def _normalize_code(code: str) -> str:
    return str(code).split(".")[0].zfill(6)
