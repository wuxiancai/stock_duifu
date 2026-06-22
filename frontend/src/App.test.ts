import { flushPromises, mount } from '@vue/test-utils'
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
        limit_up_height: 3,
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
            five_day_return: 9.2,
            three_day_return: 8.7,
            amount_change: 1000000000,
            limit_up_count: 3,
            strong_stock_count: 79,
            sector_score: 100
          }
        ]
      },
      '/api/candidates/latest': {
        trade_date: '2026-06-18',
        items: [
          {
            stock_code: '300308',
            stock_name: '中际旭创',
            sector_name: '科技风格',
            sector_rank: 7,
            strategy_type: '趋势强势',
            stock_score: 100,
            sector_score: 100,
            close_price: 1367.88,
            amount: 18000000000,
            reason: '板块共振，趋势多头排列，量价健康',
            risk_note: '趋势票避免高开追涨'
          }
        ]
      },
      '/api/trade-plans/latest': {
        plan_date: '2026-06-18',
        target_trade_date: '2026-06-19',
        items: [
          {
            id: 1,
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
            trigger_price: null,
            trigger_time: null,
            tracking_note: '',
            is_watched: false,
            risk_note: '高位强势股，严格执行止损。'
          }
        ]
      },
      '/api/trade-plans/1': {
        id: 1,
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
        trigger_price: null,
        trigger_time: null,
        tracking_note: '',
        is_watched: false,
        risk_note: '高位强势股，严格执行止损。',
        selection_reason: '板块排名 Top 10，趋势多头排列',
        key_indicators: {
          ma5: 1302.5,
          ma10: 1276.2,
          ma20: 1210.1,
          amount: 18000000000,
          turnover_rate: 3.6,
          atr14: 52.8
        }
      },
      '/api/simulation/latest': {
        as_of_date: '2026-06-19',
        account: {
          id: 1,
          account_name: '默认模拟账户',
          initial_cash: 1000000,
          available_cash: 600000,
          frozen_cash: 0,
          market_value: 420000,
          total_assets: 1020000,
          total_profit: 20000,
          total_return: 0.02,
          max_drawdown: 0
        },
        positions: [
          {
            id: 1,
            stock_code: '300308',
            stock_name: '中际旭创',
            sector_name: '科技风格',
            strategy_type: '趋势强势',
            buy_price: 1300,
            current_price: 1400,
            quantity: 300,
            market_value: 420000,
            cost_amount: 390122,
            unrealized_profit: 29878,
            unrealized_return: 0.0766,
            stop_loss_price: 1299.486,
            take_profit_price: 1641.456,
            position_status: '持仓中',
            buy_reason: '目标交易日价格触达计划买入区间',
            sell_reason: ''
          }
        ],
        trades: [
          {
            id: 1,
            trade_plan_id: 1,
            stock_code: '300308',
            stock_name: '中际旭创',
            trade_date: '2026-06-19',
            trade_time: '2026-06-19T10:01:30+08:00',
            trade_type: '买入',
            price: 1300,
            quantity: 300,
            amount: 390000,
            commission: 117,
            stamp_tax: 0,
            transfer_fee: 3.9,
            total_fee: 120.9,
            net_amount: -390120.9,
            cash_after: 609879.1,
            position_ratio_after: 0.39,
            profit_loss: null,
            profit_loss_return: null,
            reason: '目标交易日价格触达计划买入区间'
          }
        ],
        equity_curve: [
          {
            trade_date: '2026-06-19',
            available_cash: 600000,
            market_value: 420000,
            total_assets: 1020000,
            daily_profit: 20000,
            daily_return: 0.02,
            max_drawdown: 0
          }
        ],
        risk: {
          max_drawdown: 0,
          position_count: 1,
          position_ratio: 0.4118,
          win_rate: 1,
          profit_loss_ratio: 2.4
        },
        messages: []
      },
      '/api/trade-reviews/latest': {
        review_date: '2026-06-19',
        total_count: 1,
        triggered_count: 1,
        win_count: 1,
        win_rate: 1,
        avg_day_return: 0.1,
        avg_t5_return: 0.18,
        strategy_stats: [
          {
            name: '趋势强势',
            total_count: 1,
            triggered_count: 1,
            win_count: 1,
            win_rate: 1,
            avg_day_return: 0.1,
            avg_t5_return: 0.18
          }
        ],
        sector_stats: [],
        items: [
          {
            id: 1,
            trade_plan_id: 1,
            trade_date: '2026-06-19',
            stock_code: '300308',
            stock_name: '中际旭创',
            sector_name: '科技风格',
            strategy_type: '趋势强势',
            triggered: true,
            trigger_price: 1300,
            close_price: 1430,
            day_return: 0.1,
            t5_return: 0.18,
            max_profit: 0.2,
            max_loss: -0.02,
            result: '盈利',
            failure_reason: null,
            discipline_check: true,
            note: '自动生成复盘'
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

    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('今日决策面板')
    expect(wrapper.text()).toContain('中性')
    expect(wrapper.text()).toContain('91 / 12')
    expect(wrapper.text()).toContain('连板高度')
    expect(wrapper.text()).toContain('强势板块')
    expect(wrapper.text()).toContain('科技风格')
    expect(wrapper.text()).toContain('5日涨幅')
    expect(wrapper.text()).toContain('今日交易计划')
    expect(wrapper.text()).toContain('中际旭创')
    expect(wrapper.text()).toContain('40%')
    expect(wrapper.text()).toContain('关注')
    expect(wrapper.text()).toContain('模拟交易')
    expect(wrapper.text()).toContain('当前总资产')
    expect(wrapper.text()).toContain('当日盈亏')
    expect(wrapper.text()).toContain('10:01')
    expect(wrapper.text()).toContain('39%')
    expect(wrapper.text()).toContain('买入')
    expect(wrapper.text()).toContain('目标交易日价格触达计划买入区间')
    expect(wrapper.findAll('.el-table').some((table) => {
      const text = table.text()
      return text.includes('买入') && text.includes('29,878.00') && text.includes('7.66%')
    })).toBe(true)
    expect(wrapper.html()).toContain('quote-up')
    expect(wrapper.html()).toContain('href="/simulation"')
    expect(wrapper.text()).not.toContain('股票详情')
    expect(wrapper.text()).not.toContain('板块排名 Top 10，趋势多头排列')

    const stockButton = wrapper.find('.plan-stock-button')
    expect(stockButton.exists()).toBe(true)
    await stockButton.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('股票详情')
    expect(wrapper.text()).toContain('入选理由')
    expect(wrapper.text()).toContain('板块排名 Top 10，趋势多头排列')

    await stockButton.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('股票详情')
    expect(wrapper.text()).not.toContain('板块排名 Top 10，趋势多头排列')
    expect(wrapper.text()).toContain('盘中跟踪')
    expect(wrapper.text()).toContain('当前价')
    expect(wrapper.text()).toContain('交易复盘')
    expect(wrapper.text()).toContain('导出复盘')
    expect(wrapper.text()).toContain('复盘日：2026-06-19')
    expect(wrapper.text()).toContain('当日均收益')
    expect(wrapper.text()).toContain('盈利')

    expect(wrapper.text()).not.toContain('板块详情：科技风格')
    const sectorButton = wrapper.findAll('button').find((button) => button.text() === '科技风格')
    expect(sectorButton).toBeTruthy()

    await sectorButton?.trigger('click')
    await wrapper.vm.$nextTick()

    expect(window.location.pathname).toBe('/sectors/%E7%A7%91%E6%8A%80%E9%A3%8E%E6%A0%BC')
    expect(wrapper.text()).toContain('板块详情：科技风格')
    expect(wrapper.text()).toContain('板块共振，趋势多头排列，量价健康')
    expect(wrapper.text()).toContain('该板块交易计划')
    expect(wrapper.text()).toContain('返回强势板块')
  })

  it('renders empty dashboard state without showing data errors', async () => {
    window.history.pushState({}, '', '/')

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
        trade_date: '',
        market_score: null,
        market_status: '',
        suggested_position: '',
        up_count: null,
        down_count: null,
        limit_up_count: null,
        limit_down_count: null,
        limit_up_height: null,
        total_amount: null,
        suggestion: '暂无市场建议，请先生成市场环境数据。'
      },
      '/api/sectors/top': {
        trade_date: '',
        items: []
      },
      '/api/candidates/latest': {
        trade_date: '',
        items: []
      },
      '/api/trade-plans/latest': {
        plan_date: '',
        target_trade_date: '',
        items: []
      },
      '/api/simulation/latest': {
        detail: 'simulation is not generated'
      },
      '/api/trade-reviews/latest': {
        detail: 'trade reviews are not generated'
      }
    }

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString()
        const path = new URL(url, 'http://localhost').pathname
        const response = responses[path]
        const ok = !['/api/simulation/latest', '/api/trade-reviews/latest'].includes(path)

        return {
          ok,
          json: async () => response
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
    expect(wrapper.text()).toContain('暂无市场建议，请先生成市场环境数据。')
    expect(wrapper.text()).toContain('暂无强势板块数据')
    expect(wrapper.text()).toContain('暂无交易计划数据')
    expect(wrapper.text()).not.toContain('failed: 404')
    expect(wrapper.text()).not.toContain('数据异常')
  })
})
