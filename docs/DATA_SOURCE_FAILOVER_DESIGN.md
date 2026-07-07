# A 股短线系统统一多源切换设计

> 目标：所有涉及数据拉取的功能都必须走统一多源切换系统，不允许业务代码直接绑定单一源。任何源失败、超时、限流、返回空数据、返回脏数据，都必须进入统一的重试、降级、质量校验、审计和告警链路。

---

## 0. 当前落地状态

- 已新增 `backend/app/data_source_router.py`。
- 已接入历史行情、实时行情、行业、行业成分入口。
- 已新增 `docs/DATA_SOURCE_POLICY.md`。
- 数据库级源健康表和页面明细后续继续。

## 1. 设计结论

当前项目已经出现多次单点源故障：

- `limit_list_d`：TuShare 权限不足。
- `push2ex.eastmoney.com`：东方财富涨跌停池超时。
- `17.push2.eastmoney.com /api/qt/clist/get`：东方财富行业板块接口超时。
- 行业成分股：东方财富成分接口可能超时或返回空。
- 实时行情：新浪、东方财富、腾讯任一源均可能返回异常字段或不可达。

因此系统必须改成：

```text
业务模块 -> DataSourceRouter -> 数据域策略 -> 多源适配器 -> 质量校验 -> 标准化数据 -> 入库/返回
```

业务模块禁止直接调用：

```text
ak.xxx
requests.get(...eastmoney...)
requests.get(...sina...)
requests.get(...tencent...)
ts.pro_api(...)
```

所有数据获取必须通过统一入口。

---

## 2. 数据源清单

系统至少维护 10 类主流源，按“是否适合交易决策”分层使用。

| 源 | 类型 | 适合用途 | 风险 | 默认角色 |
|---|---|---|---|---|
| TuShare | 聚合付费/积分源 | 交易日历、股票基础信息、日线、指数日线、部分财务/资金数据 | 积分权限、接口限额 | 核心历史源，低权限接口优先 |
| AkShare | Python 聚合库 | 接入东方财富、同花顺、新浪、腾讯、巨潮等多个公开数据 | 底层源不稳定、字段变化 | 适配器集合，不直接作为唯一源 |
| 东方财富 | 免费公开行情源 | 实时行情、行业、板块、涨跌停池、资金流、财务 | 容易超时/限流/字段变动 | 免费首选源之一 |
| 腾讯行情 | 免费公开行情源 | 轻量实时行情、指数、个股快照 | 字段格式非正式、可能变动 | 实时行情备用 |
| 新浪行情 | 免费公开行情源 | 轻量实时行情、指数、港美指数 | 字段格式非正式、可能变动 | 实时行情首选或备用 |
| 网易财经 | 免费公开行情源 | 个股历史行情、部分行情快照 | 接口稳定性一般、字段可能变化 | 历史行情备用 |
| 同花顺 | 免费公开行情/板块源 | 行业板块、行业指数、行业成分、资金流 | 可能反爬/页面结构变化 | 行业/题材备用源 |
| Baostock | 免费 Python 数据源 | A 股日线、指数、基础行情 | 更新速度/覆盖范围需校验 | 历史日线备用 |
| 巨潮资讯 CNINFO | 官方信息披露/行业分类 | 公告、行业分类、公司资料 | 非实时行情源 | 基础信息/公告/行业分类备用 |
| 交易所/指数官方源 | 官方源 | 交易日历、证券列表、指数成分、公告 | 接口分散、自动化成本高 | 权威校验源 |

补充可选源：雪球、聚宽 JQData、米筐 RiceQuant、Wind/Choice 等。当前项目不默认接入这些源；若后续需要更高质量数据，可作为付费增强层。

---

## 3. 数据域划分

统一多源系统必须按“数据域”设计，而不是简单按源设计。每个数据域有自己的字段契约、源优先级、质量门槛和降级规则。

### 3.1 交易日历 `trading_calendar`

用途：判断是否开市、默认拉数日期、跳过非交易日。

优先级：

```text
TuShare trade_cal -> 交易所官方日历 -> Baostock -> AkShare/Sina 历史交易日
```

质量规则：

- 必须排除周末。
- 必须支持中国 A 股交易日。
- 默认以 SSE 口径为主。
- 源之间冲突时，交易所官方 / TuShare 优先。

### 3.2 股票基础信息 `stock_basic`

用途：股票池、ST 过滤、退市过滤、代码名称映射、涨跌停阈值。

优先级：

```text
TuShare stock_basic -> 东方财富股票列表 -> 巨潮/交易所证券列表 -> AkShare 股票列表 -> Baostock
```

质量规则：

- 股票代码必须 6 位。
- 必须区分 A 股、北交所、退市、ST。
- 缺失 ST 标记时，必须从名称中识别 `ST`、`*ST`、`退` 等关键词。
- 不允许因为单源名称异常导致退市/ST 股票进入可交易池。

### 3.3 个股日线 `stock_daily`

用途：市场环境、候选筛选、交易计划、模拟交易、涨跌停推导兜底。

优先级：

```text
TuShare daily -> Baostock daily -> 东方财富历史行情 -> 网易历史行情 -> 新浪历史行情 -> 腾讯历史/快照补齐
```

质量规则：

- 必须有 `open/high/low/close/pre_close/pct_chg/volume/amount`。
- `high >= max(open, close, low)`。
- `low <= min(open, close, high)`。
- `pct_chg` 必须与 `close/pre_close` 基本一致。
- `amount` 单位必须统一为元。
- 全市场覆盖率低于阈值时不可直接生成交易计划。

推荐门槛：

```text
全市场日线覆盖率 >= 98%
核心指数日线覆盖率 = 100%
计划股 / 持仓股覆盖率 = 100%
```

### 3.4 指数日线 `index_daily`

用途：市场环境、指数 MA20、指数行情条。

优先级：

```text
TuShare index_daily -> 东方财富指数历史 -> 新浪指数 -> 腾讯指数 -> 中证指数/交易所官方
```

质量规则：

- 沪指、深指、创业板、科创、沪深300、深证100 至少覆盖 3 个核心指数。
- `amount` 单位必须统一为元。
- 对旧库中千元单位残留必须兼容修正。

### 3.5 涨跌停池 `limit_snapshot`

用途：市场环境涨跌停数量、连板高度、行业涨停数、一字涨停过滤。

优先级：

```text
东方财富涨跌停池 -> 同花顺涨停池/涨停表现 -> AkShare 可用涨跌停接口 -> stock_daily.pct_chg 推导兜底
```

注意：

- `stock_daily.pct_chg` 推导只能作为兜底，不能作为高质量首选数据。
- 当前系统只使用涨跌停状态、数量、连板高度、行业内涨停数、一字涨停过滤和成交额。
- 当前系统没有使用封单额、封单强度、首次封板时间、炸板次数、主力资金等字段。

质量规则：

- 真实涨跌停池 source 优先。
- 推导 source 必须标记为 `inferred_from_stock_daily`。
- 推导数据禁止用于封单强度、炸板次数、主力资金等精细交易判断。
- 新规口径：ST 推导阈值按 10%；主板 10%；创业板/科创板 20%；北交所 30%。
- 对明显超过阈值的异常涨跌幅，不推导为涨跌停，避免新股/无涨跌幅限制误判。

### 3.6 行业/板块 `sector_daily`

用途：强势行业排名、行业持续性、候选行业配额。

优先级：

```text
东方财富行业板块 -> 同花顺行业板块 -> 申万/巨潮行业分类 + 个股聚合推导 -> 同日缓存复用
```

质量规则：

- 主榜必须是稳定行业，不允许概念题材与行业混排。
- 行业数量低于 10 个，不可作为有效强势行业结果。
- 如果行业源失败但同日已有缓存，可以复用缓存，但步骤必须记录 warning。
- 如果所有源失败且无缓存，不能伪造强势行业。

### 3.7 行业成分股 `sector_membership`

用途：行业涨停统计、候选股票筛选。

优先级：

```text
东方财富行业成分 -> 同花顺行业详情页成分 -> 巨潮/申万行业分类 -> 历史缓存
```

质量规则：

- 行业成分代码必须标准化为 6 位。
- 某些行业成分失败时，可局部降级。
- 如果所有行业成分源全部失败，不能静默返回空结果；必须抛错或复用缓存。
- 避免把候选股票覆盖为空。

### 3.8 实时行情 `realtime_quote`

用途：盘中跟踪、触发交易计划、模拟交易盯市。

优先级：

```text
新浪直连轻量源 -> 东方财富直连轻量源 -> 腾讯直连轻量源 -> AkShare Eastmoney 全市场 -> AkShare Sina 全市场
```

质量规则：

- 默认只按计划股/持仓股请求，禁止默认拉全市场。
- 全市场实时源只能作为 `auto-full` 后备。
- 价格、涨跌幅、开高低收关系异常必须丢弃，并继续切后续源。
- 目标计划股 / 持仓股覆盖率必须尽量 100%。

### 3.9 公告/公司资料/财务补充

用途：AI 新闻过滤、公告风险、基本面过滤。

优先级：

```text
巨潮资讯 -> 交易所公告 -> 东方财富公告 -> 新浪/同花顺补充
```

质量规则：

- 公告类以官方披露源优先。
- 新闻源只能作为情绪/事件补充，不可替代公告。

---

## 4. 统一多源系统模块设计

建议新增独立包：

```text
backend/app/datasource/
  __init__.py
  contracts.py
  router.py
  registry.py
  policies.py
  health.py
  validators.py
  normalizers.py
  audit.py
  adapters/
    tushare.py
    akshare_eastmoney.py
    eastmoney_direct.py
    sina_direct.py
    tencent_direct.py
    netease.py
    ths.py
    baostock.py
    cninfo.py
    exchange_official.py
```

### 4.1 统一数据域枚举

```python
class DataDomain(str, Enum):
    TRADING_CALENDAR = "trading_calendar"
    STOCK_BASIC = "stock_basic"
    STOCK_DAILY = "stock_daily"
    INDEX_DAILY = "index_daily"
    LIMIT_SNAPSHOT = "limit_snapshot"
    SECTOR_DAILY = "sector_daily"
    SECTOR_MEMBERSHIP = "sector_membership"
    REALTIME_QUOTE = "realtime_quote"
    ANNOUNCEMENT = "announcement"
```

### 4.2 数据请求对象

```python
@dataclass(frozen=True)
class DataRequest:
    domain: DataDomain
    trade_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    stock_codes: list[str] | None = None
    sector_names: list[str] | None = None
    mode: str = "auto"
    allow_cache: bool = True
    allow_inferred: bool = True
    min_coverage: float | None = None
```

### 4.3 数据响应对象

```python
@dataclass(frozen=True)
class DataResponse:
    domain: DataDomain
    source: str
    quality: str          # high / medium / low / inferred
    records: list[Any]
    warnings: list[str]
    errors: list[str]
    coverage: float | None
    is_fallback: bool
    is_inferred: bool
```

### 4.4 源适配器接口

```python
class DataSourceAdapter(Protocol):
    name: str
    domains: set[DataDomain]
    priority: int

    def fetch(self, request: DataRequest) -> DataResponse:
        ...
```

### 4.5 路由器入口

```python
class DataSourceRouter:
    def fetch(self, request: DataRequest) -> DataResponse:
        policy = self.policy_registry.get(request.domain)
        for source in policy.ordered_sources:
            if self.health.is_blocked(source):
                continue
            try:
                response = source.fetch(request)
                response = self.normalizer.normalize(response)
                self.validator.validate_or_raise(response, policy)
                self.audit.success(source, request, response)
                return response
            except Exception as exc:
                self.health.record_failure(source, exc)
                self.audit.failure(source, request, exc)
                continue
        return self.fallback_or_raise(request, policy)
```

---

## 5. 多源策略配置

建议新增：

```text
config/data_sources.yaml
```

示例：

```yaml
stock_daily:
  mode: first_valid
  min_coverage: 0.98
  sources:
    - tushare_daily
    - baostock_daily
    - eastmoney_daily
    - netease_daily
    - sina_daily

limit_snapshot:
  mode: first_valid_with_inferred_fallback
  min_rows: 1
  sources:
    - eastmoney_limit_pool
    - ths_limit_pool
    - akshare_limit_pool
  inferred_fallback:
    enabled: true
    from_domain: stock_daily
    quality: inferred

sector_daily:
  mode: first_valid_with_cache_fallback
  min_rows: 10
  sources:
    - eastmoney_industry
    - ths_industry
    - sw_industry_aggregate
  cache_fallback:
    enabled: true
    same_trade_date_only: true

realtime_quote:
  mode: merge_by_requested_codes
  min_coverage: 0.95
  sources:
    - sina_direct_realtime
    - eastmoney_direct_realtime
    - tencent_direct_realtime
    - akshare_eastmoney_realtime
    - akshare_sina_realtime
```

---

## 6. 质量校验规则

### 6.1 通用校验

每个源返回后必须先过校验，不允许直接入库：

- schema 完整性。
- 字段类型。
- 单位归一化。
- 日期时区。
- 股票代码标准化。
- 行数覆盖率。
- 重复行去重。
- 异常值过滤。
- 与已有数据库/上一交易日交叉校验。

### 6.2 行情数据校验

```text
high >= open/close/low
low <= open/close/high
close > 0
volume >= 0
amount >= 0
pct_chg 与 close/pre_close 差异在容忍范围内
```

### 6.3 实时行情校验

```text
价格不能为 0 或负数
涨跌幅不能远超对应市场制度阈值，除非明确为新股/无涨跌幅限制
开高低收关系必须合理
成交额不能为负
返回时间不能明显早于当前交易日
```

### 6.4 涨跌停推导校验

```text
真实涨跌停池优先
推导数据必须标记 inferred
推导不能覆盖真实源
推导不能用于封单/炸板/主力资金类判断
```

### 6.5 行业数据校验

```text
行业主榜不少于 10 个行业
行业名称不能为空
行业涨跌幅必须是数值
行业成交额缺失时可降级，但必须标记 warning
行业成分全部为空时不能生成候选股票
```

---

## 7. 源健康与熔断

新增源健康状态：

```text
healthy
warning
cooldown
blocked
```

熔断规则：

| 条件 | 动作 |
|---|---|
| 连续 3 次超时 | 进入 cooldown 10 分钟 |
| 连续 5 次失败 | blocked 30 分钟 |
| 返回脏数据 | 立即降权，并记录 bad_data |
| 返回空数据 | 计入 soft failure |
| 成功返回并通过校验 | 恢复 healthy |

每个源必须记录：

```text
last_success_at
last_failure_at
consecutive_failures
avg_latency_ms
last_error
cooldown_until
success_rate_1d
success_rate_7d
```

---

## 8. 数据库审计表设计

建议新增迁移：

### 8.1 `data_source_health`

```text
source_name
status
consecutive_failures
last_success_at
last_failure_at
cooldown_until
last_error
avg_latency_ms
success_rate_1d
success_rate_7d
updated_at
```

### 8.2 `data_source_attempt`

每一次源尝试都记录：

```text
run_id
domain
source_name
request_json
status
started_at
ended_at
latency_ms
rows_count
coverage
quality
is_fallback
is_inferred
error_message
summary_json
```

### 8.3 `data_quality_issue`

记录脏数据：

```text
trade_date
domain
source_name
stock_code
field_name
raw_value
normalized_value
issue_type
severity
message
created_at
```

---

## 9. 页面展示要求

数据健康页不应只显示 success/failed，必须显示数据源链路：

```text
拉取行情快照：
  TuShare daily: success, rows=5305
  Eastmoney limit pool: timeout
  inferred limit snapshot: warning, rows=134

生成强势行业：
  Eastmoney industry: timeout
  THS industry: success, rows=31
```

状态定义：

| 状态 | 含义 |
|---|---|
| success | 首选源成功且通过校验 |
| warning | 首选源失败但备用源/缓存/推导成功 |
| failed | 所有源失败且无安全兜底 |
| partial | 部分股票/行业缺失，但达到最低覆盖率 |
| bad_data | 源返回数据但未通过质量校验 |

---

## 10. 迁移计划

### Phase 1：基础框架

新增 `backend/app/datasource/`：

- `DataDomain`
- `DataRequest`
- `DataResponse`
- `DataSourceAdapter`
- `DataSourceRouter`
- `SourceHealthRegistry`
- `DataQualityValidator`
- `DataSourceAuditLogger`

不改业务逻辑，只补框架和单测。

### Phase 2：行情快照迁移

迁移：

- `trade_cal`
- `stock_basic`
- `stock_daily`
- `index_daily`
- `limit_snapshot`

目标：`backend/app/data/providers.py` 不再由业务直接选择源，而是走 `DataSourceRouter`。

### Phase 3：行业与候选迁移

迁移：

- `sector_daily`
- `sector_membership`

目标：删除当前散落的 `FallbackSectorDataProvider` 和 `FallbackIndustrySectorMembershipProvider` 逻辑，统一收敛到 router。

### Phase 4：实时行情迁移

迁移：

- `SinaDirectRealtimeQuoteProvider`
- `EastmoneyDirectRealtimeQuoteProvider`
- `TencentDirectRealtimeQuoteProvider`
- `AkShareRealtimeQuoteProvider`
- `AkShareSinaRealtimeQuoteProvider`

目标：盘中触发、模拟交易、持仓盯市全部通过统一 router。

### Phase 5：数据健康页升级

页面新增：

- 每个数据域的源尝试明细。
- 当前源健康状态。
- 最近 24 小时失败源排行。
- 备用源使用次数。
- 推导数据占比。
- 对交易结论有影响的数据质量风险提示。

---

## 11. 禁止事项

以下行为后续禁止：

1. 业务模块直接调用外部源。
2. 源失败后静默返回空列表。
3. 脏数据未经校验直接入库。
4. 推导数据伪装成真实数据。
5. 缓存数据伪装成实时数据。
6. 不记录 source 和 quality 就生成交易结论。
7. 单个免费源失败导致整个系统停止。
8. 所有源失败时仍强行生成交易计划。

---

## 12. 交易结论可靠性规则

交易计划生成前必须计算数据可信等级：

| 等级 | 条件 | 是否允许生成交易计划 |
|---|---|---|
| A | 核心数据均为首选/高质量源 | 允许 |
| B | 有备用源，但覆盖率达标 | 允许，但标记数据源降级 |
| C | 使用缓存或推导数据，但未影响核心字段 | 谨慎允许，页面提示 |
| D | 核心字段来自推导或覆盖率不足 | 不允许生成新交易计划 |
| E | 所有源失败或数据质量不通过 | 禁止生成交易计划 |

核心字段包括：

```text
交易日历
全市场日线
核心指数日线
强势行业排名
候选行业成分
计划股行情
```

---

## 13. 后续实施优先级

优先级从高到低：

1. `stock_daily / index_daily / limit_snapshot` 统一 router。
2. `sector_daily / sector_membership` 统一 router。
3. `realtime_quote` 统一 router。
4. 数据健康页展示源尝试链路。
5. 加入 `data_source_health` 熔断表。
6. 加入质量等级到交易计划生成逻辑。
7. 再考虑新增付费或更高质量数据源。

---

## 14. 验收标准

完成后必须满足：

```text
任一单源超时，不导致整个 get_data.sh 失败。
任一单源返回空，不覆盖已有可信数据为空。
任一源返回脏数据，不进入交易计划。
每次数据生成都能追溯具体源、备用源、失败原因和质量等级。
数据健康页能清楚解释：哪个源失败了、哪个源接管了、数据是否仍可用于交易。
```

测试必须覆盖：

```text
首选源成功
首选源超时，备用源成功
首选源返回脏数据，备用源成功
所有源失败，无缓存
所有源失败，有缓存
推导兜底成功
推导兜底被禁止
覆盖率不足
单位错误被修正
单位错误无法修正时拒绝入库
```
