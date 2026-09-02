<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">任务中心</h2>
    </div>
    <div class="page-card">
      <a-table :dataSource="tasks" :columns="columns" rowKey="task_id" :loading="loading" @row-click="showDetail">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag>{{ record.status }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a @click.stop="showDetail(record)">详情</a>
              <a v-if="['RECEIVED','QUEUED','RUNNING','NEED_HUMAN'].includes(record.status)" @click.stop="cancel(record)">取消</a>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>
    <a-drawer v-model:open="open" title="任务详情" width="560">
      <template v-if="detail">
        <p><b>标题：</b>{{ detail.title }}</p>
        <p><b>状态：</b>{{ detail.status }}</p>
        <p><b>进度：</b>{{ detail.progress_note }}</p>
        <p><b>结果：</b></p>
        <pre style="white-space:pre-wrap;font-size:12px">{{ JSON.stringify(detail.result, null, 2) }}</pre>
        <h4>时间线</h4>
        <a-timeline>
          <a-timeline-item v-for="(e, i) in detail.timeline || []" :key="i">
            {{ e.event }} · {{ e.at }}
          </a-timeline-item>
        </a-timeline>
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { taskApi } from '../../api'

const route = useRoute()

const loading = ref(false)
const tasks = ref([])
const open = ref(false)
const detail = ref(null)
const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  { title: '状态', key: 'status', width: 120 },
  { title: 'Token', dataIndex: 'tokens_used', key: 'tokens_used', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 120 },
]

async function load() {
  loading.value = true
  try {
    const res = await taskApi.list({ page_size: 50 })
    tasks.value = res.items || []
  } finally {
    loading.value = false
  }
}

async function showDetail(record) {
  detail.value = await taskApi.get(record.task_id)
  open.value = true
}

async function cancel(record) {
  try {
    await taskApi.cancel(record.task_id)
    message.success('已取消')
    await load()
  } catch (e) {
    message.error(e.message)
  }
}

onMounted(async () => {
  await load()
  const taskId = route.query.task_id
  if (taskId) {
    const record = tasks.value.find((t) => t.task_id === taskId)
    if (record) {
      await showDetail(record)
    } else {
      try {
        detail.value = await taskApi.get(taskId)
        open.value = true
      } catch (e) {
        message.error(e.message || '任务不存在')
      }
    }
  }
})
</script>
