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
        "trade_plan",
        "trade_review",
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
