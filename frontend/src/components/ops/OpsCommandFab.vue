<template>
  <Teleport to="body">
    <button
      v-if="!open"
      type="button"
      class="ops-fab"
      title="办公操作助手"
      aria-label="打开办公操作助手"
      @click="open = true"
    >
      <ThunderboltOutlined class="ops-fab-icon" />
    </button>
    <OpsAgentPanel v-model="open" />
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { ThunderboltOutlined } from '@ant-design/icons-vue'
import OpsAgentPanel from './OpsAgentPanel.vue'

const open = ref(false)
</script>

<style scoped>
.ops-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  border: none;
  background: #4f46e5;
  color: #fff;
  cursor: pointer;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(79, 70, 229, 0.28);
}
.ops-fab:hover {
  background: #4338ca;
}
.ops-fab-icon {
  font-size: 24px;
}
</style>
