from datetime import date

import pandas as pd

from backend.app.candidate.providers import TushareDCSectorMembershipProvider


class FakeTushareClient:
    def __init__(self):
        self.member_kwargs = []

    def dc_index(self, **kwargs):
        return pd.DataFrame(
            [
                {"ts_code": "BK0001.DC", "trade_date": "20260618", "name": "机器人"},
                {"ts_code": "BK0002.DC", "trade_date": "20260618", "name": "半导体"},
            ]
        )

    def dc_member(self, **kwargs):
        self.member_kwargs.append(kwargs)
        return pd.DataFrame(
            [
                {"ts_code": kwargs["ts_code"], "con_code": "000001.SZ", "name": "平安银行"},
                {"ts_code": kwargs["ts_code"], "con_code": "600519.SH", "name": "贵州茅台"},
            ]
        )


def test_tushare_dc_sector_membership_provider_maps_names_to_member_codes() -> None:
    client = FakeTushareClient()
    provider = TushareDCSectorMembershipProvider(
        token="token-value",
        trade_date=date(2026, 6, 18),
        pro_client=client,
    )

    members = provider.sector_members(["机器人", "不存在"])

    assert members == {"机器人": ["000001", "600519"], "不存在": []}
    assert client.member_kwargs == [{"ts_code": "BK0001.DC"}]
