# Handoff

## 当前状态

- 日期：2026-06-21
- 仓库路径：`/Users/wuxiancai/Documents/stock`
- 当前系统是全新的 A 股短线量化辅助决策系统。
- 旧 `stock` 项目已被废弃，不继承旧代码、旧部署方式、旧验收结论或旧业务假设。
- 当前已完成任务 1「项目骨架与配置」、任务 2「数据库模型与迁移」、任务 3「数据采集与交易日历」、任务 4「市场环境评分」、任务 5「强势板块排序」、任务 6「候选股票筛选」、任务 7「交易计划生成」、任务 8「P0 Web 页面」、任务 9「盘中跟踪」、任务 10「复盘统计」、任务 11「模拟交易」、任务 12「模拟交易盘中实盘化基础链路」和任务 13 第一阶段「真实目标交易日日线回补入口」。
- TuShare token 已脱敏保存在本机 `.env` 并通过 `TUSHARE_TOKEN` 读取；`.env` 不提交到 git。
- 已在本机目录补齐一键启动入口：`start.sh` / `make start`。

## 已完成

- 已保留 MVP 需求文档：`PRD_MVP.md`。
- 已建立项目协作规则：`AGENTS.md`。
- 已建立核心文档：
  - `docs/PROJECT_CONTEXT.md`
  - `docs/TRADING_RULES.md`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `docs/TASKS.md`
  - `docs/HANDOFF.md`
- 已创建 FastAPI 后端骨架。
- 已创建 Vue 3 + Element Plus 前端骨架。
- 已创建 PostgreSQL compose 配置和 `.env.example`。
- 已创建健康检查接口：`GET /api/health`。
- 已创建本地启动脚本：
  - `scripts/dev-api.sh`
  - `scripts/dev-web.sh`
- 已新增一键启动脚本：
  - `start.sh`
  - `scripts/check-dev-environment.sh`
  - `make start`
  - `make check-dev-environment`
- `start.sh` 会自动检测 PostgreSQL、API、前端宿主机端口占用，并顺延到下一个可用端口；PostgreSQL 容器内部端口保持 `5432`。
- 已创建基础测试：
  - `tests/test_health.py`
  - `frontend/src/App.test.ts`
- 已创建 SQLAlchemy 业务模型和 Alembic 迁移：
  - `backend/app/db/models.py`
  - `migrations/versions/0001_core_mvp_tables.py`
- 已创建数据库命令：
  - `scripts/db-upgrade.sh`
  - `scripts/db-current.sh`
- 已在真实 PostgreSQL 容器中初始化核心业务表：
  - `market_daily`
  - `sector_daily`
  - `trade_plan`
  - `trade_review`
  - `alembic_version`
- 已新增原始行情表并迁移到 `0002_market_data_tables (head)`：
  - `trading_calendar`
  - `stock_basic`
  - `index_daily`
  - `stock_daily`
  - `limit_snapshot`
  - `data_ingest_run`
- 已新增真实数据采集命令：
  - `scripts/ingest-market-data.sh`
  - `make ingest-market-data`
- 已新增数据覆盖审计命令：
  - `scripts/audit-market-data.sh`
  - `make audit-market-data`
- 已用 AkShare/Sina 日线和 AkShare/Eastmoney 涨跌停池写入真实 PostgreSQL。
- 已新增 provider 选择：
  - `--provider auto`
  - `--provider akshare`
  - `--provider tushare`
- 缺少 `TUSHARE_TOKEN` 时，`--provider tushare` 会明确报错，不会静默伪装为 TuShare 数据。
- 已完成 TuShare 真实拉取映射：
  - 交易日历：`trade_cal`
  - 个股基础信息：`stock_basic`
  - 指数日线：`index_daily`
  - 个股日线：`daily`
  - 涨跌停明细：`limit_list_d`
- 已新增全市场初始化参数：
  - `scripts/ingest-market-data.sh --provider tushare --trade-date YYYY-MM-DD --all-stocks`
- 已新增市场环境评分服务：
  - `backend/app/market/service.py`
- 已新增市场环境生成命令：
  - `scripts/generate-market-environment.sh --trade-date YYYY-MM-DD`
  - `make generate-market-environment`
- 已新增最新市场环境 API：
  - `GET /api/market/latest`
- TuShare 采集已为三大指数写入近 45 个自然日历史日线，用于计算 MA20。
- 已修复真实 PostgreSQL 下重复采集多日交易日历时的幂等写入顺序问题。
- 已新增强势板块评分服务：
  - `backend/app/sector/service.py`
- 已新增 TuShare 东方财富板块 provider：
  - `backend/app/sector/providers.py`
- 已新增强势板块生成命令：
  - `scripts/generate-sector-ranking.sh --trade-date YYYY-MM-DD`
  - `make generate-sector-ranking`
- 已新增强势板块 API：
  - `GET /api/sectors/top`
- 强势板块真实数据路径使用 TuShare `dc_index`、`dc_member` 和本地 `limit_snapshot`。
- 已新增候选股票表和迁移：
  - `candidate_stock`
  - `migrations/versions/0003_candidate_stock_table.py`
- 已新增候选筛选服务：
  - `backend/app/candidate/service.py`
- 已新增 TuShare 东方财富板块成分 provider：
  - `backend/app/candidate/providers.py`
- 已新增候选生成命令：
  - `scripts/generate-candidates.sh --trade-date YYYY-MM-DD`
  - `make generate-candidates`
- 已新增候选查询 API：
  - `GET /api/candidates/latest`
- 已新增交易计划生成服务：
  - `backend/app/trade/service.py`
- 已新增交易计划生成命令：
  - `scripts/generate-trade-plans.sh --plan-date YYYY-MM-DD`
  - `make generate-trade-plans`
- 已新增交易计划查询 API：
  - `GET /api/trade-plans/latest`
- 交易计划已从 `candidate_stock`、`market_daily`、`stock_daily` 和 `trading_calendar` 生成次日条件单计划。
- 交易计划已实现市场状态仓位限制：强势最多 3 只，中性最多 2 只，弱势最多 1 只，风险不生成新计划。
- 交易计划已实现止损价硬约束：止损价无效或高于计划买入参考价时不入库。
- 已完成 P0 Web 页面：
  - 今日决策面板接入 `GET /api/market/latest`。
  - 强势板块页面接入 `GET /api/sectors/top`，支持排序、筛选和 CSV 导出。
  - 今日交易计划页面接入 `GET /api/trade-plans/latest`，支持排序、筛选和 CSV 导出。
  - 交易复盘页面保留真实空态，等待任务 10 接入 `trade_review`。
- 已完成任务 9 盘中跟踪：
  - `trade_plan` 新增 `trigger_price`、`trigger_time`、`tracking_note`。
  - 新增迁移 `0004_trade_plan_tracking_fields`。
  - 新增 `scripts/track-trade-plans.sh` 和 `make track-trade-plans`。
  - 新增 `POST /api/trade-plans/track` 和 `PATCH /api/trade-plans/{plan_id}/status`。
  - 今日交易计划页面支持跟踪触发、收盘确认、手动标记触发/取消，展示触发价和跟踪备注。
- 已完成任务 10 复盘统计：
  - 新增 `generate_trade_reviews` 和 `load_latest_trade_reviews`。
  - 新增 `scripts/generate-trade-reviews.sh` 和 `make generate-trade-reviews`。
  - 新增 `POST /api/trade-reviews/generate` 和 `GET /api/trade-reviews/latest`。
  - 交易复盘页面接入真实复盘 API，展示复盘汇总、策略统计和复盘明细。
  - 缺少目标交易日日线时不伪造收益，复盘记录保留明确原因和备注。
- 已完成任务 11 模拟交易：
  - 新增 `simulation_account`、`simulation_position`、`simulation_trade`、`simulation_equity` 四张表和迁移 `0005_simulation_trading_tables`。
  - 新增 `backend/app/simulation/service.py` 和 `backend/app/simulation/cli.py`，默认模拟账户初始资金为 `1000000`。
  - 新增 `scripts/run-simulation.sh`、`make run-simulation`。
  - 新增 `POST /api/simulation/run` 和 `GET /api/simulation/latest`。
  - 模拟买入只执行计划内且状态为 `已触发` 的股票；涨停、高开过多、低开跌破止损、无止损或无触发价均不买入。
  - 模拟卖出优先处理止损，跌停时不强行卖出。
  - 已计入佣金、印花税、过户费，并保留每笔交易原因。
  - Web 新增“模拟交易”页面，展示账户、持仓、交易记录、资金曲线和回撤。
- 已完成任务 12 模拟交易盘中实盘化基础链路：
  - 新增 `run_simulation_workflow`，先执行 `track_trade_plans`，再执行 `run_simulation`。
  - 新增 `POST /api/simulation/run-workflow`。
  - `backend.app.simulation.cli` 新增 `run-workflow` 子命令。
  - `scripts/run-simulation.sh` 保持旧的 `--trade-date` 用法，同时支持 `run`、`run-workflow`、`latest` 子命令。
  - Web 模拟交易按钮改为“跟踪并模拟交易”，调用连续 workflow，并刷新交易计划状态和模拟结果。
- 已完成任务 13 第一阶段真实目标交易日日线回补入口：
  - 新增 `backend/app/data/target_daily.py`，按目标交易日交易计划查询缺失 `stock_daily`。
  - 新增 `backend.app.data.cli backfill-target-daily` 子命令。
  - 新增 `scripts/backfill-target-daily.sh` 和 `make backfill-target-daily`。
  - 回补结果输出 `planned_stock_count`、`existing_stock_count`、`requested_stock_count`、`fetched_stock_daily_rows`、`missing_stock_codes` 和 `target_is_open`。
  - `track_trade_plans` 在目标日明确非开市且无日线时写入闭市备注，不伪造成交。

## 未完成
- 全市场 `2026-06-18` 覆盖审计仍有 `missing_stock_daily_rows=22`，首批清单包含 ST、退市风险或当日无交易个股；任务 6 已在基础过滤中处理缺失日线、ST/退市风险和非 active 股票。
- 连板高度暂无结构化数据，任务 4 中未计入市场评分；后续需要补连板高度数据源后再纳入评分。
- AkShare/Eastmoney 板块接口在本机网络环境下仍断连；任务 5 已采用 TuShare `dc_index` 作为真实可运行路径。
- `sector_daily.five_day_return` 字段当前保存近 3 日累计涨幅；后续如改为 5 日，应同步迁移字段命名或 API 展示。
- `amount_change` 当前使用 TuShare `dc_index.total_mv * turnover_rate / 100` 作为成交额代理值；后续若取得板块真实成交额字段，应替换为真实成交额。
- 真实数据库当前 `2026-06-19` 的两只计划股经 TuShare 回补确认 `target_is_open=false`，不是开市日，因此没有个股日线，workflow 会写入“目标交易日不是开市日，未产生行情数据，计划需重新生成到下一开市日”，并且不会伪造成交。
- 下一步需要处理闭市目标日计划自动顺延或重新生成到下一开市日，再补延迟实时行情，让开市目标日计划能基于真实数据触发后进入模拟成交。
- 模拟交易后续可继续完善分批止盈、移动止损、按实时行情轮询和多账户参数化。
- 工作区存在未提交/未跟踪文件 `.gitignore`、`.git.zip`、`.logs/`，不是本轮任务创建或修改，未纳入提交。
- 本机本轮 PostgreSQL 映射为 `127.0.0.1:5432 -> postgres:5432`；真实验收命令使用了 `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock`。

## 本轮验证

- 任务 13 第一阶段验证：`.venv/bin/pytest`：65 passed，1 个 LibreSSL/urllib3 warning。
- 任务 13 第一阶段验证：`cd frontend && npm test -- --run`：1 passed。
- 任务 13 第一阶段验证：`cd frontend && npm run build`：通过；Element Plus / chunk size warning 仍存在。
- 任务 13 第一阶段验证：`bash -n scripts/backfill-target-daily.sh scripts/ingest-market-data.sh scripts/run-simulation.sh`：通过。
- 任务 13 真实数据库验证：`docker compose ps postgres` 显示 `stock-postgres` healthy，端口 `127.0.0.1:5432->5432`。
- 任务 13 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 任务 13 真实回补验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/backfill-target-daily.sh --provider tushare --target-trade-date 2026-06-19` 返回 `planned_stock_count=2`、`requested_stock_count=2`、`fetched_stock_daily_rows=0`、`missing_stock_codes=["300308", "603986"]`、`target_is_open=false`。
- 任务 13 真实 workflow 验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-simulation.sh run-workflow --trade-date 2026-06-19` 返回 `tracking=2`、总资产 `1000000.0`、交易 `0` 笔；两只计划股保持 `待触发`，备注为目标日不是开市日。

- 任务 12 验证：`.venv/bin/pytest`：60 passed，1 个 LibreSSL/urllib3 warning。
- 任务 12 验证：`cd frontend && npm test -- --run`：1 passed。
- 任务 12 验证：`cd frontend && npm run build`：通过；Element Plus / chunk size warning 仍存在。
- 任务 12 验证：`bash -n scripts/run-simulation.sh`：通过。
- 任务 12 真实数据库验证：`docker compose ps postgres` 显示 `stock-postgres` healthy，端口 `127.0.0.1:5432->5432`。
- 任务 12 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 任务 12 真实 workflow 验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-simulation.sh run-workflow --trade-date 2026-06-19` 返回 `tracking=2`、总资产 `1000000.0`、交易 `0` 笔；两只计划股因缺少目标日日线保持 `待触发`，不伪造成交。
- 任务 12 API 快验：`POST /api/simulation/run-workflow` 返回 200，`target_trade_date=2026-06-19`、`tracking=2`、`total_assets=1000000.0`、`trades=0`。

- 任务 11 验证：`.venv/bin/pytest`：57 passed，1 个 LibreSSL/urllib3 warning。
- 任务 11 验证：`cd frontend && npm test -- --run`：1 passed。
- 任务 11 验证：`cd frontend && npm run build`：通过；Element Plus / chunk size warning 仍存在。
- 任务 11 验证：`bash -n scripts/run-simulation.sh`：通过。
- 任务 11 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-upgrade.sh` 成功。
- 任务 11 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0005_simulation_trading_tables (head)`。
- 任务 11 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/run-simulation.sh --trade-date 2026-06-19` 创建默认模拟账户并生成资金曲线；总资产 `1000000.0`，交易 `0` 笔，持仓 `0`，原因是两条真实计划仍为 `待触发`。
- 任务 11 API 快验：`GET /api/simulation/latest` 返回 200，`as_of_date=2026-06-19`、`total_assets=1000000.0`、资金曲线 `1` 条。

- `bash -n start.sh scripts/check-dev-environment.sh`：通过。
- `bash -n scripts/track-trade-plans.sh`：通过。
- `.venv/bin/pytest`：47 passed，1 个 LibreSSL/urllib3 warning。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过；Element Plus 相关 bundle 仍有 chunk size warning。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5433/stock scripts/db-upgrade.sh`：迁移到 `0004_trade_plan_tracking_fields (head)`。
- `DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5433/stock scripts/track-trade-plans.sh --target-trade-date 2026-06-19 --mark-untriggered-at-close`：返回 2 条真实计划；因 `2026-06-19` 日线暂无数据，状态保持 `待触发` 并写入明确备注。
- 运行中 API 快验：`POST /api/trade-plans/track` 返回 200，`target_trade_date=2026-06-19`、`items=2`。
- 任务 10 验证：`.venv/bin/pytest`：49 passed，1 个 LibreSSL/urllib3 warning。
- 任务 10 验证：`cd frontend && npm test -- --run`：1 passed。
- 任务 10 验证：`cd frontend && npm run build`：通过；Element Plus / chunk size warning 仍存在。
- 任务 10 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-upgrade.sh` 成功。
- 任务 10 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/db-current.sh` 输出 `0004_trade_plan_tracking_fields (head)`。
- 任务 10 真实数据库验证：`DATABASE_URL=postgresql+psycopg://stock:stock@127.0.0.1:5432/stock bash scripts/generate-trade-reviews.sh --trade-date 2026-06-19` 生成 2 条复盘记录；因目标交易日日线暂无数据，`day_return` / `t5_return` / `max_profit` / `max_loss` 为 `null`，结果为 `未触发`。
- `.venv/bin/pytest`：18 passed。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过。当前 Element Plus 全量引入触发 chunk size warning，属于后续优化项，不影响任务 1 验收。
- `docker compose up -d postgres`：PostgreSQL 容器 healthy。
- `scripts/db-upgrade.sh`：执行 `0001_core_mvp_tables` 成功。
- `scripts/db-current.sh`：`0001_core_mvp_tables (head)`。
- PostgreSQL 查询确认存在 `alembic_version`、`market_daily`、`sector_daily`、`trade_plan`、`trade_review`。
- 重复执行 `scripts/db-upgrade.sh` 成功，说明初始化命令可重复调用。
- `scripts/db-upgrade.sh` 已迁移到 `0002_market_data_tables (head)`。
- 真实采集命令：
  - `scripts/ingest-market-data.sh --stock-code 000001 --stock-code 600519 --stock-code 300750 --stock-code 000002 --stock-code 000063`
- 采集结果：
  - `trade_date=2026-06-18`
  - `trading_calendar=109`
  - `stock_basic=5`
  - `index_daily=3`
  - `stock_daily=5`
  - `limit_snapshot=103`
  - `limit_up=91`
  - `limit_down=12`
- 样本日线均为目标交易日 `2026-06-18`：`000001`、`000002`、`000063`、`300750`、`600519`。
- 覆盖审计命令：
  - `scripts/audit-market-data.sh --trade-date 2026-06-18`
- 覆盖审计输出：
  - `open_trading_days=109`
  - `stock_basic_rows=5`
  - `stock_daily_rows=5`
  - `missing_stock_daily_rows=0`
  - `index_daily_rows=3`
  - `limit_up_rows=91`
  - `limit_down_rows=12`
  - `latest_stock_daily_date=2026-06-18`
- TuShare 缺 token 验证：
  - `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-18 --sample-size 5`
  - 结果：退出码 2，错误为 `TUSHARE_TOKEN is required for provider=tushare`
- TuShare 全市场初始化命令：
  - `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-18 --all-stocks`
- TuShare 全市场写入结果：
  - `trading_calendar=169`
  - `stock_basic=5529`
  - `index_daily=3`
  - `stock_daily=5507`
  - `limit_snapshot=103`
  - `limit_up=91`
  - `limit_down=12`
  - `provider=tushare`
  - `status=success`
- TuShare 全市场覆盖审计：
  - `scripts/audit-market-data.sh --trade-date 2026-06-18`
  - `open_trading_days=109`
  - `stock_basic_rows=5529`
  - `stock_daily_rows=5507`
  - `missing_stock_daily_rows=22`
  - `index_daily_rows=3`
  - `latest_stock_daily_date=2026-06-18`
- 缺失日线首批清单：
  - `000004 *ST国华`
  - `000793 *ST华闻`
  - `001331 胜通能源`
  - `002076 *ST星光`
  - `002731 ST萃华`
  - `002762 *ST金比`
  - `002808 *ST恒久`
  - `002898 *ST赛隆`
  - `300159 *ST新研`
  - `300313 *ST天山`
  - `300665 飞鹿股份`
  - `600228 返利科技`
  - `600717 天津港`
  - `603137 恒尚节能`
  - `603159 上海亚虹`
  - `603721 中广天择`
  - `688121 卓然股份`
  - `688143 长盈通`
  - `688287 退市观典`
  - `688689 银河微电`
  - `920305 *ST云创`
  - `920675 秉扬科技`
- 本轮完整验证：
  - `.venv/bin/pytest`：20 passed，1 个 LibreSSL/urllib3 warning。
  - `cd frontend && npm test -- --run`：1 passed。
  - `cd frontend && npm run build`：通过；Element Plus 相关 bundle 仍有 chunk size warning。
- 任务 4 真实数据验证：
  - `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-17 --all-stocks`：成功，`stock_daily_rows=5509`、`index_daily_rows=93`、`limit_snapshot_rows=87`。
  - `scripts/ingest-market-data.sh --provider tushare --trade-date 2026-06-18 --all-stocks`：成功，`stock_daily_rows=5507`、`index_daily_rows=96`、`limit_snapshot_rows=103`。
  - 指数历史覆盖：`000001.SH`、`399001.SZ`、`399006.SZ` 均为 32 条，范围 `2026-05-06` 到 `2026-06-18`。
  - `scripts/generate-market-environment.sh --trade-date 2026-06-18`：成功生成 `market_daily`。
  - PostgreSQL 最新 `market_daily`：`trade_date=2026-06-18`、`market_score=55`、`market_status=中性`、`up_count=2023`、`down_count=3395`、`limit_up_count=91`、`limit_down_count=12`、`total_amount=3331719013167.0800`。
  - `GET /api/market/latest`：返回 200，最新结果与数据库一致。
  - 评分解释：上证指数站上 MA20 `+15`、创业板指站上 MA20 `+15`、上涨家数未超过下跌家数 `+0`、涨停家数不少于 40 `+15`、跌停家数超过 10 `+0`、成交额较上一交易日放大 `+10`、连板高度暂无结构化数据未计分。
- 任务 5 真实数据验证：
  - AkShare/Eastmoney 板块接口在当前网络下报 `RemoteDisconnected` / `ProxyError`，未作为验收路径。
  - TuShare `dc_index(trade_date=20260618)`：返回 `1021` 条板块数据。
  - `scripts/generate-sector-ranking.sh --trade-date 2026-06-18 --member-fetch-limit 80`：成功生成 Top 10 并写入 `sector_daily`。
  - PostgreSQL `sector_daily`：`count=10`、`rank_no=1..10`、`sector_score=100..100`。
  - `GET /api/sectors/top`：返回 200，最新结果与数据库一致。
  - 真实 Top 10：
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
- 任务 6 真实数据验证：
  - `scripts/db-upgrade.sh` 已升级到 `0003_candidate_stock_table (head)`。
  - 已回补 `2026-05-20` 到 `2026-06-18` 的 22 个交易日个股日线，共 `121182` 条。
  - `scripts/generate-candidates.sh --trade-date 2026-06-18 --limit 50`：成功生成候选并写入 `candidate_stock`。
  - PostgreSQL `candidate_stock`：`trade_date=2026-06-18`、`count=42`、分数范围 `91-100`。
  - 策略分布：`趋势强势=34`、`强势回踩=6`、`放量突破=2`。
  - `GET /api/candidates/latest`：返回 200，`trade_date=2026-06-18`，`items=42`。
  - Top 候选样例：
    - `300308 中际旭创`：`科技风格`，`趋势强势`，评分 `100`。
    - `603986 兆易创新`：`科技风格`，`趋势强势`，评分 `100`。
    - `600487 亨通光电`：`科技风格`，`趋势强势`，评分 `100`。
    - `002384 东山精密`：`科技风格`，`趋势强势`，评分 `100`。
    - `688525 佰维存储`：`科技风格`，`趋势强势`，评分 `100`。
- 任务 7 真实数据验证：
  - `.venv/bin/pytest`：42 passed，1 个 LibreSSL/urllib3 warning。
  - `cd frontend && npm test -- --run`：1 passed。
  - `cd frontend && npm run build`：通过；Element Plus 相关 bundle 仍有 chunk size warning。
  - `scripts/generate-trade-plans.sh --plan-date 2026-06-18`：成功生成 2 条真实交易计划并写入 `trade_plan`。
  - 真实 API `GET /api/trade-plans/latest`：返回 200，`plan_date=2026-06-18`、`target_trade_date=2026-06-19`、`items=2`。
  - 真实计划目标交易日：`2026-06-19`。
  - 真实计划样例：
    - `300308 中际旭创`：`科技风格`，`趋势强势`，买入区间 `1207.2060 - 1367.8800`，止损 `1299.4860`，止盈 `1641.4560`，仓位 `40%`。
    - `603986 兆易创新`：`科技风格`，`趋势强势`，买入区间 `517.4120 - 629.0000`，止损 `597.5500`，止盈 `754.8000`，仓位 `40%`。
- 任务 8 真实数据验证：
  - `.venv/bin/pytest`：42 passed，1 个 LibreSSL/urllib3 warning。
  - `cd frontend && npm test -- --run`：1 passed。
  - `cd frontend && npm run build`：通过；Element Plus 相关 bundle 仍有 chunk size warning。
  - 真实 API 快验：`/api/market/latest 200 2026-06-18 中性 55`。
  - 真实 API 快验：`/api/sectors/top 200 2026-06-18 10`。
  - 真实 API 快验：`/api/trade-plans/latest 200 2026-06-18 2`。
  - Playwright 浏览器快验：`http://127.0.0.1:5173/` 展示 `今日决策面板`、`科技风格`、`中际旭创`、`40%` 和 `交易复盘`；console 仅有缺少 `favicon.ico` 的 404。

## 验收口径

当前阶段已完成任务 1-12，并完成任务 13 第一阶段真实目标交易日日线回补入口。模拟交易基础链路可运行，但真实成交仍依赖目标交易日开市且有真实日线或延迟行情数据；闭市日和缺数据时不得宣称已触发或已成交。

在以下事项完成前，不得宣称任务 13 全部完成：

- 闭市目标日计划可自动顺延或重新生成到下一开市日。
- 开市目标日能通过真实日线或延迟行情触发计划并进入模拟成交。
- 分批止盈、移动止损和交易时段轮询完成。

## 下一步

继续 `docs/TASKS.md` 的任务 13 第二阶段：

1. 当交易计划目标日被真实日历确认非开市时，自动顺延或重新生成到下一开市日。
2. 接入延迟实时行情，让开市目标日计划能基于真实数据触发并进入模拟成交。
3. 后续完善分批止盈、移动止损和交易时段轮询。
4. 更新 `docs/HANDOFF.md`。
5. 提交 git commit。

## 必须保留的约束

- 每次开发前运行 `git status --short --branch`。
- 每个开发节点必须 git commit。
- 所有长期上下文写入仓库文档。
- 真实数据优先，mock 不作为完成依据。
- 所有交易信号必须可解释。
- 没有止损价的股票不得进入交易计划。
- 任何交易计划都不得使用未来函数。
