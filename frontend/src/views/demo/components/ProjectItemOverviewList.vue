<template>
  <div class="item-overview">
    <div class="section-hd">
      <h2>事项进度总览</h2>
      <span class="count-badge">{{ items.length }}</span>
    </div>
    <div class="item-list">
      <div
        v-for="(item, idx) in items"
        :key="item.item_id"
        class="item-row"
        :class="{ active: isActive(item), done: item.status === 'COMPLETED' }"
        @click="$emit('select-item', item)"
      >
        <div class="item-idx" :class="'st-' + (item.status || 'TODO').toLowerCase()">
          {{ idx + 1 }}
        </div>
        <div class="item-main">
          <div class="item-title-row">
            <span class="item-name">{{ item.name }}</span>
            <ItemStatusTag :status="item.status" />
          </div>
          <div class="item-meta">
            <template v-if="item.status === 'COMPLETED'">
              <span v-if="ownerName"><UserOutlined /> 负责人：{{ ownerName }}</span>
              <span v-if="item.completed_at">
                <CheckCircleOutlined /> 完成时间：{{ formatDate(item.completed_at) }}
              </span>
            </template>
            <template v-else-if="item.worker_name">
              <span><FolderOutlined /> 委派给：{{ item.worker_name }}</span>
            </template>
            <template v-else>
              <span v-if="item.planned_start">
                <CalendarOutlined /> 计划时间：{{ formatDate(item.planned_start) }}
              </span>
              <span v-else>待开始</span>
            </template>
          </div>
          <template v-if="['IN_PROGRESS', 'DELEGATED'].includes(item.status)">
            <a-progress
              :percent="item.progress_pct || 0"
              size="small"
              stroke-color="var(--brand)"
              :show-info="true"
            />
            <div v-if="progressNote(item)" class="item-note">
              <ThunderboltOutlined /> {{ progressNote(item) }}
            </div>
          </template>
        </div>
        <div class="item-aside">
          <CheckCircleFilled v-if="item.status === 'COMPLETED'" class="done-icon" />
          <a-button
            v-else-if="['IN_PROGRESS', 'DELEGATED'].includes(item.status)"
            size="small"
            type="link"
            @click.stop="$emit('select-item', item)"
          >
            查看详情
          </a-button>
          <span v-else class="pending-ring" />
        </div>
      </div>
      <div v-if="!items.length" class="empty-hint">暂无事项</div>
    </div>
  </div>
</template>

<script setup>
import {
  UserOutlined,
  CheckCircleOutlined,
  CheckCircleFilled,
  FolderOutlined,
  CalendarOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import ItemStatusTag from './ItemStatusTag.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  ownerName: { type: String, default: '' },
  activeItemId: { type: String, default: '' },
})

defineEmits(['select-item'])

function isActive(item) {
  return props.activeItemId === item.item_id || ['IN_PROGRESS', 'DELEGATED'].includes(item.status)
}

function progressNote(item) {
  return item.meta?.progress_note || ''
}

function formatDate(ts) {
  if (!ts) return ''
  const s = String(ts)
  const d = new Date(/Z$|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`)
  if (Number.isNaN(d.getTime())) {
    return s.slice(0, 10)
  }
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
</script>

<style scoped>
.section-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.section-hd h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
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

.item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.item-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 12px;
  cursor: pointer;
  background: var(--surface, #fff);
  transition: border-color 0.15s, background 0.15s;
}

.item-row:hover {
  border-color: var(--brand, #4f46e5);
}

.item-row.active {
  border-color: var(--brand, #4f46e5);
  border-left-width: 3px;
  background: #fafaff;
}

.item-idx {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  margin-top: 2px;
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.item-idx.st-completed {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.item-idx.st-in_progress,
.item-idx.st-delegated {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.item-name {
  font-weight: 600;
  font-size: 14px;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-bottom: 6px;
}

.item-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.item-note {
  margin-top: 6px;
  font-size: 12px;
  color: var(--brand, #4f46e5);
  display: flex;
  align-items: center;
  gap: 4px;
}

.item-aside {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  min-height: 28px;
}

.done-icon {
  color: var(--state-success, #16a34a);
  font-size: 20px;
}

.pending-ring {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid var(--surface-3, #e2e8f0);
}

.empty-hint {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  padding: 8px 0;
}
</style>
