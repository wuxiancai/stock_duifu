from datetime import date
from typing import Callable, Optional

import akshare as ak
import pandas as pd
import tushare as ts

from backend.app.data.providers import normalize_stock_code, without_proxy_env
from backend.app.data_source_router import DataDomain, DataRequest, DataSourceRouter, DomainPolicy, sector_membership_adapter
from backend.app.sector.providers import ThsIndustryMemberFetcher, _filter_industry_sector_universe


class MissingCandidateDataTokenError(RuntimeError):
    pass


class FallbackIndustrySectorMembershipProvider:
    source = "fallback_industry_membership"

    def __init__(self, trade_date: date, providers: Optional[list] = None):
        self.trade_date = trade_date
        self.providers = providers or [
            EastmoneyIndustrySectorMembershipProvider(trade_date=trade_date),
            ThsIndustrySectorMembershipProvider(trade_date=trade_date),
        ]

    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {name: [] for name in sector_names}
        remaining = list(sector_names)
        errors: list[str] = []
        for provider in self.providers:
            if not remaining:
                break
            router = DataSourceRouter(
                [sector_membership_adapter(provider)],
                policies=[
                    DomainPolicy(
                        domain=DataDomain.SECTOR_MEMBERSHIP,
                        ordered_sources=[provider.source],
                        min_rows=0,
                        allow_empty=True,
                    )
                ],
            )
            try:
                response = router.fetch(
                    DataRequest(
                        domain=DataDomain.SECTOR_MEMBERSHIP,
                        sector_names=remaining,
                        min_rows=0,
                    )
                )
                provider_result = response.records
            except Exception as exc:
                errors.extend(router.errors or [f"{provider.source}: {exc.__class__.__name__}: {exc}"])
                continue
            for sector_name, codes in provider_result.items():
                if codes:
                    result[sector_name] = codes
            remaining = [name for name in sector_names if not result.get(name)]
        if sector_names and all(not codes for codes in result.values()):
            raise RuntimeError("所有免费行业成分股数据源均失败：" + "；".join(errors))
        return result


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
        failures: list[str] = []
        for sector_name in sector_names:
            try:
                with without_proxy_env():
                    member_frame = self._member_fetcher(symbol=sector_name)
            except Exception as exc:
                failures.append(f"{sector_name}: {exc.__class__.__name__}: {exc}")
                result[sector_name] = []
                continue
            result[sector_name] = [
                normalize_stock_code(code)
                for code in member_frame.get("代码", pd.Series(dtype=str)).dropna().tolist()
                if normalize_stock_code(code)
            ]
        if sector_names and len(failures) == len(sector_names):
            raise RuntimeError("东方财富行业成分股接口全部失败：" + "；".join(failures[:5]))
        return result


class ThsIndustrySectorMembershipProvider:
    source = "akshare_ths_industry_membership"

    def __init__(
        self,
        trade_date: date,
        member_fetcher: Optional[Callable[[str], list[str]]] = None,
    ):
        self.trade_date = trade_date
        self._member_fetcher = member_fetcher or ThsIndustryMemberFetcher().fetch_member_codes

    def sector_members(self, sector_names: list[str]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        failures: list[str] = []
        for sector_name in sector_names:
            try:
                result[sector_name] = self._member_fetcher(sector_name)
            except Exception as exc:
                failures.append(f"{sector_name}: {exc.__class__.__name__}: {exc}")
                result[sector_name] = []
        if sector_names and len(failures) == len(sector_names):
            raise RuntimeError("同花顺行业成分股接口全部失败：" + "；".join(failures[:5]))
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
