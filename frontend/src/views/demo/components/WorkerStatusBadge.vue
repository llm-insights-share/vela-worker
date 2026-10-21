<template>
  <span class="worker-status" :class="'act-' + activity">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  activity: { type: String, default: 'online' },
})

const label = computed(() => {
  const map = { online: '空闲', working: '工作中', offline: '离线' }
  return map[props.activity] || props.activity
})
</script>

<style scoped>
.worker-status {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  display: inline-block;
}
.act-online { background: var(--state-success-light, #f0fdf4); color: var(--state-success, #16a34a); }
.act-working { background: var(--brand-light, #eef2ff); color: var(--brand, #4f46e5); }
.act-offline { background: var(--surface-2, #f1f5f9); color: var(--ink-2, #475569); }
</style>
