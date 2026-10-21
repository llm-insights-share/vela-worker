<template>
  <main class="wb-center">
    <a-spin :spinning="store.loading">
      <ItemTaskDetail
        v-if="store.selectedItem"
        :item="itemDetail || store.selectedItem"
        @refresh="$emit('refresh')"
        @delegate="showDelegate = true"
        @back="onBackToProject"
      />
      <WorkerParticipationView
        v-else-if="store.selectedWorker"
        :worker="store.selectedWorker"
        @select-item="onSelectItem"
        @create-item="$emit('create-item')"
        @refresh="$emit('refresh')"
      />
      <ProjectOverview
        v-else-if="store.selectedProject"
        :project="store.selectedProject"
        @select-item="(item) => store.selectItem(item.item_id, store.selectedProject.project_id, item.worker_id || null)"
        @delegate="showDelegate = true"
        @open-approval="(a) => $emit('open-approval', a)"
        @refresh="$emit('refresh')"
      />
      <WorkbenchHome
        v-else
        @create-project="$emit('create-project')"
        @create-item="$emit('create-item')"
        @select-worker="(id) => store.selectWorker(id)"
        @open-approval="(a) => $emit('open-approval', a)"
      />
    </a-spin>

    <DelegateModal
      v-model:open="showDelegate"
      :item="store.selectedItem"
      :project="store.selectedProject"
      @done="$emit('refresh')"
    />
  </main>
</template>

<script setup>
import { ref, watch } from 'vue'
import { projectApi } from '../../../api'
import { useWorkbenchStore } from '../store/workbench'
import ProjectOverview from './ProjectOverview.vue'
import ItemTaskDetail from './ItemTaskDetail.vue'
import WorkerParticipationView from './WorkerParticipationView.vue'
import WorkbenchHome from './WorkbenchHome.vue'
import DelegateModal from './DelegateModal.vue'

defineEmits(['refresh', 'open-approval', 'create-project', 'create-item'])
const store = useWorkbenchStore()
const showDelegate = ref(false)
const itemDetail = ref(null)

watch(() => store.selectedItemId, async (id) => {
  if (!id) {
    itemDetail.value = null
    return
  }
  try {
    itemDetail.value = await projectApi.getItem(id)
  } catch {
    itemDetail.value = store.selectedItem
  }
}, { immediate: true })

function onSelectItem(item, projectId) {
  store.selectItem(item.item_id, projectId, item.worker_id || null)
}

function onSelectProject(projectId) {
  store.selectProject(projectId)
}

function onBackToProject() {
  const pid = store.selectedProjectId
  store.selectProject(pid)
}
</script>

<style scoped>
.wb-center {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  min-width: 0;
  background: var(--bg, #f8fafc);
}
</style>
