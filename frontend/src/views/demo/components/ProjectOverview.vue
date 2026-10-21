<template>
  <div class="project-overview">
    <div class="ws-card header-card">
      <div class="title-row">
        <h1>{{ project.name }}</h1>
        <div class="title-actions">
          <a-tooltip title="中止">
            <button
              type="button"
              class="icon-btn warn"
              :disabled="actionLoading"
              @click="confirmSuspend"
            >
              <PauseCircleOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="完成">
            <button
              type="button"
              class="icon-btn ok"
              :disabled="actionLoading"
              @click="confirmComplete"
            >
              <CheckCircleOutlined />
            </button>
          </a-tooltip>
          <a-tooltip title="删除">
            <button
              type="button"
              class="icon-btn danger"
              :disabled="actionLoading"
              @click="confirmDelete"
            >
              <DeleteOutlined />
            </button>
          </a-tooltip>
        </div>
      </div>
      <p v-if="displayDescription" class="desc">{{ displayDescription }}</p>
      <div v-if="dateRangeLabel" class="date-range">
        <CalendarOutlined />
        {{ dateRangeLabel }}
      </div>
      <div class="progress-row">
        <a-progress :percent="project.progress_pct || 0" stroke-color="var(--brand)" :show-info="false" :stroke-width="10" />
        <span class="progress-label">{{ project.progress_pct || 0 }}% 完成</span>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <b>{{ project.item_count || 0 }}</b>
        <span>事项总数</span>
      </div>
      <div class="stat-card">
        <b class="ok">{{ project.completed_count || 0 }}</b>
        <span>已完成</span>
      </div>
      <div class="stat-card">
        <b class="run">{{ project.in_progress_count || 0 }}</b>
        <span>进行中</span>
      </div>
      <div class="stat-card">
        <b class="del">{{ project.delegated_count || 0 }}</b>
        <span>已委派</span>
      </div>
    </div>

    <div v-if="projectApprovals.length" class="ws-card approval-banner">
      <div class="approval-banner-hd">
        <span class="section-title">待审核操作</span>
        <span class="badge-count">{{ projectApprovals.length }}</span>
      </div>
      <div
        v-for="a in projectApprovals"
        :key="a.msg_id"
        class="approval-row"
      >
        <div>
          <div class="approval-title">{{ a.title }}</div>
          <div class="approval-meta">
            <span class="risk-tag">高风险</span>
            {{ a.worker_name }} · {{ a.item_name }}
          </div>
        </div>
        <a-button type="primary" size="small" @click="$emit('open-approval', a)">审核</a-button>
      </div>
    </div>

    <div class="ws-card section-card">
      <ProjectItemOverviewList
        :items="flatItems"
        :owner-name="ownerName"
        @select-item="(item) => $emit('select-item', item)"
      />
    </div>

    <div class="ws-card tabs-card">
      <div class="tabs-bar">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <component :is="tab.icon" />
          {{ tab.label }}
          <span v-if="tab.count != null" class="tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <div class="tab-body">
        <a-spin :spinning="tabLoading">
          <ProjectGanttTab
            v-if="activeTab === 'timeline'"
            :project="project"
            :items="flatItems"
          />
          <ProjectMembersTab
            v-else-if="activeTab === 'members'"
            :members="members"
          />
          <ProjectDocumentsTab
            v-else-if="activeTab === 'documents'"
            :documents="documents"
            :uploading="uploading"
            @upload="onUploadFile"
          />
          <ProjectActivityTab
            v-else
            :activities="activities"
          />
        </a-spin>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  CalendarOutlined,
  ScheduleOutlined,
  TeamOutlined,
  FolderOutlined,
  FundOutlined,
  PauseCircleOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { projectApi } from '../../../api'
import { useWorkbenchStore } from '../store/workbench'
import ProjectItemOverviewList from './ProjectItemOverviewList.vue'
import ProjectGanttTab from './ProjectGanttTab.vue'
import ProjectMembersTab from './ProjectMembersTab.vue'
import ProjectDocumentsTab from './ProjectDocumentsTab.vue'
import ProjectActivityTab from './ProjectActivityTab.vue'

const props = defineProps({
  project: { type: Object, required: true },
})

const emit = defineEmits(['select-item', 'delegate', 'open-approval', 'refresh'])

const store = useWorkbenchStore()
const activeTab = ref('timeline')
const members = ref([])
const documents = ref([])
const activities = ref([])
const tabLoading = ref(false)
const uploading = ref(false)
const actionLoading = ref(false)

function flattenItems(items, acc = []) {
  for (const item of items || []) {
    acc.push(item)
    if (item.children?.length) flattenItems(item.children, acc)
  }
  return acc
}

const flatItems = computed(() => flattenItems(props.project.items))

const ownerName = computed(() => props.project.owner?.name || '')

const displayDescription = computed(() => {
  const raw = props.project.description || ''
  return raw
    .split('\n')
    .filter((line) => line.trim() && line.trim() !== 'demo-workbench-v1')
    .join('\n')
    .trim()
})

function formatDateOnly(ts) {
  if (!ts) return ''
  const s = String(ts)
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10)
  return s
}

const dateRangeLabel = computed(() => {
  const a = formatDateOnly(props.project.start_date)
  const b = formatDateOnly(props.project.end_date)
  if (a && b) return `${a} 至 ${b}`
  if (a) return a
  if (b) return b
  return ''
})

const projectApprovals = computed(() =>
  store.pendingApprovals.filter((a) =>
    a.project_name === props.project.name ||
    flatItems.value.some((i) => i.item_id === a.item_id)
  )
)

const tabs = computed(() => [
  { key: 'timeline', label: '项目时间线', icon: ScheduleOutlined },
  { key: 'members', label: '项目成员', icon: TeamOutlined, count: members.value.length || null },
  { key: 'documents', label: '项目资料', icon: FolderOutlined, count: documents.value.length || null },
  { key: 'activity', label: '项目动态', icon: FundOutlined },
])

async function loadTabs(projectId) {
  if (!projectId) {
    members.value = []
    documents.value = []
    activities.value = []
    return
  }
  tabLoading.value = true
  try {
    const [m, d, a] = await Promise.all([
      projectApi.members(projectId),
      projectApi.documents(projectId),
      projectApi.activities(projectId),
    ])
    members.value = m?.items || []
    documents.value = d?.items || []
    activities.value = a?.items || []
  } catch (e) {
    message.error(e.message || '加载项目详情失败')
  } finally {
    tabLoading.value = false
  }
}

watch(
  () => props.project?.project_id,
  (id) => {
    activeTab.value = 'timeline'
    loadTabs(id)
  },
  { immediate: true }
)

async function onUploadFile(file) {
  if (!file || !props.project?.project_id) return
  uploading.value = true
  try {
    await projectApi.uploadDocument(props.project.project_id, file)
    message.success('上传成功')
    await loadTabs(props.project.project_id)
  } catch (err) {
    message.error(err.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function setStatus(status, successText) {
  if (!props.project?.project_id) return
  actionLoading.value = true
  try {
    await projectApi.update(props.project.project_id, { status })
    message.success(successText)
    store.clearSelection()
    emit('refresh')
  } catch (e) {
    message.error(e.message || '操作失败')
    throw e
  } finally {
    actionLoading.value = false
  }
}

function confirmSuspend() {
  Modal.confirm({
    title: '中止项目',
    content: `确认中止「${props.project.name}」？中止后将不再出现在工作台项目列表中。`,
    okText: '中止',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      await setStatus('SUSPENDED', '项目已中止')
    },
  })
}

function confirmComplete() {
  Modal.confirm({
    title: '完成项目',
    content: `确认将「${props.project.name}」标记为已完成？`,
    okText: '完成',
    cancelText: '取消',
    async onOk() {
      await setStatus('COMPLETED', '项目已完成')
    },
  })
}

function confirmDelete() {
  Modal.confirm({
    title: '删除项目',
    content: `确认删除「${props.project.name}」？删除后不可恢复，相关事项与资料将一并清理。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      if (!props.project?.project_id) return
      actionLoading.value = true
      try {
        await projectApi.remove(props.project.project_id)
        message.success('项目已删除')
        store.clearSelection()
        emit('refresh')
      } catch (e) {
        message.error(e.message || '删除失败')
        throw e
      } finally {
        actionLoading.value = false
      }
    },
  })
}
</script>

<style scoped>
.project-overview {
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

.header-card h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  flex: 1;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.title-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--line, #e2e8f0);
  background: var(--surface, #fff);
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--ink-2, #475569);
  font-size: 16px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.icon-btn:hover:not(:disabled) {
  border-color: currentColor;
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.icon-btn.warn:hover:not(:disabled) {
  color: var(--state-warning, #d97706);
  background: var(--state-warning-light, #fffbeb);
}

.icon-btn.ok:hover:not(:disabled) {
  color: var(--state-success, #16a34a);
  background: var(--state-success-light, #f0fdf4);
}

.icon-btn.danger:hover:not(:disabled) {
  color: var(--state-error, #dc2626);
  background: var(--state-error-light, #fef2f2);
}

.desc {
  margin: 0 0 10px;
  color: var(--ink-2, #475569);
  font-size: 14px;
}

.date-range {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-2, #475569);
  margin-bottom: 14px;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-row :deep(.ant-progress) {
  flex: 1;
  margin: 0;
}

.progress-label {
  font-size: 13px;
  color: var(--ink-2, #475569);
  white-space: nowrap;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 14px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.stat-card b {
  display: block;
  font-size: 24px;
  color: var(--ink, #0f172a);
  line-height: 1.2;
}

.stat-card b.ok { color: var(--state-success, #16a34a); }
.stat-card b.run { color: var(--brand, #4f46e5); }
.stat-card b.del { color: #0891b2; }

.stat-card span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.approval-banner-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.badge-count {
  background: var(--state-warning-light, #fffbeb);
  color: var(--state-warning, #d97706);
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
}

.approval-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--line, #e2e8f0);
}

.approval-title {
  font-size: 13px;
  font-weight: 600;
}

.approval-meta {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-tag {
  background: var(--state-error-light, #fef2f2);
  color: var(--state-error, #dc2626);
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
}

.tabs-card {
  padding-top: 8px;
}

.tabs-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid var(--line, #e2e8f0);
  padding-bottom: 0;
  flex-wrap: wrap;
}

.tab-btn {
  border: none;
  background: transparent;
  padding: 12px 12px;
  font-size: 13px;
  color: var(--ink-2, #475569);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.tab-btn.active {
  color: var(--brand, #4f46e5);
  border-bottom-color: var(--brand, #4f46e5);
  font-weight: 600;
}

.tab-count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.tab-body {
  padding-top: 16px;
  min-height: 120px;
}

@media (max-width: 720px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
