from datetime import date
from types import SimpleNamespace

from backend.app.sector.cli import main as cli_main


def test_sector_cli_generates_json_summary(monkeypatch, capsys) -> None:
    calls = []

    def fake_generate_sector_rankings(engine, trade_date, provider):
        calls.append((engine, trade_date, provider.source))
        return [
            SimpleNamespace(
                trade_date=trade_date,
                sector_name="机器人",
                rank_no=1,
                daily_return=5.5,
                three_day_return=8.0,
                amount_change=30.0,
                limit_up_count=2,
                strong_stock_count=8,
                sector_score=100,
            )
        ]

    monkeypatch.setattr("backend.app.sector.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr(
        "backend.app.sector.cli.generate_sector_rankings",
        fake_generate_sector_rankings,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["sector", "generate", "--trade-date", "2026-06-18"],
    )

    cli_main()

    assert calls == [("engine", date(2026, 6, 18), "akshare_eastmoney_industry")]
    assert '"sector_name": "机器人"' in capsys.readouterr().out
