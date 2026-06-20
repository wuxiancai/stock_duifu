# Handoff

## 当前状态

- 日期：2026-06-21
- 仓库路径：`/Users/wuxiancai/Documents/stock`
- 当前系统是全新的 A 股短线量化辅助决策系统。
- 旧 `stock` 项目已被废弃，不继承旧代码、旧部署方式、旧验收结论或旧业务假设。
- 当前已完成任务 1「项目骨架与配置」、任务 2「数据库模型与迁移」、任务 3「数据采集与交易日历」、任务 4「市场环境评分」、任务 5「强势板块排序」和任务 6「候选股票筛选」。
- TuShare token 已脱敏保存在本机 `.env` 并通过 `TUSHARE_TOKEN` 读取；`.env` 不提交到 git。

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

## 未完成

- 未创建交易业务 API。
- 未创建 P0 交易业务页面。
- 未完成任务 7「交易计划生成」。
- 全市场 `2026-06-18` 覆盖审计仍有 `missing_stock_daily_rows=22`，首批清单包含 ST、退市风险或当日无交易个股；任务 6 已在基础过滤中处理缺失日线、ST/退市风险和非 active 股票。
- 连板高度暂无结构化数据，任务 4 中未计入市场评分；后续需要补连板高度数据源后再纳入评分。
- AkShare/Eastmoney 板块接口在本机网络环境下仍断连；任务 5 已采用 TuShare `dc_index` 作为真实可运行路径。
- `sector_daily.five_day_return` 字段当前保存近 3 日累计涨幅；后续如改为 5 日，应同步迁移字段命名或 API 展示。
- `amount_change` 当前使用 TuShare `dc_index.total_mv * turnover_rate / 100` 作为成交额代理值；后续若取得板块真实成交额字段，应替换为真实成交额。
- 工作区存在未跟踪文件 `prd_by_glm.md`，不是本轮任务创建或修改，未纳入提交。
- 任务 6 只生成候选股票，不生成买入区间、止损价、止盈价和建议仓位；下一步任务 7 必须补齐这些交易计划字段，且无止损价不得入库。

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

## 验收口径

当前阶段只完成文档初始化、工程骨架、配置、健康检查、数据库表初始化和真实数据采集基础链路，不代表 MVP 完成。

在以下事项完成前，不得宣称系统可用于每日交易准备：

- TuShare 主源和全市场真实行情数据可拉取并入库。
- 市场环境、强势板块和交易计划可由真实数据生成。
- P0 Web 页面可展示真实数据库结果。
- 交易计划可跟踪触发并生成复盘。

## 下一步

继续 `docs/TASKS.md` 的任务 7：交易计划生成。

1. 从 `candidate_stock` 读取候选，按股票/策略生成第二天条件交易计划。
2. 生成买入条件、买入区间、止损价、止盈价、建议仓位和风险提示。
3. 严格执行“没有止损价不得进入计划”。
4. 提供交易计划查询 API。
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
