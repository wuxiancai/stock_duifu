const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)

  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

async function sendJson<T>(path: string, method: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export interface MarketLatestResponse {
  trade_date: string
  market_score: number
  market_status: string
  suggested_position: string
  up_count: number
  down_count: number
  limit_up_count: number
  limit_down_count: number
  limit_up_height: number
  total_amount: number
  suggestion: string
}

export interface SectorTopItem {
  rank_no: number
  sector_name: string
  daily_return: number
  five_day_return: number
  three_day_return: number
  amount_change: number
  limit_up_count: number
  strong_stock_count: number
  sector_score: number
  rank_history: Array<{
    trade_date: string
    rank_no: number | null
  }>
}

export interface SectorTopResponse {
  trade_date: string
  items: SectorTopItem[]
}

export interface TradePlanItem {
  id: number
  stock_code: string
  stock_name: string
  sector_name: string
  strategy_type: string
  stock_score: number
  sector_score: number
  market_status: string
  buy_condition: string
  buy_price_low: number
  buy_price_high: number
  stop_loss_price: number
  take_profit_price: number
  position_ratio: number
  status: string
  trigger_price: number | null
  trigger_time: string | null
  tracking_note: string
  is_watched: boolean
  risk_note: string
  current_price?: number | null
  pct_chg?: number | null
}

export interface CandidateItem {
  stock_code: string
  stock_name: string
  sector_name: string
  sector_rank: number
  strategy_type: string
  stock_score: number
  sector_score: number
  close_price: number
  amount: number
  reason: string
  risk_note: string
}

export interface CandidateLatestResponse {
  trade_date: string
  items: CandidateItem[]
}

export interface TradePlanDetail extends TradePlanItem {
  selection_reason: string
  key_indicators: {
    ma5: number | null
    ma10: number | null
    ma20: number | null
    amount: number | null
    turnover_rate: number | null
    atr14: number | null
  }
}

export interface TradePlansLatestResponse {
  plan_date: string
  target_trade_date: string
  items: TradePlanItem[]
}

export interface TradePlanTrackingResponse {
  target_trade_date: string
  items: Array<{
    id: number
    stock_code: string
    stock_name: string
    status: string
    current_price: number | null
    pct_chg: number | null
    trigger_price: number | null
    tracking_note: string
  }>
  realtime?: {
    target_trade_date: string
    china_today: string
    provider: string
    planned_stock_count: number
    existing_stock_count: number
    requested_stock_count: number
    fetched_stock_daily_rows: number
    target_is_open: boolean | null
    missing_stock_codes: string[]
    skipped_reason: string
  }
}

export interface TradeReviewGroupStats {
  name: string
  total_count: number
  triggered_count: number
  win_count: number
  win_rate: number
  avg_day_return: number | null
  avg_t5_return: number | null
}

export interface TradeReviewItem {
  id: number
  trade_plan_id: number
  trade_date: string
  stock_code: string
  stock_name: string
  sector_name: string
  strategy_type: string
  triggered: boolean
  trigger_price: number | null
  close_price: number | null
  day_return: number | null
  t5_return: number | null
  max_profit: number | null
  max_loss: number | null
  result: string
  failure_reason: string | null
  discipline_check: boolean
  note: string
}

export interface TradeReviewLatestResponse {
  review_date: string
  total_count: number
  triggered_count: number
  win_count: number
  win_rate: number
  avg_day_return: number | null
  avg_t5_return: number | null
  strategy_stats: TradeReviewGroupStats[]
  sector_stats: TradeReviewGroupStats[]
  items: TradeReviewItem[]
}

export interface SimulationAccount {
  id: number
  account_name: string
  initial_cash: number
  available_cash: number
  frozen_cash: number
  market_value: number
  total_assets: number
  total_profit: number
  total_return: number
  max_drawdown: number
}

export interface SimulationPosition {
  id: number
  stock_code: string
  stock_name: string
  sector_name: string
  strategy_type: string
  buy_price: number
  current_price: number
  quantity: number
  market_value: number
  cost_amount: number
  unrealized_profit: number
  unrealized_return: number
  stop_loss_price: number
  take_profit_price: number
  position_status: string
  buy_reason: string
  sell_reason: string
}

export interface SimulationTrade {
  id: number
  trade_plan_id: number
  stock_code: string
  stock_name: string
  trade_date: string
  trade_time: string
  trade_type: string
  price: number
  quantity: number
  amount: number
  commission: number
  stamp_tax: number
  transfer_fee: number
  total_fee: number
  net_amount: number
  cash_after: number
  position_ratio_after: number
  profit_loss: number | null
  profit_loss_return: number | null
  reason: string
}

export interface SimulationEquityPoint {
  trade_date: string
  available_cash: number
  market_value: number
  total_assets: number
  daily_profit: number
  daily_return: number
  max_drawdown: number
}

export interface SimulationLatestResponse {
  as_of_date: string
  account: SimulationAccount
  positions: SimulationPosition[]
  trades: SimulationTrade[]
  equity_curve: SimulationEquityPoint[]
  risk: {
    max_drawdown: number
    position_count: number
    position_ratio: number
    win_rate: number
    profit_loss_ratio: number | null
  }
  messages: string[]
}

export interface SimulationWorkflowResponse {
  target_trade_date: string
  tracking: TradePlanTrackingResponse['items']
  simulation: SimulationLatestResponse
}

export function fetchMarketLatest(): Promise<MarketLatestResponse> {
  return fetchJson<MarketLatestResponse>('/api/market/latest')
}

export function fetchTopSectors(): Promise<SectorTopResponse> {
  return fetchJson<SectorTopResponse>('/api/sectors/top')
}

export function fetchLatestCandidates(): Promise<CandidateLatestResponse> {
  return fetchJson<CandidateLatestResponse>('/api/candidates/latest')
}

export function fetchLatestTradePlans(): Promise<TradePlansLatestResponse> {
  return fetchJson<TradePlansLatestResponse>('/api/trade-plans/latest')
}

export function fetchTradePlanDetail(planId: number): Promise<TradePlanDetail> {
  return fetchJson<TradePlanDetail>(`/api/trade-plans/${planId}`)
}

export function fetchLatestTradeReviews(): Promise<TradeReviewLatestResponse> {
  return fetchJson<TradeReviewLatestResponse>('/api/trade-reviews/latest')
}

export function fetchLatestSimulation(): Promise<SimulationLatestResponse> {
  return fetchJson<SimulationLatestResponse>('/api/simulation/latest')
}

export function runSimulation(tradeDate: string): Promise<SimulationLatestResponse> {
  return sendJson<SimulationLatestResponse>('/api/simulation/run', 'POST', {
    trade_date: tradeDate
  })
}

export function runSimulationWorkflow(
  tradeDate: string,
  markUntriggeredAtClose = false
): Promise<SimulationWorkflowResponse> {
  return sendJson<SimulationWorkflowResponse>('/api/simulation/run-workflow', 'POST', {
    trade_date: tradeDate,
    mark_untriggered_at_close: markUntriggeredAtClose
  })
}

export function trackTradePlans(targetTradeDate: string, markUntriggeredAtClose = false): Promise<TradePlanTrackingResponse> {
  return sendJson<TradePlanTrackingResponse>('/api/trade-plans/track', 'POST', {
    target_trade_date: targetTradeDate,
    mark_untriggered_at_close: markUntriggeredAtClose
  })
}

export function trackRealtimeTradePlans(
  targetTradeDate: string,
  markUntriggeredAtClose = false
): Promise<TradePlanTrackingResponse> {
  return sendJson<TradePlanTrackingResponse>('/api/trade-plans/track-realtime', 'POST', {
    target_trade_date: targetTradeDate,
    mark_untriggered_at_close: markUntriggeredAtClose,
    include_existing: true
  })
}

export function updateTradePlanStatus(
  planId: number,
  status: string,
  note: string,
  triggerPrice?: number,
  isWatched?: boolean
): Promise<TradePlanItem> {
  return sendJson<TradePlanItem>(`/api/trade-plans/${planId}/status`, 'PATCH', {
    status,
    note,
    trigger_price: triggerPrice,
    is_watched: isWatched
  })
}
