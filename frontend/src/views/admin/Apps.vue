<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">开放应用</h2>
        <div class="page-desc">企业应用通过 API Key 派发任务并接收 Webhook 回调</div>
      </div>
      <a-button type="primary" @click="open = true">注册应用</a-button>
    </div>
    <div class="page-card">
      <a-table :dataSource="apps" :columns="columns" rowKey="app_id" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'api_key'">
            <code>{{ record.api_key }}</code>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal v-model:open="open" title="注册开放应用" @ok="create" :confirmLoading="saving">
      <a-form layout="vertical">
        <a-form-item label="应用名称" required><a-input v-model:value="form.name" /></a-form-item>
        <a-form-item label="允许的 task_types（逗号分隔）">
          <a-input v-model:value="typesText" />
        </a-form-item>
        <a-form-item label="默认回调 URL">
          <a-input v-model:value="form.default_callback_url" placeholder="https://..." />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="secretOpen" title="请妥善保存凭证" :footer="null">
      <a-alert type="warning" message="App Secret 仅展示一次" show-icon style="margin-bottom:12px" />
      <p><b>API Key：</b><code>{{ created.api_key }}</code></p>
      <p><b>App Secret：</b><code>{{ created.app_secret }}</code></p>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { appApi } from '../../api'

const apps = ref([])
const open = ref(false)
const secretOpen = ref(false)
const saving = ref(false)
const form = ref({ name: '', default_callback_url: '' })
const typesText = ref('')
const created = ref({})
const columns = [
  { title: '名称', dataIndex: 'name' },
  { title: 'API Key', key: 'api_key' },
  { title: '状态', dataIndex: 'status', width: 90 },
  { title: '回调', dataIndex: 'default_callback_url', ellipsis: true },
]

async function load() {
  try {
    apps.value = await appApi.list()
  } catch (e) {
    message.error(e.message)
  }
}

async function create() {
  if (!form.value.name) return message.error('请填写名称')
  saving.value = true
  try {
    created.value = await appApi.create({
      name: form.value.name,
      default_callback_url: form.value.default_callback_url,
      allowed_task_types: typesText.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
    })
    open.value = false
    secretOpen.value = true
    form.value = { name: '', default_callback_url: '' }
    typesText.value = ''
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
