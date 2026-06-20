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


def test_market_data_tables_are_declared() -> None:
    assert {
        "trading_calendar",
        "stock_basic",
        "index_daily",
        "stock_daily",
        "limit_snapshot",
        "data_ingest_run",
    }.issubset(metadata.tables.keys())


def test_trading_calendar_is_unique_by_trade_date() -> None:
    columns = set(metadata.tables["trading_calendar"].columns.keys())

    assert {"id", "trade_date", "is_open", "source", "created_at"}.issubset(columns)
    assert ("trade_date",) in _unique_columns("trading_calendar")


def test_stock_basic_is_unique_by_stock_code() -> None:
    columns = set(metadata.tables["stock_basic"].columns.keys())

    assert {
        "id",
        "stock_code",
        "stock_name",
        "market",
        "list_date",
        "is_st",
        "status",
        "source",
        "updated_at",
    }.issubset(columns)
    assert ("stock_code",) in _unique_columns("stock_basic")


def test_daily_market_tables_have_duplicate_guards_and_date_indexes() -> None:
    assert ("index_code", "trade_date") in _unique_columns("index_daily")
    assert ("trade_date",) in _index_columns("index_daily")
    assert ("stock_code", "trade_date") in _unique_columns("stock_daily")
    assert ("trade_date",) in _index_columns("stock_daily")
    assert ("stock_code",) in _index_columns("stock_daily")
    assert ("trade_date", "stock_code", "limit_status") in _unique_columns("limit_snapshot")
    assert ("trade_date",) in _index_columns("limit_snapshot")


def test_ingest_run_records_provider_status_and_row_counts() -> None:
    columns = set(metadata.tables["data_ingest_run"].columns.keys())

    assert {
        "id",
        "provider",
        "trade_date",
        "status",
        "message",
        "trading_calendar_rows",
        "stock_basic_rows",
        "index_daily_rows",
        "stock_daily_rows",
        "limit_snapshot_rows",
        "created_at",
    }.issubset(columns)
    assert ("trade_date",) in _index_columns("data_ingest_run")
