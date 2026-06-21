from datetime import date

from backend.app.simulation.cli import main as cli_main
from backend.app.simulation.service import SimulationAccountSnapshot, SimulationRiskSnapshot, SimulationSummary, SimulationWorkflowSummary


def test_simulation_cli_runs_trade_date(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_simulation(engine, trade_date):
        calls.append((engine, trade_date))
        return _summary(trade_date)

    monkeypatch.setattr("backend.app.simulation.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("backend.app.simulation.cli.run_simulation", fake_run_simulation)
    monkeypatch.setattr("sys.argv", ["simulation", "run", "--trade-date", "2026-06-19"])

    cli_main()

    assert calls == [("engine", date(2026, 6, 19))]
    assert '"as_of_date": "2026-06-19"' in capsys.readouterr().out


def test_simulation_cli_runs_workflow(monkeypatch, capsys) -> None:
    calls = []

    def fake_run_simulation_workflow(engine, trade_date, mark_untriggered_at_close=False):
        calls.append((engine, trade_date, mark_untriggered_at_close))
        return SimulationWorkflowSummary(target_trade_date=trade_date, tracking=[], simulation=_summary(trade_date))

    monkeypatch.setattr("backend.app.simulation.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("backend.app.simulation.cli.run_simulation_workflow", fake_run_simulation_workflow)
    monkeypatch.setattr(
        "sys.argv",
        ["simulation", "run-workflow", "--trade-date", "2026-06-19", "--mark-untriggered-at-close"],
    )

    cli_main()

    assert calls == [("engine", date(2026, 6, 19), True)]
    output = capsys.readouterr().out
    assert '"target_trade_date": "2026-06-19"' in output
    assert '"simulation"' in output


def test_simulation_cli_prints_latest(monkeypatch, capsys) -> None:
    monkeypatch.setattr("backend.app.simulation.cli.create_database_engine", lambda: "engine")
    monkeypatch.setattr("backend.app.simulation.cli.load_latest_simulation", lambda engine: _summary(date(2026, 6, 19)))
    monkeypatch.setattr("sys.argv", ["simulation", "latest"])

    cli_main()

    assert '"as_of_date": "2026-06-19"' in capsys.readouterr().out


def _summary(as_of_date: date) -> SimulationSummary:
    return SimulationSummary(
        as_of_date=as_of_date,
        account=SimulationAccountSnapshot(
            id=1,
            account_name="默认模拟账户",
            initial_cash=1000000.0,
            available_cash=1000000.0,
            frozen_cash=0.0,
            market_value=0.0,
            total_assets=1000000.0,
            total_profit=0.0,
            total_return=0.0,
            max_drawdown=0.0,
        ),
        positions=[],
        trades=[],
        equity_curve=[],
        risk=SimulationRiskSnapshot(max_drawdown=0.0, position_count=0, position_ratio=0.0),
        messages=[],
    )
