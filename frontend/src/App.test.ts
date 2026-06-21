import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('App', () => {
  it('renders the P0 trading workbench from dashboard endpoints', async () => {
    const responses: Record<string, unknown> = {
      '/api/health': {
        status: 'ok',
        service: 'A股短线量化辅助决策系统',
        environment: 'development',
        database: {
          engine: 'postgresql',
          configured: true
        }
      },
      '/api/market/latest': {
        trade_date: '2026-06-18',
        market_score: 55,
        market_status: '中性',
        suggested_position: '50% - 80%',
        up_count: 2023,
        down_count: 3395,
        limit_up_count: 91,
        limit_down_count: 12,
        total_amount: 3331719013167.08,
        suggestion: '市场震荡，轻仓参与，优先选择强势板块。'
      },
      '/api/sectors/top': {
        trade_date: '2026-06-18',
        items: [
          {
            rank_no: 1,
            sector_name: '科技风格',
            daily_return: 2.83,
            three_day_return: 8.7,
            amount_change: 1000000000,
            limit_up_count: 3,
            strong_stock_count: 79,
            sector_score: 100
          }
        ]
      },
      '/api/trade-plans/latest': {
        plan_date: '2026-06-18',
        target_trade_date: '2026-06-19',
        items: [
          {
            stock_code: '300308',
            stock_name: '中际旭创',
            sector_name: '科技风格',
            strategy_type: '趋势强势',
            stock_score: 100,
            sector_score: 100,
            market_status: '中性',
            buy_condition: '盘中回踩 MA5 或放量突破前高',
            buy_price_low: 1207.206,
            buy_price_high: 1367.88,
            stop_loss_price: 1299.486,
            take_profit_price: 1641.456,
            position_ratio: 0.4,
            status: '待触发',
            risk_note: '高位强势股，严格执行止损。'
          }
        ]
      }
    }

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString()
        const path = new URL(url, 'http://localhost').pathname

        return {
          ok: true,
          json: async () => responses[path]
        }
      })
    )

    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('今日决策面板')
    expect(wrapper.text()).toContain('中性')
    expect(wrapper.text()).toContain('91 / 12')
    expect(wrapper.text()).toContain('强势板块')
    expect(wrapper.text()).toContain('科技风格')
    expect(wrapper.text()).toContain('今日交易计划')
    expect(wrapper.text()).toContain('中际旭创')
    expect(wrapper.text()).toContain('40%')
    expect(wrapper.text()).toContain('交易复盘')
  })
})
