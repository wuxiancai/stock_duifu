const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)

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
  risk_note: string
}

export interface TradePlansLatestResponse {
  plan_date: string
  target_trade_date: string
  items: TradePlanItem[]
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
