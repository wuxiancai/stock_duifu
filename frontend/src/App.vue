<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
  fetchLatestCandidates,
  fetchLatestDataRuns,
  fetchLatestSimulation,
  fetchLatestTradePlans,
  fetchLatestTradeReviews,
  fetchDatabaseHealth,
  fetchIndexTicker,
  fetchMarketHistory,
  fetchTradePlanDetail,
  fetchTopSectors,
  runSimulationWorkflow,
  trackRealtimeTradePlans,
  updateTradePlanStatus,
  type CandidateItem,
  type CandidateLatestResponse,
  type DataJobRunItem,
  type DataJobStepItem,
  type DataRunsLatestResponse,
  type DatabaseHealthItem,
  type DatabaseHealthResponse,
  type IndexTickerResponse,
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
const marketHistory = ref<MarketLatestResponse[]>([])
const market = computed(() => marketHistory.value[0] ?? null)
const indexTicker = ref<IndexTickerResponse | null>(null)
const sectors = ref<SectorTopResponse | null>(null)
const candidates = ref<CandidateLatestResponse | null>(null)
const tradePlans = ref<TradePlansLatestResponse | null>(null)
const tradeReviews = ref<TradeReviewLatestResponse | null>(null)
const simulation = ref<SimulationLatestResponse | null>(null)
const dataRuns = ref<DataRunsLatestResponse | null>(null)
const databaseHealth = ref<DatabaseHealthResponse | null>(null)
const selectedPlanDetail = ref<TradePlanDetail | null>(null)
const trackingItems = ref<TradePlanTrackingResponse['items']>([])
const loading = ref(true)
const error = ref('')
const sectorKeyword = ref('')
const planKeyword = ref('')
const planTrackingLoading = ref(false)
const simulationLoading = ref(false)
const routePath = ref(window.location.pathname)
const intradayRefreshTimer = ref<number | null>(null)
const intradayRefreshRunning = ref(false)
const intradayRefreshFailureCount = ref(0)
const INTRADAY_REFRESH_INTERVAL_MS = 60_000
const MAX_INTRADAY_REFRESH_FAILURES = 3

const statusType = computed(() => {
  if (error.value) return 'danger'
  return health.value?.status === 'ok' ? 'success' : 'warning'
})

const marketTagType = computed(() => {
  return marketStatusType(market.value?.market_status)
})

function marketStatusType(status: string | null | undefined) {
  switch (status) {
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
}

const filteredSectors = computed(() => {
  const keyword = sectorKeyword.value.trim().toLowerCase()
  const items = sectors.value?.items ?? []

  if (!keyword) return items

  return items.filter((item) => item.sector_name.toLowerCase().includes(keyword))
})

const sectorRankHistoryDates = computed(() => {
  const dates: string[] = []

  for (const item of filteredSectors.value) {
    for (const history of item.rank_history) {
      if (!dates.includes(history.trade_date)) {
        dates.push(history.trade_date)
      }
    }
  }

  return dates.slice(0, 5)
})

const selectedSectorName = computed(() => {
  const prefix = '/sectors/'
  if (!routePath.value.startsWith(prefix)) return ''
  return decodeURIComponent(routePath.value.slice(prefix.length))
})

const isSectorDetailPage = computed(() => Boolean(selectedSectorName.value))

const selectedSector = computed(() => {
  if (!selectedSectorName.value) return null
  return (sectors.value?.items ?? []).find((item) => item.sector_name === selectedSectorName.value) ?? null
})

const filteredCandidates = computed(() => {
  const sectorName = selectedSectorName.value.trim()
  const items = candidates.value?.items ?? []

  if (!sectorName) return items

  return items.filter((item) => item.sector_name === sectorName)
})

const stockPoolTop10 = computed(() => {
  return (candidates.value?.items ?? [])
    .filter((item) => item.stock_pool_rank !== null)
    .sort((a, b) => (a.stock_pool_rank ?? 9999) - (b.stock_pool_rank ?? 9999))
})

const sectorTradePlans = computed(() => {
  const sectorName = selectedSectorName.value.trim()
  if (!sectorName) return []
  return (tradePlans.value?.items ?? []).filter((item) => item.sector_name === sectorName)
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

const trackingRows = computed(() => {
  const trackedById = new Map(trackingItems.value.map((item) => [item.id, item]))
  return (tradePlans.value?.items ?? []).map((plan) => ({
    ...plan,
    current_price: trackedById.get(plan.id)?.current_price ?? plan.current_price ?? null,
    pct_chg: trackedById.get(plan.id)?.pct_chg ?? plan.pct_chg ?? null,
    tracking_note: trackedById.get(plan.id)?.tracking_note ?? plan.tracking_note,
    status: trackedById.get(plan.id)?.status ?? plan.status,
    trigger_price: trackedById.get(plan.id)?.trigger_price ?? plan.trigger_price
  }))
})

const simulationTrades = computed(() => {
  const positionsByCode = new Map((simulation.value?.positions ?? []).map((position) => [position.stock_code, position]))
  return (simulation.value?.trades ?? []).map((trade) => {
    const position = positionsByCode.get(trade.stock_code)
    return {
      ...trade,
      display_profit_loss: trade.profit_loss ?? position?.unrealized_profit ?? null,
      display_profit_loss_return: trade.profit_loss_return ?? position?.unrealized_return ?? null
    }
  })
})

const virtualTrades = computed(() => {
  const positionsByCode = new Map((simulation.value?.virtual_positions ?? []).map((position) => [position.stock_code, position]))
  return (simulation.value?.virtual_trades ?? []).map((trade) => {
    const position = positionsByCode.get(trade.stock_code)
    return {
      ...trade,
      display_profit_loss: trade.profit_loss ?? position?.unrealized_profit ?? null,
      display_profit_loss_return: trade.profit_loss_return ?? position?.unrealized_return ?? null
    }
  })
})

const latestDataRun = computed(() => dataRuns.value?.items[0] ?? null)

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

function monitorStatusType(status: string | null | undefined) {
  switch (status) {
    case 'ok':
    case 'success':
      return 'success'
    case 'warning':
      return 'warning'
    case 'error':
    case 'failed':
      return 'danger'
    case 'running':
      return 'info'
    default:
      return 'info'
  }
}

async function loadDashboard() {
  loading.value = true
  error.value = ''

  try {
    const [healthResult, marketHistoryResult, indexTickerResult, sectorsResult, candidatesResult, initialTradePlansResult, tradeReviewsResult, dataRunsResult, databaseHealthResult] = await Promise.all([
      fetchHealth(),
      fetchMarketHistory(),
      fetchIndexTicker().catch(() => ({ items: [] })),
      fetchTopSectors(),
      fetchLatestCandidates().catch(() => null),
      fetchLatestTradePlans(),
      fetchLatestTradeReviews().catch(() => null),
      fetchLatestDataRuns().catch(() => ({ items: [] })),
      fetchDatabaseHealth().catch(() => null)
    ])
    let tradePlansResult = initialTradePlansResult
    let simulationResult = await fetchLatestSimulation().catch(() => null)
    let realtimeTrackingItems: TradePlanTrackingResponse['items'] = []

    const realtimeTargetDate = intradayRefreshTargetDate(tradePlansResult, simulationResult)
    if (realtimeTargetDate) {
      const realtimeResult = await trackRealtimeTradePlans(realtimeTargetDate).catch(() => null)
      if (realtimeResult) {
        realtimeTrackingItems = realtimeResult.items
        const workflowResult = await runSimulationWorkflow(realtimeTargetDate).catch(() => null)
        if (workflowResult) {
          realtimeTrackingItems = workflowResult.tracking
          simulationResult = workflowResult.simulation
        }
        tradePlansResult = await fetchLatestTradePlans()
      }
    }

    health.value = healthResult
    marketHistory.value = marketHistoryResult.items
    indexTicker.value = indexTickerResult
    sectors.value = sectorsResult
    candidates.value = candidatesResult
    tradePlans.value = tradePlansResult
    tradeReviews.value = tradeReviewsResult
    simulation.value = simulationResult
    dataRuns.value = dataRunsResult
    databaseHealth.value = databaseHealthResult
    trackingItems.value = realtimeTrackingItems
    selectedPlanDetail.value = null
    configureIntradayRefresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '业务数据加载失败'
  } finally {
    loading.value = false
  }
}

async function refreshIntradayWorkflow() {
  const targetTradeDate = intradayRefreshTargetDate(tradePlans.value, simulation.value)
  if (!targetTradeDate || intradayRefreshRunning.value) return

  intradayRefreshRunning.value = true

  try {
    const realtimeResult = await trackRealtimeTradePlans(targetTradeDate)
    trackingItems.value = realtimeResult.items
    const workflowResult = await runSimulationWorkflow(targetTradeDate)
    trackingItems.value = workflowResult.tracking
    simulation.value = workflowResult.simulation
    tradePlans.value = await fetchLatestTradePlans()
    intradayRefreshFailureCount.value = 0
    error.value = ''
  } catch (err) {
    intradayRefreshFailureCount.value += 1
    const message = err instanceof Error ? err.message : '盘中实时刷新失败'
    if (intradayRefreshFailureCount.value >= MAX_INTRADAY_REFRESH_FAILURES) {
      stopIntradayRefresh()
      error.value = `${message}；自动刷新已暂停，请重启服务或手动点击“跟踪并模拟交易”重试`
    } else {
      error.value = message
    }
  } finally {
    intradayRefreshRunning.value = false
  }
}

function configureIntradayRefresh() {
  stopIntradayRefresh()
  intradayRefreshFailureCount.value = 0
  if (!intradayRefreshTargetDate(tradePlans.value, simulation.value)) return
  intradayRefreshTimer.value = window.setInterval(() => {
    void refreshIntradayWorkflow()
  }, INTRADAY_REFRESH_INTERVAL_MS)
}

function stopIntradayRefresh() {
  if (intradayRefreshTimer.value === null) return
  window.clearInterval(intradayRefreshTimer.value)
  intradayRefreshTimer.value = null
}

function navigateToSector(sectorName: string) {
  window.history.pushState({}, '', `/sectors/${encodeURIComponent(sectorName)}`)
  routePath.value = window.location.pathname
  scrollToTop()
}

function navigateToDashboardSection(sectionId = 'sectors') {
  window.history.pushState({}, '', '/')
  routePath.value = window.location.pathname
  planKeyword.value = ''
  window.setTimeout(() => {
    document.querySelector(`#${sectionId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 0)
}

function syncRoutePath() {
  routePath.value = window.location.pathname
}

function formatNineTurn(row: CandidateItem) {
  if (!row.nine_turn_signal || !row.nine_turn_count) return '-'
  return String(row.nine_turn_count)
}

function nineTurnClass(row: CandidateItem) {
  return {
    'nine-turn-sell': row.nine_turn_signal === 'sell',
    'nine-turn-buy': row.nine_turn_signal === 'buy'
  }
}

function scrollToTop() {
  if (navigator.userAgent.toLowerCase().includes('jsdom')) {
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
    return
  }
  try {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch {
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }
}

async function loadPlanDetail(planId: number | undefined) {
  if (!planId) {
    selectedPlanDetail.value = null
    return
  }
  selectedPlanDetail.value = await fetchTradePlanDetail(planId)
}

async function togglePlanDetail(row: TradePlanItem) {
  if (selectedPlanDetail.value?.id === row.id) {
    selectedPlanDetail.value = null
    return
  }
  await loadPlanDetail(row.id)
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

function formatSignedPrice(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${value.toFixed(2)}`
}

function formatSignedPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${value.toFixed(2)}%`
}

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatIndexAmount(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  if (Math.abs(value) >= 1000000000000) return `${(value / 1000000000000).toFixed(3)}万亿`
  if (Math.abs(value) >= 100000000) return `${(value / 100000000).toFixed(2)}亿`
  return value.toLocaleString('zh-CN')
}

function formatTime(value: string | null | undefined) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(new Date(value))
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(new Date(value))
}

function formatStepSummary(value: Record<string, unknown>) {
  const entries = Object.entries(value).filter(([, item]) => item !== null && item !== undefined && item !== '')
  if (!entries.length) return '-'
  return entries.map(([key, item]) => `${key}: ${String(item)}`).join('，')
}

function chinaToday() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(new Date())
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${byType.year}-${byType.month}-${byType.day}`
}

function isTodayInChina(value: string | null | undefined) {
  return Boolean(value) && value === chinaToday()
}

function intradayRefreshTargetDate(
  plans: TradePlansLatestResponse | null | undefined,
  simulationResult: SimulationLatestResponse | null | undefined
) {
  if (isTodayInChina(plans?.target_trade_date)) return plans?.target_trade_date ?? null
  if ((simulationResult?.positions.length ?? 0) > 0) return chinaToday()
  if ((simulationResult?.virtual_positions?.length ?? 0) > 0) return chinaToday()
  return null
}

function sectorRankForDate(row: SectorTopItem, tradeDate: string) {
  return row.rank_history.find((history) => history.trade_date === tradeDate)?.rank_no ?? null
}

function formatRankHistoryDate(value: string | null | undefined) {
  if (!value) return '-'
  const [, , month, day] = value.match(/^(\d{4})-(\d{2})-(\d{2})$/) ?? []
  if (!month || !day) return value
  return `${month}-${day}`
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

function polarityClass(value: number | null | undefined, inverse = false) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) return 'quote-flat'
  const isUp = inverse ? value < 0 : value > 0
  return isUp ? 'quote-up' : 'quote-down'
}

function priceVsClass(value: number | null | undefined, base: number | null | undefined) {
  if (
    value === null ||
    value === undefined ||
    base === null ||
    base === undefined ||
    Number.isNaN(value) ||
    Number.isNaN(base) ||
    value === base
  ) {
    return 'quote-flat'
  }
  return value > base ? 'quote-up' : 'quote-down'
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
    ['排名', '板块', '近5日排名', '今日涨幅', '5日涨幅', '成交额代理变化', '涨停数', '强势股数', '评分'],
    filteredSectors.value.map((item) => [
      item.rank_no,
      item.sector_name,
      item.rank_history.map((history) => `${history.trade_date}:${history.rank_no ? `#${history.rank_no}` : '-'}`).join(' / '),
      item.daily_return,
      item.five_day_return,
      item.amount_change,
      item.limit_up_count,
      item.strong_stock_count,
      item.sector_score
    ])
  )
}

function exportCandidates() {
  exportCsv(
    `candidates-${candidates.value?.trade_date ?? 'latest'}${selectedSectorName.value ? `-${selectedSectorName.value}` : ''}.csv`,
    ['股票代码', '股票名称', '板块', '板块排名', '策略', '个股评分', '板块评分', '收盘价', '成交额', '入选理由', '风险提示'],
    filteredCandidates.value.map((item) => [
      item.stock_code,
      item.stock_name,
      item.sector_name,
      item.sector_rank,
      item.strategy_type,
      item.stock_score,
      item.sector_score,
      item.close_price,
      item.amount,
      item.reason,
      item.risk_note
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
    const result = await trackRealtimeTradePlans(tradePlans.value.target_trade_date, markUntriggeredAtClose)
    await loadDashboard()
    trackingItems.value = result.items
    const realtime = result.realtime
    const realtimeText = realtime?.skipped_reason
      ? `，实时行情：${realtime.skipped_reason}`
      : realtime
        ? `，实时行情更新 ${realtime.fetched_stock_daily_rows} 条`
        : ''
    ElMessage.success(`已更新 ${result.items.length} 条计划状态${realtimeText}`)
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
    const realtimeResult = await trackRealtimeTradePlans(tradePlans.value.target_trade_date)
    trackingItems.value = realtimeResult.items
    const result = await runSimulationWorkflow(tradePlans.value.target_trade_date)
    simulation.value = result.simulation
    await loadDashboard()
    trackingItems.value = result.tracking
    const realtime = realtimeResult.realtime
    const realtimeText = realtime?.skipped_reason
      ? `，实时行情：${realtime.skipped_reason}`
      : realtime
        ? `，实时行情更新 ${realtime.fetched_stock_daily_rows} 条`
        : ''
    ElMessage.success(`已实时跟踪 ${result.tracking.length} 条计划，并模拟到 ${result.simulation.as_of_date}${realtimeText}`)
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

function navigateToSimulation() {
  window.history.pushState({}, '', '/simulation')
  routePath.value = window.location.pathname
  document.querySelector('#simulation')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(async () => {
  window.addEventListener('popstate', syncRoutePath)
  await loadDashboard()
  if (window.location.pathname === '/simulation') {
    document.querySelector('#simulation')?.scrollIntoView({ block: 'start' })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('popstate', syncRoutePath)
  stopIntradayRefresh()
})
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
          <span>强势行业</span>
        </a>
        <a class="nav-item" href="#stock-pool">
          <el-icon><DataAnalysis /></el-icon>
          <span>股票池</span>
        </a>
        <a class="nav-item" href="#plans">
          <el-icon><Finished /></el-icon>
          <span>交易计划</span>
        </a>
        <a v-if="selectedPlanDetail" class="nav-item" href="#plan-detail">
          <el-icon><DataAnalysis /></el-icon>
          <span>股票详情</span>
        </a>
        <a class="nav-item" href="#tracking">
          <el-icon><Refresh /></el-icon>
          <span>盘中跟踪</span>
        </a>
        <a class="nav-item" href="/simulation" @click.prevent="navigateToSimulation">
          <el-icon><Connection /></el-icon>
          <span>模拟交易</span>
        </a>
        <a class="nav-item" href="#review">
          <el-icon><Calendar /></el-icon>
          <span>交易复盘</span>
        </a>
        <a class="nav-item" href="#data-monitor">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据健康</span>
        </a>
      </nav>
    </aside>

    <section class="workspace" v-loading="loading">
      <header class="toolbar">
        <div class="index-ticker-strip" aria-label="主要指数行情">
          <span
            v-for="(item, index) in indexTicker?.items ?? []"
            :key="item.name"
            class="index-ticker-item"
            :class="polarityClass(item.pct_chg)"
          >
            <strong>{{ item.name }}</strong>
            <template v-if="item.available">
              <span>{{ formatPrice(item.close) }}</span>
              <span class="ticker-value-separator">｜</span>
              <span>{{ formatSignedPrice(item.change) }}</span>
              <span class="ticker-value-separator">｜</span>
              <span>{{ formatSignedPercent(item.pct_chg) }}</span>
              <span class="ticker-value-separator">｜</span>
              <span>{{ formatIndexAmount(item.amount) }}</span>
            </template>
            <span v-else class="ticker-empty">暂无</span>
            <span v-if="index < (indexTicker?.items.length ?? 0) - 1" class="ticker-separator">｜</span>
          </span>
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

      <template v-if="isSectorDetailPage">
        <section class="panel sector-detail-panel">
          <div class="section-heading table-heading">
            <div>
              <h2>行业详情：{{ selectedSectorName }}</h2>
              <p>交易日：{{ sectors?.trade_date ?? '-' }}，集中查看该行业候选股票和交易计划。</p>
            </div>
            <div class="table-tools">
              <el-button @click="navigateToDashboardSection('sectors')">返回强势行业</el-button>
              <el-button :icon="Download" :disabled="!filteredCandidates.length" @click="exportCandidates">导出候选</el-button>
            </div>
          </div>

          <section v-if="selectedSector" class="metric-grid sector-detail-grid">
            <article class="metric primary-metric">
              <el-icon><TrendCharts /></el-icon>
              <div>
                <span>行业排名</span>
                <strong>{{ selectedSector.rank_no }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><DataAnalysis /></el-icon>
              <div>
                <span>板块评分</span>
                <strong>{{ selectedSector.sector_score }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Finished /></el-icon>
              <div>
                <span>今日 / 5日涨幅</span>
                <strong>
                  <span :class="polarityClass(selectedSector.daily_return)">{{ formatPercent(selectedSector.daily_return) }}</span>
                  /
                  <span :class="polarityClass(selectedSector.five_day_return)">{{ formatPercent(selectedSector.five_day_return) }}</span>
                </strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Connection /></el-icon>
              <div>
                <span>涨停 / 强势股</span>
                <strong>{{ selectedSector.limit_up_count }} / {{ selectedSector.strong_stock_count }}</strong>
              </div>
            </article>
          </section>
          <el-alert
            v-else
            title="当前行业不在最新 Top 10 中，请返回强势行业选择。"
            type="warning"
            :closable="false"
            show-icon
          />
        </section>

        <section class="panel">
          <div class="section-heading table-heading">
            <div>
              <h2>该行业候选股票</h2>
              <p>展示候选股票、策略、评分、入选理由和风险提示。</p>
            </div>
          </div>

          <el-table :data="filteredCandidates" border stripe empty-text="暂无该行业候选股票">
            <el-table-column label="股票" min-width="150" sortable prop="stock_name">
              <template #default="{ row }: { row: CandidateItem }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="sector_rank" label="行业排名" min-width="110" sortable />
            <el-table-column prop="strategy_type" label="策略" min-width="120" sortable />
            <el-table-column label="评分" min-width="110" sortable prop="stock_score">
              <template #default="{ row }: { row: CandidateItem }">{{ row.stock_score }} / {{ row.sector_score }}</template>
            </el-table-column>
            <el-table-column label="收盘价" min-width="110" sortable prop="close_price">
              <template #default="{ row }: { row: CandidateItem }">{{ formatPrice(row.close_price) }}</template>
            </el-table-column>
            <el-table-column label="成交额" min-width="130" sortable prop="amount">
              <template #default="{ row }: { row: CandidateItem }">{{ formatLargeAmount(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="入选理由" min-width="300" show-overflow-tooltip />
            <el-table-column prop="risk_note" label="风险提示" min-width="260" show-overflow-tooltip />
          </el-table>
        </section>

        <section class="panel">
          <div class="section-heading table-heading">
            <div>
              <h2>该行业交易计划</h2>
              <p>只展示目标交易日属于 {{ selectedSectorName }} 的交易计划。</p>
            </div>
          </div>

          <el-table :data="sectorTradePlans" border stripe empty-text="暂无该板块交易计划">
            <el-table-column label="股票" min-width="150" sortable prop="stock_name">
              <template #default="{ row }: { row: TradePlanItem }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
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
            <el-table-column prop="risk_note" label="风险提示" min-width="260" show-overflow-tooltip />
          </el-table>
        </section>
      </template>

      <template v-else>
      <section id="decision" class="panel">
        <div class="section-heading">
          <div>
            <h2>今日决策面板</h2>
            <p>最近 {{ marketHistory.length }} 个交易日，最新日期排第一行。</p>
          </div>
          <el-tag :type="marketTagType" size="large">{{ market?.market_status ?? '待生成' }}</el-tag>
        </div>

        <el-table class="market-history-table" :data="marketHistory" border stripe max-height="320" empty-text="暂无市场环境数据">
          <el-table-column prop="trade_date" label="交易日" min-width="120" sortable />
          <el-table-column prop="market_status" label="市场状态" min-width="100" sortable>
            <template #default="{ row }: { row: MarketLatestResponse }">
              <el-tag :type="marketStatusType(row.market_status)">{{ row.market_status || '-' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="market_score" label="评分" min-width="90" sortable />
          <el-table-column prop="suggested_position" label="建议总仓位" min-width="120" sortable />
          <el-table-column label="上涨 / 下跌" min-width="120">
            <template #default="{ row }: { row: MarketLatestResponse }">{{ row.up_count ?? '-' }} / {{ row.down_count ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="涨停 / 跌停" min-width="120">
            <template #default="{ row }: { row: MarketLatestResponse }">{{ row.limit_up_count ?? '-' }} / {{ row.limit_down_count ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="limit_up_height" label="连板高度" min-width="100" sortable />
          <el-table-column label="全市场成交额" min-width="140" sortable prop="total_amount">
            <template #default="{ row }: { row: MarketLatestResponse }">{{ formatLargeAmount(row.total_amount) }}</template>
          </el-table-column>
        </el-table>

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
            <h2>强势行业</h2>
            <p>交易日：{{ sectors?.trade_date ?? '-' }}，主榜只展示东财一级行业 Top {{ sectors?.items.length ?? 0 }}；概念题材不再与行业混排。</p>
          </div>
          <div class="table-tools">
            <el-input v-model="sectorKeyword" clearable placeholder="筛选行业" />
            <el-button :icon="Download" :disabled="!filteredSectors.length" @click="exportSectors">导出</el-button>
          </div>
        </div>

        <el-table :data="filteredSectors" border stripe empty-text="暂无强势行业数据">
          <el-table-column prop="rank_no" label="排名" width="88" sortable>
            <template #default="{ row }: { row: SectorTopItem }">
              <el-tag :type="row.rank_no <= 3 ? 'success' : 'info'">{{ row.rank_no }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sector_name" label="行业" min-width="150" sortable>
            <template #default="{ row }: { row: SectorTopItem }">
              <el-button link type="primary" @click="navigateToSector(row.sector_name)">{{ row.sector_name }}</el-button>
            </template>
          </el-table-column>
          <el-table-column label="近5日排名" align="center">
            <el-table-column
              v-for="tradeDate in sectorRankHistoryDates"
              :key="tradeDate"
              :label="formatRankHistoryDate(tradeDate)"
              align="center"
              width="76"
            >
              <template #default="{ row }: { row: SectorTopItem }">
                <span class="rank-history-rank" :class="{ missing: !sectorRankForDate(row, tradeDate) }">
                  {{ sectorRankForDate(row, tradeDate) ?? '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table-column>
          <el-table-column prop="daily_return" label="今日涨幅" min-width="120" sortable>
            <template #default="{ row }: { row: SectorTopItem }">
              <span :class="polarityClass(row.daily_return)">{{ formatPercent(row.daily_return) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="five_day_return" label="5日涨幅" min-width="120" sortable>
            <template #default="{ row }: { row: SectorTopItem }">
              <span :class="polarityClass(row.five_day_return)">{{ formatPercent(row.five_day_return) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="amount_change" label="成交额代理" min-width="140" sortable>
            <template #default="{ row }: { row: SectorTopItem }">{{ formatLargeAmount(row.amount_change) }}</template>
          </el-table-column>
          <el-table-column prop="limit_up_count" label="涨停" min-width="90" sortable />
          <el-table-column prop="strong_stock_count" label="强势股" min-width="100" sortable />
          <el-table-column prop="sector_score" label="评分" min-width="90" sortable />
        </el-table>
      </section>

      <section id="stock-pool" class="panel stock-pool-panel">
        <div class="section-heading table-heading">
          <div>
            <h2>股票池</h2>
            <p>交易日：{{ candidates?.trade_date ?? '-' }}，按核心主升 5 / 稳定强势 3 / 强势延续 2 生成股票池；不足 10 只则宁缺毋滥。今日交易计划对股票池全部生成。</p>
          </div>
          <div class="table-tools">
            <el-button :icon="Download" :disabled="!stockPoolTop10.length" @click="exportCandidates">导出候选</el-button>
          </div>
        </div>

        <el-table :data="stockPoolTop10" border stripe empty-text="暂无股票池数据" class="stock-pool-table">
          <el-table-column label="排名" width="62" align="center">
            <template #default="{ row }: { row: CandidateItem }">{{ row.stock_pool_rank ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="股票" min-width="116" sortable prop="stock_name">
            <template #default="{ row }: { row: CandidateItem }">
              <strong>{{ row.stock_name }}</strong>
              <small class="muted-code">{{ row.stock_code }}</small>
            </template>
          </el-table-column>
          <el-table-column prop="sector_name" label="行业" min-width="88" sortable>
            <template #default="{ row }: { row: CandidateItem }">
              <el-button link type="primary" @click="navigateToSector(row.sector_name)">{{ row.sector_name }}</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="sector_rank" label="行业排名" width="88" sortable />
          <el-table-column prop="sector_category" label="行业类型" width="100" sortable />
          <el-table-column prop="strategy_type" label="策略" min-width="92" sortable />
          <el-table-column label="九转" width="76" sortable prop="nine_turn_count">
            <template #default="{ row }: { row: CandidateItem }">
              <span :class="nineTurnClass(row)">{{ formatNineTurn(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="评分" width="92" sortable prop="stock_score">
            <template #default="{ row }: { row: CandidateItem }">{{ row.stock_score }} / {{ row.sector_score }}</template>
          </el-table-column>
          <el-table-column label="收盘" width="82" sortable prop="close_price">
            <template #default="{ row }: { row: CandidateItem }">{{ formatPrice(row.close_price) }}</template>
          </el-table-column>
          <el-table-column label="成交额" width="96" sortable prop="amount">
            <template #default="{ row }: { row: CandidateItem }">{{ formatLargeAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="入选理由" min-width="150" show-overflow-tooltip />
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

        <section v-if="filteredTradePlans.length" class="plan-card-grid">
          <article v-for="row in filteredTradePlans" :key="row.id" class="plan-card">
            <header class="plan-card-header">
              <div>
                <button
                  type="button"
                  class="plan-stock-button"
                  :aria-expanded="selectedPlanDetail?.id === row.id"
                  @click="togglePlanDetail(row)"
                >
                  <strong>{{ row.stock_name }}</strong>
                  <small class="muted-code">{{ row.stock_code }} · {{ row.sector_name }}</small>
                </button>
              </div>
              <div class="plan-tags">
                <el-tag :type="planStatusType(row.status)">{{ row.status }}</el-tag>
                <el-tag :type="row.is_watched ? 'success' : 'info'">{{ row.is_watched ? '已关注' : '未关注' }}</el-tag>
              </div>
            </header>

            <div class="plan-card-meta">
              <span>{{ row.strategy_type }}</span>
              <span>评分 {{ row.stock_score }} / {{ row.sector_score }}</span>
              <span>仓位 {{ formatPosition(row.position_ratio) }}</span>
            </div>

            <p class="plan-condition">{{ row.buy_condition }}</p>

            <dl class="plan-price-grid">
              <div>
                <dt>买入区间</dt>
                <dd>{{ formatPrice(row.buy_price_low) }} - {{ formatPrice(row.buy_price_high) }}</dd>
              </div>
              <div>
                <dt>止损</dt>
                <dd class="quote-down">{{ formatPrice(row.stop_loss_price) }}</dd>
              </div>
              <div>
                <dt>止盈</dt>
                <dd class="quote-up">{{ formatPrice(row.take_profit_price) }}</dd>
              </div>
              <div>
                <dt>触发价</dt>
                <dd :class="priceVsClass(row.trigger_price, row.buy_price_low)">{{ formatPrice(row.trigger_price) }}</dd>
              </div>
            </dl>

            <p v-if="row.tracking_note" class="plan-note">{{ row.tracking_note }}</p>
            <p class="plan-risk">{{ row.risk_note }}</p>

            <footer class="plan-card-actions">
              <el-button size="small" :disabled="planTrackingLoading" @click="togglePlanWatch(row)">
                {{ row.is_watched ? '取消关注' : '关注' }}
              </el-button>
              <el-button size="small" :disabled="planTrackingLoading" @click="setPlanStatus(row, '已触发')">触发</el-button>
              <el-button size="small" type="danger" :disabled="planTrackingLoading" @click="setPlanStatus(row, '取消')">取消</el-button>
            </footer>
          </article>
        </section>
        <el-empty v-else description="暂无交易计划数据" />
      </section>

      <section v-if="selectedPlanDetail" id="plan-detail" class="panel">
        <div class="section-heading">
          <div>
            <h2>股票详情</h2>
            <p>{{ selectedPlanDetail ? `${selectedPlanDetail.stock_name} ${selectedPlanDetail.stock_code}` : '请选择一条交易计划' }}</p>
          </div>
          <el-tag v-if="selectedPlanDetail" :type="planStatusType(selectedPlanDetail.status)">
            {{ selectedPlanDetail.status }}
          </el-tag>
        </div>

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
          <el-table-column prop="sector_name" label="板块" min-width="120" sortable />
          <el-table-column label="当前价" min-width="100" sortable prop="current_price">
            <template #default="{ row }: { row: TradePlanItem & { current_price: number | null, buy_price_low: number | null } }">
              <span :class="priceVsClass(row.current_price, row.buy_price_low)">{{ formatPrice(row.current_price) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" min-width="100" sortable prop="pct_chg">
            <template #default="{ row }: { row: TradePlanItem & { pct_chg: number | null } }">
              <span :class="polarityClass(row.pct_chg)">{{ formatPercent(row.pct_chg) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="buy_condition" label="买入条件" min-width="260" show-overflow-tooltip />
          <el-table-column label="触发" min-width="90" sortable prop="status">
            <template #default="{ row }: { row: TradePlanItem }">
              <el-tag :type="planStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发时间" min-width="160" prop="trigger_time">
            <template #default="{ row }: { row: TradePlanItem }">{{ formatDateTime(row.trigger_time) }}</template>
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
                <strong>
                  <span :class="polarityClass(simulation.account.total_return)">{{ formatReturn(simulation.account.total_return) }}</span>
                  /
                  <span :class="polarityClass(simulation.risk.max_drawdown, true)">{{ formatReturn(simulation.risk.max_drawdown) }}</span>
                </strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><Calendar /></el-icon>
              <div>
                <span>当日盈亏 / 今日收益率</span>
                <strong>
                  <span :class="polarityClass(simulation.equity_curve.at(-1)?.daily_profit)">{{ formatMoney(simulation.equity_curve.at(-1)?.daily_profit) }}</span>
                  /
                  <span :class="polarityClass(simulation.equity_curve.at(-1)?.daily_return)">{{ formatReturn(simulation.equity_curve.at(-1)?.daily_return) }}</span>
                </strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><DataAnalysis /></el-icon>
              <div>
                <span>胜率 / 盈亏比</span>
                <strong>{{ formatReturn(simulation.risk.win_rate) }} / {{ simulation.risk.profit_loss_ratio ?? '-' }}</strong>
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

          <div class="table-subheading">
            <h3>模拟持仓</h3>
          </div>
          <el-table class="value-fit-table" :data="simulation.positions" border stripe max-height="260" empty-text="暂无模拟持仓">
            <el-table-column label="股票" width="96" sortable prop="stock_name">
              <template #default="{ row }: { row: SimulationPosition }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="sector_name" label="板块" width="58" sortable />
            <el-table-column prop="strategy_type" label="策略" width="84" sortable />
            <el-table-column prop="quantity" label="数量" width="68" sortable />
            <el-table-column label="成本/现价" width="116">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatPrice(row.buy_price) }} /
                <span :class="priceVsClass(row.current_price, row.buy_price)">{{ formatPrice(row.current_price) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="市值" width="108" sortable prop="market_value">
              <template #default="{ row }: { row: SimulationPosition }">{{ formatMoney(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="浮盈亏" width="132" sortable prop="unrealized_profit">
              <template #default="{ row }: { row: SimulationPosition }">
                <span class="profit-stack">
                  <span :class="polarityClass(row.unrealized_profit)">{{ formatMoney(row.unrealized_profit) }}</span>
                  <span :class="polarityClass(row.unrealized_return)">{{ formatReturn(row.unrealized_return) }}</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="持仓天数" width="58" sortable prop="holding_days">
              <template #default="{ row }: { row: SimulationPosition }">{{ row.holding_days || '-' }}</template>
            </el-table-column>
            <el-table-column label="止损/第一止盈" width="110">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatPrice(row.stop_loss_price) }} / {{ formatPrice(row.take_profit_price) }}
              </template>
            </el-table-column>
            <el-table-column prop="buy_reason" label="买入原因" min-width="160" show-overflow-tooltip />
            <el-table-column prop="position_status" label="状态" width="66" sortable />
          </el-table>

          <div class="table-subheading">
            <h3>模拟交易记录</h3>
          </div>
          <el-table class="value-fit-table" :data="simulationTrades" border stripe max-height="300" empty-text="暂无模拟交易记录">
            <el-table-column label="时间" width="64" sortable prop="trade_time">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatTime(row.trade_time) }}</template>
            </el-table-column>
            <el-table-column prop="trade_type" label="方向" width="54" sortable />
            <el-table-column label="股票" width="96" sortable prop="stock_name">
              <template #default="{ row }: { row: SimulationTrade }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column label="价格/数量" width="100">
              <template #default="{ row }: { row: SimulationTrade }">
                {{ formatPrice(row.price) }} / {{ row.quantity }}
              </template>
            </el-table-column>
            <el-table-column label="成交金额" width="104" sortable prop="amount">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="费用" width="68" sortable prop="total_fee">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.total_fee) }}</template>
            </el-table-column>
            <el-table-column label="交易后现金" width="108" sortable prop="cash_after">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.cash_after) }}</template>
            </el-table-column>
            <el-table-column label="交易后仓位" width="64" sortable prop="position_ratio_after">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatPosition(row.position_ratio_after) }}</template>
            </el-table-column>
            <el-table-column label="盈亏" width="132" sortable prop="display_profit_loss">
              <template #default="{ row }: { row: SimulationTrade & { display_profit_loss: number | null, display_profit_loss_return: number | null } }">
                <span class="profit-stack">
                  <span :class="polarityClass(row.display_profit_loss)">{{ formatMoney(row.display_profit_loss) }}</span>
                  <span :class="polarityClass(row.display_profit_loss_return)">{{ formatReturn(row.display_profit_loss_return) }}</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="持仓天数" width="58" sortable prop="holding_days">
              <template #default="{ row }: { row: SimulationTrade }">{{ row.holding_days || '-' }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
          </el-table>

          <div class="table-subheading">
            <h3>资金曲线</h3>
          </div>
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
              <template #default="{ row }: { row: SimulationEquityPoint }">
                <span :class="polarityClass(row.daily_return)">{{ formatReturn(row.daily_return) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最大回撤" min-width="110" sortable prop="max_drawdown">
              <template #default="{ row }: { row: SimulationEquityPoint }">
                <span :class="polarityClass(row.max_drawdown, true)">{{ formatReturn(row.max_drawdown) }}</span>
              </template>
            </el-table-column>
          </el-table>

          <div class="table-subheading virtual-heading">
            <h3>虚拟交易</h3>
            <span>每只触发股票独立按 100 万本金 × 计划仓位验证，不计入资金曲线。</span>
          </div>

          <div class="table-subheading">
            <h3>虚拟持仓</h3>
          </div>
          <el-table class="value-fit-table" :data="simulation.virtual_positions ?? []" border stripe max-height="260" empty-text="暂无虚拟持仓">
            <el-table-column label="股票" width="96" sortable prop="stock_name">
              <template #default="{ row }: { row: SimulationPosition }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="sector_name" label="板块" width="58" sortable />
            <el-table-column prop="strategy_type" label="策略" width="84" sortable />
            <el-table-column prop="quantity" label="数量" width="68" sortable />
            <el-table-column label="成本/现价" width="116">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatPrice(row.buy_price) }} /
                <span :class="priceVsClass(row.current_price, row.buy_price)">{{ formatPrice(row.current_price) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="市值" width="108" sortable prop="market_value">
              <template #default="{ row }: { row: SimulationPosition }">{{ formatMoney(row.market_value) }}</template>
            </el-table-column>
            <el-table-column label="浮盈亏" width="132" sortable prop="unrealized_profit">
              <template #default="{ row }: { row: SimulationPosition }">
                <span class="profit-stack">
                  <span :class="polarityClass(row.unrealized_profit)">{{ formatMoney(row.unrealized_profit) }}</span>
                  <span :class="polarityClass(row.unrealized_return)">{{ formatReturn(row.unrealized_return) }}</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="持仓天数" width="58" sortable prop="holding_days">
              <template #default="{ row }: { row: SimulationPosition }">{{ row.holding_days || '-' }}</template>
            </el-table-column>
            <el-table-column label="止损/第一止盈" width="110">
              <template #default="{ row }: { row: SimulationPosition }">
                {{ formatPrice(row.stop_loss_price) }} / {{ formatPrice(row.take_profit_price) }}
              </template>
            </el-table-column>
            <el-table-column prop="buy_reason" label="买入原因" min-width="160" show-overflow-tooltip />
            <el-table-column prop="position_status" label="状态" width="66" sortable />
          </el-table>

          <div class="table-subheading">
            <h3>虚拟交易记录</h3>
            <span>胜率 {{ formatReturn(simulation.virtual_risk?.win_rate ?? 0) }} / 盈亏比 {{ simulation.virtual_risk?.profit_loss_ratio ?? '-' }}</span>
          </div>
          <el-table class="value-fit-table" :data="virtualTrades" border stripe max-height="300" empty-text="暂无虚拟交易记录">
            <el-table-column label="时间" width="64" sortable prop="trade_time">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatTime(row.trade_time) }}</template>
            </el-table-column>
            <el-table-column prop="trade_type" label="方向" width="54" sortable />
            <el-table-column label="股票" width="96" sortable prop="stock_name">
              <template #default="{ row }: { row: SimulationTrade }">
                <strong>{{ row.stock_name }}</strong>
                <small class="muted-code">{{ row.stock_code }}</small>
              </template>
            </el-table-column>
            <el-table-column label="价格/数量" width="100">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatPrice(row.price) }} / {{ row.quantity }}</template>
            </el-table-column>
            <el-table-column label="成交金额" width="104" sortable prop="amount">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="费用" width="68" sortable prop="total_fee">
              <template #default="{ row }: { row: SimulationTrade }">{{ formatMoney(row.total_fee) }}</template>
            </el-table-column>
            <el-table-column label="盈亏" width="132" sortable prop="display_profit_loss">
              <template #default="{ row }: { row: SimulationTrade & { display_profit_loss: number | null, display_profit_loss_return: number | null } }">
                <span class="profit-stack">
                  <span :class="polarityClass(row.display_profit_loss)">{{ formatMoney(row.display_profit_loss) }}</span>
                  <span :class="polarityClass(row.display_profit_loss_return)">{{ formatReturn(row.display_profit_loss_return) }}</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="持仓天数" width="58" sortable prop="holding_days">
              <template #default="{ row }: { row: SimulationTrade }">{{ row.holding_days || '-' }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
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
                <strong :class="polarityClass(tradeReviews.avg_day_return)">{{ formatReturn(tradeReviews.avg_day_return) }}</strong>
              </div>
            </article>
            <article class="metric">
              <el-icon><DataAnalysis /></el-icon>
              <div>
                <span>T+5 均收益</span>
                <strong :class="polarityClass(tradeReviews.avg_t5_return)">{{ formatReturn(tradeReviews.avg_t5_return) }}</strong>
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
              <template #default="{ row }: { row: TradeReviewGroupStats }">
                <span :class="polarityClass(row.avg_day_return)">{{ formatReturn(row.avg_day_return) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="T+5 均收益" min-width="120" sortable prop="avg_t5_return">
              <template #default="{ row }: { row: TradeReviewGroupStats }">
                <span :class="polarityClass(row.avg_t5_return)">{{ formatReturn(row.avg_t5_return) }}</span>
              </template>
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
              <template #default="{ row }: { row: TradeReviewItem }">
                <span :class="polarityClass(row.day_return)">{{ formatReturn(row.day_return) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="T+5收益" min-width="110" sortable prop="t5_return">
              <template #default="{ row }: { row: TradeReviewItem }">
                <span :class="polarityClass(row.t5_return)">{{ formatReturn(row.t5_return) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最大浮盈/浮亏" min-width="150">
              <template #default="{ row }: { row: TradeReviewItem }">
                <span :class="polarityClass(row.max_profit)">{{ formatReturn(row.max_profit) }}</span>
                /
                <span :class="polarityClass(row.max_loss)">{{ formatReturn(row.max_loss) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="result" label="结果" min-width="100" sortable />
            <el-table-column prop="failure_reason" label="失败原因" min-width="130" show-overflow-tooltip />
            <el-table-column prop="note" label="备注" min-width="220" show-overflow-tooltip />
          </el-table>
        </template>
        <el-empty v-else description="暂无复盘统计数据，请先运行复盘生成命令" />
      </section>

      <section id="data-monitor" class="panel data-monitor-panel">
        <div class="section-heading table-heading">
          <div>
            <h2>数据拉取与数据库健康</h2>
            <p>交易日：{{ databaseHealth?.trade_date || latestDataRun?.trade_date || '-' }}，展示夜间任务证据和系统数据完整性。</p>
          </div>
          <el-tag :type="monitorStatusType(databaseHealth?.status)" size="large">
            {{ databaseHealth?.status ?? '待检查' }}
          </el-tag>
        </div>

        <section class="monitor-summary-grid">
          <article class="metric">
            <el-icon><Refresh /></el-icon>
            <div>
              <span>最近拉取状态</span>
              <strong>
                <el-tag :type="monitorStatusType(latestDataRun?.status)">{{ latestDataRun?.status ?? '无日志' }}</el-tag>
              </strong>
            </div>
          </article>
          <article class="metric">
            <el-icon><Calendar /></el-icon>
            <div>
              <span>开始 / 结束</span>
              <strong>{{ formatDateTime(latestDataRun?.started_at) }} / {{ formatDateTime(latestDataRun?.ended_at) }}</strong>
            </div>
          </article>
          <article class="metric">
            <el-icon><DataAnalysis /></el-icon>
            <div>
              <span>数据库健康</span>
              <strong>
                <el-tag :type="monitorStatusType(databaseHealth?.status)">{{ databaseHealth?.status ?? '待检查' }}</el-tag>
              </strong>
            </div>
          </article>
        </section>

        <el-alert
          v-if="latestDataRun?.message"
          class="suggestion-alert"
          :title="latestDataRun.message"
          :type="monitorStatusType(latestDataRun.status)"
          :closable="false"
          show-icon
        />

        <el-table :data="latestDataRun?.steps ?? []" border stripe max-height="320" empty-text="暂无夜间数据拉取日志">
          <el-table-column prop="step_name" label="步骤" min-width="150" />
          <el-table-column prop="status" label="状态" min-width="100" sortable>
            <template #default="{ row }: { row: DataJobStepItem }">
              <el-tag :type="monitorStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始 / 结束" min-width="170">
            <template #default="{ row }: { row: DataJobStepItem }">
              {{ formatDateTime(row.started_at) }} / {{ formatDateTime(row.ended_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="rows_count" label="行数" min-width="90" sortable />
          <el-table-column label="拉取/生成内容" min-width="360" show-overflow-tooltip>
            <template #default="{ row }: { row: DataJobStepItem }">{{ formatStepSummary(row.summary) }}</template>
          </el-table-column>
          <el-table-column prop="error_message" label="报错" min-width="220" show-overflow-tooltip />
        </el-table>

        <el-table :data="databaseHealth?.items ?? []" border stripe empty-text="暂无数据库健康检查">
          <el-table-column prop="name" label="检查项" min-width="140" />
          <el-table-column prop="status" label="状态" min-width="100" sortable>
            <template #default="{ row }: { row: DatabaseHealthItem }">
              <el-tag :type="monitorStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="actual" label="实际" min-width="140" />
          <el-table-column prop="expected" label="要求" min-width="220" show-overflow-tooltip />
          <el-table-column prop="message" label="说明" min-width="240" show-overflow-tooltip />
          <el-table-column label="补数据命令" min-width="300" show-overflow-tooltip>
            <template #default="{ row }: { row: DatabaseHealthItem }">
              <code v-if="row.fix_command" class="command-text">{{ row.fix_command }}</code>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>

        <el-table :data="dataRuns?.items ?? []" border stripe max-height="260" empty-text="暂无历史拉取任务">
          <el-table-column prop="trade_date" label="交易日" min-width="110" sortable />
          <el-table-column prop="status" label="状态" min-width="100" sortable>
            <template #default="{ row }: { row: DataJobRunItem }">
              <el-tag :type="monitorStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始 / 结束" min-width="180">
            <template #default="{ row }: { row: DataJobRunItem }">
              {{ formatDateTime(row.started_at) }} / {{ formatDateTime(row.ended_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="message" label="结论" min-width="260" show-overflow-tooltip />
          <el-table-column prop="command" label="命令" min-width="300" show-overflow-tooltip>
            <template #default="{ row }: { row: DataJobRunItem }">
              <code class="command-text">{{ row.command }}</code>
            </template>
          </el-table-column>
        </el-table>
      </section>
      </template>
    </section>
  </main>
</template>
