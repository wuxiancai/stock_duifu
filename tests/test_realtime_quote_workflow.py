from datetime import date

import pandas as pd
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.data.providers import (
    AkShareRealtimeQuoteProvider,
    AkShareSinaRealtimeQuoteProvider,
    FallbackRealtimeQuoteProvider,
    SinaDirectRealtimeQuoteProvider,
)
from backend.app.data.cli import load_realtime_quote_provider
import backend.app.data.realtime_quotes as realtime_quotes
from backend.app.data.realtime_quotes import run_realtime_quote_workflow
from backend.app.data.types import StockDailyRecord
from backend.app.db.models import SimulationAccount, SimulationPosition, SimulationTrade, StockDaily, TradePlan, TradingCalendar, metadata


def _engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    return engine


def _seed_plan(session: Session, stock_code: str = "000001") -> None:
    session.add(
        TradingCalendar(trade_date=date(2026, 6, 19), is_open=True, source="unit-test")
    )
    session.add(
        TradePlan(
            plan_date=date(2026, 6, 18),
            target_trade_date=date(2026, 6, 19),
            stock_code=stock_code,
            stock_name="计划内股票",
            sector_name="科技风格",
            strategy_type="趋势强势",
            stock_score=99,
            sector_score=100,
            market_status="中性",
            buy_condition="目标交易日价格触达计划买入区间",
            buy_price_low=10.0,
            buy_price_high=11.0,
            stop_loss_price=9.5,
            take_profit_price=13.2,
            position_ratio=0.4,
            status="待触发",
            risk_note="严格执行止损",
        )
    )


def _daily(stock_code: str = "000001") -> StockDailyRecord:
    return StockDailyRecord(
        stock_code=stock_code,
        trade_date=date(2026, 6, 19),
        open=10.1,
        high=10.8,
        low=10.0,
        close=10.5,
        pre_close=10.0,
        change=0.5,
        pct_chg=5.0,
        volume=100000,
        amount=105000000,
        turnover_rate=3.0,
        source="unit-test-realtime",
    )


class FakeRealtimeProvider:
    name = "unit-test-realtime"

    def __init__(self, rows: list[StockDailyRecord]):
        self.rows = rows
        self.calls = []

    def fetch_realtime_stock_daily(self, stock_codes, trade_date):
        self.calls.append((list(stock_codes), trade_date))
        wanted = set(stock_codes)
        return [row for row in self.rows if row.stock_code in wanted and row.trade_date == trade_date]


class FailingRealtimeProvider:
    name = "failing-realtime"

    def __init__(self):
        self.calls = []

    def fetch_realtime_stock_daily(self, stock_codes, trade_date):
        self.calls.append((list(stock_codes), trade_date))
        raise RuntimeError("primary disconnected")


def test_akshare_realtime_quote_provider_maps_spot_rows_to_stock_daily_records() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "000001",
                "名称": "平安银行",
                "最新价": 10.5,
                "今开": 10.1,
                "最高": 10.8,
                "最低": 10.0,
                "昨收": 10.0,
                "涨跌额": 0.5,
                "涨跌幅": 5.0,
                "成交量": 100000,
                "成交额": 105000000,
                "换手率": 3.0,
            },
            {
                "代码": "000002",
                "最新价": 0,
                "今开": 0,
                "最高": 0,
                "最低": 0,
                "昨收": 10.0,
            },
        ]
    )
    provider = AkShareRealtimeQuoteProvider(spot_fetcher=lambda: frame)

    records = provider.fetch_realtime_stock_daily(["000001", "000002"], date(2026, 6, 19))

    assert len(records) == 1
    record = records[0]
    assert record.stock_code == "000001"
    assert record.trade_date == date(2026, 6, 19)
    assert record.open == 10.1
    assert record.high == 10.8
    assert record.low == 10.0
    assert record.close == 10.5
    assert record.pre_close == 10.0
    assert record.pct_chg == 5.0
    assert record.turnover_rate == 3.0
    assert record.source == "akshare_realtime"


def test_akshare_sina_realtime_quote_provider_maps_sina_spot_rows() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "sh600000",
                "code": "600000",
                "name": "浦发银行",
                "trade": 8.88,
                "open": 8.8,
                "high": 9.0,
                "low": 8.7,
                "settlement": 8.6,
                "pricechange": 0.28,
                "changepercent": 3.25,
                "volume": 123456,
                "amount": 12345678,
                "turnoverratio": 1.23,
            }
        ]
    )
    provider = AkShareSinaRealtimeQuoteProvider(spot_fetcher=lambda: frame)

    records = provider.fetch_realtime_stock_daily(["600000"], date(2026, 6, 19))

    assert len(records) == 1
    record = records[0]
    assert record.stock_code == "600000"
    assert record.close == 8.88
    assert record.pre_close == 8.6
    assert record.change == 0.28
    assert record.pct_chg == 3.25
    assert record.turnover_rate == 1.23
    assert record.source == "akshare_sina_realtime"


def test_sina_direct_realtime_quote_provider_fetches_only_requested_symbols() -> None:
    calls = []
    text = (
        'var hq_str_sz000001="平安银行,10.10,10.00,10.50,10.80,10.00,'
        '10.49,10.50,100000,105000000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,'
        '2026-06-19,14:59:59,00,";\n'
        'var hq_str_sh600000="浦发银行,8.80,8.60,8.88,9.00,8.70,'
        '8.87,8.88,123456,12345678,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,'
        '2026-06-19,14:59:59,00,";'
    )

    def fetcher(url: str, timeout: float) -> str:
        calls.append((url, timeout))
        return text

    provider = SinaDirectRealtimeQuoteProvider(fetcher=fetcher, timeout=1.5)

    records = provider.fetch_realtime_stock_daily(["000001", "600000"], date(2026, 6, 19))

    assert calls == [("https://hq.sinajs.cn/list=sz000001,sh600000", 1.5)]
    assert [record.stock_code for record in records] == ["000001", "600000"]
    assert records[0].close == 10.5
    assert records[0].pre_close == 10.0
    assert round(records[0].pct_chg, 2) == 5.0
    assert records[0].amount == 105000000
    assert records[0].source == "sina_direct_realtime"


def test_fallback_realtime_quote_provider_uses_sina_after_primary_error() -> None:
    primary = FailingRealtimeProvider()
    fallback = FakeRealtimeProvider([_daily("600000")])
    provider = FallbackRealtimeQuoteProvider([primary, fallback])

    records = provider.fetch_realtime_stock_daily(["600000"], date(2026, 6, 19))

    assert len(records) == 1
    assert records[0].stock_code == "600000"
    assert primary.calls == [(["600000"], date(2026, 6, 19))]
    assert fallback.calls == [(["600000"], date(2026, 6, 19))]
    assert provider.last_provider_name == "unit-test-realtime"
    assert provider.name == "unit-test-realtime"
    assert provider.errors == ["failing-realtime: RuntimeError: primary disconnected"]


def test_auto_realtime_provider_prefers_direct_sina_before_full_market_sources() -> None:
    provider = load_realtime_quote_provider("auto")

    assert isinstance(provider, FallbackRealtimeQuoteProvider)
    assert isinstance(provider.providers[0], SinaDirectRealtimeQuoteProvider)


def test_run_realtime_quote_workflow_backfills_quotes_tracks_plan_and_buys() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_plan(session)
        session.commit()

    provider = FakeRealtimeProvider([_daily()])

    result = run_realtime_quote_workflow(
        engine,
        date(2026, 6, 19),
        provider,
        allow_date_mismatch=True,
    )

    assert result.backfill.planned_stock_count == 1
    assert result.backfill.requested_stock_count == 1
    assert result.backfill.fetched_stock_daily_rows == 1
    assert result.backfill.missing_stock_codes == []
    assert result.backfill.skipped_reason == ""
    assert provider.calls == [(["000001"], date(2026, 6, 19))]
    assert result.workflow is not None
    assert result.workflow.tracking[0].status == "已触发"
    assert result.workflow.simulation.trades[0].trade_type == "买入"

    with Session(engine) as session:
        plan = session.scalar(select(TradePlan).where(TradePlan.stock_code == "000001"))
        assert plan.status == "已触发"
        assert plan.trigger_price is not None
        assert session.scalar(select(StockDaily).where(StockDaily.stock_code == "000001"))
        assert session.scalar(select(SimulationTrade).where(SimulationTrade.stock_code == "000001"))


def test_run_realtime_quote_workflow_backfills_active_position_quotes() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_plan(session)
        old_plan = TradePlan(
            plan_date=date(2026, 6, 17),
            target_trade_date=date(2026, 6, 18),
            stock_code="300308",
            stock_name="持仓股票",
            sector_name="科技风格",
            strategy_type="趋势强势",
            stock_score=88,
            sector_score=90,
            market_status="中性",
            buy_condition="目标交易日价格触达计划买入区间",
            buy_price_low=100,
            buy_price_high=110,
            stop_loss_price=95,
            take_profit_price=132,
            position_ratio=0.2,
            status="已触发",
            trigger_price=100,
            tracking_note="历史持仓",
            risk_note="严格执行止损",
        )
        session.add(old_plan)
        account = SimulationAccount(
            account_name="默认模拟账户",
            initial_cash=1000000,
            available_cash=800000,
            frozen_cash=0,
            market_value=100000,
            total_assets=900000,
            total_profit=-100000,
            total_return=-0.1,
            max_drawdown=0.1,
        )
        session.add(account)
        session.flush()
        session.add(
            SimulationPosition(
                account_id=account.id,
                trade_plan_id=old_plan.id,
                stock_code="300308",
                stock_name="持仓股票",
                sector_name="科技风格",
                strategy_type="趋势强势",
                buy_price=100,
                current_price=100,
                quantity=1000,
                market_value=100000,
                cost_amount=100000,
                unrealized_profit=0,
                unrealized_return=0,
                stop_loss_price=95,
                take_profit_price=132,
                position_status="持仓中",
                buy_reason="历史持仓",
                sell_reason="",
            )
        )
        session.commit()

    position_daily = StockDailyRecord(
        stock_code="300308",
        trade_date=date(2026, 6, 19),
        open=101,
        high=106,
        low=99,
        close=105,
        pre_close=100,
        change=5,
        pct_chg=5,
        volume=100000,
        amount=105000000,
        turnover_rate=3.0,
        source="unit-test-realtime",
    )
    provider = FakeRealtimeProvider([_daily(), position_daily])

    result = run_realtime_quote_workflow(
        engine,
        date(2026, 6, 19),
        provider,
        allow_date_mismatch=True,
    )

    assert provider.calls == [(["000001", "300308"], date(2026, 6, 19))]
    assert result.backfill.planned_stock_count == 1
    assert result.backfill.requested_stock_count == 2
    assert result.backfill.fetched_stock_daily_rows == 2
    assert result.workflow is not None
    with Session(engine) as session:
        position = session.scalar(select(SimulationPosition).where(SimulationPosition.stock_code == "300308"))
        assert float(position.current_price) == 105.0
        assert float(position.market_value) == 105000.0


def test_run_realtime_quote_workflow_refreshes_when_stock_daily_already_exists() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_plan(session)
        session.add(StockDaily(**_daily().__dict__))
        session.commit()

    refreshed = StockDailyRecord(
        **{
            **_daily().__dict__,
            "close": 10.8,
            "high": 11.0,
            "change": 0.8,
            "pct_chg": 8.0,
            "source": "unit-test-realtime-refresh",
        }
    )
    provider = FakeRealtimeProvider([refreshed])

    result = run_realtime_quote_workflow(
        engine,
        date(2026, 6, 19),
        provider,
        allow_date_mismatch=True,
    )

    assert result.backfill.existing_stock_count == 1
    assert result.backfill.requested_stock_count == 1
    assert result.backfill.fetched_stock_daily_rows == 1
    assert result.backfill.skipped_reason == ""
    assert provider.calls == [(["000001"], date(2026, 6, 19))]
    assert result.workflow is not None
    assert result.workflow.tracking[0].status == "已触发"
    assert result.workflow.simulation.trades[0].trade_type == "买入"
    with Session(engine) as session:
        daily = session.scalar(select(StockDaily).where(StockDaily.stock_code == "000001"))
        assert float(daily.close) == 10.8
        assert float(daily.pct_chg) == 8.0


def test_run_realtime_quote_workflow_fetches_today_quotes_when_calendar_row_is_missing(monkeypatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_plan(session)
        session.execute(delete(TradingCalendar).where(TradingCalendar.trade_date == date(2026, 6, 19)))
        session.commit()
    monkeypatch.setattr(realtime_quotes, "_china_today", lambda: date(2026, 6, 19))
    provider = FakeRealtimeProvider([_daily()])

    result = run_realtime_quote_workflow(
        engine,
        date(2026, 6, 19),
        provider,
        allow_date_mismatch=False,
    )

    assert result.backfill.target_is_open is None
    assert result.backfill.skipped_reason == ""
    assert result.backfill.fetched_stock_daily_rows == 1
    assert provider.calls == [(["000001"], date(2026, 6, 19))]
    assert result.workflow is not None
    assert result.workflow.tracking[0].current_price == 10.5
