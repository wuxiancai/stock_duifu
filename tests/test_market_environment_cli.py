from datetime import date
from types import SimpleNamespace

from backend.app.market.cli import main as cli_main


def test_market_environment_cli_generates_json_summary(monkeypatch, capsys) -> None:
    calls = []

    def fake_generate_market_environment(engine, trade_date):
        calls.append((engine, trade_date))
        return SimpleNamespace(
            trade_date=trade_date,
            market_score=70,
            market_status="中性",
            suggested_position="50% - 80%",
            up_count=3000,
            down_count=2000,
            limit_up_count=45,
            limit_down_count=8,
            total_amount=1200000000000,
            suggestion="测试建议",
        )

    monkeypatch.setattr("backend.app.market.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr(
        "backend.app.market.cli.generate_market_environment",
        fake_generate_market_environment,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["market", "generate", "--trade-date", "2026-06-18"],
    )

    cli_main()

    assert calls == [("engine", date(2026, 6, 18))]
    assert '"market_score": 70' in capsys.readouterr().out
