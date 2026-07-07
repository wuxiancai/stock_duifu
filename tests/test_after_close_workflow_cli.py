from datetime import date
from types import SimpleNamespace

from backend.app.workflow.cli import main as cli_main
from backend.app.workflow.service import AfterCloseWorkflowResult


def test_after_close_workflow_cli_outputs_json_summary(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_after_close_workflow(
        engine,
        trade_date,
        market_provider,
        sector_provider,
        candidate_provider,
        candidate_limit=50,
        trade_plan_limit=None,
    ):
        calls.append(
            (
                engine,
                trade_date,
                market_provider.source,
                sector_provider.source,
                candidate_provider.source,
                candidate_limit,
                trade_plan_limit,
            )
        )
        return AfterCloseWorkflowResult(
            trade_date=trade_date,
            trading_calendar_rows=3,
            stock_basic_rows=2,
            index_daily_rows=3,
            stock_daily_rows=2,
            limit_snapshot_rows=1,
            ingest_run_id=7,
            market_score=65,
            market_status="中性",
            sector_count=10,
            candidate_count=42,
            review_count=2,
            trade_plan_count=2,
            target_trade_date=date(2026, 6, 19),
        )

    monkeypatch.setattr("backend.app.workflow.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("backend.app.workflow.cli.load_provider", lambda provider: SimpleNamespace(source=provider))
    monkeypatch.setattr("backend.app.workflow.cli.run_after_close_workflow", fake_run_after_close_workflow)
    monkeypatch.setattr(
        "sys.argv",
        [
            "workflow",
            "after-close",
            "--trade-date",
            "2026-06-18",
            "--provider",
            "auto",
            "--candidate-limit",
            "50",
            "--trade-plan-limit",
            "2",
        ],
    )

    cli_main()

    assert calls == [
        (
            "engine",
            date(2026, 6, 18),
            "auto",
            "akshare_eastmoney_industry",
            "akshare_eastmoney_industry_membership",
            50,
            2,
        )
    ]
    output = capsys.readouterr().out
    assert '"market_status": "中性"' in output
    assert '"review_count": 2' in output
    assert '"trade_plan_count": 2' in output
