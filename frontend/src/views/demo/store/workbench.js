import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useWorkbenchStore = defineStore('workbench', () => {
  const projects = ref([])
  const workers = ref([])
  const pendingApprovals = ref([])
  const recentActivities = ref([])
  const workloadDone = ref(0)
  const workloadTotal = ref(0)
  const loading = ref(false)

  const selectedProjectId = ref(null)
  const selectedItemId = ref(null)
  const selectedWorkerId = ref(null)
  const activeConvId = ref(null)
  const activeApproval = ref(null)
  const searchQuery = ref('')
  /** side | collapsed | fullscreen */
  const chatPanel = ref('side')

  const selectedProject = computed(() =>
    projects.value.find((p) => p.project_id === selectedProjectId.value) || null
  )

  function findItemInTree(items, itemId) {
    for (const item of items || []) {
      if (item.item_id === itemId) return item
      const found = findItemInTree(item.children, itemId)
      if (found) return found
    }
    return null
  }

  const selectedItem = computed(() => {
    if (!selectedItemId.value) return null
    for (const p of projects.value) {
      const item = findItemInTree(p.items, selectedItemId.value)
      if (item) return { ...item, project_name: p.name, project_id: p.project_id }
    }
    return null
  })

  const selectedWorker = computed(() =>
    workers.value.find((w) => w.worker_id === selectedWorkerId.value) || null
  )

  function setWorkbench(data) {
    projects.value = data.projects || []
    workers.value = data.workers || []
    pendingApprovals.value = data.pending_approvals || []
    recentActivities.value = data.recent_activities || []
    workloadDone.value = data.workload_done || 0
    workloadTotal.value = data.workload_total || 0
  }

  function clearSelection() {
    selectedProjectId.value = null
    selectedItemId.value = null
    selectedWorkerId.value = null
  }

  function selectProject(projectId) {
    selectedProjectId.value = projectId
    selectedItemId.value = null
    selectedWorkerId.value = null
  }

  function selectItem(itemId, projectId, workerId) {
    if (projectId) selectedProjectId.value = projectId
    selectedItemId.value = itemId
    if (workerId) selectedWorkerId.value = workerId
  }

  function selectWorker(workerId) {
    selectedWorkerId.value = workerId
    selectedItemId.value = null
  }

  function clearWorker() {
    selectedWorkerId.value = null
  }

  function openApproval(approval) {
    activeApproval.value = approval
  }

  function closeApproval() {
    activeApproval.value = null
  }

  function setChatPanel(mode) {
    if (['side', 'collapsed', 'fullscreen'].includes(mode)) {
      chatPanel.value = mode
    }
  }

  function toggleChatCollapse() {
    chatPanel.value = chatPanel.value === 'collapsed' ? 'side' : 'collapsed'
  }

  function toggleChatFullscreen() {
    chatPanel.value = chatPanel.value === 'fullscreen' ? 'side' : 'fullscreen'
  }

  return {
    projects,
    workers,
    pendingApprovals,
    recentActivities,
    workloadDone,
    workloadTotal,
    loading,
    selectedProjectId,
    selectedItemId,
    selectedWorkerId,
    activeConvId,
    activeApproval,
    searchQuery,
    chatPanel,
    selectedProject,
    selectedItem,
    selectedWorker,
    setWorkbench,
    clearSelection,
    selectProject,
    selectItem,
    selectWorker,
    clearWorker,
    openApproval,
    closeApproval,
    setChatPanel,
    toggleChatCollapse,
    toggleChatFullscreen,
    findItemInTree,
  }
})
