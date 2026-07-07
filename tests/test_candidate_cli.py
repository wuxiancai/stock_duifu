from datetime import date
from types import SimpleNamespace

from backend.app.candidate.cli import main as cli_main


def test_candidate_cli_generates_json_summary(monkeypatch, capsys) -> None:
    calls = []

    def fake_generate_candidate_stocks(engine, trade_date, provider, limit):
        calls.append((engine, trade_date, type(provider).__name__, limit))
        return [
            SimpleNamespace(
                trade_date=trade_date,
                stock_code="000001",
                stock_name="平安银行",
                sector_name="机器人",
                sector_rank=1,
                strategy_type="趋势强势",
                stock_score=95,
                sector_score=100,
                close_price=10.5,
                amount=1200000000,
                reason="测试原因",
                risk_note="测试风险",
            )
        ]

    monkeypatch.setattr("backend.app.candidate.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("backend.app.candidate.cli.generate_candidate_stocks", fake_generate_candidate_stocks)
    monkeypatch.setattr(
        "sys.argv",
        ["candidate", "generate", "--trade-date", "2026-06-18", "--limit", "20"],
    )

    cli_main()

    assert calls == [("engine", date(2026, 6, 18), "FallbackIndustrySectorMembershipProvider", 20)]
    assert '"stock_code": "000001"' in capsys.readouterr().out
