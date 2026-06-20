# Handoff

## 当前状态

- 日期：2026-06-20
- 仓库路径：`/Users/wuxiancai/Documents/stock`
- 当前系统是全新的 A 股短线量化辅助决策系统。
- 旧 `stock` 项目已被废弃，不继承旧代码、旧部署方式、旧验收结论或旧业务假设。
- 当前已完成任务 1「项目骨架与配置」、任务 2「数据库模型与迁移」，并打通任务 3 的真实数据采集基础链路、provider 选择入口和覆盖审计。

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

## 未完成

- 未完成 TuShare 真实拉取映射；当前只完成 provider 选择和缺 token 保护。
- 未执行全市场全量股票日线初始化。
- 未创建交易业务 API。
- 未创建 P0 交易业务页面。
- 未完成全市场数据覆盖审计。

## 本轮验证

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

## 验收口径

当前阶段只完成文档初始化、工程骨架、配置、健康检查、数据库表初始化和真实数据采集基础链路，不代表 MVP 完成。

在以下事项完成前，不得宣称系统可用于每日交易准备：

- TuShare 主源和全市场真实行情数据可拉取并入库。
- 市场环境、强势板块和交易计划可由真实数据生成。
- P0 Web 页面可展示真实数据库结果。
- 交易计划可跟踪触发并生成复盘。

## 下一步

继续补齐 `docs/TASKS.md` 的任务 3：

1. 完成 TuShare 真实拉取映射，环境变量为 `TUSHARE_TOKEN`。
2. 建立全市场股票日线初始化命令，避免只停留在 5 只样本。
3. 扩展数据覆盖审计：目标交易日全市场股票数、最新交易日、缺失日线清单、涨跌停行数。
4. 明确 AkShare/Eastmoney 全市场实时快照当前在本机代理环境下会断连；可用路径是 Sina 日线和 Eastmoney 涨跌停池。
5. 更新 `docs/HANDOFF.md`。
6. 提交 git commit。

## 必须保留的约束

- 每次开发前运行 `git status --short --branch`。
- 每个开发节点必须 git commit。
- 所有长期上下文写入仓库文档。
- 真实数据优先，mock 不作为完成依据。
- 所有交易信号必须可解释。
- 没有止损价的股票不得进入交易计划。
- 任何交易计划都不得使用未来函数。
