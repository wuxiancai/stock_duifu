import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.data.audit import MarketDataCoverageAudit, audit_market_data_coverage
from backend.app.db.models import (
    CandidateStock,
    DataJobRun,
    DataJobStep,
    IndexDaily,
    LimitSnapshot,
    MarketDaily,
    SectorDaily,
    StockBasic,
    StockDaily,
    TradePlan,
    TradingCalendar,
)


@dataclass(frozen=True)
class DataJobStepSummary:
    step_name: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    rows_count: int
    summary: dict[str, Any]
    error_message: str


@dataclass(frozen=True)
class DataJobRunSummary:
    id: int
    job_name: str
    trade_date: date
    status: str
    command: str
    message: str
    started_at: datetime
    ended_at: Optional[datetime]
    steps: list[DataJobStepSummary]


@dataclass(frozen=True)
class DatabaseHealthItem:
    name: str
    status: str
    message: str
    actual: str
    expected: str
    fix_command: str


@dataclass(frozen=True)
class DatabaseHealthSummary:
    trade_date: Optional[date]
    status: str
    generated_at: datetime
    items: list[DatabaseHealthItem]


def create_data_job_run(engine: Engine, trade_date: date, command: str) -> int:
    with Session(engine) as session:
        run = DataJobRun(
            job_name="after_close_data_pull",
            trade_date=trade_date,
            status="running",
            command=command,
            message="夜间数据拉取进行中",
            started_at=_now(),
        )
        session.add(run)
        session.commit()
        return run.id


def record_data_job_step(
    engine: Engine,
    run_id: int,
    step_name: str,
    operation: Callable[[], Any],
    summary_builder: Callable[[Any], dict[str, Any]],
    rows_counter: Callable[[Any], int],
) -> Any:
    step_id = _start_step(engine, run_id, step_name)
    try:
        result = operation()
    except Exception as exc:
        _finish_step(engine, step_id, "failed", {}, 0, str(exc))
        raise
    summary = summary_builder(result)
    _finish_step(engine, step_id, "success", summary, rows_counter(result), "")
    return result


def finish_data_job_run(engine: Engine, run_id: int, status: str, message: str) -> None:
    with Session(engine) as session:
        run = session.get(DataJobRun, run_id)
        if run is None:
            return
        run.status = status
        run.message = message
        run.ended_at = _now()
        session.commit()


def load_latest_data_job_runs(engine: Engine, limit: int = 5) -> list[DataJobRunSummary]:
    with Session(engine) as session:
        runs = session.scalars(
            select(DataJobRun).order_by(desc(DataJobRun.started_at)).limit(limit)
        ).all()
        if not runs:
            return []
        steps = session.scalars(
            select(DataJobStep)
            .where(DataJobStep.run_id.in_([run.id for run in runs]))
            .order_by(DataJobStep.started_at)
        ).all()
        steps_by_run: dict[int, list[DataJobStepSummary]] = {}
        for step in steps:
            steps_by_run.setdefault(step.run_id, []).append(
                DataJobStepSummary(
                    step_name=step.step_name,
                    status=step.status,
                    started_at=step.started_at,
                    ended_at=step.ended_at,
                    rows_count=step.rows_count,
                    summary=json.loads(step.summary_json or "{}"),
                    error_message=step.error_message,
                )
            )
        return [
            DataJobRunSummary(
                id=run.id,
                job_name=run.job_name,
                trade_date=run.trade_date,
                status=run.status,
                command=run.command,
                message=run.message,
                started_at=run.started_at,
                ended_at=run.ended_at,
                steps=steps_by_run.get(run.id, []),
            )
            for run in runs
        ]


def load_database_health(engine: Engine, trade_date: Optional[date] = None) -> DatabaseHealthSummary:
    with Session(engine) as session:
        target_date = trade_date or _latest_relevant_trade_date(session)
        items: list[DatabaseHealthItem] = []
        if target_date is None:
            return DatabaseHealthSummary(
                trade_date=None,
                status="error",
                generated_at=_now(),
                items=[
                    DatabaseHealthItem(
                        name="交易日历",
                        status="error",
                        message="数据库没有任何交易日或行情日期，无法判断数据完整性。",
                        actual="0",
                        expected="至少 1 个交易日",
                        fix_command="TRADE_DATE=YYYY-MM-DD bash get_data.sh",
                    )
                ],
            )

        open_days = _count(session, TradingCalendar, TradingCalendar.trade_date <= target_date, TradingCalendar.is_open.is_(True))
        stock_basic_rows = _count(session, StockBasic)
        stock_daily_rows = _count(session, StockDaily, StockDaily.trade_date == target_date)
        index_daily_rows = _count(session, IndexDaily, IndexDaily.trade_date == target_date)
        limit_rows = _count(session, LimitSnapshot, LimitSnapshot.trade_date == target_date)
        market_rows = _count(session, MarketDaily, MarketDaily.trade_date == target_date)
        sector_rows = _count(session, SectorDaily, SectorDaily.trade_date == target_date)
        max_sector_rank = session.scalar(
            select(func.max(SectorDaily.rank_no)).where(SectorDaily.trade_date == target_date)
        ) or 0
        candidate_rows = _count(session, CandidateStock, CandidateStock.trade_date == target_date)
        trade_plan_rows = _count(session, TradePlan, TradePlan.plan_date == target_date)
        latest_run = session.scalar(
            select(DataJobRun).where(DataJobRun.trade_date == target_date).order_by(desc(DataJobRun.started_at)).limit(1)
        )

        command = f"TRADE_DATE={target_date.isoformat()} bash get_data.sh"
        items.extend(
            [
                _health_item("交易日历", open_days > 0, open_days, "至少 1 个开市日", command, error=True),
                _health_item("股票基础信息", stock_basic_rows >= 5000, stock_basic_rows, "不少于 5000 只 A 股", command, error=True),
                _stock_daily_health_item(target_date, stock_basic_rows, stock_daily_rows, command),
                _health_item("指数日线", index_daily_rows >= 3, index_daily_rows, "三大指数至少 3 行", command, error=True),
                _health_item("涨跌停池", limit_rows > 0, limit_rows, "涨停/跌停记录不能为 0", command, error=False),
                _health_item("市场环境", market_rows > 0, market_rows, "必须生成 market_daily", f"bash scripts/generate-market-environment.sh --trade-date {target_date.isoformat()}", error=True),
                _sector_health_item(target_date, sector_rows, max_sector_rank, command),
                _health_item("候选股票", candidate_rows > 0, candidate_rows, "应生成候选股票或明确为空", f"bash scripts/generate-candidates.sh --trade-date {target_date.isoformat()}", error=False),
                _health_item("交易计划", trade_plan_rows > 0, trade_plan_rows, "应生成次日交易计划或明确为空", f"bash scripts/generate-trade-plans.sh --plan-date {target_date.isoformat()}", error=False),
                _latest_job_health_item(target_date, latest_run, command),
            ]
        )

    statuses = {item.status for item in items}
    status = "error" if "error" in statuses else "warning" if "warning" in statuses else "ok"
    return DatabaseHealthSummary(trade_date=target_date, status=status, generated_at=_now(), items=items)


def audit_step_summary(audit: MarketDataCoverageAudit) -> dict[str, Any]:
    return _jsonable(asdict(audit))


def audit_step_status(audit: MarketDataCoverageAudit) -> tuple[str, str]:
    if audit.index_daily_rows < 3 or audit.stock_basic_rows == 0 or audit.stock_daily_rows == 0:
        return "error", "覆盖审计发现核心行情缺失"
    if audit.stock_basic_rows < 5000 or audit.missing_stock_daily_rows > 0 or audit.limit_up_rows + audit.limit_down_rows == 0:
        return "warning", "覆盖审计发现部分数据缺失，页面已明示补数命令"
    return "success", "夜间数据拉取完成，覆盖审计通过"


def run_coverage_audit_step(engine: Engine, run_id: int, trade_date: date) -> MarketDataCoverageAudit:
    return record_data_job_step(
        engine,
        run_id,
        "覆盖审计",
        lambda: audit_market_data_coverage(engine, trade_date),
        audit_step_summary,
        lambda audit: audit.stock_daily_rows,
    )


def _start_step(engine: Engine, run_id: int, step_name: str) -> int:
    with Session(engine) as session:
        step = DataJobStep(
            run_id=run_id,
            step_name=step_name,
            status="running",
            started_at=_now(),
            rows_count=0,
            summary_json="{}",
            error_message="",
        )
        session.add(step)
        session.commit()
        return step.id


def _finish_step(
    engine: Engine,
    step_id: int,
    status: str,
    summary: dict[str, Any],
    rows_count: int,
    error_message: str,
) -> None:
    with Session(engine) as session:
        step = session.get(DataJobStep, step_id)
        if step is None:
            return
        step.status = status
        step.ended_at = _now()
        step.rows_count = rows_count
        step.summary_json = json.dumps(_jsonable(summary), ensure_ascii=False, sort_keys=True)
        step.error_message = error_message
        session.commit()


def _latest_relevant_trade_date(session: Session) -> Optional[date]:
    calendar_date = session.scalar(
        select(func.max(TradingCalendar.trade_date)).where(TradingCalendar.is_open.is_(True))
    )
    if calendar_date is not None:
        return calendar_date
    return session.scalar(select(func.max(StockDaily.trade_date))) or session.scalar(select(func.max(MarketDaily.trade_date)))


def _health_item(name: str, ok: bool, actual, expected: str, fix_command: str, error: bool) -> DatabaseHealthItem:
    status = "ok" if ok else "error" if error else "warning"
    message = "正常" if ok else "不完整，必须补数据" if error else "不完整，请确认是否符合当日市场状态"
    return DatabaseHealthItem(
        name=name,
        status=status,
        message=message,
        actual=str(actual),
        expected=expected,
        fix_command="" if ok else fix_command,
    )


def _stock_daily_health_item(target_date: date, stock_basic_rows: int, stock_daily_rows: int, command: str) -> DatabaseHealthItem:
    missing = max(stock_basic_rows - stock_daily_rows, 0)
    if stock_basic_rows == 0 or stock_daily_rows == 0:
        status = "error"
        message = "个股日线为空，策略无法可靠运行。"
    elif missing > 0:
        status = "warning"
        message = f"个股日线缺少 {missing} 行，请确认是否为停牌/ST/退市等合理缺口。"
    else:
        status = "ok"
        message = "正常"
    return DatabaseHealthItem(
        name="个股日线",
        status=status,
        message=message,
        actual=f"{stock_daily_rows} / {stock_basic_rows}",
        expected="覆盖全部 stock_basic 股票，合理停牌缺口需人工可见",
        fix_command="" if status == "ok" else command,
    )


def _sector_health_item(target_date: date, sector_rows: int, max_rank: int, command: str) -> DatabaseHealthItem:
    if sector_rows == 0:
        status = "error"
        message = "强势板块未生成。"
    elif max_rank > 511:
        status = "error"
        message = "板块排名超过 511，说明排名宇宙错误。"
    elif sector_rows != 511:
        status = "warning"
        message = "板块排名不是 511 行，请确认数据源返回口径。"
    else:
        status = "ok"
        message = "正常"
    return DatabaseHealthItem(
        name="强势板块排名",
        status=status,
        message=message,
        actual=f"rows={sector_rows}, max_rank={max_rank}",
        expected="511 行，max_rank <= 511",
        fix_command="" if status == "ok" else command,
    )


def _latest_job_health_item(target_date: date, latest_run: Optional[DataJobRun], command: str) -> DatabaseHealthItem:
    if latest_run is None:
        return DatabaseHealthItem(
            name="夜间任务日志",
            status="warning",
            message="该交易日没有结构化夜间任务日志。",
            actual="0",
            expected="至少 1 条 data_job_run",
            fix_command=command,
        )
    return DatabaseHealthItem(
        name="夜间任务日志",
        status="ok" if latest_run.status == "success" else latest_run.status,
        message=latest_run.message,
        actual=latest_run.status,
        expected="success 或 warning，失败必须展示错误",
        fix_command="" if latest_run.status in {"success", "warning"} else command,
    )


def _count(session: Session, model, *criteria) -> int:
    query = select(func.count()).select_from(model)
    if criteria:
        query = query.where(*criteria)
    return int(session.scalar(query) or 0)


def _jsonable(value):
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _now() -> datetime:
    return datetime.now(timezone.utc)
