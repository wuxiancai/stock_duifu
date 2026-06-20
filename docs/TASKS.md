# Tasks

## 当前状态

- [x] 已创建 MVP PRD：`PRD_MVP.md`
- [x] 已明确本仓库为全新系统，旧 `stock` 项目作废
- [x] 已创建任务 1 的项目骨架与健康检查
- [x] 已创建任务 2 的业务数据库模型与迁移
- [x] 已打通任务 3 的真实数据采集基础链路
- [x] 已增加 TuShare 主源选择入口和数据覆盖审计
- [x] 已完成 TuShare 真实拉取映射和全市场数据初始化
- [x] 已完成市场环境评分、入库命令和最新结果 API
- [ ] 尚未完成强势板块排序

## 开发原则

- 每个任务都必须包含测试、真实数据验收、文档更新和 git commit。
- 每个任务完成后必须更新 `docs/HANDOFF.md`。
- 不允许用 mock、静态页面、脚本存在或单次测试通过冒充阶段完成。
- 优先做能独立演示的垂直切片，避免先搭复杂平台。

## 垂直切片计划

### 1. 项目骨架与配置

- 建立后端 FastAPI 工程。
- 建立前端 Vue 3 + Element Plus 工程。
- 建立 PostgreSQL 配置、环境变量示例和本地启动脚本。
- 建立测试命令和基础健康检查。

验收：能启动 API 和前端，健康检查返回正常，git 提交记录完整。

状态：已完成。

验证：

- `.venv/bin/pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`

### 2. 数据库模型与迁移

- 创建 `market_daily`、`sector_daily`、`trade_plan`、`trade_review` 表。
- 建立迁移工具和初始化命令。
- 增加唯一约束和日期索引，避免重复写入。

验收：真实 PostgreSQL 可初始化，表结构可查询，重复初始化可控。

状态：已完成。

验证：

- `.venv/bin/pytest`
- `docker compose up -d postgres`
- `scripts/db-upgrade.sh`
- `scripts/db-current.sh` -> `0001_core_mvp_tables (head)`
- PostgreSQL 已查询到 `market_daily`、`sector_daily`、`trade_plan`、`trade_review`、`alembic_version`
- 重复执行 `scripts/db-upgrade.sh` 成功，无重复建表错误

### 3. 数据采集与交易日历

- 接入 TuShare 作为主数据源。
- 补充 AkShare 或公开数据源作为后备读取路径。
- 落地交易日历、指数行情、个股日线、基础信息、涨跌停和成交额数据。

验收：能拉取最近可用交易日真实数据并写入数据库，失败时有清晰错误。

状态：已完成主源真实拉取、全市场日线初始化和覆盖审计。

已完成：

- 新增原始行情表：`trading_calendar`、`stock_basic`、`index_daily`、`stock_daily`、`limit_snapshot`、`data_ingest_run`。
- 新增采集命令：`scripts/ingest-market-data.sh` / `make ingest-market-data`。
- 使用 AkShare/Sina 真实日线和 AkShare/Eastmoney 涨跌停池写入 PostgreSQL。
- 指定股票样本 `000001`、`600519`、`300750`、`000002`、`000063` 均写入目标交易日 `2026-06-18` 的真实日线。
- TuShare token 已通过 `.env` 脱敏保存并由 `TUSHARE_TOKEN` 环境变量读取，`.env` 不提交到 git。
- 新增 TuShare 真实映射：交易日历、个股基础信息、指数日线、个股日线、涨跌停明细。
- 新增全市场初始化开关：`scripts/ingest-market-data.sh --provider tushare --trade-date YYYY-MM-DD --all-stocks`。

验证：

- `scripts/db-upgrade.sh` -> `0002_market_data_tables (head)`
- `scripts/ingest-market-data.sh --stock-code 000001 --stock-code 600519 --stock-code 300750 --stock-code 000002 --stock-code 000063`
- PostgreSQL 行数：`trading_calendar=109`、`stock_basic=5`、`index_daily=3`、`stock_daily=5`、`limit_snapshot=103`、`data_ingest_run=1`
- 涨跌停拆分：`limit_up=91`、`limit_down=12`

补充进展：

- 已新增 provider 选择：`--provider auto|tushare|akshare`；`auto` 在存在 `TUSHARE_TOKEN` 时选择 TuShare，否则选择 AkShare/Sina。
- 已新增覆盖审计命令：`scripts/audit-market-data.sh --trade-date YYYY-MM-DD` / `make audit-market-data`。
- 缺少 `TUSHARE_TOKEN` 时执行 `--provider tushare` 会以清晰错误退出，不会静默伪装为 TuShare 数据。
- 当前 AkShare/Eastmoney 全市场实时快照接口在本机代理环境下会断连，已保留可用的 Sina 日线和 Eastmoney 涨跌停池组合为后备路径。

覆盖审计验证：

- `scripts/audit-market-data.sh --trade-date 2026-06-18`
- 样本模式输出：`open_trading_days=109`、`stock_basic_rows=5`、`stock_daily_rows=5`、`missing_stock_daily_rows=0`、`index_daily_rows=3`、`limit_up_rows=91`、`limit_down_rows=12`、`latest_stock_daily_date=2026-06-18`
- 全市场 TuShare 输出：`open_trading_days=109`、`stock_basic_rows=5529`、`stock_daily_rows=5507`、`missing_stock_daily_rows=22`、`index_daily_rows=3`、`limit_up_rows=91`、`limit_down_rows=12`、`latest_stock_daily_date=2026-06-18`
- 缺失日线清单首批包含多只 ST、退市风险或当日无交易个股，需要在任务 6 的基础过滤中继续分类处理。

TuShare 全市场初始化验证：

- `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-18 --all-stocks`
- 写入结果：`trading_calendar=169`、`stock_basic=5529`、`index_daily=3`、`stock_daily=5507`、`limit_snapshot=103`。
- 最新入库运行记录：`provider=tushare`、`trade_date=2026-06-18`、`status=success`。

### 4. 市场环境评分

- 计算指数 MA20、上涨/下跌家数、涨停/跌停家数、成交额变化和连板高度。
- 生成 `market_daily` 记录。
- 输出市场状态、评分、建议仓位和系统建议。

验收：用真实交易日数据生成市场环境，API 可返回结果。

状态：已完成。

已完成：

- 新增市场环境评分服务：`backend/app/market/service.py`。
- 新增市场环境生成命令：`scripts/generate-market-environment.sh --trade-date YYYY-MM-DD` / `make generate-market-environment`。
- 新增最新市场环境 API：`GET /api/market/latest`。
- TuShare 采集已为三大指数补足 MA20 所需历史日线。
- 修复真实 PostgreSQL 下重复采集多日交易日历时的幂等写入顺序问题。
- 连板高度目前没有结构化字段，评分中明确不计分，不伪造结果。

验证：

- `.venv/bin/pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-17 --all-stocks`
- `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-18 --all-stocks`
- `scripts/generate-market-environment.sh --trade-date 2026-06-18`
- PostgreSQL `market_daily` 最新结果：`trade_date=2026-06-18`、`market_score=55`、`market_status=中性`、`up_count=2023`、`down_count=3395`、`limit_up_count=91`、`limit_down_count=12`、`total_amount=3331719013167.0800`。
- API `GET /api/market/latest` 返回 200，最新结果与数据库一致。

说明：

- 评分项已覆盖上证指数 MA20、创业板指 MA20、上涨/下跌家数、涨停/跌停家数、成交额环比。
- 连板高度需要后续增加连板结构化数据后再纳入评分。

### 5. 强势板块排序

- 计算板块当日涨幅、3 日或 5 日涨幅、成交额变化、涨停数量、强势股数量。
- 输出 Top 10 强势板块并写入 `sector_daily`。

验收：真实交易日能生成 Top 10 板块，板块评分可解释。

### 6. 候选股票筛选

- 实现基础过滤：ST、退市风险、停牌、新股、低成交额、低价股、一字涨停。
- 实现趋势强势、放量突破、强势回踩三类策略。
- 每只候选股票必须生成入选理由。

验收：真实交易日能输出候选股票，且每条候选都有策略命中和解释。

### 7. 交易计划生成

- 生成买入条件、买入区间、止损价、止盈价、建议仓位和风险提示。
- 写入 `trade_plan`。
- 禁止没有止损价的计划入库。

验收：真实交易日能生成第二天交易计划，API 可查询，计划字段完整。

### 8. P0 Web 页面

- 实现今日决策面板。
- 实现强势板块页面。
- 实现今日交易计划页面。
- 实现交易复盘页面。

验收：浏览器能展示真实数据库结果，支持基础排序、筛选和导出。

### 9. 盘中跟踪

- 跟踪昨日交易计划是否触发。
- 判断取消条件和风险状态。
- 支持手动更新状态和备注。

验收：能基于真实或延迟行情更新计划状态，页面/API 有证据。

### 10. 复盘统计

- 生成 `trade_review` 记录。
- 计算当日收益、T+5 收益、最大浮盈、最大浮亏、结果和失败原因。
- 统计最近 30 日策略胜率、板块胜率和盈亏表现。

验收：真实历史计划能生成复盘统计，页面可查看和导出。

### 11. 模拟交易

- 创建模拟账户，默认初始资金 100 万。
- 基于交易计划自动模拟买入、卖出、持仓和交易记录。
- 计入佣金、印花税、过户费。
- 展示账户概览、今日持仓、交易记录、资金曲线和风险指标。

验收：模拟交易只执行计划内股票，每笔买卖都有原因，资金曲线和最大回撤可查。

## 下一步

下一次开发进入任务 5：强势板块排序。开始前必须先读 `AGENTS.md` 和本文件，并运行 `git status --short --branch`。
