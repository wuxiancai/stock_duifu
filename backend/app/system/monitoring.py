import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from sqlalchemy import desc, func, or_, select
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


def record_recoverable_data_job_step(
    engine: Engine,
    run_id: int,
    step_name: str,
    operation: Callable[[], Any],
    recovery: Callable[[Exception], Any],
    summary_builder: Callable[[Any], dict[str, Any]],
    rows_counter: Callable[[Any], int],
    recovery_message: Callable[[Exception], str],
) -> Any:
    step_id = _start_step(engine, run_id, step_name)
    try:
        result = operation()
    except Exception as exc:
        result = recovery(exc)
        summary = summary_builder(result)
        _finish_step(engine, step_id, "warning", summary, rows_counter(result), recovery_message(exc))
        return result
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
            select(DataJobRun)
            .outerjoin(TradingCalendar, TradingCalendar.trade_date == DataJobRun.trade_date)
            .where(or_(TradingCalendar.id.is_(None), TradingCalendar.is_open.is_(True)))
            .order_by(desc(DataJobRun.started_at))
            .limit(limit)
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
        stock_daily_coverage = _stock_daily_coverage_counts(session, target_date)
        index_daily_rows = _count(session, IndexDaily, IndexDaily.trade_date == target_date)
        limit_rows = _count(session, LimitSnapshot, LimitSnapshot.trade_date == target_date)
        market_rows = _count(session, MarketDaily, MarketDaily.trade_date == target_date)
        sector_rows = _count(session, SectorDaily, SectorDaily.trade_date == target_date)
        max_sector_rank = session.scalar(
            select(func.max(SectorDaily.rank_no)).where(SectorDaily.trade_date == target_date)
        ) or 0
        candidate_rows = _count(session, CandidateStock, CandidateStock.trade_date == target_date)
        stock_pool_rows = _count(
            session,
            CandidateStock,
            CandidateStock.trade_date == target_date,
            CandidateStock.stock_pool_rank.is_not(None),
        )
        trade_plan_rows = _count(session, TradePlan, TradePlan.plan_date == target_date)
        latest_run = session.scalar(
            select(DataJobRun).where(DataJobRun.trade_date == target_date).order_by(desc(DataJobRun.started_at)).limit(1)
        )

        command = f"TRADE_DATE={target_date.isoformat()} bash get_data.sh"
        items.extend(
            [
                _health_item("交易日历", open_days > 0, open_days, "至少 1 个开市日", command, error=True),
                _health_item("股票基础信息", stock_basic_rows >= 5000, stock_basic_rows, "不少于 5000 只 A 股", command, error=True),
                _stock_daily_health_item(stock_daily_coverage, command),
                _health_item("指数日线", index_daily_rows >= 3, index_daily_rows, "三大指数至少 3 行", command, error=True),
                _health_item("涨跌停池", limit_rows > 0, limit_rows, "涨停/跌停记录不能为 0", command, error=False),
                _health_item("市场环境", market_rows > 0, market_rows, "必须生成 market_daily", f"bash scripts/generate-market-environment.sh --trade-date {target_date.isoformat()}", error=True),
                _sector_health_item(target_date, sector_rows, max_sector_rank, command),
                _health_item("候选股票", candidate_rows > 0, candidate_rows, "应生成候选股票或明确为空", f"bash scripts/generate-candidates.sh --trade-date {target_date.isoformat()}", error=False),
                _trade_plan_health_item(target_date, trade_plan_rows, candidate_rows, stock_pool_rows),
                _latest_job_health_item(target_date, latest_run, command),
            ]
        )

    statuses = {item.status for item in items}
    status = "error" if "error" in statuses else "warning" if "warning" in statuses else "ok"
    return DatabaseHealthSummary(trade_date=target_date, status=status, generated_at=_now(), items=items)


def audit_step_summary(audit: MarketDataCoverageAudit) -> dict[str, Any]:
    return _jsonable(asdict(audit))


def audit_step_status(engine: Engine, audit: MarketDataCoverageAudit) -> tuple[str, str]:
    if audit.index_daily_rows < 3 or audit.stock_basic_rows == 0 or audit.stock_daily_rows == 0:
        return "error", "覆盖审计发现核心行情缺失"
    with Session(engine) as session:
        coverage = _stock_daily_coverage_counts(session, audit.trade_date)
    if (
        audit.stock_basic_rows < 5000
        or coverage["missing_required_rows"] > coverage["allowed_no_trade_gap"]
        or audit.limit_up_rows + audit.limit_down_rows == 0
    ):
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


def _eligible_stock_basic_criteria():
    return (
        StockBasic.status == "active",
        StockBasic.is_st.is_(False),
        StockBasic.stock_name.not_ilike("%ST%"),
        ~StockBasic.stock_name.contains("退"),
    )


def _stock_daily_coverage_counts(session: Session, target_date: date) -> dict[str, int]:
    criteria = _eligible_stock_basic_criteria()
    stock_basic_rows = _count(session, StockBasic)
    required_rows = _count(session, StockBasic, *criteria)
    covered_required_rows = int(
        session.scalar(
            select(func.count(func.distinct(StockDaily.stock_code)))
            .join(StockBasic, StockBasic.stock_code == StockDaily.stock_code)
            .where(StockDaily.trade_date == target_date, *criteria)
        )
        or 0
    )
    return {
        "stock_basic_rows": stock_basic_rows,
        "required_rows": required_rows,
        "covered_required_rows": covered_required_rows,
        "excluded_rows": max(stock_basic_rows - required_rows, 0),
        "missing_required_rows": max(required_rows - covered_required_rows, 0),
        "allowed_no_trade_gap": _allowed_no_trade_gap(required_rows),
    }


def _stock_daily_health_item(coverage: dict[str, int], command: str) -> DatabaseHealthItem:
    stock_basic_rows = coverage["stock_basic_rows"]
    required_rows = coverage["required_rows"]
    covered_required_rows = coverage["covered_required_rows"]
    excluded_rows = coverage["excluded_rows"]
    missing_required_rows = coverage["missing_required_rows"]
    allowed_no_trade_gap = coverage["allowed_no_trade_gap"]
    if stock_basic_rows == 0 or covered_required_rows == 0:
        status = "error"
        message = "个股日线为空，策略无法可靠运行。"
    elif missing_required_rows > allowed_no_trade_gap:
        status = "warning"
        message = f"应覆盖股票缺少 {missing_required_rows} 行，超过合理停牌/无交易容忍范围，请补齐可交易股票日线。"
    else:
        status = "ok"
        if missing_required_rows:
            message = (
                f"正常，{missing_required_rows} 只未出日线按停牌/当日无交易等合理缺口处理；"
                f"已排除 ST、退市/退市风险等系统不需要股票 {excluded_rows} 只。"
            )
        else:
            message = f"正常，已排除 ST、退市/退市风险等系统不需要股票 {excluded_rows} 只。"
    return DatabaseHealthItem(
        name="个股日线",
        status=status,
        message=message,
        actual=f"{covered_required_rows} / {required_rows}",
        expected=f"覆盖可交易股票；已排除无需覆盖 {excluded_rows} / 全量 {stock_basic_rows}",
        fix_command="" if status == "ok" else command,
    )


def _allowed_no_trade_gap(required_rows: int) -> int:
    if required_rows < 1000:
        return 0
    return max(20, int(required_rows * 0.005))


def _sector_health_item(target_date: date, sector_rows: int, max_rank: int, command: str) -> DatabaseHealthItem:
    min_industry_rows = 10
    max_reasonable_industry_rows = 80
    if sector_rows == 0:
        status = "error"
        message = "强势行业未生成。"
    elif max_rank > max_reasonable_industry_rows:
        status = "error"
        message = "强势行业排名数量异常偏大，可能混入了概念板块或旧口径数据。"
    elif max_rank != sector_rows:
        status = "warning"
        message = "强势行业排名不连续，请确认生成流程是否完整。"
    elif sector_rows < min_industry_rows:
        status = "warning"
        message = "强势行业数量少于 Top 10，可能数据源返回不完整。"
    else:
        status = "ok"
        message = "正常，按东财一级行业口径生成强势行业排名。"
    return DatabaseHealthItem(
        name="强势行业排名",
        status=status,
        message=message,
        actual=f"rows={sector_rows}, max_rank={max_rank}",
        expected=f"至少 {min_industry_rows} 个东财一级行业，max_rank=rows，且 max_rank <= {max_reasonable_industry_rows}",
        fix_command="" if status == "ok" else command,
    )


def _trade_plan_health_item(
    target_date: date,
    trade_plan_rows: int,
    candidate_rows: int,
    stock_pool_rows: int,
) -> DatabaseHealthItem:
    command = f"bash scripts/generate-trade-plans.sh --plan-date {target_date.isoformat()}"
    if trade_plan_rows > 0:
        return DatabaseHealthItem(
            name="交易计划",
            status="ok",
            message="正常",
            actual=str(trade_plan_rows),
            expected="生成次日交易计划；若股票池为空则允许明确为空",
            fix_command="",
        )
    if candidate_rows > 0 and stock_pool_rows == 0:
        return DatabaseHealthItem(
            name="交易计划",
            status="ok",
            message="正常，候选股票未满足股票池规则，按宁缺毋滥口径不生成交易计划。",
            actual=str(trade_plan_rows),
            expected="股票池有合格股票时生成计划；股票池为空时明确为空",
            fix_command="",
        )
    return DatabaseHealthItem(
        name="交易计划",
        status="warning",
        message="不完整，请确认是否符合当日市场状态",
        actual=str(trade_plan_rows),
        expected="应生成次日交易计划或明确为空",
        fix_command=command,
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
