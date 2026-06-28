import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('App', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.history.pushState({}, '', '/')
  })

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
      '/api/market/history': {
        items: [
          {
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
          {
            trade_date: '2026-06-17',
            market_score: 48,
            market_status: '中性',
            suggested_position: '30% - 50%',
            up_count: 1800,
            down_count: 3600,
            limit_up_count: 60,
            limit_down_count: 18,
            limit_up_height: 2,
            total_amount: 2800000000000,
            suggestion: '上一交易日说明不应作为当前解释。'
          }
        ]
      },
      '/api/market/index-ticker': {
        items: [
          {
            name: '沪指',
            index_code: '000001.SH',
            trade_date: '2026-06-18',
            close: 3020,
            change: 20,
            pct_chg: 0.6667,
            amount: 10000000000,
            available: true
          },
          {
            name: '深指',
            index_code: '399001.SZ',
            trade_date: '2026-06-18',
            close: 10000,
            change: -100,
            pct_chg: -0.99,
            amount: 21000000000,
            available: true
          },
          {
            name: '创指',
            index_code: '399006.SZ',
            trade_date: '',
            close: null,
            change: null,
            pct_chg: null,
            amount: null,
            available: false
          }
        ]
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
            sector_score: 100,
            rank_history: [
              { trade_date: '2026-06-18', rank_no: 7 },
              { trade_date: '2026-06-17', rank_no: 2 },
              { trade_date: '2026-06-16', rank_no: null },
              { trade_date: '2026-06-15', rank_no: 5 },
              { trade_date: '2026-06-12', rank_no: 8 }
            ]
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
            nine_turn_signal: 'sell',
            nine_turn_count: 4,
            nine_turn_score: 4,
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
          },
          {
            id: 0,
            trade_plan_id: 1,
            stock_code: '300308',
            stock_name: '中际旭创',
            trade_date: '2026-06-18',
            trade_time: '2026-06-18T14:30:00+08:00',
            trade_type: '买入',
            price: 1280,
            quantity: 100,
            amount: 128000,
            commission: 38.4,
            stamp_tax: 0,
            transfer_fee: 1.28,
            total_fee: 39.68,
            net_amount: -128039.68,
            cash_after: 871960.32,
            position_ratio_after: 0.13,
            profit_loss: null,
            profit_loss_return: null,
            reason: '历史模拟买入记录'
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
      },
      '/api/system/data-runs/latest': {
        items: [
          {
            id: 1,
            job_name: 'after_close_data_pull',
            trade_date: '2026-06-18',
            status: 'warning',
            command: 'TRADE_DATE=2026-06-18 bash get_data.sh',
            message: '覆盖审计发现部分数据缺失，页面已明示补数命令',
            started_at: '2026-06-18T22:00:00+08:00',
            ended_at: '2026-06-18T22:08:00+08:00',
            steps: [
              {
                step_name: '拉取行情快照',
                status: 'success',
                started_at: '2026-06-18T22:00:00+08:00',
                ended_at: '2026-06-18T22:03:00+08:00',
                rows_count: 5507,
                summary: { stock_daily_rows: 5507, index_daily_rows: 3 },
                error_message: ''
              },
              {
                step_name: '覆盖审计',
                status: 'success',
                started_at: '2026-06-18T22:07:00+08:00',
                ended_at: '2026-06-18T22:08:00+08:00',
                rows_count: 5507,
                summary: { missing_stock_daily_rows: 22 },
                error_message: ''
              }
            ]
          }
        ]
      },
      '/api/system/database-health': {
        trade_date: '2026-06-18',
        status: 'warning',
        generated_at: '2026-06-18T22:08:10+08:00',
        items: [
          {
            name: '个股日线',
            status: 'warning',
            message: '个股日线缺少 22 行，请确认是否为停牌/ST/退市等合理缺口。',
            actual: '5507 / 5529',
            expected: '覆盖全部 stock_basic 股票，合理停牌缺口需人工可见',
            fix_command: 'TRADE_DATE=2026-06-18 bash get_data.sh'
          },
          {
            name: '强势板块排名',
            status: 'ok',
            message: '正常',
            actual: 'rows=511, max_rank=511',
            expected: '511 行，max_rank <= 511',
            fix_command: ''
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
    expect(wrapper.text()).toContain('沪指')
    expect(wrapper.text()).toContain('3020.00')
    expect(wrapper.text()).toContain('+20.00')
    expect(wrapper.text()).toContain('+0.67%')
    expect(wrapper.text()).toContain('深指')
    expect(wrapper.text()).toContain('-0.99%')
    expect(wrapper.text()).toContain('最近 2 个交易日')
    expect(wrapper.text()).toContain('2026-06-18')
    expect(wrapper.text()).toContain('2026-06-17')
    expect(wrapper.text()).toContain('中性')
    expect(wrapper.text()).toContain('91 / 12')
    expect(wrapper.text()).toContain('连板高度')
    expect(wrapper.text()).toContain('市场震荡，轻仓参与，优先选择强势板块。')
    expect(wrapper.text()).not.toContain('上一交易日说明不应作为当前解释。')
    expect(wrapper.text()).toContain('强势行业')
    expect(wrapper.text()).toContain('科技风格')
    expect(wrapper.text()).toContain('近5日排名')
    expect(wrapper.text()).toContain('06-18')
    expect(wrapper.text()).toContain('06-17')
    expect(wrapper.text()).toContain('06-16')
    expect(wrapper.text()).toContain('06-15')
    expect(wrapper.text()).toContain('06-12')
    expect(wrapper.findAll('.rank-history-rank').map((rank) => rank.text())).toEqual(['7', '2', '-', '5', '8'])
    expect(wrapper.text()).toContain('5日涨幅')
    expect(wrapper.text()).toContain('股票池')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('核心主升 5 / 稳定强势 3 / 强势延续 2')
    expect(wrapper.text()).toContain('今日交易计划对股票池全部生成')
    expect(wrapper.text()).toContain('今日交易计划')
    expect(wrapper.text()).toContain('中际旭创')
    expect(wrapper.text()).toContain('40%')
    expect(wrapper.text()).toContain('关注')
    expect(wrapper.text()).toContain('模拟交易')
    expect(wrapper.text()).toContain('当前总资产')
    expect(wrapper.text()).toContain('当日盈亏')
    expect(wrapper.text()).toContain('模拟持仓')
    expect(wrapper.text()).toContain('模拟交易记录')
    expect(wrapper.text()).toContain('资金曲线')
    expect(wrapper.text()).toContain('10:01')
    expect(wrapper.text()).toContain('14:30')
    expect(wrapper.text()).toContain('39%')
    expect(wrapper.text()).toContain('历史模拟买入记录')
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
    expect(wrapper.findAll('.el-table').some((table) => {
      const text = table.text()
      return text.includes('当前价') && text.includes('买入条件') && text.includes('板块') && text.includes('科技风格')
    })).toBe(true)
    expect(wrapper.text()).toContain('交易复盘')
    expect(wrapper.text()).toContain('导出复盘')
    expect(wrapper.text()).toContain('复盘日：2026-06-19')
    expect(wrapper.text()).toContain('当日均收益')
    expect(wrapper.text()).toContain('盈利')
    expect(wrapper.text()).toContain('数据拉取与数据库健康')
    expect(wrapper.text()).toContain('拉取行情快照')
    expect(wrapper.text()).toContain('覆盖审计')
    expect(wrapper.text()).toContain('个股日线')
    expect(wrapper.text()).toContain('TRADE_DATE=2026-06-18 bash get_data.sh')
    const databaseHealthTable = wrapper.findAllComponents({ name: 'ElTable' }).find((table) => table.text().includes('个股日线'))
    expect(databaseHealthTable?.props('maxHeight')).toBeUndefined()

    expect(wrapper.text()).not.toContain('行业详情：科技风格')
    const sectorButton = wrapper.findAll('button').find((button) => button.text() === '科技风格')
    expect(sectorButton).toBeTruthy()

    await sectorButton?.trigger('click')
    await wrapper.vm.$nextTick()

    expect(window.location.pathname).toBe('/sectors/%E7%A7%91%E6%8A%80%E9%A3%8E%E6%A0%BC')
    expect(wrapper.text()).toContain('行业详情：科技风格')
    expect(wrapper.text()).toContain('板块共振，趋势多头排列，量价健康')
    expect(wrapper.text()).toContain('该行业交易计划')
    expect(wrapper.text()).toContain('返回强势行业')
  })

  it('refreshes realtime quotes before loading simulation when target trade date is today', async () => {
    window.history.pushState({}, '', '/')
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-22T10:00:00+08:00'))
    let simulationFetchCount = 0
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
      '/api/market/history': {
        items: [
          {
            trade_date: '2026-06-22',
            market_score: 55,
            market_status: '中性',
            suggested_position: '50% - 80%',
            up_count: 2000,
            down_count: 3000,
            limit_up_count: 80,
            limit_down_count: 10,
            limit_up_height: 3,
            total_amount: 3000000000000,
            suggestion: '盘中刷新实时行情。'
          }
        ]
      },
      '/api/sectors/top': {
        trade_date: '2026-06-22',
        items: []
      },
      '/api/candidates/latest': {
        trade_date: '2026-06-22',
        items: []
      },
      '/api/trade-plans/latest': {
        plan_date: '2026-06-19',
        target_trade_date: '2026-06-22',
        items: [
          {
            id: 3,
            stock_code: '300308',
            stock_name: '中际旭创',
            sector_name: '科技风格',
            strategy_type: '趋势强势',
            stock_score: 100,
            sector_score: 100,
            market_status: '中性',
            buy_condition: '目标交易日价格触达计划买入区间',
            buy_price_low: 1200,
            buy_price_high: 1400,
            stop_loss_price: 1299.49,
            take_profit_price: 1641.46,
            position_ratio: 0.4,
            status: '已触发',
            trigger_price: 1367.78,
            trigger_time: null,
            tracking_note: '目标交易日价格触达计划买入区间',
            is_watched: false,
            risk_note: '严格执行止损',
            current_price: 1382.33,
            pct_chg: 1.07
          }
        ]
      },
      '/api/trade-plans/track-realtime': {
        target_trade_date: '2026-06-22',
        items: [
          {
            id: 3,
            stock_code: '300308',
            stock_name: '中际旭创',
            status: '已触发',
            current_price: 1382.33,
            pct_chg: 1.07,
            trigger_price: 1367.78,
            tracking_note: '实时行情已更新'
          }
        ],
        realtime: {
          target_trade_date: '2026-06-22',
          china_today: '2026-06-22',
          provider: 'akshare_sina_realtime',
          planned_stock_count: 1,
          existing_stock_count: 0,
          requested_stock_count: 1,
          fetched_stock_daily_rows: 1,
          target_is_open: true,
          missing_stock_codes: [],
          skipped_reason: ''
        }
      },
      '/api/trade-reviews/latest': {
        review_date: '2026-06-22',
        total_count: 0,
        triggered_count: 0,
        win_count: 0,
        win_rate: 0,
        avg_day_return: null,
        avg_t5_return: null,
        strategy_stats: [],
        sector_stats: [],
        items: []
      },
      '/api/system/data-runs/latest': {
        items: []
      },
      '/api/system/database-health': {
        trade_date: '2026-06-22',
        status: 'ok',
        generated_at: '2026-06-22T10:00:00+08:00',
        items: []
      }
    }
    const simulationBeforeRealtime = {
      as_of_date: '2026-06-22',
      account: {
        id: 1,
        account_name: '默认模拟账户',
        initial_cash: 1000000,
        available_cash: 700000,
        frozen_cash: 0,
        market_value: 271648,
        total_assets: 971648,
        total_profit: -28352,
        total_return: -0.0284,
        max_drawdown: 0.0284
      },
      positions: [
        {
          id: 1,
          stock_code: '300308',
          stock_name: '中际旭创',
          sector_name: '科技风格',
          strategy_type: '趋势强势',
          buy_price: 1367.78,
          current_price: 1358.24,
          quantity: 200,
          market_value: 271648,
          cost_amount: 273640,
          unrealized_profit: -1992,
          unrealized_return: -0.0073,
          stop_loss_price: 1299.49,
          take_profit_price: 1641.46,
          position_status: '持仓中',
          buy_reason: '目标交易日价格触达计划买入区间',
          sell_reason: ''
        }
      ],
      trades: [],
      equity_curve: [],
      risk: {
        max_drawdown: 0.0284,
        position_count: 1,
        position_ratio: 0.28,
        win_rate: 0,
        profit_loss_ratio: null
      },
      messages: []
    }
    const simulationAfterRealtime = {
      ...simulationBeforeRealtime,
      account: {
        ...simulationBeforeRealtime.account,
        market_value: 276466,
        total_assets: 976466,
        total_profit: -23534,
        total_return: -0.0235
      },
      positions: [
        {
          ...simulationBeforeRealtime.positions[0],
          current_price: 1382.33,
          market_value: 276466,
          unrealized_profit: 2826,
          unrealized_return: 0.0103
        }
      ]
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      const path = new URL(url, 'http://localhost').pathname
      const realtimeTrackingResponse = responses['/api/trade-plans/track-realtime'] as { items: unknown[] }
      const response = path === '/api/simulation/latest'
        ? (++simulationFetchCount === 1 ? simulationBeforeRealtime : simulationAfterRealtime)
        : path === '/api/simulation/run-workflow'
          ? {
              target_trade_date: '2026-06-22',
              tracking: realtimeTrackingResponse.items,
              simulation: simulationAfterRealtime
            }
          : responses[path]

      return {
        ok: true,
        json: async () => response
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await flushPromises()
    await wrapper.vm.$nextTick()
    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(fetchMock.mock.calls.map((call) => new URL(String(call[0]), 'http://localhost').pathname)).toContain('/api/trade-plans/track-realtime')
    expect(fetchMock.mock.calls.map((call) => new URL(String(call[0]), 'http://localhost').pathname)).toContain('/api/simulation/run-workflow')
    expect(simulationFetchCount).toBe(1)
    expect(wrapper.text()).toContain('1382.33')
    expect(wrapper.text()).not.toContain('1358.24')

    await vi.advanceTimersByTimeAsync(60_000)
    await flushPromises()
    await wrapper.vm.$nextTick()

    const paths = fetchMock.mock.calls.map((call) => new URL(String(call[0]), 'http://localhost').pathname)
    expect(paths.filter((path) => path === '/api/trade-plans/track-realtime')).toHaveLength(2)
    expect(paths.filter((path) => path === '/api/simulation/run-workflow')).toHaveLength(2)
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
      '/api/market/history': {
        items: []
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
      },
      '/api/system/data-runs/latest': {
        items: []
      },
      '/api/system/database-health': {
        trade_date: '',
        status: 'error',
        generated_at: '2026-06-22T10:00:00+08:00',
        items: []
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
    expect(wrapper.text()).toContain('暂无强势行业数据')
    expect(wrapper.text()).toContain('暂无交易计划数据')
    expect(wrapper.text()).not.toContain('failed: 404')
    expect(wrapper.text()).not.toContain('数据异常')
  })
})
