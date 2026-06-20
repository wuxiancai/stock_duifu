# Handoff

## 当前状态

- 日期：2026-06-20
- 仓库路径：`/Users/wuxiancai/Documents/stock`
- 当前系统是全新的 A 股短线量化辅助决策系统。
- 旧 `stock` 项目已被废弃，不继承旧代码、旧部署方式、旧验收结论或旧业务假设。
- 当前已完成任务 1「项目骨架与配置」，尚未实现交易业务逻辑。

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

## 未完成

- 未创建 PostgreSQL 数据库模型。
- 未接入 TuShare、AkShare 或其他真实行情数据源。
- 未创建交易业务 API。
- 未创建 P0 交易业务页面。
- 未完成任何真实数据验收。

## 本轮验证

- `.venv/bin/pytest`：1 passed。
- `cd frontend && npm test -- --run`：1 passed。
- `cd frontend && npm run build`：通过。当前 Element Plus 全量引入触发 chunk size warning，属于后续优化项，不影响任务 1 验收。

## 验收口径

当前阶段只完成文档初始化、工程骨架、配置和健康检查，不代表 MVP 完成。

在以下事项完成前，不得宣称系统可用于每日交易准备：

- 真实 PostgreSQL 数据库可初始化。
- 真实行情数据可拉取并入库。
- 市场环境、强势板块和交易计划可由真实数据生成。
- P0 Web 页面可展示真实数据库结果。
- 交易计划可跟踪触发并生成复盘。

## 下一步

从 `docs/TASKS.md` 的任务 2「数据库模型与迁移」开始：

1. 创建 `market_daily`、`sector_daily`、`trade_plan`、`trade_review` 表。
2. 建立迁移工具和初始化命令。
3. 增加唯一约束和日期索引，避免重复写入。
4. 使用真实 PostgreSQL 验证初始化。
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
