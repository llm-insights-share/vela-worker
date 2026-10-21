<template>
  <div
    class="worker-card"
    :class="{ active: selected, [`act-${worker.activity}`]: true, 'is-offline': worker.activity === 'offline' }"
    @click="$emit('select', worker)"
  >
    <span v-if="selected" class="selected-mark" aria-hidden="true">
      <CheckOutlined />
    </span>
    <div class="worker-icon" :class="{ 'icon-selected': selected }">
      <RobotOutlined />
    </div>
    <div class="worker-body">
      <span class="worker-name">{{ worker.name }}</span>
      <span class="worker-status-line">
        <span class="status-dot" :class="`dot-${worker.activity}`" />
        <span class="status-label">{{ statusLabel }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RobotOutlined, CheckOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  worker: { type: Object, required: true },
  selected: { type: Boolean, default: false },
})

defineEmits(['select'])

const statusLabel = computed(() => {
  const map = { online: '空闲', working: '工作中', offline: '离线' }
  return map[props.worker.activity] || props.worker.activity
})
</script>

<style scoped>
.worker-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
  min-height: 36px;
  padding: 6px 10px;
  margin: 0;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, opacity 0.15s;
}

.worker-card.is-offline {
  opacity: 0.72;
}

.selected-mark {
  position: absolute;
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #22c55e;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  line-height: 1;
  box-shadow: 0 1px 3px rgba(34, 197, 94, 0.35);
}

.worker-card:hover {
  background: #f8fafc;
}

.worker-card.active {
  background: #ebe7ff;
  border-color: transparent;
}

.worker-icon {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
  background: #f1f5f9;
  color: #64748b;
  border: none;
  transition: background 0.15s, color 0.15s;
}

.worker-icon.icon-selected {
  background: var(--brand, #4f46e5);
  color: #fff;
}

.worker-body {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 22px;
}

.worker-name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.worker-card.active .worker-name {
  color: #5b4cdb;
}

.worker-status-line {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-online { background: #22c55e; }
.dot-working { background: var(--brand, #4f46e5); }
.dot-offline { background: #9ca3af; }

.status-label {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}
</style>
