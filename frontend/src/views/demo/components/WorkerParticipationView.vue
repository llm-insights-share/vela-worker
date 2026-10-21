<template>
  <div class="worker-detail">
    <!-- Header -->
    <div class="ws-card header-card">
      <div class="header-top">
        <div class="avatar">
          <RobotOutlined />
        </div>
        <div class="intro">
          <div class="title-row">
            <h1>{{ worker.name }}</h1>
            <span class="status-pill" :class="'act-' + (worker.activity || 'online')">
              <i class="dot" />
              {{ activityLabel }}
            </span>
          </div>
          <p v-if="worker.description" class="desc">{{ worker.description }}</p>
        </div>
      </div>
      <div class="header-actions">
        <a-button type="primary" @click="$emit('create-item')">
          <SendOutlined />
          委派任务
        </a-button>
        <a-button @click="goSettings">
          <SettingOutlined />
          设置
        </a-button>
      </div>
    </div>

    <!-- KPI row -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon blue"><UnorderedListOutlined /></div>
        <div class="kpi-value">{{ worker.today_task_count || 0 }}</div>
        <div class="kpi-label">今日任务</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon green"><CheckCircleOutlined /></div>
        <div class="kpi-value">{{ worker.week_done_count || 0 }}</div>
        <div class="kpi-label">本周完成</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon cyan"><FieldTimeOutlined /></div>
        <div class="kpi-value">{{ avgDurationLabel }}</div>
        <div class="kpi-label">平均完成时长</div>
      </div>
    </div>

    <!-- Current tasks -->
    <div class="ws-card section-card">
      <div class="section-hd">
        <h2>当前执行任务</h2>
        <span v-if="currentTasks.length" class="count-badge">{{ currentTasks.length }}</span>
      </div>

      <a-spin :spinning="loadingTasks">
        <div v-if="!currentTasks.length && !loadingTasks" class="empty-hint">暂无执行中或排队中的任务</div>

        <div
          v-for="task in runningTasks"
          :key="task.task_id"
          class="active-task"
        >
          <div class="active-hd">
            <div class="active-title-wrap">
              <span class="task-title">{{ task.title || '执行中任务' }}</span>
              <span class="tag tag-running">{{ task.status === 'NEED_HUMAN' ? '待人工' : '执行中' }}</span>
            </div>
            <span class="pct">{{ task.progress_pct || 0 }}%</span>
          </div>
          <div v-if="projectName(task.project_id)" class="project-line">
            <FolderOutlined />
            {{ projectName(task.project_id) }}
          </div>
          <a-progress
            :percent="task.progress_pct || 0"
            :show-info="false"
            stroke-color="var(--brand)"
            :stroke-width="8"
          />
          <div class="progress-meta">
            <span v-if="task.progress_note" class="note">{{ task.progress_note }}</span>
            <div v-if="task.progress_steps?.length" class="step-dots">
              <i
                v-for="(step, idx) in task.progress_steps"
                :key="step.key || idx"
                class="step-dot"
                :class="'dot-' + (step.status || 'pending')"
              />
            </div>
          </div>
          <div class="active-ft">
            <span v-if="estimatedRemaining(task)" class="eta">
              <ClockCircleOutlined />
              预计还需 {{ estimatedRemaining(task) }}
            </span>
            <span v-else />
            <div class="active-actions">
              <a-button
                type="primary"
                size="small"
                :disabled="!task.item_id"
                @click="onViewTask(task)"
              >
                查看详情
              </a-button>
              <a-button size="small" :loading="cancellingId === task.task_id" @click="onCancelTask(task)">
                取消任务
              </a-button>
            </div>
          </div>
        </div>

        <div
          v-for="task in queuedTasks"
          :key="task.task_id"
          class="queued-task"
        >
          <div class="queued-main">
            <div class="queued-hd">
              <span class="task-title">{{ task.title || '排队任务' }}</span>
              <span class="tag tag-queued">排队中</span>
            </div>
            <p class="queued-desc">{{ task.instruction || '等待前置任务完成后自动触发' }}</p>
          </div>
          <ClockCircleOutlined class="queued-icon" />
        </div>
      </a-spin>
    </div>

    <!-- History -->
    <div class="ws-card section-card">
      <div class="section-hd">
        <h2>历史任务记录</h2>
      </div>
      <a-spin :spinning="loadingTasks">
        <div v-if="!historyTasks.length && !loadingTasks" class="empty-hint">暂无历史任务</div>
        <table v-else class="history-table">
          <thead>
            <tr>
              <th>任务名称</th>
              <th>项目</th>
              <th>完成时间</th>
              <th>耗时</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in historyTasks" :key="task.task_id">
              <td class="name-cell">{{ task.title || '—' }}</td>
              <td>{{ projectName(task.project_id) || '—' }}</td>
              <td>{{ formatFinishedAt(task.finished_at || task.created_at) }}</td>
              <td>{{ formatDuration(task) }}</td>
              <td>
                <span class="tag" :class="historyStatusClass(task.status)">
                  {{ historyStatusLabel(task.status) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </a-spin>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import {
  RobotOutlined,
  SendOutlined,
  SettingOutlined,
  UnorderedListOutlined,
  CheckCircleOutlined,
  FieldTimeOutlined,
  FolderOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons-vue'
import { taskApi } from '../../../api'
import { useWorkbenchStore } from '../store/workbench'

const props = defineProps({
  worker: { type: Object, required: true },
})

const emit = defineEmits(['select-item', 'create-item', 'refresh'])

const store = useWorkbenchStore()
const router = useRouter()

const tasks = ref([])
const loadingTasks = ref(false)
const cancellingId = ref('')
let fetchSeq = 0

const activityLabel = computed(() => {
  const map = { online: '空闲', working: '工作中', offline: '离线' }
  return map[props.worker?.activity] || props.worker?.activity || '空闲'
})

function parseUtc(ts) {
  if (!ts) return null
  if (ts instanceof Date) return Number.isNaN(ts.getTime()) ? null : ts
  const s = String(ts)
  const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

function flattenItems(items, acc = []) {
  for (const item of items || []) {
    acc.push(item)
    if (item.children?.length) flattenItems(item.children, acc)
  }
  return acc
}

const projectNameMap = computed(() => {
  const map = {}
  for (const p of store.projects || []) {
    map[p.project_id] = p.name
  }
  return map
})

function projectName(projectId) {
  if (!projectId) return ''
  return projectNameMap.value[projectId] || ''
}

function findItem(itemId) {
  if (!itemId) return null
  for (const p of store.projects || []) {
    const found = flattenItems(p.items).find((i) => i.item_id === itemId)
    if (found) return found
  }
  return null
}

function estimatedRemaining(task) {
  const item = findItem(task.item_id)
  const meta = item?.meta || {}
  return meta.estimated_remaining || ''
}

async function loadTasks(workerId) {
  if (!workerId) {
    tasks.value = []
    return
  }
  const seq = ++fetchSeq
  loadingTasks.value = true
  try {
    const res = await taskApi.list({ worker_id: workerId, page_size: 50 })
    if (seq !== fetchSeq) return
    tasks.value = res?.items || []
  } catch (e) {
    if (seq !== fetchSeq) return
    tasks.value = []
    message.error(e.message || '加载任务失败')
  } finally {
    if (seq === fetchSeq) loadingTasks.value = false
  }
}

// Re-fetch when worker object is replaced (e.g. WS → setWorkbench) or selection changes
watch(
  () => props.worker,
  (w) => loadTasks(w?.worker_id),
  { immediate: true }
)

const runningTasks = computed(() =>
  tasks.value.filter((t) => t.status === 'RUNNING' || t.status === 'NEED_HUMAN')
)

const queuedTasks = computed(() =>
  tasks.value.filter((t) => t.status === 'QUEUED' || t.status === 'RECEIVED')
)

const currentTasks = computed(() => [...runningTasks.value, ...queuedTasks.value])

const historyTasks = computed(() =>
  tasks.value
    .filter((t) => ['COMPLETED', 'FAILED', 'CANCELED'].includes(t.status))
    .slice(0, 10)
)

const avgDurationLabel = computed(() => {
  const completed = tasks.value.filter(
    (t) => t.status === 'COMPLETED' && t.started_at && t.finished_at
  )
  if (!completed.length) return '--'
  let totalMs = 0
  let count = 0
  for (const t of completed) {
    const start = parseUtc(t.started_at)
    const end = parseUtc(t.finished_at)
    if (!start || !end) continue
    const ms = end.getTime() - start.getTime()
    if (ms <= 0) continue
    totalMs += ms
    count += 1
  }
  if (!count) return '--'
  const mins = Math.max(1, Math.round(totalMs / count / 60000))
  return `${mins} 分钟`
})

function goSettings() {
  router.push('/admin/workers')
}

function onViewTask(task) {
  if (!task.item_id) {
    message.info('该任务未关联项目事项')
    return
  }
  const item = findItem(task.item_id) || {
    item_id: task.item_id,
    worker_id: props.worker.worker_id,
  }
  emit('select-item', item, task.project_id)
}

function onCancelTask(task) {
  Modal.confirm({
    title: '取消任务',
    content: `确认取消「${task.title || '该任务'}」？`,
    okText: '确认取消',
    okType: 'danger',
    cancelText: '返回',
    async onOk() {
      cancellingId.value = task.task_id
      try {
        await taskApi.cancel(task.task_id)
        message.success('任务已取消')
        await loadTasks(props.worker.worker_id)
        emit('refresh')
      } catch (e) {
        message.error(e.message || '取消失败')
      } finally {
        cancellingId.value = ''
      }
    },
  })
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function formatFinishedAt(ts) {
  const d = parseUtc(ts)
  if (!d) return '—'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.round((today.getTime() - day.getTime()) / 86400000)
  const hm = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
  if (diffDays === 0) return `今天 ${hm}`
  if (diffDays === 1) return `昨天 ${hm}`
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${hm}`
}

function formatDuration(task) {
  const start = parseUtc(task.started_at)
  const end = parseUtc(task.finished_at)
  if (!start || !end) return '—'
  const mins = Math.max(1, Math.round((end.getTime() - start.getTime()) / 60000))
  if (mins < 60) return `${mins} 分钟`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `${h} 小时 ${m} 分钟` : `${h} 小时`
}

function historyStatusLabel(status) {
  const map = {
    COMPLETED: '已完成',
    FAILED: '失败',
    CANCELED: '已取消',
  }
  return map[status] || status
}

function historyStatusClass(status) {
  const map = {
    COMPLETED: 'tag-done',
    FAILED: 'tag-fail',
    CANCELED: 'tag-cancel',
  }
  return map[status] || 'tag-cancel'
}
</script>

<style scoped>
.worker-detail {
  max-width: 920px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ws-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.header-top {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.avatar {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: var(--brand, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  flex-shrink: 0;
}

.intro {
  min-width: 0;
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.intro h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: var(--ink, #0f172a);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 999px;
}

.status-pill .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.act-online {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.act-working {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.act-offline {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--ink-2, #475569);
  line-height: 1.55;
}

.header-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.kpi-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.kpi-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  margin-bottom: 12px;
}

.kpi-icon.blue {
  background: #eff6ff;
  color: #2563eb;
}

.kpi-icon.green {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.kpi-icon.cyan {
  background: #ecfeff;
  color: #0891b2;
}

.kpi-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink, #0f172a);
  line-height: 1.2;
}

.kpi-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.section-card .section-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.section-hd h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
  color: var(--ink, #0f172a);
}

.count-badge {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.active-task {
  border: 1px solid var(--brand-light, #eef2ff);
  background: #fafaff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.active-hd {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.active-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.task-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--ink, #0f172a);
}

.pct {
  font-size: 22px;
  font-weight: 700;
  color: var(--brand, #4f46e5);
  line-height: 1;
  flex-shrink: 0;
}

.project-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-2, #475569);
  margin-bottom: 10px;
}

.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.note {
  font-size: 12px;
  color: var(--ink-2, #475569);
}

.step-dots {
  display: flex;
  gap: 6px;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--surface-3, #e2e8f0);
}

.dot-completed {
  background: var(--state-success, #16a34a);
}

.dot-running {
  background: var(--brand, #4f46e5);
}

.dot-pending,
.dot-queued {
  background: var(--surface-3, #e2e8f0);
}

.active-ft {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.eta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-2, #475569);
}

.active-actions {
  display: flex;
  gap: 8px;
}

.queued-task {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
  background: var(--surface, #fff);
}

.queued-main {
  min-width: 0;
  flex: 1;
}

.queued-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.queued-desc {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  line-height: 1.45;
}

.queued-icon {
  color: var(--ink-3, #94a3b8);
  font-size: 18px;
  flex-shrink: 0;
}

.tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 500;
  white-space: nowrap;
}

.tag-running {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.tag-queued {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.tag-done {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.tag-fail {
  background: var(--state-error-light, #fef2f2);
  color: var(--state-error, #dc2626);
}

.tag-cancel {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.history-table th {
  text-align: left;
  font-weight: 500;
  color: var(--ink-3, #94a3b8);
  padding: 0 12px 10px 0;
  border-bottom: 1px solid var(--line, #e2e8f0);
}

.history-table td {
  padding: 12px 12px 12px 0;
  border-bottom: 1px solid var(--line, #e2e8f0);
  color: var(--ink-2, #475569);
  vertical-align: middle;
}

.history-table tr:last-child td {
  border-bottom: none;
}

.name-cell {
  color: var(--ink, #0f172a);
  font-weight: 500;
}

.empty-hint {
  color: var(--ink-3, #94a3b8);
  font-size: 13px;
  text-align: center;
  padding: 8px 0;
}

@media (max-width: 720px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
