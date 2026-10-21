<template>
  <div class="demo-workbench" :class="chatLayoutClass">
    <WorkbenchLeft @refresh="onLeftRefresh" />
    <WorkbenchCenter
      v-show="store.chatPanel !== 'fullscreen'"
      @refresh="loadWorkbench"
      @open-approval="store.openApproval"
      @create-project="createProjectOpen = true"
      @create-item="onCreateItem"
    />
    <WorkbenchChat @open-approval="store.openApproval" />

    <ApprovalAuditModal
      v-if="store.activeApproval"
      :approval="store.activeApproval"
      @close="store.closeApproval"
      @done="onApprovalDone"
    />

    <CreateProjectModal
      v-model:open="createProjectOpen"
      @done="onProjectCreated"
    />
    <CreateItemModal
      v-model:open="createItemOpen"
      :project-id="createItemProjectId"
      @done="onItemCreated"
    />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { projectApi } from '../../api'
import { useWorkbenchStore } from './store/workbench'
import { useWorkbenchWs } from './composables/useWorkbenchWs'
import WorkbenchLeft from './components/WorkbenchLeft.vue'
import WorkbenchCenter from './components/WorkbenchCenter.vue'
import WorkbenchChat from './components/WorkbenchChat.vue'
import ApprovalAuditModal from './components/ApprovalAuditModal.vue'
import CreateProjectModal from './components/CreateProjectModal.vue'
import CreateItemModal from './components/CreateItemModal.vue'

const store = useWorkbenchStore()
const createProjectOpen = ref(false)
const createItemOpen = ref(false)
const createItemProjectId = ref('')

const chatLayoutClass = computed(() => `chat-${store.chatPanel}`)

async function loadWorkbench(selectProjectId, selectItemId, selectWorkerId) {
  store.loading = true
  try {
    const data = await projectApi.workbench()
    store.setWorkbench(data)

    if (selectProjectId) {
      if (selectItemId) {
        store.selectItem(selectItemId, selectProjectId, selectWorkerId || null)
      } else {
        store.selectProject(selectProjectId)
      }
    }
    // Default: stay on home (no auto-select)
  } finally {
    store.loading = false
  }
}

async function onApprovalDone() {
  store.closeApproval()
  await loadWorkbench()
}

function onLeftRefresh(projectId, itemId, workerId) {
  loadWorkbench(projectId, itemId, workerId)
}

function onCreateItem(projectId) {
  createItemProjectId.value = projectId || store.selectedProjectId || store.projects[0]?.project_id || ''
  if (!createItemProjectId.value) {
    createProjectOpen.value = true
    return
  }
  createItemOpen.value = true
}

function onProjectCreated({ project_id }) {
  loadWorkbench(project_id, null, null)
}

function onItemCreated({ project_id, item_id, worker_id }) {
  loadWorkbench(project_id, item_id, worker_id)
}

function onOpsRefresh() {
  loadWorkbench()
}

useWorkbenchWs({
  onTaskUpdate: () => loadWorkbench(),
})

onMounted(() => {
  loadWorkbench()
  window.addEventListener('vela-workbench-refresh', onOpsRefresh)
})
onUnmounted(() => {
  window.removeEventListener('vela-workbench-refresh', onOpsRefresh)
})

defineExpose({ loadWorkbench })
</script>

<style scoped>
.demo-workbench {
  --brand: #4f46e5;
  --brand-hover: #4338ca;
  --brand-light: #eef2ff;
  --bg: #f8fafc;
  --surface: #ffffff;
  --surface-2: #f1f5f9;
  --surface-3: #e2e8f0;
  --ink: #0f172a;
  --ink-2: #475569;
  --ink-3: #94a3b8;
  --line: #e2e8f0;
  --state-success: #16a34a;
  --state-success-light: #f0fdf4;
  --state-warning: #d97706;
  --state-warning-light: #fffbeb;
  --state-error: #dc2626;
  --state-error-light: #fef2f2;
  --wb-primary: var(--brand);
  --wb-bg: var(--bg);
  --wb-side-width: 300px;
  display: flex;
  height: 100%;
  background: var(--bg);
  overflow: hidden;
  color: var(--ink);
}
</style>
