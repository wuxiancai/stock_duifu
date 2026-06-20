import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('App', () => {
  it('renders the project status workbench from the health endpoint', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          status: 'ok',
          service: 'A股短线量化辅助决策系统',
          environment: 'development',
          database: {
            engine: 'postgresql',
            configured: true
          }
        })
      }))
    )

    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus]
      }
    })

    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('项目骨架与配置')
    expect(wrapper.text()).toContain('API 正常')
    expect(wrapper.text()).toContain('PostgreSQL 已配置')
    expect(wrapper.text()).toContain('真实行情数据')
  })
})

