<template>
  <ul class="item-tree">
    <li v-for="item in items" :key="item.item_id">
      <div
        class="item-row"
        :class="[
          { active: store.selectedItemId === item.item_id },
          'st-' + statusKey(item),
        ]"
        @click.stop="$emit('select', item)"
      >
        <span class="status-icon" :class="'icon-' + statusKey(item)" aria-hidden="true">
          <CheckCircleFilled v-if="statusKey(item) === 'completed'" />
          <LoadingOutlined v-else-if="statusKey(item) === 'running'" spin />
          <PauseCircleOutlined v-else-if="statusKey(item) === 'suspended'" />
          <span v-else class="hollow-circle" />
        </span>
        <span class="item-name">{{ item.name }}</span>
        <span class="item-status-meta">
          <template v-if="statusKey(item) === 'running'">
            <span class="status-text running">进行中</span>
            <span v-if="item.worker_name" class="worker-name">{{ item.worker_name }}</span>
          </template>
          <template v-else-if="statusKey(item) === 'pending'">
            <span class="status-text pending">待启动</span>
            <span v-if="item.worker_name" class="worker-name">{{ item.worker_name }}</span>
          </template>
          <span v-else class="status-text" :class="statusKey(item)">
            {{ statusLabel(item) }}
          </span>
        </span>
      </div>
      <ProjectTree
        v-if="item.children?.length"
        :items="item.children"
        :project-id="projectId"
        @select="$emit('select', $event)"
      />
    </li>
  </ul>
</template>

<script setup>
import {
  CheckCircleFilled,
  LoadingOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons-vue'
import { useWorkbenchStore } from '../store/workbench'

defineProps({
  items: { type: Array, default: () => [] },
  projectId: { type: String, default: '' },
})

defineEmits(['select'])
const store = useWorkbenchStore()

/** DELEGATED without task = pending start; with task / IN_PROGRESS = running */
function statusKey(item) {
  const status = item?.status
  const taskId = item?.task_id
  if (status === 'COMPLETED') return 'completed'
  if (status === 'SUSPENDED') return 'suspended'
  if (status === 'IN_PROGRESS') return 'running'
  if (status === 'DELEGATED' && taskId) return 'running'
  if (status === 'DELEGATED') return 'pending'
  return 'todo'
}

function statusLabel(item) {
  const key = statusKey(item)
  const map = {
    todo: '待开始',
    pending: '待启动',
    running: '进行中',
    completed: '已完成',
    suspended: '已暂停',
  }
  return map[key] || '待开始'
}
</script>

<style scoped>
.item-tree {
  list-style: none;
  padding-left: 4px;
  margin: 2px 0 6px;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #334155;
}

.item-row:hover {
  background: #f8fafc;
}

.item-row.active,
.item-row.st-running:not(.active) {
  background: #eef2ff;
}

.item-row.st-pending:not(.active) {
  background: transparent;
}

.item-row.active {
  background: #e8edff;
}

.status-icon {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
}

.icon-completed {
  color: #22c55e;
}

.icon-running {
  color: #6366f1;
}

.icon-suspended {
  color: #d97706;
}

.hollow-circle {
  width: 12px;
  height: 12px;
  border: 1.5px solid #cbd5e1;
  border-radius: 50%;
  display: inline-block;
  box-sizing: border-box;
}

.item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.item-status-meta {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.status-text.completed {
  color: #16a34a;
}

.status-text.running {
  color: #6366f1;
}

.status-text.pending {
  color: #b45309;
}

.status-text.todo {
  color: #94a3b8;
}

.status-text.suspended {
  color: #d97706;
}

.worker-name {
  color: #6366f1;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
