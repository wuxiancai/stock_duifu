from datetime import date
from types import SimpleNamespace

from backend.app.trade.cli import main as cli_main


def test_trade_plan_cli_generates_json_summary(monkeypatch, capsys) -> None:
    calls = []

    def fake_generate_trade_plans(engine, plan_date, target_trade_date=None, limit=None):
        calls.append((engine, plan_date, target_trade_date, limit))
        return [
            SimpleNamespace(
                plan_date=plan_date,
                target_trade_date=target_trade_date,
                stock_code="000001",
                stock_name="平安银行",
                sector_name="机器人",
                strategy_type="趋势强势",
                stock_score=95,
                sector_score=100,
                market_status="中性",
                buy_condition="回踩 MA5 不破",
                buy_price_low=10.0,
                buy_price_high=10.5,
                stop_loss_price=9.8,
                take_profit_price=12.6,
                position_ratio=0.4,
                status="待触发",
                risk_note="测试风险",
            )
        ]

    monkeypatch.setattr("backend.app.trade.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("backend.app.trade.cli.generate_trade_plans", fake_generate_trade_plans)
    monkeypatch.setattr(
        "sys.argv",
        [
            "trade",
            "generate",
            "--plan-date",
            "2026-06-18",
            "--target-trade-date",
            "2026-06-19",
            "--limit",
            "2",
        ],
    )

    cli_main()

    assert calls == [("engine", date(2026, 6, 18), date(2026, 6, 19), 2)]
    assert '"stock_code": "000001"' in capsys.readouterr().out
