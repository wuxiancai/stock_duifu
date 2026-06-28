from datetime import date

from backend.app.data.global_index_quotes import load_global_index_quotes, parse_sina_global_quotes


SINA_SAMPLE = """
var hq_str_gb_dji="道琼斯,51876.1094,-0.09,2026-06-27 05:12:06,-44.5100,51803.7695,52130.0703,51614.7383,52655.6602,43340.6797,1321068148,647274708,0,0.00,--,0.00,0.00,0.00,0.00,0,0,0.0000,0.00,0.0000,,Jun 26 05:11PM EDT,51920.6211,0,1,2026";
var hq_str_gb_ixic="纳斯达克,25297.6177,-0.24,2026-06-27 05:30:00,-60.9852,25105.4142,25491.3747,25014.9599,27190.2070,20095.0488,16299253327,10567992138,0,0.00,--,0.00,0.00,0.00,0.00,0,0,0.0000,0.00,0.00,,Jun 26 05:16PM EDT,25358.6029,0,1,2026,0.0000,0.0000,0.0000,0.0000,0.0000,0.0000";
var hq_str_gb_inx="标普500指数,7354.0200,-0.05,2026-06-27 05:07:24,-3.4700,7312.7402,7392.9502,7294.1802,7620.8999,6174.9702,5860380568,3933014998,0,0.00,--,0.00,0.00,0.00,0.00,0,0,0.0000,0.00,0.0000,,Jun 26 05:07PM EDT,7357.4902,0,1,2026";
var hq_str_rt_hkHSI="HSI,恒生指数,22952.090,23076.910,22962.460,22518.000,22671.859,-405.050,-1.760,0.000,0.000,342100755.868,18476196242,0.000,0.000,28056.100,22978.590,2026/06/26,16:08:32,,,,,,";
"""


def test_parse_sina_global_quotes_returns_four_configured_indices() -> None:
    quotes = parse_sina_global_quotes(SINA_SAMPLE)

    assert set(quotes) == {"HSI", "IXIC", "SPX", "DJI"}
    assert quotes["HSI"].name == "恒生"
    assert quotes["HSI"].trade_date == date(2026, 6, 26)
    assert quotes["HSI"].close == 22671.859
    assert quotes["HSI"].change == -405.05
    assert quotes["HSI"].pct_chg == -1.76
    assert quotes["HSI"].amount == 342100755.868
    assert quotes["IXIC"].name == "纳斯达克"
    assert quotes["IXIC"].close == 25297.6177
    assert quotes["IXIC"].change == -60.9852
    assert quotes["IXIC"].pct_chg == -0.24
    assert quotes["SPX"].name == "标普"
    assert quotes["DJI"].name == "道琼斯"


def test_load_global_index_quotes_uses_isolated_fetcher() -> None:
    def fake_fetcher(url: str, timeout: float) -> str:
        assert "hq.sinajs.cn" in url
        assert timeout == 2.5
        return SINA_SAMPLE

    quotes = load_global_index_quotes(fetcher=fake_fetcher, timeout=2.5)

    assert quotes["DJI"].close == 51876.1094
    assert quotes["SPX"].trade_date == date(2026, 6, 27)
