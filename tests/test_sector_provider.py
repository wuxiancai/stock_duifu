from datetime import date

import pandas as pd

from backend.app.sector.providers import TushareDCSectorDataProvider


class FakeTushareSectorClient:
    def __init__(self):
        self.member_kwargs = []

    def dc_index(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "BK0001.DC",
                    "trade_date": "20260618",
                    "name": "机器人",
                    "pct_change": 5.5,
                    "total_mv": 1000000,
                    "turnover_rate": 3.0,
                    "up_num": 12,
                    "down_num": 3,
                },
                {
                    "ts_code": "BK0002.DC",
                    "trade_date": "20260618",
                    "name": "银行",
                    "pct_change": 1.2,
                    "total_mv": 2000000,
                    "turnover_rate": 1.0,
                    "up_num": 8,
                    "down_num": 4,
                },
                {
                    "ts_code": "BK0001.DC",
                    "trade_date": "20260617",
                    "name": "机器人",
                    "pct_change": 2.0,
                    "total_mv": 900000,
                    "turnover_rate": 2.0,
                    "up_num": 10,
                    "down_num": 5,
                },
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


def test_tushare_dc_sector_provider_maps_index_and_member_rows() -> None:
    client = FakeTushareSectorClient()
    provider = TushareDCSectorDataProvider(token="token-value", pro_client=client, member_fetch_limit=1)

    records = provider.fetch_sector_window(date(2026, 6, 18))

    today_records = [record for record in records if record.trade_date == date(2026, 6, 18)]
    assert len(records) == 3
    assert today_records[0].sector_code == "BK0001.DC"
    assert today_records[0].sector_name == "机器人"
    assert today_records[0].amount == 30000
    assert today_records[0].member_codes == ["000001.SZ", "600519.SH"]
    assert client.member_kwargs == [{"ts_code": "BK0001.DC"}]
