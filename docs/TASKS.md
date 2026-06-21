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
- [x] 已完成强势板块排序、入库命令和最新结果 API
- [x] 已完成候选股票筛选、入库命令和最新结果 API
- [x] 已完成交易计划生成、入库命令和最新结果 API
- [x] 已完成 P0 Web 页面，展示真实市场、板块和交易计划 API 结果
- [x] 已完成交易计划盘中跟踪、手动状态更新、命令/API/Web 展示
- [x] 已完成交易复盘生成、最近复盘 API 和 Web 展示

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

状态：已完成。

已完成：

- 新增强势板块评分服务：`backend/app/sector/service.py`。
- 新增 TuShare 东方财富板块 provider：`backend/app/sector/providers.py`。
- 新增生成命令：`scripts/generate-sector-ranking.sh --trade-date YYYY-MM-DD` / `make generate-sector-ranking`。
- 新增强势板块 API：`GET /api/sectors/top`。
- 使用 TuShare `dc_index` 拉取板块窗口数据，使用 `dc_member` 为候选板块补成分股。
- 结合本地 `limit_snapshot` 计算板块内涨停数量。
- 当前 AkShare/Eastmoney 板块接口在本机网络下仍会断连，本任务真实路径采用 TuShare `dc_index`。

评分规则：

- 当日涨幅排名前 10%：`+20`。
- 近 3 日涨幅排名前 20%：`+20`。
- 成交额代理值较前期均值放大：`+20`。
- 板块内涨停数量不少于 2：`+20`。
- 板块上涨家数不少于 5：`+20`。

验证：

- `.venv/bin/pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `scripts/generate-sector-ranking.sh --trade-date 2026-06-18 --member-fetch-limit 80`
- PostgreSQL `sector_daily` 生成 10 条，排名 `1-10`。
- API `GET /api/sectors/top` 返回 200，最新结果与数据库一致。

真实 Top 10：

1. `非金属材料Ⅲ`：日涨幅 `5.96`，3 日涨幅 `12.49`，涨停 `3`，强势股 `8`，评分 `100`。
2. `非金属材料Ⅱ`：日涨幅 `5.96`，3 日涨幅 `12.49`，涨停 `5`，强势股 `8`，评分 `100`。
3. `蓝宝石`：日涨幅 `3.99`，3 日涨幅 `9.34`，涨停 `2`，强势股 `13`，评分 `100`。
4. `半导体设备`：日涨幅 `3.16`，3 日涨幅 `11.12`，涨停 `2`，强势股 `17`，评分 `100`。
5. `金属新材料`：日涨幅 `3.07`，3 日涨幅 `5.49`，涨停 `2`，强势股 `27`，评分 `100`。
6. `Kimi概念`：日涨幅 `3.03`，3 日涨幅 `2.55`，涨停 `2`，强势股 `14`，评分 `100`。
7. `科技风格`：日涨幅 `2.83`，3 日涨幅 `8.70`，涨停 `3`，强势股 `79`，评分 `100`。
8. `先进封装`：日涨幅 `2.81`，3 日涨幅 `9.84`，涨停 `4`，强势股 `30`，评分 `100`。
9. `CPO概念`：日涨幅 `2.74`，3 日涨幅 `8.58`，涨停 `2`，强势股 `46`，评分 `100`。
10. `小金属`：日涨幅 `2.73`，3 日涨幅 `3.32`，涨停 `6`，强势股 `17`，评分 `100`。

说明：

- `amount_change` 当前使用 TuShare `dc_index.total_mv * turnover_rate / 100` 作为成交额代理值，后续若取得板块真实成交额字段，应替换为真实成交额。
- `sector_daily.five_day_return` 字段当前保存近 3 日累计涨幅；后续如改为 5 日，应同步迁移字段命名或 API 展示。

### 6. 候选股票筛选

- 实现基础过滤：ST、退市风险、停牌、新股、低成交额、低价股、一字涨停。
- 实现趋势强势、放量突破、强势回踩三类策略。
- 每只候选股票必须生成入选理由。

验收：真实交易日能输出候选股票，且每条候选都有策略命中和解释。

状态：已完成。

已完成：

- 新增候选股票表：`candidate_stock`。
- 新增候选股票迁移：`0003_candidate_stock_table`。
- 新增候选筛选服务：`backend/app/candidate/service.py`。
- 新增 TuShare 东方财富板块成分 provider：`backend/app/candidate/providers.py`。
- 新增生成命令：`scripts/generate-candidates.sh --trade-date YYYY-MM-DD` / `make generate-candidates`。
- 新增候选查询 API：`GET /api/candidates/latest`。
- 基础过滤已覆盖 ST/退市风险、非 active、新股、低成交额、低价股、一字涨停和历史窗口不足。
- 策略已覆盖趋势强势、放量突破、强势回踩，所有候选都带中文入选理由和风险提示。

验证：

- `.venv/bin/pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `scripts/db-upgrade.sh` -> `0003_candidate_stock_table (head)`
- 已回补 `2026-05-20` 到 `2026-06-18` 的 22 个交易日个股日线，共 `121182` 条。
- `scripts/generate-candidates.sh --trade-date 2026-06-18 --limit 50`
- PostgreSQL `candidate_stock`：`trade_date=2026-06-18` 生成 `42` 条候选，分数范围 `91-100`。
- 策略分布：`趋势强势=34`、`强势回踩=6`、`放量突破=2`。
- API `GET /api/candidates/latest` 返回 200，最新结果与数据库一致。

真实 Top 候选样例：

- `300308 中际旭创`：`科技风格`，`趋势强势`，评分 `100`。
- `603986 兆易创新`：`科技风格`，`趋势强势`，评分 `100`。
- `600487 亨通光电`：`科技风格`，`趋势强势`，评分 `100`。
- `002384 东山精密`：`科技风格`，`趋势强势`，评分 `100`。
- `688525 佰维存储`：`科技风格`，`趋势强势`，评分 `100`。

说明：

- 本任务只输出候选股票，不生成买入区间、止损价、止盈价和建议仓位。
- 同一股票可以因多个策略重复入选；后续交易计划生成时需要合并或择优处理。
- 候选必须有板块 Top 10 共振；弱板块孤立强股不进入当前候选池。

### 7. 交易计划生成

- 生成买入条件、买入区间、止损价、止盈价、建议仓位和风险提示。
- 写入 `trade_plan`。
- 禁止没有止损价的计划入库。

验收：真实交易日能生成第二天交易计划，API 可查询，计划字段完整。

状态：已完成。

已完成：

- 新增交易计划生成服务：`backend/app/trade/service.py`。
- 新增交易计划生成命令：`scripts/generate-trade-plans.sh --plan-date YYYY-MM-DD` / `make generate-trade-plans`。
- 新增最新交易计划 API：`GET /api/trade-plans/latest`。
- 从 `candidate_stock`、`market_daily`、`stock_daily` 和 `trading_calendar` 生成次日条件交易计划。
- 已实现市场状态仓位限制：强势最多 3 只，中性最多 2 只，弱势最多 1 只，风险不生成新计划。
- 已实现止损价硬约束：止损价无效或高于计划买入参考价时不入库。
- 止损价按技术止损、固定 5% 止损、ATR14 止损三者中更接近买入价者计算。

验证：

- `.venv/bin/pytest`：42 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus 相关 chunk size warning。
- `scripts/generate-trade-plans.sh --plan-date 2026-06-18`：成功生成 2 条真实交易计划并写入 `trade_plan`。
- 真实 API `GET /api/trade-plans/latest`：返回 200，`plan_date=2026-06-18`、`target_trade_date=2026-06-19`、`items=2`。
- 真实计划目标交易日：`2026-06-19`。
- 真实计划样例：
  - `300308 中际旭创`：`科技风格`，`趋势强势`，买入区间 `1207.2060 - 1367.8800`，止损 `1299.4860`，止盈 `1641.4560`，仓位 `40%`。
  - `603986 兆易创新`：`科技风格`，`趋势强势`，买入区间 `517.4120 - 629.0000`，止损 `597.5500`，止盈 `754.8000`，仓位 `40%`。

### 8. P0 Web 页面

- 实现今日决策面板。
- 实现强势板块页面。
- 实现今日交易计划页面。
- 实现交易复盘页面。

验收：浏览器能展示真实数据库结果，支持基础排序、筛选和导出。

状态：已完成。

已完成：

- 前端首页已改为 P0 业务工作台，包含今日决策面板、强势板块、今日交易计划和交易复盘入口。
- 今日决策面板接入 `GET /api/market/latest`，展示交易日、市场状态、评分、建议仓位、涨跌停、上涨/下跌家数、成交额和系统建议。
- 强势板块页面接入 `GET /api/sectors/top`，展示 Top 10 排名、涨幅、3 日涨幅、成交额代理、涨停数、强势股数和评分；支持表格排序、关键词筛选和 CSV 导出。
- 今日交易计划页面接入 `GET /api/trade-plans/latest`，展示股票、板块、策略、评分、买入条件、买入区间、止损/止盈、仓位、状态和风险提示；支持表格排序、关键词筛选和 CSV 导出。
- 交易复盘页面当前展示明确空态，等待任务 10 接入真实 `trade_review` 后显示复盘统计，不伪造复盘数据。

验证：

- `.venv/bin/pytest`：42 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus 相关 chunk size warning。
- 真实 API 快验：`/api/market/latest` 返回 200，`trade_date=2026-06-18`、`market_status=中性`、`market_score=55`。
- 真实 API 快验：`/api/sectors/top` 返回 200，`trade_date=2026-06-18`、`items=10`。
- 真实 API 快验：`/api/trade-plans/latest` 返回 200，`plan_date=2026-06-18`、`items=2`。
- Playwright 浏览器快验：`http://127.0.0.1:5173/` 展示 `今日决策面板`、`科技风格`、`中际旭创`、`40%` 和 `交易复盘`；console 仅有缺少 `favicon.ico` 的 404。

### 9. 盘中跟踪

- 跟踪昨日交易计划是否触发。
- 判断取消条件和风险状态。
- 支持手动更新状态和备注。

验收：能基于真实或延迟行情更新计划状态，页面/API 有证据。

状态：已完成。

已完成：

- `trade_plan` 新增 `trigger_price`、`trigger_time`、`tracking_note` 字段。
- 新增迁移：`migrations/versions/0004_trade_plan_tracking_fields.py`。
- 新增自动跟踪服务：`track_trade_plans`。
- 新增手动状态更新服务：`update_trade_plan_status`。
- 新增 CLI：`scripts/track-trade-plans.sh --target-trade-date YYYY-MM-DD [--mark-untriggered-at-close]`。
- 新增 Makefile 入口：`make track-trade-plans`。
- 新增 API：
  - `POST /api/trade-plans/track`
  - `PATCH /api/trade-plans/{plan_id}/status`
- 今日交易计划页面新增“跟踪触发”“收盘确认”按钮，支持手动标记触发/取消，展示触发价和跟踪备注。

验证：

- `.venv/bin/pytest`：47 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus 相关 chunk size warning。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5433/stock scripts/db-upgrade.sh`：迁移到 `0004_trade_plan_tracking_fields (head)`。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5433/stock scripts/track-trade-plans.sh --target-trade-date 2026-06-19 --mark-untriggered-at-close`：返回 2 条真实计划；因目标交易日日线暂无数据，状态保持 `待触发` 并写入 `目标交易日暂无日线数据，保持待触发状态`。
- 运行中 API 快验：`POST /api/trade-plans/track` 返回 200，`target_trade_date=2026-06-19`、`items=2`。

### 10. 复盘统计

- 生成 `trade_review` 记录。
- 计算当日收益、T+5 收益、最大浮盈、最大浮亏、结果和失败原因。
- 统计最近 30 日策略胜率、板块胜率和盈亏表现。

验收：真实历史计划能生成复盘统计，页面可查看和导出。

状态：已完成。

已完成：

- 新增交易复盘生成服务：`generate_trade_reviews`。
- 新增最近交易复盘读取服务：`load_latest_trade_reviews`。
- 新增 CLI：`scripts/generate-trade-reviews.sh --trade-date YYYY-MM-DD`。
- 新增 Makefile 入口：`make generate-trade-reviews`。
- 新增 API：
  - `POST /api/trade-reviews/generate`
  - `GET /api/trade-reviews/latest`
- Web 交易复盘页面已接入真实复盘 API，展示计划数量、触发数量、胜率、当日均收益、T+5 均收益、策略统计和复盘明细。
- 复盘计算只使用目标交易日及之后已经入库的日线；缺少日线时不伪造收益，记录明确失败原因和备注。

验证：

- `.venv/bin/pytest`：49 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus / chunk size warning。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-upgrade.sh`：成功。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh`：`0004_trade_plan_tracking_fields (head)`。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/generate-trade-reviews.sh --trade-date 2026-06-19`：生成 `2` 条真实复盘记录；因 `2026-06-19` 目标日线暂无数据，收益字段为 `null`，结果为 `未触发`，备注为 `目标交易日暂无日线数据，保持待触发状态`。
- 真实复盘统计：`total_count=2`、`triggered_count=0`、`win_rate=0.0`，策略统计和板块统计均按 `趋势强势` / `科技风格` 输出。

### 11. 模拟交易

- 创建模拟账户，默认初始资金 100 万。
- 基于交易计划自动模拟买入、卖出、持仓和交易记录。
- 计入佣金、印花税、过户费。
- 展示账户概览、今日持仓、交易记录、资金曲线和风险指标。

验收：模拟交易只执行计划内股票，每笔买卖都有原因，资金曲线和最大回撤可查。

## 下一步

下一次开发进入任务 11：模拟交易。开始前必须先读 `AGENTS.md` 和本文件，并运行 `git status --short --branch`。
