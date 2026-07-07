from datetime import date
from types import SimpleNamespace

from backend.app.workflow.service import run_after_close_workflow


class FakeMarketProvider:
    def fetch_snapshot(self, trade_date, sample_size, stock_codes=None):
        return SimpleNamespace(trade_date=trade_date, sample_size=sample_size, stock_codes=stock_codes)


class FakeSectorProvider:
    source = "sector-test"


class FakeCandidateProvider:
    source = "candidate-test"


def test_after_close_workflow_runs_prd_steps_in_order(monkeypatch) -> None:
    calls = []

    def fake_ingest(engine, snapshot):
        calls.append(("ingest", engine, snapshot.trade_date, snapshot.sample_size))
        return SimpleNamespace(
            trading_calendar_rows=3,
            stock_basic_rows=2,
            index_daily_rows=3,
            stock_daily_rows=2,
            limit_snapshot_rows=1,
            ingest_run_id=None,
        )

    def fake_market(engine, trade_date):
        calls.append(("market", engine, trade_date))
        return SimpleNamespace(trade_date=trade_date, market_score=65, market_status="中性")

    def fake_sectors(engine, trade_date, provider):
        calls.append(("sectors", engine, trade_date, provider.source))
        return [SimpleNamespace(sector_name="机器人")]

    def fake_candidates(engine, trade_date, provider, limit):
        calls.append(("candidates", engine, trade_date, provider.source, limit))
        return [SimpleNamespace(stock_code="000001"), SimpleNamespace(stock_code="000002")]

    def fake_reviews(engine, trade_date):
        calls.append(("reviews", engine, trade_date))
        return SimpleNamespace(review_date=trade_date, total_count=2, triggered_count=1, win_rate=0.5)

    def fake_plans(engine, plan_date, limit=None):
        calls.append(("plans", engine, plan_date, limit))
        return [SimpleNamespace(stock_code="000001", target_trade_date=date(2026, 6, 19))]

    monkeypatch.setattr("backend.app.workflow.service.ingest_market_snapshot", fake_ingest)
    monkeypatch.setattr("backend.app.workflow.service.generate_market_environment", fake_market)
    monkeypatch.setattr("backend.app.workflow.service.generate_sector_rankings", fake_sectors)
    monkeypatch.setattr("backend.app.workflow.service.generate_candidate_stocks", fake_candidates)
    monkeypatch.setattr("backend.app.workflow.service.generate_trade_reviews", fake_reviews)
    monkeypatch.setattr("backend.app.workflow.service.generate_trade_plans", fake_plans)

    result = run_after_close_workflow(
        "engine",
        date(2026, 6, 18),
        FakeMarketProvider(),
        FakeSectorProvider(),
        FakeCandidateProvider(),
        candidate_limit=50,
        trade_plan_limit=2,
    )

    assert calls == [
        ("ingest", "engine", date(2026, 6, 18), 0),
        ("market", "engine", date(2026, 6, 18)),
        ("sectors", "engine", date(2026, 6, 18), "sector-test"),
        ("candidates", "engine", date(2026, 6, 18), "candidate-test", 50),
        ("reviews", "engine", date(2026, 6, 18)),
        ("plans", "engine", date(2026, 6, 18), 2),
    ]
    assert result.trade_date == date(2026, 6, 18)
    assert result.stock_daily_rows == 2
    assert result.ingest_run_id is None
    assert result.market_status == "中性"
    assert result.sector_count == 1
    assert result.candidate_count == 2
    assert result.review_count == 2
    assert result.trade_plan_count == 1
    assert result.target_trade_date == date(2026, 6, 19)


def test_after_close_workflow_reuses_existing_sectors_when_provider_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.workflow.service.ingest_market_snapshot",
        lambda engine, snapshot: SimpleNamespace(
            trading_calendar_rows=3,
            stock_basic_rows=2,
            index_daily_rows=3,
            stock_daily_rows=2,
            limit_snapshot_rows=1,
            ingest_run_id=None,
        ),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_market_environment",
        lambda engine, trade_date: SimpleNamespace(trade_date=trade_date, market_score=65, market_status="中性"),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_sector_rankings",
        lambda engine, trade_date, provider: (_ for _ in ()).throw(Exception("sector source failed")),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service._load_existing_sector_rankings_or_raise",
        lambda engine, trade_date, exc: [SimpleNamespace(sector_name="半导体")],
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_candidate_stocks",
        lambda engine, trade_date, provider, limit: [SimpleNamespace(stock_code="000001")],
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_trade_reviews",
        lambda engine, trade_date: SimpleNamespace(review_date=trade_date, total_count=0, triggered_count=0, win_rate=0),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_trade_plans",
        lambda engine, plan_date, limit=None: [SimpleNamespace(stock_code="000001", target_trade_date=date(2026, 6, 19))],
    )

    result = run_after_close_workflow(
        "engine",
        date(2026, 6, 18),
        FakeMarketProvider(),
        FakeSectorProvider(),
        FakeCandidateProvider(),
    )

    assert result.sector_count == 1
    assert result.candidate_count == 1


def test_after_close_workflow_reuses_existing_candidates_when_membership_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.workflow.service.ingest_market_snapshot",
        lambda engine, snapshot: SimpleNamespace(
            trading_calendar_rows=3,
            stock_basic_rows=2,
            index_daily_rows=3,
            stock_daily_rows=2,
            limit_snapshot_rows=1,
            ingest_run_id=None,
        ),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_market_environment",
        lambda engine, trade_date: SimpleNamespace(trade_date=trade_date, market_score=65, market_status="中性"),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_sector_rankings",
        lambda engine, trade_date, provider: [SimpleNamespace(sector_name="半导体")],
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_candidate_stocks",
        lambda engine, trade_date, provider, limit: (_ for _ in ()).throw(Exception("member source failed")),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service._load_existing_candidates_or_raise",
        lambda engine, trade_date, exc: [SimpleNamespace(stock_code="000001"), SimpleNamespace(stock_code="000002")],
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_trade_reviews",
        lambda engine, trade_date: SimpleNamespace(review_date=trade_date, total_count=0, triggered_count=0, win_rate=0),
    )
    monkeypatch.setattr(
        "backend.app.workflow.service.generate_trade_plans",
        lambda engine, plan_date, limit=None: [SimpleNamespace(stock_code="000001", target_trade_date=date(2026, 6, 19))],
    )

    result = run_after_close_workflow(
        "engine",
        date(2026, 6, 18),
        FakeMarketProvider(),
        FakeSectorProvider(),
        FakeCandidateProvider(),
    )

    assert result.sector_count == 1
    assert result.candidate_count == 2
