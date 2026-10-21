<template>
  <div class="gantt-tab">
    <div v-if="!rows.length" class="empty-hint">暂无事项计划时间</div>
    <div v-else class="gantt">
      <div class="gantt-grid">
        <div class="corner" />
        <div class="axis">
          <span v-for="m in months" :key="m.key" class="month" :style="{ flex: m.span }">{{ m.label }}</span>
        </div>
        <template v-for="row in rows" :key="row.item_id">
          <div class="label">{{ row.name }}</div>
          <div class="track">
            <div
              class="bar"
              :class="'bar-' + row.statusClass"
              :style="{ left: row.left, width: row.width }"
            />
          </div>
        </template>
        <div class="corner spacer" />
        <div class="track-overlay">
          <div class="today-line" :style="{ left: todayLeft }">
            <span class="today-tag">今天</span>
          </div>
        </div>
      </div>
      <div class="legend">
        <span><i class="dot done" />已完成</span>
        <span><i class="dot run" />进行中</span>
        <span><i class="dot todo" />待开始</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  project: { type: Object, required: true },
  items: { type: Array, default: () => [] },
})

function parseDate(ts) {
  if (!ts) return null
  if (ts instanceof Date) return Number.isNaN(ts.getTime()) ? null : ts
  const s = String(ts)
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    const d = new Date(`${s}T00:00:00Z`)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

const range = computed(() => {
  let start = parseDate(props.project.start_date)
  let end = parseDate(props.project.end_date)
  const itemDates = []
  for (const item of props.items) {
    const a = parseDate(item.planned_start)
    const b = parseDate(item.planned_end) || parseDate(item.completed_at)
    if (a) itemDates.push(a)
    if (b) itemDates.push(b)
  }
  if (!start && itemDates.length) start = new Date(Math.min(...itemDates.map((d) => d.getTime())))
  if (!end && itemDates.length) end = new Date(Math.max(...itemDates.map((d) => d.getTime())))
  if (!start || !end) {
    const now = new Date()
    start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))
    end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 2, 1))
  }
  if (end.getTime() <= start.getTime()) end = new Date(start.getTime() + 30 * 86400000)
  return { start, end, total: end.getTime() - start.getTime() }
})

const months = computed(() => {
  const { start, end } = range.value
  const list = []
  let cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 1))
  while (cursor.getTime() < end.getTime()) {
    const next = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 1, 1))
    const from = Math.max(cursor.getTime(), start.getTime())
    const to = Math.min(next.getTime(), end.getTime())
    list.push({
      key: `${cursor.getUTCFullYear()}-${cursor.getUTCMonth()}`,
      label: `${cursor.getUTCMonth() + 1}月`,
      span: Math.max(to - from, 1),
    })
    cursor = next
  }
  return list
})

function pct(ms) {
  const { start, total } = range.value
  return `${Math.min(100, Math.max(0, ((ms - start.getTime()) / total) * 100))}%`
}

const todayLeft = computed(() => pct(Date.now()))

const rows = computed(() =>
  props.items
    .map((item) => {
      const start = parseDate(item.planned_start)
      const end = parseDate(item.planned_end) || parseDate(item.completed_at) || start
      if (!start || !end) return null
      const leftMs = start.getTime()
      const rightMs = Math.max(end.getTime(), leftMs + 86400000)
      const status = item.status || 'TODO'
      let statusClass = 'todo'
      if (status === 'COMPLETED') statusClass = 'done'
      else if (status === 'IN_PROGRESS' || status === 'DELEGATED') statusClass = 'run'
      return {
        item_id: item.item_id,
        name: item.name,
        left: pct(leftMs),
        width: `${Math.max(2, ((rightMs - leftMs) / range.value.total) * 100)}%`,
        statusClass,
      }
    })
    .filter(Boolean)
)
</script>

<style scoped>
.gantt-grid {
  display: grid;
  grid-template-columns: 100px 1fr;
  column-gap: 12px;
  row-gap: 14px;
  align-items: center;
  position: relative;
}

.corner {
  height: 1px;
}

.axis {
  display: flex;
  border-bottom: 1px solid var(--line, #e2e8f0);
  padding-bottom: 6px;
}

.month {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  text-align: center;
}

.label {
  font-size: 12px;
  color: var(--ink-2, #475569);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track {
  position: relative;
  height: 14px;
  background: var(--surface-2, #f1f5f9);
  border-radius: 999px;
  overflow: hidden;
}

.bar {
  position: absolute;
  top: 0;
  height: 100%;
  border-radius: 999px;
  min-width: 8px;
}

.bar-done { background: var(--state-success, #16a34a); }
.bar-run { background: var(--brand, #4f46e5); }
.bar-todo { background: #cbd5e1; }

.spacer { height: 0; }

.track-overlay {
  position: relative;
  height: 0;
  grid-column: 2;
  grid-row: 2 / -1;
  pointer-events: none;
  align-self: stretch;
}

.today-line {
  position: absolute;
  top: -8px;
  bottom: 0;
  width: 2px;
  background: #ef4444;
  transform: translateX(-50%);
}

.today-tag {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translate(-50%, -100%);
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.legend {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  font-size: 12px;
  color: var(--ink-2, #475569);
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot.done { background: var(--state-success, #16a34a); }
.dot.run { background: var(--brand, #4f46e5); }
.dot.todo { background: #cbd5e1; }

.empty-hint {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  padding: 12px 0;
}
</style>
