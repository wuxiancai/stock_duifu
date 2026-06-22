from sqlalchemy import UniqueConstraint

from backend.app.db.models import metadata


def _unique_columns(table_name: str) -> set[tuple[str, ...]]:
    table = metadata.tables[table_name]
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _index_columns(table_name: str) -> set[tuple[str, ...]]:
    table = metadata.tables[table_name]
    return {tuple(column.name for column in index.columns) for index in table.indexes}


def test_core_mvp_tables_are_declared() -> None:
    assert {
        "market_daily",
        "sector_daily",
        "candidate_stock",
        "trade_plan",
        "trade_review",
        "simulation_account",
        "simulation_position",
        "simulation_trade",
        "simulation_equity",
    }.issubset(metadata.tables.keys())


def test_market_daily_has_required_columns_and_trade_date_uniqueness() -> None:
    columns = set(metadata.tables["market_daily"].columns.keys())

    assert {
        "id",
        "trade_date",
        "market_score",
        "market_status",
        "up_count",
        "down_count",
        "limit_up_count",
        "limit_down_count",
        "limit_up_height",
        "total_amount",
        "suggestion",
        "created_at",
    }.issubset(columns)
    assert ("trade_date",) in _unique_columns("market_daily")


def test_sector_daily_has_required_columns_and_duplicate_guards() -> None:
    columns = set(metadata.tables["sector_daily"].columns.keys())

    assert {
        "id",
        "trade_date",
        "sector_name",
        "rank_no",
        "daily_return",
        "five_day_return",
        "amount_change",
        "limit_up_count",
        "strong_stock_count",
        "sector_score",
        "created_at",
    }.issubset(columns)
    assert ("trade_date", "sector_name") in _unique_columns("sector_daily")
    assert ("trade_date", "rank_no") in _unique_columns("sector_daily")


def test_candidate_stock_has_required_columns_indexes_and_duplicate_guards() -> None:
    columns = set(metadata.tables["candidate_stock"].columns.keys())

    assert {
        "id",
        "trade_date",
        "stock_code",
        "stock_name",
        "sector_name",
        "sector_rank",
        "strategy_type",
        "stock_score",
        "sector_score",
        "close_price",
        "amount",
        "reason",
        "risk_note",
        "created_at",
    }.issubset(columns)
    assert ("trade_date", "stock_code", "strategy_type") in _unique_columns("candidate_stock")
    assert ("trade_date",) in _index_columns("candidate_stock")
    assert ("stock_code",) in _index_columns("candidate_stock")
    assert ("strategy_type",) in _index_columns("candidate_stock")


def test_trade_plan_has_required_columns_indexes_and_duplicate_guards() -> None:
    columns = set(metadata.tables["trade_plan"].columns.keys())

    assert {
        "id",
        "plan_date",
        "target_trade_date",
        "stock_code",
        "stock_name",
        "sector_name",
        "strategy_type",
        "stock_score",
        "sector_score",
        "market_status",
        "buy_condition",
        "buy_price_low",
        "buy_price_high",
        "stop_loss_price",
        "take_profit_price",
        "position_ratio",
        "status",
        "trigger_price",
        "trigger_time",
        "tracking_note",
        "is_watched",
        "risk_note",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert (
        "plan_date",
        "target_trade_date",
        "stock_code",
        "strategy_type",
    ) in _unique_columns("trade_plan")
    assert ("plan_date",) in _index_columns("trade_plan")
    assert ("target_trade_date",) in _index_columns("trade_plan")
    assert ("status",) in _index_columns("trade_plan")


def test_trade_review_has_required_columns_and_plan_date_guard() -> None:
    columns = set(metadata.tables["trade_review"].columns.keys())

    assert {
        "id",
        "trade_plan_id",
        "trade_date",
        "stock_code",
        "stock_name",
        "strategy_type",
        "triggered",
        "trigger_price",
        "close_price",
        "day_return",
        "t5_return",
        "max_profit",
        "max_loss",
        "result",
        "failure_reason",
        "discipline_check",
        "note",
        "created_at",
    }.issubset(columns)
    assert ("trade_plan_id", "trade_date") in _unique_columns("trade_review")
    assert ("trade_date",) in _index_columns("trade_review")


def test_simulation_tables_have_required_columns_indexes_and_duplicate_guards() -> None:
    account_columns = set(metadata.tables["simulation_account"].columns.keys())
    position_columns = set(metadata.tables["simulation_position"].columns.keys())
    trade_columns = set(metadata.tables["simulation_trade"].columns.keys())
    equity_columns = set(metadata.tables["simulation_equity"].columns.keys())

    assert {
        "id",
        "account_name",
        "initial_cash",
        "available_cash",
        "market_value",
        "total_assets",
        "total_profit",
        "total_return",
        "max_drawdown",
    }.issubset(account_columns)
    assert ("account_name",) in _unique_columns("simulation_account")

    assert {
        "id",
        "account_id",
        "trade_plan_id",
        "stock_code",
        "stock_name",
        "sector_name",
        "strategy_type",
        "buy_price",
        "current_price",
        "quantity",
        "market_value",
        "cost_amount",
        "unrealized_profit",
        "unrealized_return",
        "stop_loss_price",
        "take_profit_price",
        "position_status",
        "buy_reason",
        "sell_reason",
    }.issubset(position_columns)
    assert ("account_id", "trade_plan_id") in _unique_columns("simulation_position")
    assert ("position_status",) in _index_columns("simulation_position")
    position_plan_fk = next(iter(metadata.tables["simulation_position"].c.trade_plan_id.foreign_keys))
    assert position_plan_fk.ondelete is None

    assert {
        "id",
        "account_id",
        "trade_plan_id",
        "trade_date",
        "trade_type",
        "price",
        "quantity",
        "amount",
        "commission",
        "stamp_tax",
        "transfer_fee",
        "total_fee",
        "net_amount",
        "cash_after",
        "position_ratio_after",
        "profit_loss",
        "profit_loss_return",
        "reason",
    }.issubset(trade_columns)
    trade_plan_fk = next(iter(metadata.tables["simulation_trade"].c.trade_plan_id.foreign_keys))
    assert trade_plan_fk.ondelete is None
    assert ("trade_date",) in _index_columns("simulation_trade")

    assert {
        "id",
        "account_id",
        "trade_date",
        "available_cash",
        "market_value",
        "total_assets",
        "daily_profit",
        "daily_return",
        "max_drawdown",
    }.issubset(equity_columns)
    assert ("account_id", "trade_date") in _unique_columns("simulation_equity")
    assert ("trade_date",) in _index_columns("simulation_equity")
