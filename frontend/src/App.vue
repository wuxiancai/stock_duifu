<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Connection, DataAnalysis, Finished, TrendCharts } from '@element-plus/icons-vue'
import { fetchHealth, type HealthResponse } from './api/health'

const health = ref<HealthResponse | null>(null)
const loading = ref(true)
const error = ref('')

const statusType = computed(() => {
  if (error.value) return 'danger'
  return health.value?.status === 'ok' ? 'success' : 'warning'
})

onMounted(async () => {
  try {
    health.value = await fetchHealth()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'API health check failed'
  } finally {
    loading.value = false
  }
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
        <button class="nav-item active" type="button">
          <el-icon><DataAnalysis /></el-icon>
          <span>系统状态</span>
        </button>
        <button class="nav-item" type="button" disabled>
          <el-icon><TrendCharts /></el-icon>
          <span>市场环境</span>
        </button>
        <button class="nav-item" type="button" disabled>
          <el-icon><Finished /></el-icon>
          <span>交易计划</span>
        </button>
      </nav>
    </aside>

    <section class="workspace">
      <header class="toolbar">
        <div>
          <h1>项目骨架与配置</h1>
          <p>FastAPI、Vue 3、PostgreSQL 配置和健康检查已接入。</p>
        </div>
        <el-tag :type="statusType" size="large">
          {{ error ? 'API 异常' : health?.status === 'ok' ? 'API 正常' : '检测中' }}
        </el-tag>
      </header>

      <section class="metric-grid">
        <article class="metric">
          <el-icon><Connection /></el-icon>
          <div>
            <span>后端服务</span>
            <strong>{{ loading ? '检测中' : health?.service ?? '不可用' }}</strong>
          </div>
        </article>
        <article class="metric">
          <el-icon><DataAnalysis /></el-icon>
          <div>
            <span>运行环境</span>
            <strong>{{ health?.environment ?? 'development' }}</strong>
          </div>
        </article>
        <article class="metric">
          <el-icon><Finished /></el-icon>
          <div>
            <span>数据库配置</span>
            <strong>{{ health?.database.configured ? 'PostgreSQL 已配置' : '待配置' }}</strong>
          </div>
        </article>
      </section>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
      />

      <section class="status-table" aria-label="MVP readiness">
        <el-table
          :data="[
            { item: '后端 API', state: '已建立', note: '/api/health 可用于启动验收' },
            { item: '前端工作台', state: '已建立', note: 'Vue 3 + Element Plus' },
            { item: 'PostgreSQL', state: '已配置', note: '等待任务 2 创建业务表' },
            { item: '真实行情数据', state: '未接入', note: '任务 3 开始接入 TuShare' }
          ]"
          border
        >
          <el-table-column prop="item" label="项目" min-width="160" />
          <el-table-column prop="state" label="状态" min-width="140" />
          <el-table-column prop="note" label="说明" min-width="260" />
        </el-table>
      </section>
    </section>
  </main>
</template>

