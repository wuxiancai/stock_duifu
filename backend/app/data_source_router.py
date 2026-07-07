from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from time import perf_counter
from typing import Any, Callable, Iterable, Protocol


class DataDomain(str, Enum):
    """Canonical data domains routed by the unified multi-source system."""

    MARKET_SNAPSHOT = "market_snapshot"
    TRADING_CALENDAR = "trading_calendar"
    STOCK_BASIC = "stock_basic"
    STOCK_DAILY = "stock_daily"
    INDEX_DAILY = "index_daily"
    LIMIT_SNAPSHOT = "limit_snapshot"
    SECTOR_DAILY = "sector_daily"
    SECTOR_MEMBERSHIP = "sector_membership"
    REALTIME_QUOTE = "realtime_quote"
    ANNOUNCEMENT = "announcement"


@dataclass(frozen=True)
class DataRequest:
    domain: DataDomain
    trade_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    stock_codes: list[str] = field(default_factory=list)
    sector_names: list[str] = field(default_factory=list)
    sample_size: int = 30
    lookback_days: int = 5
    mode: str = "auto"
    allow_cache: bool = True
    allow_inferred: bool = True
    min_rows: int = 1
    min_coverage: float | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataResponse:
    domain: DataDomain
    source: str
    records: Any
    quality: str = "medium"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    coverage: float | None = None
    is_fallback: bool = False
    is_inferred: bool = False

    @property
    def rows_count(self) -> int:
        return _rows_count(self.records)


@dataclass(frozen=True)
class DataSourceAttempt:
    domain: DataDomain
    source: str
    status: str
    started_at: datetime
    ended_at: datetime
    latency_ms: float
    rows_count: int = 0
    coverage: float | None = None
    quality: str | None = None
    is_fallback: bool = False
    is_inferred: bool = False
    error_message: str = ""


class DataSourceAdapter(Protocol):
    name: str
    domains: set[DataDomain]

    def fetch(self, request: DataRequest) -> DataResponse:
        ...


@dataclass(frozen=True)
class DomainPolicy:
    domain: DataDomain
    ordered_sources: list[str]
    min_rows: int = 1
    min_coverage: float | None = None
    allow_empty: bool = False


class CallableAdapter:
    """Adapter wrapper that makes existing project providers routable."""

    def __init__(self, name: str, domain: DataDomain, fetcher: Callable[[DataRequest], Any], quality: str = "medium"):
        self.name = name
        self.domains = {domain}
        self.domain = domain
        self._fetcher = fetcher
        self.quality = quality

    def fetch(self, request: DataRequest) -> DataResponse:
        records = self._fetcher(request)
        return DataResponse(domain=request.domain, source=self.name, records=records, quality=self.quality)


class DataSourceRouter:
    """First-valid multi-source router with validation, attempts, and fallback diagnostics.

    Business code should call this router instead of manually binding to one market-data source.
    The router is deliberately lightweight: it can wrap the current providers today and can later
    persist attempts/health to database tables without changing business call sites.
    """

    def __init__(
        self,
        adapters: Iterable[DataSourceAdapter],
        policies: Iterable[DomainPolicy] | None = None,
    ):
        self.adapters = {adapter.name: adapter for adapter in adapters}
        self.policies = {policy.domain: policy for policy in (policies or [])}
        self.attempts: list[DataSourceAttempt] = []
        self.errors: list[str] = []
        self.last_response: DataResponse | None = None

    def fetch(self, request: DataRequest) -> DataResponse:
        self.attempts = []
        self.errors = []
        self.last_response = None
        policy = self.policies.get(request.domain) or DomainPolicy(
            domain=request.domain,
            ordered_sources=[name for name, adapter in self.adapters.items() if request.domain in adapter.domains],
            min_rows=request.min_rows,
            min_coverage=request.min_coverage,
        )
        if not policy.ordered_sources:
            raise RuntimeError(f"数据域 {request.domain.value} 没有配置任何数据源")

        for index, source_name in enumerate(policy.ordered_sources):
            adapter = self.adapters.get(source_name)
            if adapter is None:
                self.errors.append(f"{source_name}: 未注册")
                continue
            started = _utcnow()
            timer = perf_counter()
            try:
                response = adapter.fetch(request)
                response = _with_fallback_flag(response, is_fallback=index > 0)
                self._validate(response, request, policy)
            except Exception as exc:
                ended = _utcnow()
                message = f"{source_name}: {exc.__class__.__name__}: {exc}"
                self.errors.append(message)
                self.attempts.append(
                    DataSourceAttempt(
                        domain=request.domain,
                        source=source_name,
                        status="failed",
                        started_at=started,
                        ended_at=ended,
                        latency_ms=(perf_counter() - timer) * 1000,
                        error_message=message,
                        is_fallback=index > 0,
                    )
                )
                continue
            ended = _utcnow()
            self.attempts.append(
                DataSourceAttempt(
                    domain=request.domain,
                    source=response.source,
                    status="success" if index == 0 else "warning",
                    started_at=started,
                    ended_at=ended,
                    latency_ms=(perf_counter() - timer) * 1000,
                    rows_count=response.rows_count,
                    coverage=response.coverage,
                    quality=response.quality,
                    is_fallback=index > 0,
                    is_inferred=response.is_inferred,
                )
            )
            self.last_response = response
            return response

        raise RuntimeError(f"数据域 {request.domain.value} 所有数据源均失败：" + "；".join(self.errors))

    def _validate(self, response: DataResponse, request: DataRequest, policy: DomainPolicy) -> None:
        rows_count = response.rows_count
        min_rows = request.min_rows if request.min_rows is not None else policy.min_rows
        if not policy.allow_empty and min_rows and rows_count < min_rows:
            raise RuntimeError(f"返回行数不足：{rows_count} < {min_rows}")
        min_coverage = request.min_coverage if request.min_coverage is not None else policy.min_coverage
        if min_coverage is not None and response.coverage is not None and response.coverage < min_coverage:
            raise RuntimeError(f"覆盖率不足：{response.coverage:.2%} < {min_coverage:.2%}")
        if response.is_inferred and not request.allow_inferred:
            raise RuntimeError("请求禁止使用推导数据，但当前响应是 inferred")


def market_snapshot_adapter(provider: Any, quality: str = "high") -> CallableAdapter:
    name = getattr(provider, "name", provider.__class__.__name__)

    def fetch(request: DataRequest):
        return provider.fetch_snapshot(
            trade_date=request.trade_date,
            sample_size=request.sample_size,
            stock_codes=request.stock_codes or None,
        )

    return CallableAdapter(name=name, domain=DataDomain.MARKET_SNAPSHOT, fetcher=fetch, quality=quality)


def realtime_quote_adapter(provider: Any, quality: str = "medium") -> CallableAdapter:
    name = getattr(provider, "name", provider.__class__.__name__)

    def fetch(request: DataRequest):
        return provider.fetch_realtime_stock_daily(request.stock_codes, request.trade_date)

    return CallableAdapter(name=name, domain=DataDomain.REALTIME_QUOTE, fetcher=fetch, quality=quality)


def sector_window_adapter(provider: Any, quality: str = "medium") -> CallableAdapter:
    name = getattr(provider, "source", getattr(provider, "name", provider.__class__.__name__))

    def fetch(request: DataRequest):
        return provider.fetch_sector_window(trade_date=request.trade_date, lookback_days=request.lookback_days)

    return CallableAdapter(name=name, domain=DataDomain.SECTOR_DAILY, fetcher=fetch, quality=quality)


def sector_membership_adapter(provider: Any, quality: str = "medium") -> CallableAdapter:
    name = getattr(provider, "source", getattr(provider, "name", provider.__class__.__name__))

    def fetch(request: DataRequest):
        return provider.sector_members(request.sector_names)

    return CallableAdapter(name=name, domain=DataDomain.SECTOR_MEMBERSHIP, fetcher=fetch, quality=quality)


def _with_fallback_flag(response: DataResponse, is_fallback: bool) -> DataResponse:
    return DataResponse(
        domain=response.domain,
        source=response.source,
        records=response.records,
        quality=response.quality,
        warnings=response.warnings,
        errors=response.errors,
        coverage=response.coverage,
        is_fallback=is_fallback,
        is_inferred=response.is_inferred,
    )


def _rows_count(records: Any) -> int:
    if records is None:
        return 0
    if isinstance(records, dict):
        return sum(1 for value in records.values() if value)
    if isinstance(records, (list, tuple, set)):
        return len(records)
    for attr in ("stock_daily", "index_daily", "limit_snapshot", "trading_calendar", "stock_basic"):
        value = getattr(records, attr, None)
        if value:
            return len(value)
    return 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def supported_data_sources() -> list[dict[str, str]]:
    """Authoritative source catalog for design docs, CLI diagnostics, and tests."""

    return [
        {"name": "tushare", "label": "TuShare", "role": "核心历史源 / 低权限接口优先"},
        {"name": "akshare", "label": "AkShare", "role": "Python 聚合适配器集合"},
        {"name": "eastmoney", "label": "东方财富", "role": "免费行情、行业、涨跌停、资金流"},
        {"name": "tencent", "label": "腾讯行情", "role": "轻量实时行情备用"},
        {"name": "sina", "label": "新浪行情", "role": "轻量实时行情和指数备用"},
        {"name": "netease", "label": "网易财经", "role": "历史行情备用"},
        {"name": "ths", "label": "同花顺", "role": "行业、题材、资金流备用"},
        {"name": "baostock", "label": "Baostock", "role": "A 股历史日线备用"},
        {"name": "cninfo", "label": "巨潮资讯", "role": "公告、公司资料、行业分类"},
        {"name": "exchange_official", "label": "交易所/指数官方源", "role": "交易日历、证券列表、指数校验"},
    ]
