<template>
  <div class="step-timeline">
    <div
      v-for="(step, i) in steps"
      :key="step.key || i"
      class="tl-step"
      :class="'st-' + (step.status || 'pending')"
    >
      <div class="tl-rail">
        <div class="tl-dot">
          <CheckOutlined v-if="step.status === 'completed'" />
          <LoadingOutlined v-else-if="step.status === 'running'" spin />
          <span v-else>{{ i + 1 }}</span>
        </div>
        <div v-if="i < steps.length - 1" class="tl-line" />
      </div>

      <div class="tl-body">
        <div class="tl-hd">
          <div class="tl-title">{{ i + 1 }}. {{ step.title }}</div>
          <span class="tl-status-tag" :class="'tag-' + (step.status || 'pending')">
            {{ statusLabel(step.status) }}
          </span>
        </div>
        <div v-if="step.agent_name || step.duty_name" class="tl-agent">
          执行 Agent：{{ step.agent_name || step.duty_name }}
        </div>
        <div v-if="step.time_range || step.planned_start || step.started_at || step.eta" class="tl-time">
          {{ step.time_range || formatTime(step) }}
        </div>
        <div v-if="step.intent && step.intent !== step.title" class="tl-intent">{{ step.intent }}</div>
        <div v-if="step.detail" class="tl-detail">{{ step.detail }}</div>

        <div v-if="step.result" class="tl-result-row">
          <span class="tl-result-label">结果：</span>
          <span class="tl-result-link">{{ step.result }}</span>
        </div>

        <div v-if="step.tags?.length" class="tl-tags">
          <span v-for="t in step.tags" :key="t" class="tl-chip">{{ t }}</span>
        </div>

        <div v-if="stepCandidates(step).length" class="tl-table-wrap">
          <table class="tl-table">
            <thead>
              <tr>
                <th>简历编号</th>
                <th>候选人</th>
                <th>结果</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in stepCandidates(step)" :key="row.id || row.name || ri">
                <td>{{ row.id || row.no || '—' }}</td>
                <td>{{ row.name }}</td>
                <td>
                  <span :class="row.result === '通过' ? 'res-ok' : 'res-err'">{{ row.result }}</span>
                </td>
                <td>{{ row.reason || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="step.status === 'running' && (step.batch_progress || step.logs?.length)" class="tl-live">
          <div v-if="step.batch_progress" class="batch-progress">
            <div class="batch-label">当前批次进度</div>
            <a-progress
              :percent="step.batch_progress.percent || 0"
              size="small"
              stroke-color="var(--brand)"
              :format="() => `${step.batch_progress.done || 0}/${step.batch_progress.total || 0} 份`"
            />
          </div>
          <div v-if="step.logs?.length" class="live-logs">
            <div class="live-hd">实时日志 <span class="live-badge">实时更新中</span></div>
            <div v-for="(log, li) in step.logs" :key="li" class="log-line">{{ log }}</div>
          </div>
        </div>

        <div v-if="stepOutputs(step).length" class="planned">
          <div class="planned-label">产出：</div>
          <div class="tl-tags">
            <a
              v-for="o in stepOutputs(step)"
              :key="o.name || o"
              class="tl-chip tl-output"
              :href="o.path || undefined"
              :target="o.path ? '_blank' : undefined"
              rel="noopener"
            >{{ o.name || o }}</a>
          </div>
        </div>

        <div v-else-if="step.planned_outputs?.length" class="planned">
          <div class="planned-label">计划输出：</div>
          <div class="tl-tags">
            <span v-for="o in step.planned_outputs" :key="o" class="tl-chip">{{ o }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { CheckOutlined, LoadingOutlined } from '@ant-design/icons-vue'

defineProps({
  steps: { type: Array, default: () => [] },
  itemStatus: { type: String, default: '' },
})

function statusLabel(status) {
  const map = {
    completed: '已完成',
    running: '进行中',
    pending: '待执行',
    queued: '排队中',
    failed: '失败',
    cancelled: '已取消',
    canceled: '已取消',
    suspended: '已暂停',
    paused: '暂停中',
  }
  return map[status] || status || '待执行'
}

function formatTime(step) {
  if (step.planned_start && step.planned_end) {
    return `${shortTime(step.planned_start)} - ${shortTime(step.planned_end)}`
  }
  if (step.started_at && step.finished_at) return `${shortTime(step.started_at)} - ${shortTime(step.finished_at)}`
  if (step.started_at) return `${shortTime(step.started_at)} - 进行中`
  if (step.eta) return `预计 ${step.eta}`
  return ''
}

function shortTime(v) {
  if (!v) return ''
  const s = String(v)
  if (s.length >= 16) return s.slice(5, 16).replace('T', ' ')
  return s
}

function stepCandidates(step) {
  return step.candidates || step.table || []
}

function stepOutputs(step) {
  const outs = step.outputs || []
  return outs.map((o) => (typeof o === 'string' ? { name: o } : o)).filter((o) => o?.name)
}
</script>

<style scoped>
.step-timeline {
  display: flex;
  flex-direction: column;
}

.tl-step {
  display: flex;
  gap: 14px;
}

.tl-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.tl-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-3, #94a3b8);
  border: 2px solid var(--surface-3, #e2e8f0);
  box-sizing: border-box;
}

.st-completed .tl-dot {
  background: var(--state-success, #16a34a);
  border-color: var(--state-success, #16a34a);
  color: #fff;
}

.st-running .tl-dot {
  background: var(--brand-light, #eef2ff);
  border-color: var(--brand, #4f46e5);
  color: var(--brand, #4f46e5);
}

.st-failed .tl-dot {
  background: var(--state-error-light, #fef2f2);
  border-color: var(--state-error, #dc2626);
  color: var(--state-error, #dc2626);
}

.tl-line {
  flex: 1;
  width: 2px;
  min-height: 20px;
  background: var(--line, #e2e8f0);
  margin: 4px 0;
}

.st-completed .tl-line {
  background: #bbf7d0;
}

.tl-body {
  flex: 1;
  padding-bottom: 22px;
  min-width: 0;
}

.tl-hd {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.tl-title {
  font-weight: 650;
  font-size: 14px;
  color: var(--ink, #0f172a);
}

.tl-status-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}

.tag-completed {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.tag-running {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.tag-pending,
.tag-queued {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.tag-failed {
  background: var(--state-error-light, #fef2f2);
  color: var(--state-error, #dc2626);
}

.tag-suspended,
.tag-paused,
.tag-cancelled,
.tag-canceled {
  background: #fff7ed;
  color: #c2410c;
}

.st-suspended .tl-dot,
.st-paused .tl-dot {
  border-color: #fb923c;
  color: #c2410c;
}

.tl-time {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-top: 4px;
}

.tl-agent {
  font-size: 12px;
  color: var(--brand, #4f46e5);
  margin-top: 4px;
}

.tl-intent {
  font-size: 12px;
  color: var(--ink-2, #475569);
  margin-top: 6px;
  line-height: 1.45;
}

.tl-detail {
  font-size: 13px;
  color: var(--ink-2, #475569);
  margin-top: 8px;
  line-height: 1.55;
}

.tl-result-row {
  margin-top: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.tl-result-label {
  color: var(--ink-3, #94a3b8);
}

.tl-result-link {
  color: var(--brand, #4f46e5);
  font-weight: 500;
  cursor: default;
}

.tl-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tl-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid #bfdbfe;
  color: #2563eb;
  background: #eff6ff;
}

a.tl-output {
  text-decoration: none;
  cursor: pointer;
}

a.tl-output:hover {
  border-color: var(--brand, #4f46e5);
}

.tl-table-wrap {
  margin-top: 12px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 10px;
  overflow: hidden;
}

.tl-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.tl-table th {
  text-align: left;
  font-weight: 500;
  color: var(--ink-3, #94a3b8);
  background: var(--surface-2, #f1f5f9);
  padding: 8px 12px;
}

.tl-table td {
  padding: 8px 12px;
  border-top: 1px solid var(--line, #e2e8f0);
  color: var(--ink-2, #475569);
}

.res-ok { color: var(--state-success, #16a34a); font-weight: 500; }
.res-err { color: var(--state-error, #dc2626); font-weight: 500; }

.tl-live {
  margin-top: 10px;
  border: 1px solid var(--brand-light, #eef2ff);
  background: #fafaff;
  border-radius: 10px;
  padding: 12px;
}

.batch-label,
.live-hd,
.planned-label {
  font-size: 12px;
  color: var(--ink-2, #475569);
  margin-bottom: 6px;
}

.live-badge {
  color: var(--brand, #4f46e5);
  font-size: 11px;
  margin-left: 6px;
}

.log-line {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--ink-2, #475569);
  line-height: 1.6;
}

.planned {
  margin-top: 8px;
}
</style>
