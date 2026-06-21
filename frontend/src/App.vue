<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Calendar,
  Connection,
  DataAnalysis,
  Download,
  Finished,
  Refresh,
  TrendCharts
} from '@element-plus/icons-vue'
import { fetchHealth, type HealthResponse } from './api/health'
import {
  fetchLatestSimulation,
  fetchLatestTradePlans,
  fetchLatestTradeReviews,
  fetchMarketLatest,
  fetchTradePlanDetail,
  fetchTopSectors,
  runSimulationWorkflow,
  trackTradePlans,
  updateTradePlanStatus,
  type MarketLatestResponse,
  type SectorTopItem,
  type SectorTopResponse,
  type SimulationEquityPoint,
  type SimulationLatestResponse,
  type SimulationPosition,
  type SimulationTrade,
  type TradePlanItem,
  type TradePlanDetail,
  type TradePlansLatestResponse,
  type TradePlanTrackingResponse,
  type TradeReviewGroupStats,
  type TradeReviewItem,
  type TradeReviewLatestResponse
} from './api/dashboard'

const health = ref<HealthResponse | null>(null)
const market = ref<MarketLatestResponse | null>(null)
const sectors = ref<SectorTopResponse | null>(null)
const tradePlans = ref<TradePlansLatestResponse | null>(null)
const tradeReviews = ref<TradeReviewLatestResponse | null>(null)
const simulation = ref<SimulationLatestResponse | null>(null)
const selectedPlanDetail = ref<TradePlanDetail | null>(null)
const trackingItems = ref<TradePlanTrackingResponse['items']>([])
const loading = ref(true)
const error = ref('')
const sectorKeyword = ref('')
const planKeyword = ref('')
const planTrackingLoading = ref(false)
const simulationLoading = ref(false)

const statusType = computed(() => {
  if (error.value) return 'danger'
  return health.value?.status === 'ok' ? 'success' : 'warning'
})

const marketTagType = computed(() => {
  switch (market.value?.market_status) {
    case '强势':
      return 'success'
    case '中性':
      return 'warning'
    case '弱势':
      return 'info'
    case '风险':
      return 'danger'
    default:
      return 'info'
  }
})

const filteredSectors = computed(() => {
  const keyword = sectorKeyword.value.trim().toLowerCase()
  const items = sectors.value?.items ?? []

  if (!keyword) return items

  return items.filter((item) => item.sector_name.toLowerCase().includes(keyword))
})

const filteredTradePlans = computed(() => {
  const keyword = planKeyword.value.trim().toLowerCase()
  const items = tradePlans.value?.items ?? []

  if (!keyword) return items

  return items.filter((item) => {
    return [item.stock_code, item.stock_name, item.sector_name, item.strategy_type, item.status]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const totalAmountText = computed(() => formatLargeAmount(market.value?.total_amount))

const trackingRows = computed(() => {
  const trackedById = new Map(trackingItems.value.map((item) => [item.id, item]))
  return (tradePlans.value?.items ?? []).map((plan) => ({
    ...plan,
    current_price: trackedById.get(plan.id)?.current_price ?? null,
    pct_chg: trackedById.get(plan.id)?.pct_chg ?? null,
    tracking_note: trackedById.get(plan.id)?.tracking_note ?? plan.tracking_note,
    status: trackedById.get(plan.id)?.status ?? plan.status,
    trigger_price: trackedById.get(plan.id)?.trigger_price ?? plan.trigger_price
  }))
})

function planStatusType(status: string) {
  switch (status) {
    case '已触发':
      return 'success'
    case '取消':
      return 'danger'
    case '未触发':
      return 'info'
    default:
      return 'warning'
  }
}

async function loadDashboard() {
  loading.value = true
  error.value = ''

  try {
    const [healthResult, marketResult, sectorsResult, tradePlansResult, tradeReviewsResult, simulationResult] = await Promise.all([
      fetchHealth(),
      fetchMarketLatest(),
      fetchTopSectors(),
      fetchLatestTradePlans(),
      fetchLatestTradeReviews().catch(() => null),
      fetchLatestSimulation().catch(() => null)
    ])

    health.value = healthResult
    market.value = marketResult
    sectors.value = sectorsResult
    tradePlans.value = tradePlansResult
    tradeReviews.value = tradeReviewsResult
    simulation.value = simulationResult
    trackingItems.value = []
    await loadPlanDetail(tradePlansResult.items[0]?.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '业务数据加载失败'
  } finally {
    loading.value = false
  }
}

async function loadPlanDetail(planId: number | undefined) {
  if (!planId) {
    selectedPlanDetail.value = null
    return
  }
  selectedPlanDetail.value = await fetchTradePlanDetail(planId)
}

function formatPercent(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${value.toFixed(digits)}%`
}

function formatReturn(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(digits)}%`
}

function formatPrice(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return value.toFixed(2)
}

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatPosition(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  const percentValue = Math.abs(value) <= 1 ? value * 100 : value
  return `${percentValue.toFixed(0)}%`
}

function formatLargeAmount(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'

  if (Math.abs(value) >= 100000000) {
    return `${(value / 100000000).toFixed(2)} 亿`
  }

  return value.toLocaleString('zh-CN')
}

function exportCsv(filename: string, headers: string[], rows: Array<Array<string | number>>) {
  const csvRows = [headers, ...rows].map((row) => {
    return row
      .map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`)
      .join(',')
  })
  const blob = new Blob([`\uFEFF${csvRows.join('\n')}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

function exportSectors() {
  exportCsv(
    `top-sectors-${sectors.value?.trade_date ?? 'latest'}.csv`,
    ['排名', '板块', '今日涨幅', '3日涨幅', '成交额代理变化', '涨停数', '强势股数', '评分'],
    filteredSectors.value.map((item) => [
      item.rank_no,
      item.sector_name,
      item.daily_return,
      item.three_day_return,
      item.amount_change,
      item.limit_up_count,
      item.strong_stock_count,
      item.sector_score
    ])
  )
}

function exportPlans() {
  exportCsv(
    `trade-plans-${tradePlans.value?.target_trade_date ?? 'latest'}.csv`,
    ['股票代码', '股票名称', '板块', '策略', '个股评分', '板块评分', '买入条件', '买入下限', '买入上限', '止损价', '止盈价', '仓位', '状态', '关注', '触发价', '跟踪备注', '风险提示'],
    filteredTradePlans.value.map((item) => [
      item.stock_code,
      item.stock_name,
      item.sector_name,
      item.strategy_type,
      item.stock_score,
      item.sector_score,
      item.buy_condition,
      item.buy_price_low,
      item.buy_price_high,
      item.stop_loss_price,
      item.take_profit_price,
      item.position_ratio,
      item.status,
      item.is_watched ? '是' : '否',
      item.trigger_price ?? '',
      item.tracking_note,
      item.risk_note
    ])
  )
}

function exportReviews() {
  exportCsv(
    `trade-reviews-${tradeReviews.value?.review_date ?? 'latest'}.csv`,
    ['日期', '股票代码', '股票名称', '板块', '策略', '是否触发', '触发价', '收盘价', '当日收益', 'T+5收益', '最大浮盈', '最大浮亏', '结果', '失败原因', '纪律检查', '备注'],
    (tradeReviews.value?.items ?? []).map((item) => [
      item.trade_date,
      item.stock_code,
      item.stock_name,
      item.sector_name,
      item.strategy_type,
      item.triggered ? '是' : '否',
      item.trigger_price ?? '',
      item.close_price ?? '',
      item.day_return ?? '',
      item.t5_return ?? '',
      item.max_profit ?? '',
      item.max_loss ?? '',
      item.result,
      item.failure_reason ?? '',
      item.discipline_check ? '是' : '否',
      item.note
    ])
  )
}

async function runPlanTracking(markUntriggeredAtClose = false) {
  if (!tradePlans.value?.target_trade_date) return
  planTrackingLoading.value = true
  error.value = ''

  try {
    const result = await trackTradePlans(tradePlans.value.target_trade_date, markUntriggeredAtClose)
    await loadDashboard()
    trackingItems.value = result.items
    ElMessage.success(`已更新 ${result.items.length} 条计划状态`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '计划跟踪失败'
  } finally {
    planTrackingLoading.value = false
  }
}

async function togglePlanWatch(row: TradePlanItem) {
  planTrackingLoading.value = true
  error.value = ''

  try {
    const nextValue = !row.is_watched
    await updateTradePlanStatus(
      row.id,
      row.status,
      nextValue ? '前端手动标记为关注' : '前端手动取消关注',
      row.trigger_price ?? undefined,
      nextValue
    )
    await loadDashboard()
    ElMessage.success(`${row.stock_name} 已${nextValue ? '加入关注' : '取消关注'}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '关注状态更新失败'
  } finally {
    planTrackingLoading.value = false
  }
}

async function runSimulationForTarget() {
  if (!tradePlans.value?.target_trade_date) return
  simulationLoading.value = true
  error.value = ''

  try {
    const result = await runSimulationWorkflow(tradePlans.value.target_trade_date)
    simulation.value = result.simulation
    await loadDashboard()
    ElMessage.success(`已跟踪 ${result.tracking.length} 条计划，并模拟到 ${result.simulation.as_of_date}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模拟交易运行失败'
  } finally {
    simulationLoading.value = false
  }
}

async function setPlanStatus(row: TradePlanItem, status: string) {
  planTrackingLoading.value = true
  error.value = ''

  try {
    await updateTradePlanStatus(row.id, status, `前端手动标记为${status}`, row.trigger_price ?? undefined)
    await loadDashboard()
    ElMessage.success(`${row.stock_name} 已标记为${status}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '计划状态更新失败'
  } finally {
    planTrackingLoading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">A</span>
        <div>
          <strong>A股短线决策</strong>
          <small>MVP 工作台</small>
        </div>
      </div>
      <nav class="nav-list">
        <a class="nav-item active" href="#decision">
          <el-icon><DataAnalysis /></el-icon>
          <span>决策面板</span>
        </a>
        <a class="nav-item" href="#sectors">
          <el-icon><TrendCharts /></el-icon>
          <span>强势板块</span>
        </a>
        <a class="nav-item" href="#plans">
          <el-icon><Finished /></el-icon>
          <span>交易计划</span>
        </a>
        <a class="nav-item" href="#plan-detail">
          <el-icon><DataAnalysis /></el-icon>
          <span>股票详情</span>
        </a>
        <a class="nav-item" href="#tracking">
          <el-icon><Refresh /></el-icon>
          <span>盘中跟踪</span>
        </a>
        <a class="nav-item" href="#simulation">
          <el-icon><Connection /></el-icon>
          <span>模拟交易</span>
        </a>
        <a class="nav-item" href="#review">
          <el-icon><Calendar /></el-icon>
          <span>交易复盘</span>
        </a>
      </nav>
    </aside>

    <section class="workspace" v-loading="loading">
      <header class="toolbar">
        <div>
          <h1>A股短线决策工作台</h1>
          <p>盘后查看市场环境、强势板块和次日条件交易计划。</p>
        </div>
        <div class="toolbar-actions">
          <el-tag :type="statusType" size="large">
            {{ error ? '数据异常' : health?.status === 'ok' ? 'API 正常' : '加载中' }}
          </el-tag>
          <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
        </div>
      </header>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
      />

      <section id="decision" class="panel">
        <div class="section-heading">
          <div>
            <h2>今日决策面板</h2>
            <p>交易日：{{ market?.trade_date ?? '-' }}</p>
          </div>
          <el-tag :type="marketTagType" size="large">{{ market?.market_status ?? '待生成' }}</el-tag>
        </div>

        <section class="metric-grid decision-grid">
          <article class="metric primary-metric">
            <el-icon><DataAnalysis /></el-icon>
            <div>
              <span>市场评分</span>
              <strong>{{ market?.market_score ?? '-' }}</strong>
            </div>
          </article>
          <article class="metric">
            <el-icon><Connection /></el-icon>
            <div>
              <span>建议总仓位</span>
              <strong>{{ market?.suggested_position ?? '-' }}</strong>
            </div>
          </article>
          <article class="metric">
            <el-icon><TrendCharts /></el-icon>
            <div>
              <span>涨停 / 跌停</span>
              <strong>{{ market?.limit_up_count ?? '-' }} / {{ market?.limit_down_count ?? '-' }}</strong>
            </div>
          </article>
          <article class="metric">
            <el-icon><Finished /></el-icon>
            <div>
              <span>上涨 / 下跌家数</span>
              <strong>{{ market?.up_count ?? '-' }} / {{ market?.down_count ?? '-' }}</strong>
            </div>
          </article>
          <article class="metric wide-metric">
            <el-icon><DataAnalysis /></el-icon>
            <div>
              <span>全市场成交额</span>
              <strong>{{ totalAmountText }}</strong>
            </div>
          </article>
        </section>

        <el-alert
          class="suggestion-alert"
          :title="market?.suggestion ?? '暂无市场建议，请先生成市场环境数据。'"
          type="info"
          :closable="false"
          show-icon
        />
      </section>

      <section id="sectors" class="panel">
        <div class="section-heading table-heading">
          <div>
            <h2>强势板块</h2>
            <p>交易日：{{ sectors?.trade_date ?? '-' }}，展示 Top {{ sectors?.items.length ?? 0 }}</p>
          </div>
          <div class="table-tools">
            <el-input v-model="sectorKeyword" clearable placeholder="筛选板块" />
            <el-button :icon="Download" :disabled="!filteredSectors.length" @click="exportSectors">导出</el-button>
          </div>
        </div>

        <el-table :data="filteredSectors" border stripe empty-text="暂无强势板块数据">
          <el-table-column prop="rank_no" label="排名" width="88" sortable>
            <template #default="{ row }: { row: SectorTopItem }">
              <el-tag :type="row.rank_no <= 3 ? 'success' : 'info'">{{ row.rank_no }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sector_name" label="板块" min-width="150" sortable />
          <el-table-column prop="daily_return" label="今日涨幅" min-width="120" sortable>
            <template #default="{ row }: { row: SectorTopItem }">{{ formatPercent(row.daily_return) }}</template>
          </el-table-column>
          <el-table-column prop="three_day_return" label="3日涨幅" min-width="120" sortable>
            <template #default="{ row }: { row: SectorTopItem }">{{ formatPercent(row.three_day_return) }}</template>
          </el-table-column>
          <el-table-column prop="amount_change" label="成交额代理" min-width="140" sortable>
            <template #default="{ row }: { row: SectorTopItem }">{{ formatLargeAmount(row.amount_change) }}</template>
          </el-table-column>
          <el-table-column prop="limit_up_count" label="涨停" min-width="90" sortable />
          <el-table-column prop="strong_stock_count" label="强势股" min-width="100" sortable />
          <el-table-column prop="sector_score" label="评分" min-width="90" sortable />
        </el-table>
      </section>

      <section id="plans" class="panel">
        <div class="section-heading table-heading">
          <div>
            <h2>今日交易计划</h2>
            <p>计划日：{{ tradePlans?.plan_date ?? '-' }}，目标交易日：{{ tradePlans?.target_trade_date ?? '-' }}</p>
          </div>
          <div class="table-tools">
            <el-input v-model="planKeyword" clearable placeholder="筛选股票/板块/策略" />
            <el-button :loading="planTrackingLoading" :disabled="!tradePlans?.target_trade_date" @click="runPlanTracking(false)">跟踪触发</el-button>
            <el-button :loading="planTrackingLoading" :disabled="!tradePlans?.target_trade_date" @click="runPlanTracking(true)">收盘确认</el-button>
            <el-button :icon="Download" :disabled="!filteredTradePlans.length" @click="exportPlans">导出</el-button>
          </div>
        </div>

        <el-table :data="filteredTradePlans" border stripe empty-text="暂无交易计划数据">
          <el-table-column label="股票" min-width="150" sortable prop="stock_name">
            <template #default="{ row }: { row: TradePlanItem }">
              <strong>{{ row.stock_name }}</strong>
              <small class="muted-code">{{ row.stock_code }}</small>
            </template>
          </el-table-column>
          <el-table-column prop="sector_name" label="板块" min-width="130" sortable />
          <el-table-column prop="strategy_type" label="策略" min-width="120" sortable />
          <el-table-column label="评分" min-width="110" sortable prop="stock_score">
            <template #default="{ row }: { row: TradePlanItem }">{{ row.stock_score }} / {{ row.sector_score }}</template>
          </el-table-column>
          <el-table-column prop="buy_condition" label="买入条件" min-width="260" show-overflow-tooltip />
          <el-table-column label="买入区间" min-width="150">
            <template #default="{ row }: { row: TradePlanItem }">
              {{ formatPrice(row.buy_price_low) }} - {{ formatPrice(row.buy_price_high) }}
            </template>
          </el-table-column>
          <el-table-column label="止损/止盈" min-width="150">
            <template #default="{ row }: { row: TradePlanItem }">
              {{ formatPrice(row.stop_loss_price) }} / {{ formatPrice(row.take_profit_price) }}
            </template>
          </el-table-column>
          <el-table-column label="仓位" min-width="90" sortable prop="position_ratio">
            <template #default="{ row }: { row: TradePlanItem }">{{ formatPosition(row.position_ratio) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" min-width="100" sortable>
            <template #default="{ row }: { row: TradePlanItem }">
              <el-tag :type="planStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关注" min-width="90" sortable prop="is_watched">
            <template #default="{ row }: { row: TradePlanItem }">
              <el-tag :type="row.is_watched ? 'success' : 'info'">{{ row.is_watched ? '已关注' : '未关注' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发价" min-width="100" sortable prop="trigger_price">
            <template #default="{ row }: { row: TradePlanItem }">{{ formatPrice(row.trigger_price) }}</template>
          </el-table-column>
          <el-table-column prop="tracking_note" label="跟踪备注" min-width="220" show-overflow-tooltip />
          <el-table-column label="手动" width="250" fixed="right">
            <template #default="{ row }: { row: TradePlanItem }">
              <el-button size="small" :disabled="planTrackingLoading" @click="loadPlanDetail(row.id)">详情</el-button>
              <el-button size="small" :disabled="planTrackingLoading" @click="togglePlanWatch(row)">
                {{ row.is_watched ? '取消关注' : '关注' }}
              </el-button>
              <el-button size="small" :disabled="planTrackingLoading" @click="setPlanStatus(row, '已触发')">触发</el-button>
              <el-button size="small" type="danger" :disabled="planTrackingLoading" @click="setPlanStatus(row, '取消')">取消</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="risk_note" label="风险提示" min-width="260" show-overflow-tooltip />
        </el-table>
      </section>

      <section id="plan-detail" class="panel">
        <div class="section-heading">
          <div>
            <h2>股票详情</h2>
            <p>{{ selectedPlanDetail ? `${selectedPlanDetail.stock_name} ${selectedPlanDetail.stock_code}` : '请选择一条交易计划' }}</p>
          </div>
          <el-tag v-if="selectedPlanDetail" :type="planStatusType(selectedPlanDetail.status)">
            {{ selectedPlanDetail.status }}
          </el-tag>
        </div>

        <template v-if="selectedPlanDetail">
          <section class="metric-grid detail-grid">
            <article class="metric">
              <el-icon><TrendCharts /></el-icon>
              <div>
                <span>策略命中</span>
                <strong>{{ selectedPlanDetail.strategy_type }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><DataAnalysis /></el-icon>
              <div>
                <span>评分</span>
                <strong>{{ selectedPlanDetail.stock_score }} / {{ selectedPlanDetail.sector_score }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Finished /></el-icon>
              <div>
                <span>买入区间</span>
                <strong>{{ formatPrice(selectedPlanDetail.buy_price_low) }} - {{ formatPrice(selectedPlanDetail.buy_price_high) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Connection /></el-icon>
              <div>
                <span>止损 / 止盈</span>
                <strong>{{ formatPrice(selectedPlanDetail.stop_loss_price) }} / {{ formatPrice(selectedPlanDetail.take_profit_price) }}</strong>
              </div>
            </article>
          </section>

          <el-descriptions border :column="2">
            <el-descriptions-item label="所属板块">{{ selectedPlanDetail.sector_name }}</el-descriptions-item>
            <el-descriptions-item label="建议仓位">{{ formatPosition(selectedPlanDetail.position_ratio) }}</el-descriptions-item>
            <el-descriptions-item label="MA5">{{ formatPrice(selectedPlanDetail.key_indicators.ma5) }}</el-descriptions-item>
            <el-descriptions-item label="MA10">{{ formatPrice(selectedPlanDetail.key_indicators.ma10) }}</el-descriptions-item>
            <el-descriptions-item label="MA20">{{ formatPrice(selectedPlanDetail.key_indicators.ma20) }}</el-descriptions-item>
            <el-descriptions-item label="ATR14">{{ formatPrice(selectedPlanDetail.key_indicators.atr14) }}</el-descriptions-item>
            <el-descriptions-item label="成交额">{{ formatLargeAmount(selectedPlanDetail.key_indicators.amount) }}</el-descriptions-item>
            <el-descriptions-item label="换手率">{{ formatPercent(selectedPlanDetail.key_indicators.turnover_rate) }}</el-descriptions-item>
            <el-descriptions-item label="买入条件" :span="2">{{ selectedPlanDetail.buy_condition }}</el-descriptions-item>
            <el-descriptions-item label="入选理由" :span="2">{{ selectedPlanDetail.selection_reason || '候选入选理由未入库' }}</el-descriptions-item>
            <el-descriptions-item label="风险提示" :span="2">{{ selectedPlanDetail.risk_note }}</el-descriptions-item>
          </el-descriptions>
        </template>
        <el-empty v-else description="暂无股票详情，请先生成交易计划" />
      </section>

      <section id="tracking" class="panel">
        <div class="section-heading table-heading">
          <div>
            <h2>盘中跟踪</h2>
            <p>目标交易日：{{ tradePlans?.target_trade_date ?? '-' }}，跟踪昨日计划触发、取消和当前行情。</p>
          </div>
          <div class="table-tools">
            <el-button :loading="planTrackingLoading" :disabled="!tradePlans?.target_trade_date" @click="runPlanTracking(false)">跟踪触发</el-button>
            <el-button :loading="planTrackingLoading" :disabled="!tradePlans?.target_trade_date" @click="runPlanTracking(true)">收盘确认</el-button>
          </div>
        </div>

        <el-table :data="trackingRows" border stripe empty-text="暂无盘中跟踪数据">
          <el-table-column label="股票" min-width="150" sortable prop="stock_name">
            <template #default="{ row }: { row: TradePlanItem & { current_price: number | null, pct_chg: number | null } }">
              <strong>{{ row.stock_name }}</strong>
              <small class="muted-code">{{ row.stock_code }}</small>
            </template>
          </el-table-column>
          <el-table-column label="当前价" min-width="100" sortable prop="current_price">
            <template #default="{ row }: { row: TradePlanItem & { current_price: number | null } }">{{ formatPrice(row.current_price) }}</template>
          </el-table-column>
          <el-table-column label="涨跌幅" min-width="100" sortable prop="pct_chg">
            <template #default="{ row }: { row: TradePlanItem & { pct_chg: number | null } }">{{ formatPercent(row.pct_chg) }}</template>
          </el-table-column>
          <el-table-column prop="buy_condition" label="买入条件" min-width="260" show-overflow-tooltip />
          <el-table-column label="触发" min-width="90" sortable prop="status">
            <template #default="{ row }: { row: TradePlanItem }">
              <el-tag :type="planStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发时间" min-width="160" prop="trigger_time">
            <template #default="{ row }: { row: TradePlanItem }">{{ row.trigger_time ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="触发价" min-width="100" sortable prop="trigger_price">
            <template #default="{ row }: { row: TradePlanItem }">{{ formatPrice(row.trigger_price) }}</template>
          </el-table-column>
          <el-table-column prop="tracking_note" label="取消原因 / 跟踪备注" min-width="260" show-overflow-tooltip />
        </el-table>
      </section>

      <section id="simulation" class="panel simulation-panel">
        <div class="section-heading table-heading">
          <div>
            <h2>模拟交易</h2>
            <p>模拟日：{{ simulation?.as_of_date ?? '-' }}，先跟踪计划触发，再按保守成交和费用规则模拟。</p>
          </div>
          <el-button :loading="simulationLoading" :disabled="!tradePlans?.target_trade_date" @click="runSimulationForTarget">
            跟踪并模拟交易
          </el-button>
        </div>

        <template v-if="simulation">
          <section class="metric-grid simulation-grid">
            <article class="metric primary-metric">
              <el-icon><Connection /></el-icon>
              <div>
                <span>当前总资产</span>
                <strong>{{ formatMoney(simulation.account.total_assets) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><DataAnalysis /></el-icon>
              <div>
                <span>可用现金</span>
                <strong>{{ formatMoney(simulation.account.available_cash) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><TrendCharts /></el-icon>
              <div>
                <span>持仓市值 / 仓位</span>
                <strong>{{ formatMoney(simulation.account.market_value) }} / {{ formatReturn(simulation.risk.position_ratio, 0) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Finished /></el-icon>
              <div>
                <span>累计收益 / 最大回撤</span>
                <strong>{{ formatReturn(simulation.account.total_return) }} / {{ formatReturn(simulation.risk.max_drawdown) }}</strong>
              </div>
            </article>
          </section>

          <el-alert
            v-if="simulation.messages.length"
            class="suggestion-alert"
            :title="simulation.messages.join('；')"
            type="warning"
            :closable="false"
            show-icon
          />

          <el-table :data="simulation.positions" border stripe empty-text="暂无模拟持仓">
            <el-table-column label="股票" min-width="150" sortable prop="stock_name">
              <template #default="{ row }: { row: SimulationPosition }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="sector_name" label="板块" min-width="120" sortable />
            <el-table-column prop="strategy_type" label="策略" min-width="120" sortable />
            <el-table-column prop="quantity" label="数量" min-width="100" sortable />
            <el-table-column label="成本/现价" min-width="130">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatPrice(row.buy_price) }} / {{ formatPrice(row.current_price) }}
              </template>
            </el-table-column>
            <el-table-column label="市值" min-width="120" sortable prop="market_value">
              <template #default="{ row }: { row: SimulationPosition }">{{ formatMoney(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="浮盈亏" min-width="130" sortable prop="unrealized_profit">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatMoney(row.unrealized_profit) }} / {{ formatReturn(row.unrealized_return) }}
              </template>
            </el-table-column>
            <el-table-column label="止损/止盈" min-width="130">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatPrice(row.stop_loss_price) }} / {{ formatPrice(row.take_profit_price) }}
              </template>
            </el-table-column>
            <el-table-column prop="buy_reason" label="买入原因" min-width="240" show-overflow-tooltip />
          </el-table>

          <el-table :data="simulation.trades" border stripe empty-text="暂无今日模拟交易记录">
            <el-table-column prop="trade_type" label="方向" width="90" sortable />
            <el-table-column label="股票" min-width="150" sortable prop="stock_name">
              <template #default="{ row }: { row: SimulationTrade }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column label="价格/数量" min-width="130">
              <template #default="{ row }: { row: SimulationTrade }">
                {{ formatPrice(row.price) }} / {{ row.quantity }}
              </template>
            </el-table-column>
            <el-table-column label="成交金额" min-width="120" sortable prop="amount">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="费用" min-width="110" sortable prop="total_fee">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.total_fee) }}</template>
            </el-table-column>
            <el-table-column label="交易后现金" min-width="130" sortable prop="cash_after">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.cash_after) }}</template>
            </el-table-column>
            <el-table-column label="盈亏" min-width="110" sortable prop="profit_loss">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.profit_loss) }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="260" show-overflow-tooltip />
          </el-table>

          <el-table :data="simulation.equity_curve" border stripe empty-text="暂无资金曲线">
            <el-table-column prop="trade_date" label="日期" min-width="120" sortable />
            <el-table-column label="总资产" min-width="130" sortable prop="total_assets">
              <template #default="{ row }: { row: SimulationEquityPoint }">{{ formatMoney(row.total_assets) }}</template>
            </el-table-column>
            <el-table-column label="现金" min-width="130" sortable prop="available_cash">
              <template #default="{ row }: { row: SimulationEquityPoint }">{{ formatMoney(row.available_cash) }}</template>
            </el-table-column>
            <el-table-column label="持仓市值" min-width="130" sortable prop="market_value">
              <template #default="{ row }: { row: SimulationEquityPoint }">{{ formatMoney(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="日收益" min-width="110" sortable prop="daily_return">
              <template #default="{ row }: { row: SimulationEquityPoint }">{{ formatReturn(row.daily_return) }}</template>
            </el-table-column>
            <el-table-column label="最大回撤" min-width="110" sortable prop="max_drawdown">
              <template #default="{ row }: { row: SimulationEquityPoint }">{{ formatReturn(row.max_drawdown) }}</template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="暂无模拟交易数据，请先运行模拟交易" />
      </section>

      <section id="review" class="panel review-panel">
        <div class="section-heading table-heading">
          <div>
            <h2>交易复盘</h2>
            <p>复盘日：{{ tradeReviews?.review_date ?? '-' }}，展示触发、收益和失败原因。</p>
          </div>
          <el-button :icon="Download" :disabled="!(tradeReviews?.items.length)" @click="exportReviews">导出复盘</el-button>
        </div>

        <template v-if="tradeReviews">
          <section class="metric-grid review-grid">
            <article class="metric">
              <el-icon><Calendar /></el-icon>
              <div>
                <span>计划数量</span>
                <strong>{{ tradeReviews.total_count }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Finished /></el-icon>
              <div>
                <span>触发 / 胜率</span>
                <strong>{{ tradeReviews.triggered_count }} / {{ formatReturn(tradeReviews.win_rate, 0) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><TrendCharts /></el-icon>
              <div>
                <span>当日均收益</span>
                <strong>{{ formatReturn(tradeReviews.avg_day_return) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><DataAnalysis /></el-icon>
              <div>
                <span>T+5 均收益</span>
                <strong>{{ formatReturn(tradeReviews.avg_t5_return) }}</strong>
              </div>
            </article>
          </section>

          <el-table class="review-stats-table" :data="tradeReviews.strategy_stats" border stripe empty-text="暂无策略统计">
            <el-table-column prop="name" label="策略" min-width="140" />
            <el-table-column prop="total_count" label="计划" width="90" sortable />
            <el-table-column prop="triggered_count" label="触发" width="90" sortable />
            <el-table-column label="胜率" width="100" sortable prop="win_rate">
              <template #default="{ row }: { row: TradeReviewGroupStats }">{{ formatReturn(row.win_rate, 0) }}</template>
            </el-table-column>
            <el-table-column label="当日均收益" min-width="120" sortable prop="avg_day_return">
              <template #default="{ row }: { row: TradeReviewGroupStats }">{{ formatReturn(row.avg_day_return) }}</template>
            </el-table-column>
            <el-table-column label="T+5 均收益" min-width="120" sortable prop="avg_t5_return">
              <template #default="{ row }: { row: TradeReviewGroupStats }">{{ formatReturn(row.avg_t5_return) }}</template>
            </el-table-column>
          </el-table>

          <el-table :data="tradeReviews.items" border stripe empty-text="暂无复盘明细">
            <el-table-column label="股票" min-width="150" sortable prop="stock_name">
              <template #default="{ row }: { row: TradeReviewItem }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="sector_name" label="板块" min-width="130" sortable />
            <el-table-column prop="strategy_type" label="策略" min-width="120" sortable />
            <el-table-column label="触发" width="90" sortable prop="triggered">
              <template #default="{ row }: { row: TradeReviewItem }">
                <el-tag :type="row.triggered ? 'success' : 'info'">{{ row.triggered ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="触发/收盘" min-width="130">
              <template #default="{ row }: { row: TradeReviewItem }">
                {{ formatPrice(row.trigger_price) }} / {{ formatPrice(row.close_price) }}
              </template>
            </el-table-column>
            <el-table-column label="当日收益" min-width="110" sortable prop="day_return">
              <template #default="{ row }: { row: TradeReviewItem }">{{ formatReturn(row.day_return) }}</template>
            </el-table-column>
            <el-table-column label="T+5收益" min-width="110" sortable prop="t5_return">
              <template #default="{ row }: { row: TradeReviewItem }">{{ formatReturn(row.t5_return) }}</template>
            </el-table-column>
            <el-table-column label="最大浮盈/浮亏" min-width="150">
              <template #default="{ row }: { row: TradeReviewItem }">
                {{ formatReturn(row.max_profit) }} / {{ formatReturn(row.max_loss) }}
              </template>
            </el-table-column>
            <el-table-column prop="result" label="结果" min-width="100" sortable />
            <el-table-column prop="failure_reason" label="失败原因" min-width="130" show-overflow-tooltip />
            <el-table-column prop="note" label="备注" min-width="220" show-overflow-tooltip />
          </el-table>
        </template>
        <el-empty v-else description="暂无复盘统计数据，请先运行复盘生成命令" />
      </section>
    </section>
  </main>
</template>
