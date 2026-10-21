<template>
  <div class="wb-home">
    <section class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon indigo"><SyncOutlined /></div>
        <div class="stat-num indigo">{{ inProgressCount }}</div>
        <div class="stat-label">进行中任务</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon amber"><ExclamationCircleOutlined /></div>
        <div class="stat-num amber">{{ pendingCount }}</div>
        <div class="stat-label">待审核操作</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon green"><CheckCircleOutlined /></div>
        <div class="stat-num green">{{ store.workloadDone }}</div>
        <div class="stat-label">今日完成</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon blue"><RobotOutlined /></div>
        <div class="stat-num blue">{{ activeWorkers }}</div>
        <div class="stat-label">活跃数字员工</div>
      </div>
    </section>

    <section class="home-section">
      <h2 class="section-title">快捷操作</h2>
      <div class="quick-grid">
        <button type="button" class="quick-card" @click="$emit('create-item')">
          <div class="quick-icon indigo"><SendOutlined /></div>
          <span class="quick-title">委派新任务</span>
          <span class="quick-desc">指派数字员工执行</span>
        </button>
        <button type="button" class="quick-card" @click="$emit('create-project')">
          <div class="quick-icon blue"><FolderAddOutlined /></div>
          <span class="quick-title">创建项目</span>
          <span class="quick-desc">新建工作项目</span>
        </button>
        <button type="button" class="quick-card" @click="onViewReports">
          <div class="quick-icon slate"><BarChartOutlined /></div>
          <span class="quick-title">查看报表</span>
          <span class="quick-desc">数据分析与洞察</span>
        </button>
        <button type="button" class="quick-card approval" @click="openFirstApproval">
          <div class="quick-icon amber">
            <SafetyOutlined />
            <span v-if="pendingCount" class="quick-badge">{{ pendingCount }}</span>
          </div>
          <span class="quick-title">审批中心</span>
          <span class="quick-desc">{{ pendingCount }} 项待审核</span>
        </button>
      </div>
    </section>

    <section class="home-section">
      <h2 class="section-title">最近活动</h2>
      <div class="ws-card activity-card">
        <div v-if="activities.length" class="activity-timeline">
          <div
            v-for="(a, idx) in activities"
            :key="a.id"
            class="timeline-item"
            :class="{ last: idx === activities.length - 1 }"
          >
            <div class="timeline-rail">
              <div class="timeline-dot" :class="'kind-' + (a.kind || 'completed')">
                <CheckCircleOutlined v-if="a.kind === 'completed'" />
                <PlayCircleOutlined v-else-if="a.kind === 'running'" />
                <ExclamationCircleOutlined v-else-if="a.kind === 'approval'" />
                <FolderAddOutlined v-else-if="a.kind === 'project'" />
                <CheckCircleOutlined v-else />
              </div>
              <div v-if="idx < activities.length - 1" class="timeline-line" />
            </div>
            <div class="timeline-body">
              <div class="timeline-text">
                <template v-if="a.worker_name"><b>{{ a.worker_name }}</b> {{ a.text }}</template>
                <template v-else>{{ a.text }}</template>
              </div>
              <div class="timeline-time">{{ formatRelative(a.created_at) }}</div>
            </div>
          </div>
        </div>
        <div v-else class="empty-hint">暂无最近活动</div>
      </div>
    </section>

    <section class="home-section">
      <h2 class="section-title">数字员工状态</h2>
      <div class="worker-grid">
        <div
          v-for="w in store.workers"
          :key="w.worker_id"
          class="worker-card"
          @click="$emit('select-worker', w.worker_id)"
        >
          <div class="worker-card-top">
            <div class="worker-avatar" :class="{ working: w.activity === 'working' }">
              <RobotOutlined />
            </div>
            <div class="worker-info">
              <div class="worker-name">{{ w.name }}</div>
              <div class="worker-status" :class="'act-' + w.activity">
                <span class="status-dot" />
                {{ activityLabel(w.activity) }}
              </div>
            </div>
          </div>
          <div class="worker-card-bottom">
            <span class="done-label">今日完成任务</span>
            <span class="done-num">{{ w.today_done_count || 0 }}</span>
          </div>
        </div>
        <div v-if="!store.workers.length" class="empty-hint">暂无数字员工</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  SyncOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  RobotOutlined,
  SendOutlined,
  FolderAddOutlined,
  BarChartOutlined,
  SafetyOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons-vue'
import { useWorkbenchStore } from '../store/workbench'

const emit = defineEmits(['create-project', 'create-item', 'select-worker', 'open-approval'])

const store = useWorkbenchStore()

const pendingCount = computed(() => store.pendingApprovals.length)

const inProgressCount = computed(() => {
  let n = 0
  for (const p of store.projects) {
    n += p.in_progress_count || 0
  }
  return n
})

const activeWorkers = computed(() =>
  store.workers.filter((w) => w.activity === 'online' || w.activity === 'working').length
)

const activities = computed(() => store.recentActivities || [])

function activityLabel(activity) {
  const map = { online: '空闲', working: '工作中', offline: '离线' }
  return map[activity] || activity || '空闲'
}

function openFirstApproval() {
  const a = store.pendingApprovals[0]
  if (a) emit('open-approval', a)
  else message.info('暂无待审核操作')
}

function onViewReports() {
  message.info('报表功能规划中')
}

function formatRelative(ts) {
  if (!ts) return ''
  const t = new Date(ts).getTime()
  if (Number.isNaN(t)) return ''
  const diff = Date.now() - t
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m}分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}小时前`
  const d = Math.floor(h / 24)
  if (d === 1) return '昨天'
  return `${d}天前`
}
</script>

<style scoped>
.wb-home {
  max-width: 960px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card,
.ws-card,
.quick-card,
.worker-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.stat-card {
  padding: 16px 18px;
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-bottom: 12px;
}

.stat-icon.indigo,
.quick-icon.indigo {
  background: #eef2ff;
  color: #4f46e5;
}

.stat-icon.amber,
.quick-icon.amber {
  background: #fffbeb;
  color: #d97706;
}

.stat-icon.green {
  background: #f0fdf4;
  color: #16a34a;
}

.stat-icon.blue,
.quick-icon.blue {
  background: #eff6ff;
  color: #2563eb;
}

.quick-icon.slate {
  background: #f1f5f9;
  color: #475569;
}

.stat-num {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.stat-num.indigo { color: #4f46e5; }
.stat-num.amber { color: #d97706; }
.stat-num.green { color: #16a34a; }
.stat-num.blue { color: #2563eb; }

.stat-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-2, #475569);
}

.home-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink, #0f172a);
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.quick-card {
  position: relative;
  text-align: left;
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.quick-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08);
}

.quick-card.approval {
  border-left: 3px solid #d97706;
}

.quick-icon {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  margin-bottom: 12px;
}

.quick-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #d97706;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.quick-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink, #0f172a);
  margin-bottom: 4px;
}

.quick-desc {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.activity-card {
  padding: 18px 20px;
}

.activity-timeline {
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  gap: 12px;
  min-height: 52px;
}

.timeline-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.timeline-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  z-index: 1;
}

.kind-completed {
  background: #f0fdf4;
  color: #16a34a;
}

.kind-running {
  background: #eff6ff;
  color: #2563eb;
}

.kind-approval {
  background: #fffbeb;
  color: #d97706;
}

.kind-project {
  background: #eef2ff;
  color: #4f46e5;
}

.timeline-line {
  flex: 1;
  width: 2px;
  background: var(--line, #e2e8f0);
  margin: 4px 0;
  min-height: 12px;
}

.timeline-body {
  flex: 1;
  padding-bottom: 16px;
  min-width: 0;
}

.timeline-item.last .timeline-body {
  padding-bottom: 0;
}

.timeline-text {
  font-size: 13px;
  color: var(--ink, #0f172a);
  line-height: 1.45;
}

.timeline-time {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-top: 4px;
}

.worker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.worker-card {
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.worker-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08);
}

.worker-card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}

.worker-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.worker-avatar.working {
  background: #4f46e5;
  color: #fff;
}

.worker-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink, #0f172a);
  margin-bottom: 4px;
}

.worker-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-2, #475569);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
}

.act-online .status-dot { background: #16a34a; }
.act-working .status-dot { background: #4f46e5; }
.act-offline .status-dot { background: #94a3b8; }

.worker-card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid var(--line, #e2e8f0);
  background: #fafbfc;
}

.done-label {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.done-num {
  font-size: 20px;
  font-weight: 700;
  color: #4f46e5;
  line-height: 1;
}

.empty-hint {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  padding: 12px 0;
}

@media (max-width: 960px) {
  .stat-grid,
  .quick-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
