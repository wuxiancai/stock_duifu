from datetime import date

import pandas as pd
import tushare as ts


class MissingCandidateDataTokenError(RuntimeError):
    pass


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
