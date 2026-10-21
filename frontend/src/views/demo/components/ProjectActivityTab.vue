<template>
  <div class="activity-tab">
    <div v-if="!activities.length" class="empty-hint">暂无项目动态</div>
    <div v-else class="timeline">
      <div
        v-for="(a, idx) in activities"
        :key="a.activity_id"
        class="tl-item"
        :class="{ last: idx === activities.length - 1 }"
      >
        <div class="tl-rail">
          <i class="tl-dot" :class="{ hollow: a.kind === 'project' }" />
        </div>
        <div class="tl-body">
          <div class="tl-top">
            <span class="tl-text">{{ a.text }}</span>
            <span class="tl-time">{{ formatRelative(a.created_at) }}</span>
          </div>
          <div class="tl-actor">
            <RobotOutlined v-if="a.actor_type === 'WORKER'" />
            <UserOutlined v-else />
            {{ a.actor_name || '系统' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { RobotOutlined, UserOutlined } from '@ant-design/icons-vue'

defineProps({
  activities: { type: Array, default: () => [] },
})

function parseUtc(ts) {
  if (!ts) return null
  const s = String(ts)
  const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

function formatRelative(ts) {
  const d = parseUtc(ts)
  if (!d) return ''
  const diff = Date.now() - d.getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m}分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}小时前`
  const days = Math.floor(h / 24)
  if (days < 7) return `${days}天前`
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
}

.tl-item {
  display: flex;
  gap: 12px;
  min-height: 64px;
}

.tl-rail {
  width: 16px;
  position: relative;
  flex-shrink: 0;
}

.tl-rail::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 14px;
  bottom: -4px;
  width: 2px;
  background: var(--line, #e2e8f0);
}

.tl-item.last .tl-rail::before {
  display: none;
}

.tl-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--brand, #4f46e5);
  display: block;
  margin: 4px auto 0;
  position: relative;
  z-index: 1;
}

.tl-dot.hollow {
  background: var(--surface, #fff);
  border: 2px solid #cbd5e1;
  box-sizing: border-box;
}

.tl-body {
  flex: 1;
  min-width: 0;
  padding-bottom: 16px;
}

.tl-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.tl-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink, #0f172a);
}

.tl-time {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  white-space: nowrap;
}

.tl-actor {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.empty-hint {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  padding: 12px 0;
}
</style>
