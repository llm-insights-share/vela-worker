<template>
  <div class="item-detail">
    <nav class="breadcrumb">
      <span class="crumb-muted">项目</span>
      <span class="sep">/</span>
      <button type="button" class="crumb-link" @click="$emit('back')">{{ projectName }}</button>
      <span class="sep">/</span>
      <span class="crumb-current">{{ item?.name }}</span>
    </nav>

    <div class="ws-card detail-header">
      <div class="detail-title-row">
        <div class="title-main">
          <div class="title-line">
            <h1>{{ item?.name }}</h1>
            <span class="status-pill" :class="statusClass">{{ statusLabel }}</span>
          </div>
          <p v-if="displayDescription" class="detail-desc">{{ displayDescription }}</p>
          <div v-if="item.worker_name" class="detail-worker">
            委派给
            <span class="worker-pill"><RobotOutlined /> {{ item.worker_name }}</span>
          </div>
        </div>
        <div class="progress-aside">
          <div class="progress-pct">{{ progressPct }}%</div>
          <div class="progress-sub">{{ completedSteps }}/{{ totalSteps }} 步骤完成</div>
        </div>
      </div>

      <a-progress
        :percent="progressPct"
        :show-info="false"
        stroke-color="var(--brand)"
        :stroke-width="10"
        class="main-progress"
      />
      <div v-if="meta.estimated_remaining || meta.started_at || meta.estimated_finish" class="time-info">
        <span v-if="meta.started_at">开始时间: {{ meta.started_at }}</span>
        <span v-if="meta.estimated_finish">预计完成: {{ meta.estimated_finish }}</span>
        <span v-if="meta.estimated_remaining" class="remain">剩余: {{ meta.estimated_remaining }}</span>
      </div>

      <div v-if="canDelegate || canStart || canResume || item.task_id || canPause || canDelete" class="action-row">
        <a-button v-if="canDelegate" type="primary" size="small" @click="$emit('delegate')">委派数字员工</a-button>
        <a-button v-if="canStart" type="primary" size="small" @click="confirmStart">确认启动</a-button>
        <a-button v-if="canResume" type="primary" size="small" @click="confirmResume">继续执行</a-button>
        <a-button v-if="item.task_id" size="small" @click="refresh">刷新进度</a-button>
        <a-button v-if="canPause" size="small" @click="confirmPause">暂停</a-button>
        <a-button v-if="canDelete" size="small" danger @click="confirmDelete">删除</a-button>
      </div>
    </div>

    <div v-if="steps.length" class="ws-card steps-card">
      <div class="section-hd">
        <h2>执行步骤</h2>
        <span class="muted">— 任务拆解为 {{ steps.length }} 个步骤</span>
      </div>
      <p v-if="workIntent" class="intent-line">意图：{{ workIntent }}</p>
      <TaskStepTimeline :steps="displaySteps" :item-status="item?.status" />
    </div>

    <div v-if="workReport" class="ws-card report-card">
      <h2>工作报告</h2>
      <pre class="report-body">{{ workReport }}</pre>
    </div>

    <div v-if="artifacts.length" class="ws-card artifacts-card">
      <h2>产出资料</h2>
      <ul class="artifact-list">
        <li v-for="(a, i) in artifacts" :key="a.doc_id || a.name || i">
          <a v-if="a.path" :href="a.path" target="_blank" rel="noopener">{{ a.name }}</a>
          <span v-else>{{ a.name }}</span>
        </li>
      </ul>
    </div>

    <div v-if="hasStats" class="summary-grid">
      <template v-if="isAuditStats">
        <div class="summary-card">
          <div class="summary-num">{{ meta.stats.total ?? 0 }}</div>
          <div class="summary-label">风险点</div>
          <div v-if="meta.stats.processed != null" class="summary-sub">已处理 {{ meta.stats.processed }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-num err">{{ meta.stats.high ?? 0 }}</div>
          <div class="summary-label">高风险</div>
        </div>
        <div class="summary-card">
          <div class="summary-num" style="color:#d97706">{{ meta.stats.medium ?? 0 }}</div>
          <div class="summary-label">中风险</div>
        </div>
        <div class="summary-card">
          <div class="summary-num ok">{{ meta.stats.low ?? 0 }}</div>
          <div class="summary-label">低风险</div>
        </div>
      </template>
      <template v-else>
        <div class="summary-card">
          <div class="summary-num">{{ meta.stats.processed ?? meta.stats.total ?? 0 }}</div>
          <div class="summary-label">已处理</div>
          <div v-if="meta.stats.total" class="summary-sub">/ {{ meta.stats.total }}</div>
        </div>
        <div class="summary-card">
          <div class="summary-num ok">{{ meta.stats.passed ?? 0 }}</div>
          <div class="summary-label">通过</div>
        </div>
        <div class="summary-card">
          <div class="summary-num err">{{ meta.stats.rejected ?? 0 }}</div>
          <div class="summary-label">淘汰</div>
        </div>
        <div v-if="passRate != null" class="summary-card">
          <div class="summary-num">{{ passRate }}%</div>
          <div class="summary-label">通过率</div>
        </div>
      </template>
    </div>

    <div v-if="candidates.length" class="ws-card results-card">
      <h2>{{ isAuditStats ? '风险/缺陷清单' : '筛选结果' }}</h2>
      <a-table
        :data-source="candidates"
        :columns="resultColumns"
        :pagination="false"
        row-key="name"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'result'">
            <span :class="resultClass(record.result)">{{ record.result }}</span>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { RobotOutlined } from '@ant-design/icons-vue'
import { projectApi } from '../../../api'
import { useWorkbenchStore } from '../store/workbench'
import TaskStepTimeline from './TaskStepTimeline.vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['refresh', 'delegate', 'back'])
const store = useWorkbenchStore()

const meta = computed(() => props.item?.meta || {})
const task = computed(() => props.item?.task || {})

const projectName = computed(() =>
  store.selectedProject?.name || props.item?.project_name || '项目'
)

const displayDescription = computed(() => {
  if (props.item?.description) return props.item.description
  const proj = store.selectedProject?.name
  if (proj && props.item?.name) return `${proj} — ${props.item.name}`
  return ''
})

const steps = computed(() =>
  task.value.progress_steps?.length
    ? task.value.progress_steps
    : meta.value.progress_steps || []
)

/** When item is paused, never show in-flight steps as「进行中」. */
const displaySteps = computed(() => {
  const list = steps.value || []
  const paused = props.item?.status === 'SUSPENDED'
  return list.map((s) => {
    if (!paused) return s
    if (s.status === 'running' || s.status === 'cancelled' || s.status === 'canceled') {
      return { ...s, status: 'suspended' }
    }
    return s
  })
})

const workIntent = computed(() =>
  task.value.result?.intent || meta.value.intent || ''
)

const workReport = computed(() => {
  const r = task.value.result || {}
  if (r.report) return r.report
  if (r.summary) return r.summary
  return ''
})

const artifacts = computed(() => {
  const list = task.value.artifacts || meta.value.artifacts || []
  return Array.isArray(list) ? list : []
})

const progressPct = computed(() =>
  task.value.progress_pct ?? props.item?.progress_pct ?? 0
)

const completedSteps = computed(() =>
  steps.value.filter((s) => s.status === 'completed').length
)

const totalSteps = computed(() => steps.value.length || 1)

const candidates = computed(() => meta.value.candidates || [])

const hasStats = computed(() => !!meta.value.stats)

const isAuditStats = computed(() => {
  const s = meta.value.stats || {}
  return s.high != null || s.medium != null || s.low != null
})

const passRate = computed(() => {
  const s = meta.value.stats
  if (!s || isAuditStats.value) return null
  if (s.pass_rate != null) return s.pass_rate
  const total = (s.passed || 0) + (s.rejected || 0)
  if (!total) return null
  return Math.round(((s.passed || 0) / total) * 1000) / 10
})

const canDelegate = computed(() =>
  ['TODO', 'IN_PROGRESS', 'SUSPENDED'].includes(props.item?.status) && !props.item?.worker_id && !props.item?.task_id
)

const canStart = computed(() => {
  if (props.item?.status !== 'DELEGATED' || !props.item?.worker_id) return false
  if (!props.item?.task_id) return true
  const ts = props.item?.task?.status
  return ['RECEIVED', 'QUEUED'].includes(ts)
})

const canPause = computed(() =>
  !!props.item?.task_id && ['IN_PROGRESS', 'DELEGATED'].includes(props.item?.status)
)

const canResume = computed(() => props.item?.status === 'SUSPENDED')

const canDelete = computed(() =>
  props.item?.status !== 'COMPLETED'
)

const statusLabel = computed(() => {
  const s = props.item?.status
  if (s === 'COMPLETED') return '已完成'
  if (s === 'DELEGATED' && !props.item?.task_id) return '待启动'
  if (s === 'IN_PROGRESS' || s === 'DELEGATED') return '执行中'
  if (s === 'SUSPENDED') return '已暂停'
  if (s === 'TODO') return '待开始'
  return s || '待开始'
})

const statusClass = computed(() => {
  const s = props.item?.status
  if (s === 'COMPLETED') return 'st-done'
  if (s === 'DELEGATED' && !props.item?.task_id) return 'st-todo'
  if (s === 'IN_PROGRESS' || s === 'DELEGATED') return 'st-run'
  if (s === 'SUSPENDED') return 'st-pause'
  return 'st-todo'
})

const columns = [
  { title: '候选人', dataIndex: 'name', key: 'name' },
  { title: '结果', key: 'result', width: 80 },
  { title: '原因', dataIndex: 'reason', key: 'reason' },
]

const resultColumns = computed(() => {
  if (isAuditStats.value) {
    return [
      { title: '事项/缺陷', dataIndex: 'name', key: 'name' },
      { title: '等级', key: 'result', width: 80 },
      { title: '说明', dataIndex: 'reason', key: 'reason' },
    ]
  }
  return columns
})

function resultClass(result) {
  if (result === '通过' || result === '低') return 'res-ok'
  if (result === '高' || result === '淘汰') return 'res-err'
  return ''
}

function refresh() {
  emit('refresh')
}

function confirmStart() {
  Modal.confirm({
    title: '确认启动',
    content: `确认启动「${props.item?.name}」并由 ${props.item?.worker_name || '数字员工'} 开始执行？`,
    okText: '启动',
    cancelText: '取消',
    async onOk() {
      try {
        await projectApi.startItem(props.item.item_id)
        message.success('已启动执行')
        emit('refresh')
      } catch (e) {
        message.error(e.message || '启动失败')
        throw e
      }
    },
  })
}

function confirmPause() {
  Modal.confirm({
    title: '暂停事项',
    content: `确认暂停「${props.item?.name}」？进行中的任务将被取消。`,
    okText: '暂停',
    cancelText: '取消',
    async onOk() {
      try {
        await projectApi.updateItem(props.item.item_id, { status: 'SUSPENDED' })
        message.success('事项已暂停')
        emit('refresh')
      } catch (e) {
        message.error(e.message || '暂停失败')
        throw e
      }
    },
  })
}

function confirmResume() {
  Modal.confirm({
    title: '继续执行',
    content: `确认继续执行「${props.item?.name}」？将从暂停处恢复未完成步骤。`,
    okText: '继续执行',
    cancelText: '取消',
    async onOk() {
      try {
        await projectApi.resumeItem(props.item.item_id)
        message.success('已继续执行')
        emit('refresh')
      } catch (e) {
        message.error(e.message || '继续执行失败')
        throw e
      }
    },
  })
}

function confirmDelete() {
  Modal.confirm({
    title: '删除事项',
    content: `确认删除「${props.item?.name}」？删除后不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        const projectId = props.item.project_id || store.selectedProjectId
        await projectApi.removeItem(props.item.item_id)
        message.success('事项已删除')
        store.selectProject(projectId)
        emit('refresh')
      } catch (e) {
        message.error(e.message || '删除失败')
        throw e
      }
    },
  })
}
</script>

<style scoped>
.item-detail {
  max-width: 920px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.breadcrumb {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.crumb-muted,
.crumb-current {
  color: var(--ink-3, #94a3b8);
}

.crumb-current {
  color: var(--ink-2, #475569);
}

.crumb-link {
  background: none;
  border: none;
  color: var(--brand, #4f46e5);
  cursor: pointer;
  padding: 0;
  font-size: 13px;
}

.sep {
  color: var(--ink-3, #94a3b8);
}

.ws-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.detail-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.title-main {
  min-width: 0;
  flex: 1;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.title-line h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--ink, #0f172a);
}

.status-pill {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 999px;
}

.st-run {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.st-done {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.st-pause {
  background: #fffbeb;
  color: #d97706;
}

.st-todo {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.detail-desc {
  margin: 0 0 10px;
  color: var(--ink-2, #475569);
  font-size: 13px;
  line-height: 1.5;
}

.detail-worker {
  font-size: 13px;
  color: var(--ink-2, #475569);
  display: flex;
  align-items: center;
  gap: 8px;
}

.worker-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.progress-aside {
  text-align: right;
  flex-shrink: 0;
}

.progress-pct {
  font-size: 32px;
  font-weight: 700;
  color: var(--brand, #4f46e5);
  line-height: 1;
}

.progress-sub {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-top: 6px;
}

.main-progress {
  margin: 0 0 10px;
}

.time-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.time-info .remain {
  color: #d97706;
  font-weight: 500;
}

.action-row {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.section-hd {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 16px;
}

.section-hd h2,
.results-card h2,
.report-card h2,
.artifacts-card h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.intent-line {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--ink-2, #475569);
}

.report-body {
  margin: 12px 0 0;
  padding: 12px 14px;
  background: var(--surface-2, #f1f5f9);
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--ink, #0f172a);
  font-family: ui-sans-serif, system-ui, sans-serif;
}

.artifact-list {
  margin: 12px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--ink-2, #475569);
}

.artifact-list a {
  color: var(--brand, #4f46e5);
}

.muted {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.summary-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 14px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.summary-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--brand, #4f46e5);
}

.summary-num.ok { color: var(--state-success, #16a34a); }
.summary-num.err { color: var(--state-error, #dc2626); }

.summary-label {
  font-size: 12px;
  color: var(--ink-2, #475569);
  margin-top: 4px;
}

.summary-sub {
  font-size: 11px;
  color: var(--ink-3, #94a3b8);
}

.res-ok { color: var(--state-success, #16a34a); font-weight: 500; }
.res-err { color: var(--state-error, #dc2626); font-weight: 500; }

@media (max-width: 720px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
