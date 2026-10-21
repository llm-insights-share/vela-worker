<template>
  <aside class="wb-left">
    <div class="wb-search-wrap">
      <button
        type="button"
        class="home-btn"
        :class="{ active: isHome }"
        title="办公工作台首页"
        @click="goHome"
      >
        <HomeOutlined />
      </button>
      <a-input
        v-model:value="store.searchQuery"
        allow-clear
        placeholder="搜索项目、事项或数字员工…"
        class="wb-search"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input>
    </div>

    <section class="wb-section wb-section-pane">
      <div class="wb-section-title-row projects-hd">
        <span class="wb-section-title projects-title">我的项目</span>
        <button type="button" class="project-add-square" title="创建项目" @click="showCreateProject = true">
          <PlusOutlined />
        </button>
      </div>
      <div class="project-list">
        <div v-for="p in filteredProjects" :key="p.project_id" class="project-block">
          <div
            class="project-row"
            :class="{ active: store.selectedProjectId === p.project_id && !store.selectedItemId && !store.selectedWorkerId }"
            @click="onSelectProject(p.project_id)"
          >
            <span class="project-left">
              <FolderOutlined class="project-folder" />
              <span class="project-name">{{ p.name }}</span>
            </span>
            <span class="project-count">{{ p.item_count }}</span>
            <button
              v-if="store.selectedProjectId === p.project_id"
              type="button"
              class="project-item-add"
              title="新建事项"
              @click.stop="openCreateItem(p.project_id)"
            >
              <PlusOutlined />
            </button>
          </div>
          <div v-if="expandedProjects.has(p.project_id)" class="item-tree">
            <ProjectTree
              :items="p.items"
              :project-id="p.project_id"
              @select="(item) => onSelectItem(item, p.project_id)"
            />
          </div>
        </div>
        <div v-if="!filteredProjects.length" class="list-empty">暂无匹配的项目</div>
      </div>
    </section>

    <section class="wb-section wb-section-pane wb-section-workers">
      <div class="wb-section-title-row">
        <div class="wb-section-title-with-badge">
          <span class="wb-section-title">数字员工</span>
          <span class="ai-badge">AI</span>
        </div>
      </div>
      <div class="worker-list">
        <WorkerCard
          v-for="w in filteredWorkers"
          :key="w.worker_id"
          :worker="w"
          :selected="store.selectedWorkerId === w.worker_id && !store.selectedItemId"
          @select="onSelectWorker"
        />
        <div v-if="!filteredWorkers.length" class="list-empty">暂无匹配的数字员工</div>
      </div>
    </section>

    <CreateProjectModal
      v-model:open="showCreateProject"
      @done="onProjectCreated"
    />
    <CreateItemModal
      v-model:open="showCreateItem"
      :project-id="createItemProjectId"
      @done="onItemCreated"
    />
  </aside>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { SearchOutlined, PlusOutlined, FolderOutlined, HomeOutlined } from '@ant-design/icons-vue'
import { useWorkbenchStore } from '../store/workbench'
import WorkerCard from './WorkerCard.vue'
import ProjectTree from './ProjectTree.vue'
import CreateProjectModal from './CreateProjectModal.vue'
import CreateItemModal from './CreateItemModal.vue'

const emit = defineEmits(['refresh'])
const store = useWorkbenchStore()
const expandedProjects = ref(new Set())
const showCreateProject = ref(false)
const showCreateItem = ref(false)
const createItemProjectId = ref('')

const isHome = computed(() =>
  !store.selectedProjectId && !store.selectedWorkerId && !store.selectedItemId
)

const filteredProjects = computed(() => {
  const q = store.searchQuery.trim().toLowerCase()
  if (!q) return store.projects
  return store.projects.filter((p) =>
    p.name.toLowerCase().includes(q) ||
    JSON.stringify(p.items).toLowerCase().includes(q)
  )
})

const filteredWorkers = computed(() => {
  const q = store.searchQuery.trim().toLowerCase()
  if (!q) return store.workers
  return store.workers.filter((w) => w.name.toLowerCase().includes(q))
})

watch(() => store.selectedProjectId, (id) => {
  if (id) expandedProjects.value.add(id)
}, { immediate: true })

function goHome() {
  store.clearSelection()
  store.searchQuery = ''
}

function onSelectProject(projectId) {
  store.selectProject(projectId)
  expandedProjects.value.add(projectId)
}

function onSelectWorker(w) {
  store.selectWorker(w.worker_id)
}

function onSelectItem(item, projectId) {
  store.selectItem(item.item_id, projectId, item.worker_id || null)
}

function openCreateItem(projectId) {
  createItemProjectId.value = projectId
  showCreateItem.value = true
}

function onProjectCreated({ project_id }) {
  emit('refresh', project_id, null, null)
}

function onItemCreated({ project_id, item_id, worker_id }) {
  emit('refresh', project_id, item_id, worker_id)
}
</script>

<style scoped>
.wb-left {
  width: var(--wb-side-width, 300px);
  flex-shrink: 0;
  height: 100%;
  min-height: 0;
  background: var(--surface, #fff);
  border-right: 1px solid var(--line, #e2e8f0);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.wb-search-wrap {
  padding: 12px 16px;
  border-bottom: 1px solid var(--line, #e2e8f0);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.home-btn {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  color: var(--ink-2, #475569);
  font-size: 15px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.home-btn:hover,
.home-btn.active {
  color: var(--brand, #4f46e5);
  border-color: var(--brand, #4f46e5);
  background: var(--brand-light, #eef2ff);
}

.wb-search {
  width: 100%;
  flex: 1;
  min-width: 0;
}

.wb-section {
  padding: 12px 16px;
  border-bottom: 1px solid var(--line, #e2e8f0);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.wb-section-pane {
  flex: 1 1 0;
  overflow: hidden;
}

.wb-section-workers {
  border-bottom: none;
}

.project-list,
.worker-list {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  width: 100%;
}

.worker-list {
  gap: 2px;
}

.wb-section-title-with-badge {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
  letter-spacing: 0.02em;
}

.list-empty {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  text-align: center;
  padding: 12px 0;
}

.wb-section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.wb-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink, #0f172a);
  letter-spacing: 0;
  text-transform: none;
}

.projects-hd {
  margin-bottom: 8px;
}

.projects-title {
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
}

.project-add-square {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.project-add-square:hover {
  border-color: var(--brand, #4f46e5);
  color: var(--brand, #4f46e5);
}

.project-block {
  margin-bottom: 2px;
}

.project-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  color: #334155;
  box-sizing: border-box;
}

.project-row:hover {
  background: #f8fafc;
}

.project-row.active {
  background: #ebe7ff;
  color: #5b4cdb;
}

.project-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.project-folder {
  font-size: 15px;
  color: #64748b;
  flex-shrink: 0;
}

.project-row.active .project-folder {
  color: #6366f1;
}

.project-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: inherit;
}

.project-count {
  font-size: 13px;
  color: #94a3b8;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.project-row.active .project-count {
  color: #818cf8;
}

.project-item-add {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--brand, #4f46e5);
  font-size: 11px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.item-tree {
  padding-left: 8px;
}
</style>
