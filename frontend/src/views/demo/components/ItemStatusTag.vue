<template>
  <span class="status-tag" :class="'status-' + (status || 'TODO').toLowerCase()">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'TODO' },
})

const label = computed(() => {
  const map = {
    TODO: '待开始',
    IN_PROGRESS: '进行中',
    COMPLETED: '已完成',
    DELEGATED: '待启动',
    SUSPENDED: '已暂停',
  }
  return map[props.status] || props.status
})
</script>

<style scoped>
.status-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
.status-todo { background: #f3f4f6; color: #6b7280; }
.status-in_progress { background: #dbeafe; color: #2563eb; }
.status-delegated { background: #fef3c7; color: #b45309; }
.status-completed { background: #dcfce7; color: #16a34a; }
.status-suspended { background: #fffbeb; color: #d97706; }
</style>
