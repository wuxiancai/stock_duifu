const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

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
  total_amount: number
  suggestion: string
}

export interface SectorTopItem {
  rank_no: number
  sector_name: string
  daily_return: number
  three_day_return: number
  amount_change: number
  limit_up_count: number
  strong_stock_count: number
  sector_score: number
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
  risk_note: string
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
}

export function fetchMarketLatest(): Promise<MarketLatestResponse> {
  return fetchJson<MarketLatestResponse>('/api/market/latest')
}

export function fetchTopSectors(): Promise<SectorTopResponse> {
  return fetchJson<SectorTopResponse>('/api/sectors/top')
}

export function fetchLatestTradePlans(): Promise<TradePlansLatestResponse> {
  return fetchJson<TradePlansLatestResponse>('/api/trade-plans/latest')
}

export function trackTradePlans(targetTradeDate: string, markUntriggeredAtClose = false): Promise<TradePlanTrackingResponse> {
  return sendJson<TradePlanTrackingResponse>('/api/trade-plans/track', 'POST', {
    target_trade_date: targetTradeDate,
    mark_untriggered_at_close: markUntriggeredAtClose
  })
}

export function updateTradePlanStatus(
  planId: number,
  status: string,
  note: string,
  triggerPrice?: number
): Promise<TradePlanItem> {
  return sendJson<TradePlanItem>(`/api/trade-plans/${planId}/status`, 'PATCH', {
    status,
    note,
    trigger_price: triggerPrice
  })
}
