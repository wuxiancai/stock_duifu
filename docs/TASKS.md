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
- [x] 已完成模拟交易账户、买卖撮合、资金曲线、API/CLI/Web 展示
- [x] 已完成模拟交易盘中实盘化基础链路：先跟踪计划触发，再自动运行模拟交易
- [x] 已完成任务 13 第一阶段：按目标交易日交易计划回补真实个股日线，并识别目标日闭市
- [x] 已完成任务 13 第二阶段：闭市目标日交易计划自动顺延/重生成到下一开市日
- [x] 已完成任务 13 第三阶段基础链路：延迟实时行情入口、目标计划股快照回补、跟踪并模拟 workflow
- [x] 已完成 PRD MVP 接口和页面对齐补口：按日期查询接口、交易计划详情、盘中跟踪页面和复盘人工更新接口
- [x] 已完成 PRD MVP 操作补口：交易计划关注标记、`POST /api/reviews` 和复盘 CSV 导出
- [x] 已完成 PRD MVP 盘后工作流入口：按顺序执行采集、市场、板块、候选和交易计划生成
- [x] 已补齐 PRD 第 17 章任务映射：扩展模块 / 模拟交易模块逐小节状态和缺口
- [x] 已补齐 PRD 市场环境遗漏项：连板高度结构化、评分加分、入库、API 和 Web 展示
- [x] 已补齐 PRD 强势板块和候选股票页面遗漏项：真实 5 日涨幅、板块点击筛选候选、候选股票池展示和导出
- [x] 已补齐 Ubuntu 一键部署与数据初始化脚本：`deploy_ubuntu.sh`、`get_data.sh`、LAN 监听启动口径
- [x] 已优化强势板块浏览体验：点击板块进入独立详情页，候选股票和交易计划按板块分页面展示
- [x] 已修复部署 PostgreSQL 端口占用：`deploy_ubuntu.sh` 会顺延宿主机端口并写回 `.env`
- [x] 已修复部署迁移连错旧端口：旧本地 `DATABASE_URL` 会按 Docker 实际端口重写
- [x] 已避开系统 PostgreSQL 默认端口：部署默认从 `15432` 启动项目 PostgreSQL
- [x] 已优化 Ubuntu 启动脚本：`start.sh` 生产启动 API 不使用 reload，失败时直接打印日志尾部
- [x] 已修复 start.sh API 端口误判：端口检测改为真实 bind 探测，8000 被占用时会选择 8001
- [x] 已修复 Ubuntu 前端 API 访问口径：浏览器固定走同源 `/api`，由 Vite 代理到实际 API 端口，并提示局域网防火墙放通 Web 端口
- [x] 已修复 `.env` 残留 `VITE_API_BASE_URL` 污染前端：`start.sh` 启动前端时强制清空浏览器端绝对 API 地址
- [x] 已修复启动脚本端口事实源不一致：`start.sh` 选定 PostgreSQL/API/Web 端口后写回 `.env`
- [x] 已修复新部署空库首页误报 404：latest 接口无数据时返回 200 空态而不是错误
- [x] 已修复 `get_data.sh` 子脚本权限问题：统一用 `bash scripts/...` 调用，不依赖执行位
- [x] 已修复 `get_data.sh` 盘后 workflow 采集摘要字段缺失：返回真实 `data_ingest_run.id`
- [x] 已修复模拟交易和复盘闭市日展示错误：请求闭市日会按交易日历顺延到下一开市日，latest 接口过滤闭市日记录
- [x] 已增强 `get_data.sh`：支持 `--start YYYYMMDD --end YYYYMMDD` 区间批量拉取并逐日生成结果
- [x] 已优化 Web 可读性：今日交易计划改为紧凑卡片展示，盘中跟踪按钮会先回补延迟实时行情，涨跌/盈亏/收益类数值统一红涨绿跌。
- [x] 已修复盘中跟踪实时展示链路：实时快照写入后，最新交易计划 API 和页面刷新会直接展示当前价/涨跌幅；模拟交易按钮会先刷新实时行情再跟踪和撮合，避免用空目标日日线或收盘后日线决定买卖。
- [x] 已优化模拟交易与股票详情阅读体验：模拟持仓现价按实时涨跌着色，买入交易记录用当前持仓浮盈亏兜底展示盈亏；股票详情默认隐藏，点击交易计划卡片股票名称展开，再次点击收起。
- [x] 已新增数据拉取跟踪日志与数据库健康监测：夜间 workflow 结构化记录每步开始/结束/数量/报错，页面底部展示运行日志、健康检查和补数命令。
- [x] 已修正数据库健康监测的个股日线完整性口径：ST、退市/退市风险、非 active 以及全市场小比例停牌/当日无交易缺口不再误报 warning。
- [x] 已优化数据健康区可读性：数据库健康检查表取消内部纵向滚动条，检查项直接全部显示。
- [x] 已修复 `get_data.sh` 区间模式交易日过滤：批量拉取不再按自然日跑 workflow，只对 TuShare 交易日历开市日执行。

## 开发原则

- 每个任务都必须包含测试、真实数据验收、文档更新和 git commit。
- 每个任务完成后必须更新 `docs/HANDOFF.md`。
- 不允许用 mock、静态页面、脚本存在或单次测试通过冒充阶段完成。
- 优先做能独立演示的垂直切片，避免先搭复杂平台。

## 最新验证记录

### 2026-06-22 盘中实时展示与模拟交易修复

- 修复点：
  - `GET /api/trade-plans/latest` 和 `GET /api/trade-plans?date=YYYY-MM-DD` 在目标交易日已有 `stock_daily` 实时快照时，返回 `current_price` / `pct_chg`。
  - 盘中跟踪表刷新后优先展示实时跟踪结果，兜底展示交易计划 API 自带的当前价/涨跌幅。
  - Web “跟踪并模拟交易” 会先调用实时行情回补与跟踪，再运行模拟交易，避免跳过盘中实时触发。
- 真实 API 验证：
  - `curl -sS -X POST http://127.0.0.1:5173/api/trade-plans/track-realtime ...` 返回 `provider=akshare_sina_realtime`、`fetched_stock_daily_rows=2`、`missing_stock_codes=[]`。
  - `GET /api/trade-plans/latest` 返回 `300308 current_price=1358.24 pct_chg=-0.705 status=已触发`，`603986 current_price=659.56 pct_chg=4.859 status=待触发`。
  - `POST /api/simulation/run-workflow` 基于 2026-06-22 实时快照买入 `300308`，返回模拟买入记录 `trade_plan_id=3`、`price=1367.78`、`quantity=200`。
- 自动化验证：
  - `.venv/bin/pytest tests/test_trade_plan_generation.py tests/test_realtime_quote_workflow.py tests/test_simulation_trading.py`：43 passed，1 个 LibreSSL/urllib3 warning。
  - `cd frontend && npm test -- --run`：2 passed。
  - `cd frontend && npm run build`：通过，仍有 VueUse pure annotation 和 chunk size warning。

### 2026-06-22 模拟交易颜色与股票详情折叠修复

- 修复点：
  - 模拟持仓表“成本/现价”中的现价按当前价相对买入价红涨绿跌显示。
  - 模拟交易记录“盈亏”列在后端买入记录未产生已实现盈亏时，使用同股票当前持仓浮盈亏和浮盈亏率兜底展示。
  - 今日交易计划不再默认展示股票详情；点击计划卡片股票名称展开详情，再次点击同一股票名称收起。
- 真实 API 依据：
  - `GET /api/simulation/latest` 当前返回 `300308 buy_price=1367.78 current_price=1358.24 unrealized_profit=-1992.8024 unrealized_return=-0.0073`，但买入交易 `profit_loss=null`；前端因此以持仓浮盈亏兜底显示买入后的实时盈亏。
- 自动化验证：
  - `cd frontend && npm test -- --run`：2 passed。
  - `cd frontend && npm run build`：通过，仍有 VueUse pure annotation 和 chunk size warning。

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
- 已补齐连板高度结构化字段 `market_daily.limit_up_height`，基于真实涨停池连续出现天数计算，连板高度不少于 3 板时按 PRD 加 15 分。

验证：

- `.venv/bin/pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-17 --all-stocks`
- `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-18 --all-stocks`
- `scripts/generate-market-environment.sh --trade-date 2026-06-18`
- PostgreSQL `market_daily` 最新结果：`trade_date=2026-06-18`、`market_score=70`、`market_status=中性`、`up_count=2023`、`down_count=3395`、`limit_up_count=91`、`limit_down_count=12`、`limit_up_height=4`、`total_amount=3331719013167.0800`。
- API `GET /api/market/latest` 返回 200，最新结果与数据库一致。

说明：

- 评分项已覆盖上证指数 MA20、创业板指 MA20、上涨/下跌家数、涨停/跌停家数、成交额环比和连板高度。

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
- `sector_daily.five_day_return` 字段当前保存真实 5 日累计涨幅；API 继续兼容返回 `three_day_return`，前端展示以 5 日涨幅为准。

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
- 今日决策面板接入 `GET /api/market/latest`，展示交易日、市场状态、评分、建议仓位、涨跌停、连板高度、上涨/下跌家数、成交额和系统建议。
- 强势板块页面接入 `GET /api/sectors/top`，展示 Top 10 排名、涨幅、3 日涨幅、成交额代理、涨停数、强势股数和评分；支持表格排序、关键词筛选和 CSV 导出。
- 今日交易计划页面接入 `GET /api/trade-plans/latest`，展示股票、板块、策略、评分、买入条件、买入区间、止损/止盈、仓位、状态和风险提示；支持表格排序、关键词筛选和 CSV 导出。
- 交易复盘页面当前展示明确空态，等待任务 10 接入真实 `trade_review` 后显示复盘统计，不伪造复盘数据。

验证：

- `.venv/bin/pytest`：42 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus 相关 chunk size warning。
- 真实 API 快验：`/api/market/latest` 返回 200；当时快验 `market_score=55`，任务 18 补齐连板高度后，同一真实库重算为 `market_score=70`、`limit_up_height=4`。
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

状态：已完成。

已完成：

- 新增模拟交易表和迁移：`simulation_account`、`simulation_position`、`simulation_trade`、`simulation_equity`，迁移版本为 `0005_simulation_trading_tables`。
- 新增模拟交易服务：`backend/app/simulation/service.py`，默认账户初始资金 `1000000`。
- 新增模拟交易 CLI：`scripts/run-simulation.sh --trade-date YYYY-MM-DD` / `make run-simulation`。
- 新增 API：
  - `POST /api/simulation/run`
  - `GET /api/simulation/latest`
- 买入只执行 `target_trade_date` 匹配且状态为 `已触发` 的交易计划；无触发价、无止损、涨停、高开过多、低开跌破止损均不买入。
- 卖出优先处理持仓止损，跌停时不强行卖出。
- 手续费已计入佣金 `0.03%`、印花税 `0.05%`、过户费 `0.001%`，佣金最低 `5` 元。
- Web 新增“模拟交易”页面，展示账户概览、持仓、交易记录和资金曲线。

验证：

- `.venv/bin/pytest`：57 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus / chunk size warning。
- `bash -n scripts/run-simulation.sh`：通过。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-upgrade.sh`：迁移到 `0005_simulation_trading_tables (head)`。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-simulation.sh --trade-date 2026-06-19`：创建默认模拟账户并生成 `2026-06-19` 权益曲线，总资产 `1000000.0`。
- 真实数据库当前 `2026-06-19` 两条交易计划仍为 `待触发`，因此模拟交易没有伪造买入，`simulation_trade=0`、持仓为 `0`。
- 真实 API 快验：`GET /api/simulation/latest` 返回 200，`as_of_date=2026-06-19`、`total_assets=1000000.0`、资金曲线 `1` 条。

### 12. 模拟交易盘中实盘化基础链路

- 将盘中跟踪和模拟交易串成一键流程。
- 先更新交易计划触发状态，再基于触发结果执行模拟买入/卖出。
- 保留独立跟踪和独立模拟入口，便于排查数据问题。
- Web 模拟交易按钮默认运行连续流程。

验收：目标交易日日线满足买入条件时，待触发计划会先变为已触发，再生成模拟买入、持仓、交易记录和资金曲线；缺少真实日线时必须明确说明，不伪造成交。

状态：已完成。

已完成：

- 新增服务入口：`run_simulation_workflow(engine, trade_date, mark_untriggered_at_close=False)`。
- 新增 API：`POST /api/simulation/run-workflow`。
- 新增 CLI：`python -m backend.app.simulation.cli run-workflow --trade-date YYYY-MM-DD`。
- `scripts/run-simulation.sh` 保持旧用法，同时支持 `run-workflow` 和 `latest` 子命令。
- Web 模拟交易按钮改为“跟踪并模拟交易”，调用新 workflow，并刷新交易计划状态和模拟结果。

验证：

- `.venv/bin/pytest`：60 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus / chunk size warning。
- `bash -n scripts/run-simulation.sh`：通过。
- 真实 PostgreSQL：`docker compose ps postgres` 显示 `stock-postgres` healthy，端口 `127.0.0.1:5432->5432`。
- 真实 PostgreSQL：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 真实 workflow：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-simulation.sh run-workflow --trade-date 2026-06-19` 返回 `tracking=2`、总资产 `1000000.0`、交易 `0` 笔；原因是两只计划股目标日日线缺失，状态保持 `待触发` 并写入明确备注。
- 真实 API 快验：`POST /api/simulation/run-workflow` 返回 200，`target_trade_date=2026-06-19`、`tracking=2`、`total_assets=1000000.0`、`trades=0`。

### 13. 真实目标交易日日线回补入口

- 为目标交易日的交易计划补齐真实 `stock_daily` 数据。
- 只拉取计划内且目标日缺失日线的股票，避免为了少数计划股重复全市场采集。
- 输出计划股票数、已有日线数、请求股票数、实际回补日线数、仍缺失股票和目标日是否开市。
- 盘中跟踪在目标日明确非开市时，写入“目标交易日不是开市日，未产生行情数据，计划需重新生成到下一开市日”，不伪造成交。

验收：目标日有真实日线时可进入后续跟踪和模拟；目标日闭市或数据源未返回日线时必须明确说明，不伪造成交。

状态：第三阶段基础链路和备用实时源已完成；真实成交验收仍需在目标交易日当天重跑。分批止盈、移动止损和交易时段轮询已在任务 17 补齐。

已完成：

- 新增服务：`backend/app/data/target_daily.py`。
- 新增 CLI：`python -m backend.app.data.cli backfill-target-daily --target-trade-date YYYY-MM-DD`。
- 新增脚本和 Makefile 入口：`scripts/backfill-target-daily.sh` / `make backfill-target-daily`。
- 回补结果新增 `target_is_open`，用于区分“数据源缺日线”和“目标日不是开市日”。
- `track_trade_plans` 在目标日闭市且无日线时输出闭市备注，保持不触发、不模拟买入。
- 新增服务：`retarget_closed_trade_plans(engine, target_trade_date, limit=None)`。
- 新增 CLI：`python -m backend.app.trade.cli retarget-closed --target-trade-date YYYY-MM-DD`。
- 新增脚本和 Makefile 入口：`scripts/retarget-closed-trade-plans.sh` / `make retarget-closed-trade-plans`。
- 闭市目标日会把旧计划标记为 `取消` 并写入顺延备注，再用原计划日重新生成到目标日之后的下一开市日；缺少下一开市日历时会明确提示先采集更晚交易日历。
- 新增 AkShare/Eastmoney 延迟实时行情 provider：`AkShareRealtimeQuoteProvider`，将 `stock_zh_a_spot_em` 快照映射为 `StockDailyRecord`。
- 新增 AkShare/Sina 备用实时行情 provider：`AkShareSinaRealtimeQuoteProvider`，将 `stock_zh_a_spot` 快照映射为 `StockDailyRecord`。
- 新增 `FallbackRealtimeQuoteProvider`，`run-realtime-workflow --provider auto` 会先尝试 Eastmoney，失败或返回空行后再尝试 Sina；CLI 默认 provider 已改为 `auto`。
- 新增服务：`backend/app/data/realtime_quotes.py`，只针对目标日交易计划股回补实时快照，并串联 `run_simulation_workflow`。
- 新增 CLI：`python -m backend.app.data.cli run-realtime-workflow --target-trade-date YYYY-MM-DD`。
- 新增脚本和 Makefile 入口：`scripts/run-realtime-workflow.sh` / `make run-realtime-workflow`。
- 默认保护实时快照只能写入中国当前自然日，避免把非目标日盘口误写到未来交易日；必要时可用 `--allow-date-mismatch` 显式放开。
- 实时数据源异常会收敛为 JSON 结果中的 `skipped_reason`，不写入伪造行情、不让命令用 traceback 作为业务结果。

验证：

- `.venv/bin/pytest`：65 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 Element Plus / chunk size warning。
- `bash -n scripts/backfill-target-daily.sh scripts/ingest-market-data.sh scripts/run-simulation.sh`：通过。
- 真实 PostgreSQL：`docker compose ps postgres` 显示 `stock-postgres` healthy，端口 `127.0.0.1:5432->5432`。
- 真实 PostgreSQL：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 真实回补：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/backfill-target-daily.sh --provider tushare --target-trade-date 2026-06-19` 返回 `planned_stock_count=2`、`requested_stock_count=2`、`fetched_stock_daily_rows=0`、`missing_stock_codes=["300308", "603986"]`、`target_is_open=false`。
- 真实 workflow：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-simulation.sh run-workflow --trade-date 2026-06-19` 返回 `tracking=2`、总资产 `1000000.0`、交易 `0` 笔；两只计划股保持 `待触发`，备注为目标日不是开市日。
- 第二阶段验证：`.venv/bin/pytest`：68 passed，1 个 LibreSSL/urllib3 warning。
- 第二阶段验证：`cd frontend && npm test -- --run`：1 passed。
- 第二阶段验证：`cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 第二阶段脚本验证：`bash -n scripts/retarget-closed-trade-plans.sh scripts/backfill-target-daily.sh scripts/ingest-market-data.sh scripts/run-simulation.sh`：通过。
- 第二阶段真实日历补充：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-22 --stock-code 300308 --stock-code 603986` 返回 `trading_calendar_rows=173`、`stock_daily_rows=0`。
- 第二阶段真实顺延：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/retarget-closed-trade-plans.sh --target-trade-date 2026-06-19` 返回 `target_is_open=false`、`new_target_trade_date=2026-06-22`、`closed_plan_count=2`、`generated_plan_count=2`。
- 第二阶段真实库确认：`2026-06-19` 两条计划状态为 `取消` 且备注为已重新生成到 `2026-06-22`；`2026-06-22` 两条计划状态为 `待触发`。
- 第三阶段备用源验证：`.venv/bin/pytest`：73 passed，1 个 LibreSSL/urllib3 warning。
- 第三阶段备用源验证：`cd frontend && npm test -- --run`：1 passed。
- 第三阶段备用源验证：`cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 第三阶段备用源脚本验证：`bash -n scripts/run-realtime-workflow.sh scripts/backfill-target-daily.sh scripts/run-simulation.sh`：通过。
- 第三阶段备用源 CLI 验证：`.venv/bin/python -m backend.app.data.cli run-realtime-workflow --help` 正常展示 `--provider {auto,akshare,sina}`。
- 第三阶段备用源真实只读验证：`AkShareSinaRealtimeQuoteProvider` 成功返回 `300308`、`603986` 两只目标计划股实时快照，source 为 `akshare_sina_realtime`。
- 第三阶段备用源真实命令：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-realtime-workflow.sh --provider auto --target-trade-date 2026-06-22` 返回 `planned_stock_count=2`、`requested_stock_count=2`、`target_is_open=true`，但因本机判断 `china_today=2026-06-21`，触发日期保护，未写入 `2026-06-22` 行情，`workflow=null`。
- 第三阶段真实 PostgreSQL：`docker compose ps postgres` 显示 `stock-postgres` healthy，端口 `127.0.0.1:5432->5432`；`scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 第三阶段真实命令：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-realtime-workflow.sh --provider akshare --target-trade-date 2026-06-22` 返回 `planned_stock_count=2`、`requested_stock_count=2`、`target_is_open=true`，但因本机判断 `china_today=2026-06-21`，触发日期保护，未写入 `2026-06-22` 行情，`workflow=null`。
- 第三阶段只读实时源验证：AkShare/Eastmoney `stock_zh_a_spot_em` 当前在本机网络下返回 `RemoteDisconnected`；Sina `stock_zh_a_spot` 本轮可作为目标计划股备用实时源。

### 14. PRD MVP 接口与页面对齐补口

- 补齐 PRD 后端接口路径：
  - `GET /api/market/today`
  - `GET /api/sectors/strong?date=YYYY-MM-DD`
  - `GET /api/trade-plans?date=YYYY-MM-DD`
  - `GET /api/trade-plans/{id}`
  - `GET /api/reviews?date=YYYY-MM-DD`
  - `PATCH /api/reviews/{id}`
- `GET /api/trade-plans/{id}` 返回交易计划、候选入选理由和 MA5/MA10/MA20/ATR14/成交额/换手率等关键指标。
- Web 工作台补齐 PRD 页面入口：
  - 股票详情
  - 盘中跟踪
- 复盘人工更新只允许修改结果、失败原因、纪律检查和备注；价格、收益和触发事实仍由复盘生成逻辑计算。

状态：已完成。

验证：

- `.venv/bin/pytest`：77 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 真实 PostgreSQL：`docker compose ps postgres` 显示 `stock-postgres` healthy，端口 `127.0.0.1:5432->5432`。
- 真实 PostgreSQL：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 真实 API 快验：
  - `GET /api/market/today` -> 200，`market_status=中性`。
  - `GET /api/sectors/strong?date=2026-06-18` -> 200，`items=10`。
  - `GET /api/trade-plans?date=2026-06-22` -> 200，`items=2`。
  - `GET /api/trade-plans/{id}` -> 200，真实计划 `300308 中际旭创`，返回入选理由和关键指标。
  - `GET /api/reviews?date=2026-06-19` -> 200，`items=2`。

### 15. PRD MVP 操作补口

- 新增 `trade_plan.is_watched` 字段和迁移 `0006_trade_plan_attention_flag`，用于交易计划页面手动标记是否关注。
- `PATCH /api/trade-plans/{id}/status` 支持 `is_watched`，可在不改变交易状态的情况下切换关注标记。
- 补齐 PRD 指定 `POST /api/reviews`，复用现有真实复盘生成逻辑，按 `trade_date` 生成或重算 `trade_review`。
- Web 今日交易计划页面新增关注状态列和关注/取消关注按钮。
- Web 交易复盘页面新增 CSV 导出。

状态：已完成。

验证：

- `.venv/bin/pytest`：79 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 真实 PostgreSQL：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-upgrade.sh` 已升级 `0005 -> 0006`。
- 真实 PostgreSQL：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0006_trade_plan_attention_flag (head)`。
- 真实 API 快验：
  - `PATCH /api/trade-plans/{id}/status` 可写入 `is_watched=true`，返回 200；快验后已恢复为 `is_watched=false` 且清空测试备注。
  - `POST /api/reviews` 使用 `trade_date=2026-06-19` 返回 200，`total_count=2`。

### 16. PRD MVP 盘后工作流入口

- 新增 `backend.app.workflow.service.run_after_close_workflow`，按 PRD 9.1 顺序执行：
  1. 拉取最新行情数据并写入数据库。
  2. 计算市场环境。
  3. 计算强势板块。
  4. 筛选候选股票。
  5. 生成交易计划。
- 新增 CLI：`python -m backend.app.workflow.cli after-close --trade-date YYYY-MM-DD`。
- 新增脚本和 Makefile 入口：
  - `scripts/run-after-close-workflow.sh`
  - `make run-after-close-workflow`
- workflow 返回每一步真实计数摘要，包括 `stock_daily_rows`、`sector_count`、`candidate_count`、`trade_plan_count` 和 `target_trade_date`。

状态：已完成。

验证：

- `.venv/bin/pytest`：81 passed，1 个 LibreSSL/urllib3 warning。
- `bash -n scripts/run-after-close-workflow.sh`：通过。
- `.venv/bin/python -m backend.app.workflow.cli after-close --help`：正常展示 `--trade-date`、`--provider`、`--member-fetch-limit`、`--candidate-limit`、`--trade-plan-limit`。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 17. PRD 第 17 章：扩展模块 / 模拟交易模块

目标：完成 `PRD_MVP.md` 第 17 章模拟交易模块的开发补齐；已提前完成的任务 11-13 基础能力继续复用，不重复造轮子。

状态：开发已补齐；`2026-06-22` 目标交易日真实盘中/延迟行情写入和模拟成交仍需到当天运行验证，不得提前宣称真实成交验收完成。

本轮补齐：

- 交易费用参数化：`SIMULATION_COMMISSION_RATE`、`SIMULATION_STAMP_TAX_RATE`、`SIMULATION_TRANSFER_FEE_RATE`、`SIMULATION_MIN_COMMISSION`。
- 卖出规则：第一止盈卖出 50%、第二止盈再卖 30%、跌破 MA5 卖出剩余仓位、市场转风险卖出、板块退潮卖出、持仓超期按收盘价卖出、快速跳水记录滑点原因。
- 持仓状态：部分止盈仓位继续作为有效持仓参与后续卖出判断。
- 交易记录：API/Web 暴露交易时间、交易后现金、交易后仓位、买卖原因。
- 风险统计：基于模拟卖出记录统计胜率和盈亏比，继续展示总资产、可用现金、持仓市值、累计收益率和最大回撤。
- 页面入口：Web 导航提供 `/simulation` 模拟交易路径，页面展示账户概览、当日盈亏、持仓、交易记录、资金曲线和风险指标。
- 定时轮询：新增 `python -m backend.app.simulation.cli loop --trade-date YYYY-MM-DD --interval-seconds 60`，交易时段 `09:30-15:00` 每 1-5 分钟运行；`--max-iterations` 用于受控验收。

逐节状态：

- 17.1.1 模块定位：已完成开发；真实目标日表现仍需当天验收。
- 17.1.2 与交易计划的关系：已完成，模拟交易只执行系统计划内交易，并通过 workflow 先跟踪触发再模拟。
- 17.1.3 初始资金：已完成，默认 `1000000`，按账户和权益曲线复利滚动。
- 17.1.4 资金账户字段：已完成基础字段；冻结资金保留字段，当前无挂单冻结逻辑。
- 17.1.5 交易费用规则：已完成，默认费率符合 PRD，且支持环境变量配置。
- 17.1.6 买入规则：已完成当前数据条件下的保守买入规则；VWAP 触发依赖后续更细盘中数据源，不在当前日线/延迟快照粒度中伪造。
- 17.1.7 卖出规则：已完成止损、两档止盈、MA5、市场风险、板块退潮、持仓超期、快速跳水和跌停不强卖。
- 17.1.8 持仓管理：已完成，支持持仓中、部分止盈、已清仓状态。
- 17.1.9 交易记录：已完成，包含时间、方向、价格、数量、金额、费用、现金、仓位、盈亏和原因。
- 17.1.10 买入原因和卖出原因：已完成，覆盖买入触发、止损、两档止盈、MA5、板块退潮、市场风险、持仓超期、快速跳水和保守不成交原因。
- 17.1.11 模拟交易页面：已完成 `/simulation` 页面入口。
- 17.1.12 模拟交易页面内容：已完成账户概览、今日持仓、交易记录、买卖原因、资金曲线和风险指标。
- 17.1.13 账户概览字段：已完成初始资金、总资产、可用现金、持仓市值、仓位、当日盈亏、累计盈亏、累计收益率、最大回撤。
- 17.1.14 今日持仓表：已完成股票、板块、策略、数量、买入均价、当前价、市值、浮盈亏、止损/止盈、买入原因和状态。
- 17.1.15 今日交易记录表：已完成时间、股票、方向、价格、数量、金额、费用、交易后现金、交易后仓位和原因。
- 17.1.16 模拟交易定时任务：已完成 CLI loop 入口和脚本分发；生产部署可用外层 supervisor/systemd/tmux 承载长轮询。
- 17.1.17 模拟交易成功标准：开发已完成；真实目标日自动买入/卖出需 `2026-06-22` 当天继续验收。
- 17.1.18 设计原则：已完成保守成交规则，真实盘中数据仍需当天验证。
- 17.1.19 与 MVP 的关系：已完成开发顺序建议里的买入、卖出、持仓页面、交易记录页面、资金曲线和统计指标。

验证：

- `.venv/bin/pytest`：89 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- `bash -n scripts/run-simulation.sh`：通过。
- `.venv/bin/python -m backend.app.simulation.cli loop --help`：正常展示 `--trade-date`、`--interval-seconds`、`--max-iterations`。

### 18. PRD MVP 市场环境连板高度补口

- 新增 `market_daily.limit_up_height` 字段和迁移 `0007_market_limit_up_height`。
- 市场环境计算从真实 `limit_snapshot` 涨停池中计算连板高度：当前交易日涨停股票向前连续出现在涨停池的最大天数。
- 连板高度不少于 3 板时，市场评分按 PRD 增加 15 分。
- `GET /api/market/latest` 和 `GET /api/market/today` 返回 `limit_up_height`。
- 今日决策面板展示“连板高度”。

状态：已完成开发；真实数据库迁移和真实数据重算见本任务验证。

验证：

- `.venv/bin/pytest tests/test_market_environment.py tests/test_database_schema.py`：12 passed。
- `cd frontend && npm test -- --run`：1 passed。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-upgrade.sh`：已升级到 `0007_market_limit_up_height (head)`。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/generate-market-environment.sh --trade-date 2026-06-18`：真实库重算返回 `limit_up_height=4`、`market_score=70`、`market_status=中性`。
- 后续全量验证见本轮交接文档。

### 19. PRD MVP 强势板块和候选股票页面补口

- 强势板块评分从近 3 日累计改为真实近 5 日累计，并写入 `sector_daily.five_day_return`。
- `GET /api/sectors/top` 和 `GET /api/sectors/strong` 新增 `five_day_return`，同时保留 `three_day_return` 兼容旧前端或脚本。
- 强势板块页面展示“5日涨幅”，CSV 导出同步改为 5 日口径。
- Web 新增“候选股票池”页面区块，接入 `GET /api/candidates/latest`，展示股票、板块、板块排名、策略、评分、收盘价、成交额、入选理由和风险提示。
- 点击强势板块名称会筛选对应板块候选股票，并同步筛选今日交易计划。
- 候选股票池支持按当前板块导出 CSV。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_sector_ranking.py`：4 passed。
- `cd frontend && npm test -- --run`：1 passed。
- `.venv/bin/pytest`：90 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 真实库刷新：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5433/stock bash scripts/generate-sector-ranking.sh --trade-date 2026-06-18 --member-fetch-limit 80` 成功；`科技风格 five_day_return=14.00`。
- 浏览器运行态快验：`http://127.0.0.1:5173/` 展示 `5日涨幅` 和 `候选股票池`，刷新后可见 `13.56%`、`14.00%` 等 5 日口径数据，无 `数据异常`。
- 浏览器交互快验：点击强势板块 `科技风格` 后，候选股票池显示 `当前板块：科技风格`，交易计划筛选框同步为 `科技风格`。

### 20. Ubuntu 部署与数据拉取脚本

- 新增 `deploy_ubuntu.sh`：
  - 检查并按需安装 Ubuntu 系统依赖：Python venv/pip、Node/npm、Docker、Docker Compose plugin、curl。
  - 检查 Node.js major 版本；低于 20 时通过 NodeSource 安装 Node.js 22.x，避免 Vite 7 构建失败。
  - 创建或复用 `.venv`，依赖已存在时跳过；`FORCE_INSTALL=1` 可强制重装 Python/frontend 依赖。
  - 创建或保留 `.env`；显式环境变量优先于 `.env`。
  - 启动 PostgreSQL 并只执行 Alembic 迁移；新部署数据库保持“只有 schema、没有行情数据”。
  - `RESET_DB=1 bash deploy_ubuntu.sh` 可清空已有 PostgreSQL volume 后重建空库。
  - 支持 `STOCK_DEPLOY_DRY_RUN=1` 查看将执行的命令，不改文件、不启容器、不写数据库。
- 新增 `get_data.sh`：
  - `TRADE_DATE=YYYY-MM-DD bash get_data.sh` 跑真实盘后 workflow：采集行情、生成市场环境、强势板块、候选股票和交易计划。
  - 明确要求 `TUSHARE_TOKEN`，避免无 token 时误把 mock/空数据当完成。
  - workflow 后执行 `scripts/audit-market-data.sh --trade-date ...` 做覆盖审计。
  - 支持 `STOCK_GET_DATA_DRY_RUN=1` 查看命令，不拉数据、不写库。
- 优化 `start.sh`：
  - API 和前端默认监听 `0.0.0.0`，局域网可访问。
  - 健康检查仍走 `127.0.0.1`；PostgreSQL 仍只绑定本机端口，不对局域网暴露。
  - 自动探测 `PUBLIC_HOST` 并打印本机和 LAN URL；如探测不准，可手动 `PUBLIC_HOST=服务器IP bash start.sh`。
- 优化 `scripts/dev-web.sh`：支持 `WEB_HOST` / `WEB_PORT`。
- `Makefile` 新增 `make deploy-ubuntu` 和 `make get-data`。
- `.env.example` 同步部署变量。

状态：已完成。

验证：

- 新增红绿测试：`tests/test_deployment_scripts.py` 先失败于脚本缺失和 `start.sh` 非 LAN 监听，再实现通过。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：3 passed。
- `bash -n deploy_ubuntu.sh get_data.sh start.sh scripts/dev-web.sh`：通过。
- `STOCK_DEPLOY_DRY_RUN=1 FORCE_INSTALL=1 TUSHARE_TOKEN=token-for-dry-run bash deploy_ubuntu.sh`：输出安装、构建、启动 PostgreSQL、迁移命令，并明确不拉行情数据。
- `STOCK_GET_DATA_DRY_RUN=1 TRADE_DATE=2026-06-18 TUSHARE_TOKEN=token-for-dry-run bash get_data.sh`：输出 `run-after-close-workflow` 和 `audit-market-data` 命令，不写库。
- `.venv/bin/pytest`：93 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

## 下一步

下一次部署时优先在 Ubuntu 服务器执行 `bash deploy_ubuntu.sh`，确认空库迁移成功后再执行 `TRADE_DATE=YYYY-MM-DD bash get_data.sh` 拉取真实数据并生成交易计划。目标交易日当天继续用 `scripts/run-realtime-workflow.sh --provider auto --target-trade-date YYYY-MM-DD` 验证真实实时快照写入、跟踪和模拟。开始前必须先读 `AGENTS.md` 和本文件，并运行 `git status --short --branch`。

### 21. 强势板块独立详情页

- 主页不再把所有候选股票池堆在同一个长页面中。
- 点击强势板块名称会进入 `/sectors/<板块名>` 独立详情页。
- 板块详情页集中展示该板块排名、评分、今日 / 5 日涨幅、涨停 / 强势股数量。
- 板块详情页只展示该板块候选股票、入选理由、风险提示和该板块交易计划。
- 板块详情页保留候选 CSV 导出和“返回强势板块”操作。
- 浏览器前进 / 后退会同步页面路径，便于把单个板块页面发给别人直接查看。

状态：已完成。

验证：

- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- `.venv/bin/pytest`：93 passed，1 个 LibreSSL/urllib3 warning。
- `bash start.sh`：API 启动于 `0.0.0.0:8000`，前端启动于 `0.0.0.0:5173`，并打印 LAN URL。
- `curl http://127.0.0.1:5173/sectors/%E7%A7%91%E6%8A%80%E9%A3%8E%E6%A0%BC`：返回 `200 text/html`。

### 22. 部署 PostgreSQL 端口占用顺延

- `deploy_ubuntu.sh` 不再固定使用宿主机 `127.0.0.1:5432`。
- 部署时会从 `POSTGRES_BASE_PORT` 或现有 `POSTGRES_HOST_PORT` 开始探测，遇到占用自动顺延到下一个可用端口。
- 选中的 `POSTGRES_HOST_PORT` 和对应 `DATABASE_URL` 会写回 `.env`，后续 `get_data.sh` 和迁移命令使用同一个数据库端口。
- `start.sh` 会先读取 `.env`，如果部署已经写入 `POSTGRES_HOST_PORT`，启动应用时复用该端口。
- `.env.example` 明示 `POSTGRES_HOST_PORT=5432`，方便 Ubuntu 部署时按需改写。

状态：已完成。

验证：

- 新增回归测试：临时占住一个端口后 dry-run `deploy_ubuntu.sh`，确认输出顺延端口、`POSTGRES_HOST_PORT=<next>` 和新 `DATABASE_URL`。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：4 passed。
- `bash -n deploy_ubuntu.sh get_data.sh start.sh scripts/dev-web.sh`：通过。
- `STOCK_DEPLOY_DRY_RUN=1 FORCE_INSTALL=1 TUSHARE_TOKEN=token-for-dry-run POSTGRES_BASE_PORT=5432 bash deploy_ubuntu.sh`：当前本机 `5432` 被占用时选择 `5433`，并输出写回 `.env`、按 `5433` 启动 PostgreSQL 和迁移。
- `.venv/bin/pytest`：94 passed，1 个 LibreSSL/urllib3 warning。

### 23. 部署迁移数据库端口同步

- 修复 Ubuntu 部署中 PostgreSQL 容器已 ready，但 Alembic 仍连接旧 `127.0.0.1:5432` 导致密码错误的问题。
- `deploy_ubuntu.sh` 遇到显式或 `.env` 中的旧本地 `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:<旧端口>/stock` 时，不再保留旧值，而是按选中的端口重写。
- Docker Compose 启动 PostgreSQL 后，脚本会读取 `docker compose port postgres 5432` 的真实 published port，并用它再次同步 `POSTGRES_HOST_PORT` / `DATABASE_URL`。
- 只有非本地 stock 数据库 URL 才会作为外部数据库配置保留。

状态：已完成。

验证：

- 新增回归测试：即使环境变量里带旧本地 `DATABASE_URL=...5432...`，部署 dry-run 也会把迁移命令改为顺延后的实际端口。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：5 passed。
- `bash -n deploy_ubuntu.sh get_data.sh start.sh scripts/dev-web.sh`：通过。
- `STOCK_DEPLOY_DRY_RUN=1 FORCE_INSTALL=1 TUSHARE_TOKEN=token-for-dry-run POSTGRES_BASE_PORT=5432 DATABASE_URL='postgresql+psycopg://stock:stock@127.0.0.1:5432/stock' bash deploy_ubuntu.sh`：当前本机 `5432` 被占用时，迁移命令使用 `127.0.0.1:5433/stock`。

### 24. 部署默认避开 5432

- `deploy_ubuntu.sh` 默认 `POSTGRES_BASE_PORT=15432`，不再从系统 PostgreSQL 常用端口 `5432` 起步。
- 部署时不再沿用 `.env` 里残留的 `POSTGRES_HOST_PORT=5432`；除非本次命令显式传入 `POSTGRES_HOST_PORT=...`，否则都会从 `15432` 开始找可用端口。
- `.env.example` 默认 PostgreSQL 端口改为 `15432`，`DATABASE_URL` 同步为 `127.0.0.1:15432/stock`。
- 如果必须指定端口，可显式运行：`POSTGRES_HOST_PORT=16432 bash deploy_ubuntu.sh`。

状态：已完成。

验证：

- `STOCK_DEPLOY_DRY_RUN=1 FORCE_INSTALL=1 TUSHARE_TOKEN=token-for-dry-run bash deploy_ubuntu.sh`：输出 `selected PostgreSQL host port: 15432`，并以 `POSTGRES_HOST_PORT=15432 docker compose up -d postgres` 启动。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：7 passed。
- `bash -n deploy_ubuntu.sh get_data.sh start.sh scripts/dev-web.sh`：通过。

### 25. Ubuntu 启动脚本诊断与 API 非 reload 启动

- `scripts/dev-api.sh` 支持 `API_RELOAD=0`，用于 Ubuntu 启动时关闭 `uvicorn --reload`。
- `start.sh` 启动 API 时显式设置 `API_RELOAD=0`，避免部署环境下 reload 派生进程或文件监听导致健康检查长时间不通过。
- `start.sh` 每次启动前清空 `.logs/api.log` 和 `.logs/web.log`，避免旧日志混淆。
- API 或前端进程提前退出时，`start.sh` 会直接在终端打印对应日志最后 80 行。
- API 或前端健康检查超时时，`start.sh` 也会直接打印对应日志最后 80 行。

状态：已完成。

验证：

- `bash -n start.sh scripts/dev-api.sh deploy_ubuntu.sh get_data.sh scripts/dev-web.sh`：通过。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：7 passed。
- `.venv/bin/pytest`：97 passed，1 个 LibreSSL/urllib3 warning。
- 本地真实启动：`bash start.sh` 已走到 `API is ready` 和 `Frontend is ready`，随后手动 Ctrl-C 停止前端/API。

### 26. start.sh API 端口 bind 探测

- 修复 `start.sh` 在 Ubuntu 上误判 `8000` 可用，随后 uvicorn 报 `address already in use` 的问题。
- 端口检测不再依赖“能否连接 `127.0.0.1:<port>`”，改为用 Python socket 实际尝试 `bind(<listen_host>, <port>)`。
- API 端口检测使用 `API_LISTEN_HOST`，前端端口检测使用 `WEB_LISTEN_HOST`，PostgreSQL 端口检测使用 `DB_HOST`。
- `start.sh` 的 PostgreSQL 默认起始端口同步改为 `15432`。

状态：已完成。

验证：

- 本地占住 `0.0.0.0:8000` 后运行 `bash start.sh`，脚本选择 `API on 0.0.0.0:8001`，并走到 `API is ready`、`Frontend is ready`。
- `bash -n start.sh scripts/dev-api.sh deploy_ubuntu.sh get_data.sh scripts/dev-web.sh`：通过。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：7 passed。
- `.venv/bin/pytest`：97 passed，1 个 LibreSSL/urllib3 warning。

### 27. Ubuntu 前端 API 同源代理

- 修复 Ubuntu 上用 `127.0.0.1:5173` 打开页面时 `/api/sectors/top` 被 Vite dev server 直接返回 `404` 的问题。
- 修复用 `192.168.x.x:5173` 打开页面时，浏览器直连绝对 API 地址造成 `Failed to fetch`、CORS 或网络路径不一致的问题。
- `start.sh` 不再向浏览器注入 `VITE_API_BASE_URL=http://<LAN_IP>:<API_PORT>`；前端默认请求同源 `/api/...`。
- `start.sh` 改为向 Vite 进程注入 `VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:<API_PORT>`，由 Vite 在 Ubuntu 本机代理到真实 API。
- 启动提示改为打印 `API proxy: /api -> ...`，并提醒另一台局域网电脑无法打开时在 Ubuntu 上放通 Web 端口：`sudo ufw allow <WEB_PORT>/tcp`。
- 这意味着局域网访问只需要浏览器能连上前端端口；API 端口不再需要直接暴露给局域网浏览器。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_deployment_scripts.py`：8 passed。
- `bash -n start.sh scripts/dev-api.sh deploy_ubuntu.sh get_data.sh scripts/dev-web.sh`：通过。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- `.venv/bin/pytest`：98 passed，1 个 LibreSSL/urllib3 warning。
- 真实启动验证：本地占住 `0.0.0.0:8000` 后运行 `bash start.sh`，脚本选择 API `8001`、前端 `5173`；`curl http://127.0.0.1:5173/api/health` 通过 Vite 代理返回 API 健康检查 JSON。

### 28. 清理 `.env` 残留前端 API 端口污染

- 修复 `.env` 中残留 `VITE_API_BASE_URL=http://127.0.0.1:8000` 时，Vite 仍把旧地址暴露给浏览器，导致局域网电脑访问页面后请求自己本机 `127.0.0.1:8000` 并报 `Failed to fetch` 的问题。
- `start.sh` 启动前端时显式传入 `VITE_API_BASE_URL=""`，即使 `.env` 或外部 shell 里有旧值，也不会进入浏览器端 bundle。
- `frontend/vite.config.ts` 不再把 `VITE_API_BASE_URL` 作为 dev proxy fallback，代理目标只使用 `VITE_DEV_API_PROXY_TARGET` 或默认 `127.0.0.1:8000`。
- `.env.example` 删除 `VITE_API_BASE_URL`，避免后续部署继续生成固定 8000 的旧配置。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_deployment_scripts.py`：8 passed。
- `bash -n start.sh scripts/dev-api.sh deploy_ubuntu.sh get_data.sh scripts/dev-web.sh`：通过。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- `.venv/bin/pytest`：98 passed，1 个 LibreSSL/urllib3 warning。
- 真实启动验证：显式带入 `VITE_API_BASE_URL=http://127.0.0.1:8000` 且占住 `8000` 后运行 `bash start.sh`，脚本选择 API `8001`；`curl http://127.0.0.1:5173/src/api/dashboard.ts` 的转换结果不含 `127.0.0.1:8000`，`curl http://127.0.0.1:5173/api/health` 通过代理返回 API 健康检查 JSON。

### 29. start.sh 运行端口写回 `.env`

- `start.sh` 会在 PostgreSQL、API、Web 都启动并通过健康检查后，把运行事实写回 `.env`。
- 写回字段包括：`POSTGRES_HOST_PORT`、`DATABASE_URL`、`API_HOST`、`API_PORT`、`WEB_HOST`、`WEB_PORT`。
- `start.sh` 会删除 `.env` 中的 `VITE_API_BASE_URL`，避免浏览器端继续使用固定 `127.0.0.1:8000`。
- `API_BASE_PORT` / `WEB_BASE_PORT` 现在会分别优先继承 `.env` 的 `API_PORT` / `WEB_PORT`，所以下一次启动会从上一次实际端口开始探测。
- `deploy_ubuntu.sh` 和 `start.sh` 的端口事实源统一为 `.env`，脚本自动顺延后的端口不会再和 `.env` 里的固定旧端口长期不一致。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_deployment_scripts.py`：8 passed。
- `bash -n start.sh scripts/dev-api.sh deploy_ubuntu.sh get_data.sh scripts/dev-web.sh`：通过。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- `.venv/bin/pytest`：98 passed，1 个 LibreSSL/urllib3 warning。
- 真实启动验证：占住 `127.0.0.1:8000` 且 `.env` 初始写 `API_PORT=8000` 后运行 `bash start.sh`，脚本选择 `API_PORT=8001`；API 和前端都 ready 后，把 `API_PORT=8001`、实际 `WEB_PORT`、`POSTGRES_HOST_PORT`、`DATABASE_URL` 写回 `.env`，同时删除 `VITE_API_BASE_URL`。

### 30. 新部署空库 latest 接口空态

- 修复新部署空库时首页请求 `/api/trade-plans/latest` 返回 `404`，导致前端显示红色 `failed: 404` 的问题。
- `/api/market/latest` 无数据时返回 200 空市场状态和“暂无市场建议”。
- `/api/sectors/top`、`/api/candidates/latest`、`/api/trade-plans/latest` 无数据时返回 200 和空 `items`。
- 按日期查询、详情查询等明确指定资源的接口仍保留 404，避免把真正不存在的资源伪装成成功。
- 前端增加空态测试，确认空库首页不会显示 `failed: 404` 或“数据异常”。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_market_environment.py tests/test_sector_ranking.py tests/test_candidate_screening.py tests/test_trade_plan_generation.py`：33 passed。
- `cd frontend && npm test -- --run`：2 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- `.venv/bin/pytest`：102 passed，1 个 LibreSSL/urllib3 warning。

### 31. get_data.sh 权限与日期口径

- 修复 Ubuntu 上执行 `bash get_data.sh` 时，`scripts/run-after-close-workflow.sh` 没有执行位导致 `Permission denied` 的问题。
- `get_data.sh` 调用 workflow 和覆盖审计时统一使用 `bash scripts/...`，不依赖子脚本 chmod 状态。
- `TRADE_DATE` 未显式提供时，脚本使用中国时区当天日期；也可以用 `TRADE_DATE=YYYY-MM-DD bash get_data.sh` 或 `bash get_data.sh YYYYMMDD` 指定目标交易日。
- `get_data.sh` 是围绕目标交易日运行盘后工作流；为计算市场环境、板块、候选和交易计划，会拉取该目标日所需的交易日历、指数历史窗口、全市场日线、基础信息、涨跌停和板块数据。
- `get_data.sh --start YYYYMMDD --end YYYYMMDD` 会按自然日区间逐日执行同一套盘后 workflow 和覆盖审计，适合一次回补多天数据。

状态：已完成。

验证：

- `STOCK_GET_DATA_DRY_RUN=1 TRADE_DATE=2026-06-18 TUSHARE_TOKEN=token-for-dry-run bash get_data.sh`：输出 `bash scripts/run-after-close-workflow.sh ...` 和 `bash scripts/audit-market-data.sh ...`。
- `bash -n get_data.sh scripts/run-after-close-workflow.sh scripts/audit-market-data.sh`：通过。
- `.venv/bin/pytest tests/test_deployment_scripts.py`：8 passed。

### 32. get_data.sh 盘后 workflow 采集摘要字段修复

- 修复 `TRADE_DATE=2026-06-18 bash get_data.sh` 在盘后 workflow 阶段报错：`AttributeError: 'IngestSummary' object has no attribute 'ingest_run_id'`。
- `backend.app.data.ingest.ingest_market_snapshot` 写入 `DataIngestRun` 后会 `flush` 获取真实主键，并通过 `IngestSummary.ingest_run_id` 返回给 `run_after_close_workflow`。
- 回归测试覆盖真实采集摘要返回 run id，避免测试 fake 再次遮住字段漂移。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_market_data_ingest.py tests/test_after_close_workflow.py tests/test_after_close_workflow_cli.py`：5 passed，1 个 LibreSSL/urllib3 warning。
- `.venv/bin/pytest`：102 passed，1 个 LibreSSL/urllib3 warning。

### 33. 模拟交易与复盘交易日历修复

- 修复 `/simulation` 页面中“模拟日”和“复盘日”可能显示闭市日期的问题。
- `run_simulation`、`run_simulation_workflow` 和 `run_trading_loop` 会先查询 `trading_calendar`；如果请求日期明确为闭市日，则顺延到之后最近的开市日。
- `load_latest_simulation` 只从交易日历标记为开市的资金曲线中取最新日期；资金曲线展示也过滤闭市日记录。
- `generate_trade_reviews` 在请求闭市日时顺延到下一开市日生成复盘；`load_latest_trade_reviews` 只返回开市日复盘，按日期查询闭市日复盘返回空态。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_simulation_trading.py tests/test_trade_plan_generation.py`：37 passed。
- `.venv/bin/pytest`：107 passed，1 个 LibreSSL/urllib3 warning。

### 34. get_data.sh 区间批量拉取

- 新增 `--start DATE --end DATE` 参数，日期支持 `YYYYMMDD` 和 `YYYY-MM-DD` 两种格式。
- 区间模式会先执行一次数据库迁移，然后按日期顺序逐日执行盘后 workflow 和覆盖审计。
- 保持原有单日用法兼容：`TRADE_DATE=YYYY-MM-DD bash get_data.sh`、`bash get_data.sh YYYY-MM-DD` 和 `bash get_data.sh YYYYMMDD` 均可继续使用。
- 支持通过命令行覆盖 `--provider`、`--member-fetch-limit`、`--candidate-limit` 和 `--trade-plan-limit`。

状态：已完成。

验证：

- `bash -n get_data.sh`：通过。
- `STOCK_GET_DATA_DRY_RUN=1 TUSHARE_TOKEN=dummy bash get_data.sh --start 20260615 --end 20260618`：输出 2026-06-15 至 2026-06-18 每天的 `run-after-close-workflow` 和 `audit-market-data` 命令，不写库。
- `STOCK_GET_DATA_DRY_RUN=1 TUSHARE_TOKEN=dummy bash get_data.sh 20260618`：输出单日 workflow 和覆盖审计命令，不写库。

### 35. 强势板块近 5 日排名轨迹

- `GET /api/sectors/top` 和 `GET /api/sectors/strong?date=YYYY-MM-DD` 每个板块项新增 `rank_history`。
- `rank_history` 按当前查询日期向前取最近 5 个已生成板块排名交易日，返回每个日期该板块在当前排名宇宙中的名次；该日缺少该板块排名数据时 `rank_no=null`。
- 强势板块表在“板块”和“今日涨幅”之间新增“近5日排名”列，用日期和 `#名次` 标签展示，例如 `06-18 #1`、`06-17 #2`。
- 强势板块 CSV 导出同步增加“近5日排名”字段。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_sector_ranking.py`：5 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：2 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 临时当前代码 API `http://127.0.0.1:8010/api/sectors/top` 返回真实 PostgreSQL 最新 `trade_date=2026-06-18`，板块项包含 `rank_history`，如 `非金属材料Ⅲ` 返回 `2026-06-18 #1` 和 `2026-06-16 -`。

### 36. 模拟交易 latest 持仓现价按最新日线刷新

- 修复 `GET /api/simulation/latest` 直接读取旧 `simulation_position.current_price`，导致收盘后页面仍显示盘中实时价的问题。
- `load_latest_simulation` 在返回前会按 latest equity 日期调用 `_mark_to_market` 和 `_save_equity`，用同日 `stock_daily.close` 刷新持仓现价、市值、浮盈亏、账户市值和总资产。
- 页面无需额外改动；模拟交易持仓表继续展示 API 返回的 `current_price`。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_simulation_trading.py`：18 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：2 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。
- 本轮环境因沙箱限制无法直连本地 PostgreSQL `127.0.0.1:15432`，真实库中的 `300308=1382.33`、`603986=156.11` 需在正常运行环境重启 API 后复验；新增回归测试已覆盖旧持仓价 `1358.24` 被同日 `stock_daily.close=1382.33` 刷新。

### 37. 首页盘中自动触发实时行情回补

- 修复首页刷新/打开时只读取已有模拟交易快照、不主动触发实时行情的问题。
- 根因：盘中实时价回补原本只在用户点击“跟踪触发”/“跟踪并模拟交易”时调用 `POST /api/trade-plans/track-realtime`；`GET /api/simulation/latest` 只会基于已入库行情重估，不负责主动拉取盘中实时行情。
- `loadDashboard` 在交易计划 `target_trade_date` 等于中国时区今天时，会先调用 `trackRealtimeTradePlans` 写入/更新实时跟踪结果，再重新读取最新交易计划和模拟交易 summary。
- 该逻辑保证盘中打开或刷新首页时，模拟交易现价会使用刚回补的实时价；收盘后仍由任务 36 的 latest 日线重估逻辑兜底展示收盘价。
- 当前实现是“页面打开/刷新时更新”，不是分钟级自动轮询；若需要持续自动刷新，需要另开轮询/节流任务。

状态：已完成。

验证：

- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 38. 强势板块近 5 日排名拆成 5 个日期列

- 修复强势板块表把最近 5 个交易日排名挤在单个“近5日排名”单元格里的可读性问题。
- 页面保留分组表头“近5日排名”，并在其下按最近 5 个交易日动态生成 5 个日期列，例如 `06-18`、`06-17`、`06-16`、`06-15`、`06-12`。
- 每个单元格显示该板块在对应交易日的排名；对应交易日缺少该板块排名数据时显示 `-`。
- 后端 `rank_history` API 和 CSV 导出字段保持兼容。

状态：已完成。

验证：

- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 39. 强势板块近 5 日排名过滤休市日

- 修复强势板块近 5 日排名把休市日 `06-19`、`06-20`、`06-21` 当成排名日期的问题。
- 根因：`rank_history` 原本只按 `sector_daily.trade_date` 取最近 5 个日期，没有与 TuShare 交易日历 `trading_calendar.is_open=true` 做交集；如果休市日存在脏 `sector_daily` 记录，API 会直接返回。
- `_rank_history_by_sector` 在交易日历存在时严格 join `trading_calendar` 并只保留开市日；仅在完全没有交易日历数据的旧/空环境中回退到旧逻辑。
- 新增回归测试覆盖：即使 `sector_daily` 中存在休市日排名，`GET /api/sectors/top` 的 `rank_history` 也只能返回开市日。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_sector_ranking.py::test_sector_rank_history_ignores_closed_calendar_dates`：先失败，确认复现休市日混入；修复后通过。
- `.venv/bin/pytest tests/test_sector_ranking.py`：6 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 40. 今日决策面板一周视图与盘中跟踪板块列

- 新增 `GET /api/market/history?limit=5`，按 `trade_date desc` 返回最近 5 条市场环境记录；`limit` 限制为 1 到 30。
- 今日决策面板从单日指标卡改为最近 5 个交易日表格，一日一行，最新交易日排第一行；表格设置最大高度，数据超过可视区域时使用滚动条。
- 今日决策面板下方解释框只展示第一行，也就是最新交易日的 `suggestion`。
- 盘中跟踪表在“股票”和“当前价”之间新增“板块”列，直接展示交易计划的 `sector_name`。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_market_environment.py`：7 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 41. 模拟持仓持续显示与交易记录历史滚动

- 修复模拟交易 latest 只把 `持仓中`、`部分止盈` 视为未清仓持仓，导致 `待卖出` 这类还没真正卖掉的持仓不显示的问题。
- `ACTIVE_POSITION_STATUSES` 增加 `待卖出`；只要不是 `已清仓`，仍应在模拟持仓表持续显示。
- `GET /api/simulation/latest` 的交易记录不再只返回 `as_of_date` 当天记录，而是返回账户全部历史交易，按交易日/交易时间倒序排列，方便当天记录在上、旧记录向下滚动查看。
- 前端模拟持仓表和模拟交易记录表增加最大高度，超出后用表格滚动；交易记录空态改为“暂无模拟交易记录”。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_simulation_trading.py`：20 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 42. 决策/板块/盘中跟踪数据口径修复

- 修复今日决策面板最近 5 日历史把休市日混入的问题：`GET /api/market/history` 在交易日历存在时只返回 `trading_calendar.is_open=true` 的开市日。
- 修复强势板块近 5 日排名只保存 Top10 导致非 Top10 历史名次显示 `-` 的问题：生成板块排名时持久化全量排名，接口仍只展示当前交易日 Top10。
- 强势板块 `rank_history` 现在可显示 Top10 之外的真实名次，例如当前 Top10 板块在前一交易日排名第 11，会显示 `11`，而不是 `-`。
- 修复盘中跟踪表当前价/涨跌幅容易显示 `-` 的问题：交易计划 API 展示行情时优先使用目标交易日实时/日线快照；目标日暂无行情时，使用目标日前最近一条 `stock_daily` 作为展示兜底，不参与触发判断。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_market_environment.py tests/test_sector_ranking.py tests/test_trade_plan_generation.py`：37 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 43. 模拟交易记录防级联删除与孤儿资金曲线防护

- 修复模拟交易持仓和交易记录在更新/重生成交易计划后消失的问题。
- 根因：`simulation_position.trade_plan_id` 和 `simulation_trade.trade_plan_id` 原本对 `trade_plan.id` 使用 `ON DELETE CASCADE`；交易计划重生成时 `_replace_trade_plans` 整批删除旧计划，数据库随即级联删除模拟持仓和模拟交易记录，但 `simulation_account` / `simulation_equity` 仍保留，导致页面出现“无持仓、无记录、现金只剩买入后余额”的不一致状态。
- 新增迁移 `0008_preserve_simulation_records`，将模拟持仓/交易到交易计划的外键改为非级联删除；真实 PostgreSQL 已升级到 `0008_preserve_simulation_records (head)`。
- `_replace_trade_plans` 改为按 `plan_date + target_trade_date + stock_code + strategy_type` 更新/插入，不再整批删除已有交易计划；已有模拟记录关联的计划会保留执行状态和历史关联。
- `load_latest_simulation` 遇到“只有账户/资金曲线、没有任何持仓和交易记录”的孤儿模拟状态时返回空态，不再把这类脏数据重算为 -76% 之类的虚假亏损。
- `run_simulation` 在孤儿账户状态下会先重置账户到初始资金并清理不可信资金曲线，再执行新的模拟，避免后续交易沿用错误现金余额。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_simulation_trading.py tests/test_trade_plan_generation.py tests/test_database_schema.py tests/test_realtime_quote_workflow.py`：57 passed，1 个 LibreSSL/urllib3 warning。
- `scripts/db-current.sh`：`0008_preserve_simulation_records (head)`。
- 真实 PostgreSQL 外键检查：`fk_simulation_position_trade_plan_id_trade_plan` 和 `fk_simulation_trade_trade_plan_id_trade_plan` 的 `confdeltype='a'`，不再级联删除。
- 真实 PostgreSQL `load_latest_simulation` 对当前孤儿状态返回 `None`，页面不应再展示虚假 -76.88% 当日亏损。
- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 44. 强势板块 511 板块宇宙与历史全量排名回填

- 修复强势板块近 5 日排名仍显示 `-` 的问题。
- 根因不是前端渲染，而是历史 `sector_daily` 仍是旧数据：`2026-06-15` 到 `2026-06-22` 每天只有 Top10 行，Top10 之外的板块历史名次在数据库中不存在，所以只能显示 `-`。
- 二次根因：直接持久化 TuShare/DC 原始 `1021` 行会把概念、地域、东财一级/二级/三级行业和风格/策略伪板块混在一起，导致历史名次出现 `800+`，超出用户确认的约 `511` 个板块宇宙。
- `TushareDCSectorDataProvider` 现在只保留 `概念板块` 和 `东财一级行业`，并排除 `东方财富热股`、`题材股`、`趋势股`、`反转股`、`金融地产风格`、`昨日首板/炸板/高换手/高振幅` 等 14 个风格/策略伪板块；`2026-06-22` 实测从原始 `1021` 行过滤为 `511` 行。
- 回填时又发现 TuShare/DC 原始板块可能出现不同 `sector_code` 但同 `sector_name`，会触发 `sector_daily(trade_date, sector_name)` 唯一约束冲突；已在排名排序后按 `sector_name` 去重，保留排序最高的一条并重新编号。
- 已用当前代码回填最近 5 个开市日 `2026-06-15`、`2026-06-16`、`2026-06-17`、`2026-06-18`、`2026-06-22` 的板块排名，每个交易日 `sector_daily` 均为 `511` 行，`max(rank_no)=511`。
- `GET /api/sectors/top` 当前返回的 `rank_history` 已包含 Top10 之外但不超过 511 的名次，例如 `培育钻石`：`06-22=1`、`06-18=27`、`06-17=98`、`06-16=141`、`06-15=31`。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_sector_provider.py tests/test_sector_ranking.py`：10 passed，1 个 LibreSSL/urllib3 warning。
- TuShare 真实快验：`dc_index(20260622)` 原始 `1021` 行，过滤后 `511` 行。
- 真实 PostgreSQL 查询：最近 5 个开市日 `sector_daily count=511, max_rank=511`，且 `rank_no > 511` 的记录为 `[]`。
- `curl http://127.0.0.1:5173/api/sectors/top`：`rank_history` 不再对已回填交易日返回 `null`，且历史名次不再出现 `800+`。

### 45. 数据拉取日志与数据库健康监测

- 新增 `data_job_run` / `data_job_step`，记录夜间数据拉取的整体任务和逐步骤日志。
- `run-after-close-workflow` 现在会记录：拉取行情快照、写入行情数据库、生成市场环境、生成强势板块、生成候选股票、生成交易计划、覆盖审计。
- 每个步骤记录开始时间、结束时间、状态、行数、摘要和错误信息；任一步失败会把任务标记为 `failed` 并保留报错。
- 新增 `GET /api/system/data-runs/latest`，返回最近任务日志和步骤明细。
- 新增 `GET /api/system/database-health`，按最新交易日检查交易日历、股票基础信息、个股日线、指数日线、涨跌停池、市场环境、强势板块、候选股票、交易计划和夜间任务日志。
- 数据库健康检查会明确 `ok` / `warning` / `error`，并在缺失项里给出补数据命令，如 `TRADE_DATE=2026-06-22 bash get_data.sh`。
- 前端页面底部新增“数据拉取与数据库健康”区块，展示最近一次拉取日志、逐步骤明细、数据库健康检查和历史拉取任务。

状态：已完成。

验证：

- `.venv/bin/pytest`：124 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过，仍有 VueUse pure annotation 和 chunk size warning。
- `bash scripts/db-upgrade.sh`：已升级到 `0009_data_job_monitoring (head)`。
- 真实 API 快验：`GET /api/system/data-runs/latest` 返回 200；当前真实库暂无新结构化任务日志，`items=0`。
- 真实 API 快验：`GET /api/system/database-health?date=2026-06-22` 返回 200；任务 46 修复后 `个股日线 status=ok`，小比例无日线股票按停牌/当日无交易等合理缺口处理。

### 46. 数据库健康监测个股日线合理缺口口径修复

- 修复数据库健康监测把 `stock_basic` 全量股票都当成个股日线必须覆盖分母的问题。
- 个股日线健康项现在只把系统需要的可交易股票纳入覆盖检查：`status=active`、非 ST、名称不含 ST、名称不含退市/退市风险标记。
- ST、退市/退市风险、非 active 股票不需要日线覆盖；全市场规模下少量未出日线的股票按停牌/当日无交易等合理缺口处理，并在页面说明里明示排除数量。
- 小样本测试仍严格：非全市场的小数据集不使用停牌容忍阈值，避免测试或局部数据缺行被误判为 ok。
- 覆盖审计的任务状态也同步使用同一口径，避免页面健康项显示 ok、夜间任务却因为合理缺口显示 warning。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_system_monitoring.py tests/test_after_close_workflow.py`：4 passed，1 个 LibreSSL/urllib3 warning。
- 真实 API 快验：`GET /api/system/database-health?date=2026-06-22` 返回 200；`个股日线 status=ok`，`actual=5287 / 5299`，说明 `12` 只未出日线按停牌/当日无交易等合理缺口处理，并已排除 ST、退市/退市风险等系统不需要股票 `230` 只。

### 47. 数据健康表取消内部滚动条

- 修复数据拉取与数据库健康区中“数据库健康检查”表格因 `max-height=360` 产生内部纵向滚动条的问题。
- 数据库健康检查项数量有限，为方便一次性阅读，表格现在直接撑开全部显示。
- 前端测试增加断言：包含“个股日线”的数据库健康表不应再带 `maxHeight` 属性，避免后续回归。

状态：已完成。

验证：

- `cd frontend && npm test -- --run`：3 passed。
- `cd frontend && npm run build`：通过；仍有 VueUse pure annotation 和 chunk size warning。

### 48. get_data.sh 区间模式过滤非交易日

- 修复 `get_data.sh --start/--end` 原本按自然日逐天运行 workflow 的问题。
- 根因：脚本旧的 `print_date_range` 使用 `timedelta(days=1)` 输出自然日列表，导致 `2026-06-19`、`2026-06-20`、`2026-06-21` 这类休市日也会执行 after-close workflow 和覆盖审计。
- 新逻辑：区间模式先用 TuShare `trade_cal` 把 `--start/--end` 转换为开市日列表，只对 `is_open=1` 的日期执行 workflow。
- 单日模式也走同一交易日历判断；如果指定日期不是开市日，会输出跳过提示，不再生成风险市场环境、空板块和空交易计划。
- dry-run/测试可通过 `STOCK_GET_DATA_OPEN_DATES` 模拟交易日历；真实运行仍使用 TuShare 交易日历。

状态：已完成。

验证：

- `.venv/bin/pytest tests/test_deployment_scripts.py`：10 passed。
- `.venv/bin/pytest`：127 passed，1 个 LibreSSL/urllib3 warning。
- `bash -n get_data.sh deploy_ubuntu.sh start.sh scripts/run-after-close-workflow.sh scripts/audit-market-data.sh`：通过。
- dry-run 验证：`STOCK_GET_DATA_DRY_RUN=1 TUSHARE_TOKEN=token-for-dry-run STOCK_GET_DATA_OPEN_DATES='2026-06-18 2026-06-22' START_DATE=20260618 END_DATE=20260622 bash get_data.sh` 只输出 `2026-06-18` 和 `2026-06-22` 的 workflow/audit 命令，没有 `2026-06-19`、`2026-06-20`、`2026-06-21`。
- 单日闭市 dry-run 验证：`TRADE_DATE=2026-06-21` 只输出 `2026-06-21 is not an open trading date; skipping workflow`，不执行 workflow/audit。
- 真实 PostgreSQL 交易日历查询确认：`2026-06-18=True`、`2026-06-19=False`、`2026-06-20=False`、`2026-06-21=False`、`2026-06-22=True`。
