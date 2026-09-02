<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">职责管理</h2>
        <div class="page-desc">每个职责绑定一个 vela-agent 模板；入职时克隆为入口 COMPOSITE 的子 Agent，关键词用于调度</div>
      </div>
      <a-button type="primary" @click="openCreate">新建职责</a-button>
    </div>

    <div class="page-card">
      <a-table :dataSource="duties" :columns="columns" rowKey="duty_id" :loading="loading" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'task_types'">
            <a-tag v-for="t in (record.task_types || [])" :key="t" color="blue">{{ t }}</a-tag>
          </template>
          <template v-else-if="column.key === 'agent'">
            <span v-if="record.template_agent_name">{{ record.template_agent_name }}</span>
            <span v-else style="color:#9e9590">未选择</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a @click="openEdit(record)">编辑</a>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? '编辑职责' : '新建职责'"
      width="560px"
      @ok="submit"
      :confirmLoading="saving"
    >
      <a-form layout="vertical">
        <a-form-item label="职责名称" required>
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="任务类型（逗号分隔，路由键）">
          <a-input v-model:value="taskTypesText" placeholder="audit.material_collect, audit.risk_scan" />
        </a-form-item>
        <a-form-item label="调度关键词（逗号分隔，写入入口 COMPOSITE 子 Agent 调度）">
          <a-input v-model:value="keywordsText" placeholder="资料, 收集, 材料" />
        </a-form-item>
        <a-form-item label="对应 Agent（vela-agent）" required>
          <a-select
            v-model:value="form.template_agent_id"
            :options="agentOptions"
            show-search
            option-filter-prop="label"
            placeholder="从 vela-agent 列表中选择"
            :loading="agentsLoading"
          />
          <div class="field-hint">模型、技能、工具、知识库等配置以所选 Agent 为准，入职时将克隆为员工专属实例</div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { dutyApi, catalogApi } from '../../api'

const loading = ref(false)
const saving = ref(false)
const agentsLoading = ref(false)
const duties = ref([])
const modalOpen = ref(false)
const editing = ref(null)
const agentOptions = ref([])
const taskTypesText = ref('')
const keywordsText = ref('')

const emptyForm = () => ({
  name: '',
  description: '',
  task_types: [],
  keywords: [],
  template_agent_id: undefined,
})
const form = ref(emptyForm())

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '任务类型', key: 'task_types' },
  { title: '对应 Agent', key: 'agent', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', key: 'action', width: 80 },
]

async function load() {
  loading.value = true
  try {
    const res = await dutyApi.list({ page_size: 100 })
    duties.value = res.items || []
  } finally {
    loading.value = false
  }
}

async function loadAgents() {
  agentsLoading.value = true
  try {
    const agents = await catalogApi.agents()
    agentOptions.value = (agents || []).map((a) => ({
      value: a.agent_id,
      label: `${a.name}${a.status ? ' · ' + a.status : ''}${a.model_name ? ' · ' + a.model_name : ''}`,
    }))
  } catch (e) {
    message.warning('无法加载 vela-agent 列表：' + e.message)
  } finally {
    agentsLoading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  taskTypesText.value = ''
  keywordsText.value = ''
  modalOpen.value = true
}

function openEdit(record) {
  editing.value = record
  form.value = {
    name: record.name,
    description: record.description || '',
    template_agent_id: record.template_agent_id || undefined,
  }
  taskTypesText.value = (record.task_types || []).join(', ')
  keywordsText.value = (record.keywords || []).join(', ')
  // ensure current template still appears in options even if filtered out
  if (record.template_agent_id && !agentOptions.value.some((o) => o.value === record.template_agent_id)) {
    agentOptions.value = [
      {
        value: record.template_agent_id,
        label: record.template_agent_name || record.template_agent_id,
      },
      ...agentOptions.value,
    ]
  }
  modalOpen.value = true
}

async function submit() {
  if (!form.value.name) return message.error('请填写职责名称')
  if (!form.value.template_agent_id) return message.error('请选择对应的 vela-agent')
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      task_types: taskTypesText.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      keywords: keywordsText.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      template_agent_id: form.value.template_agent_id,
    }
    if (editing.value) {
      await dutyApi.update(editing.value.duty_id, payload)
      message.success('已更新')
    } else {
      await dutyApi.create(payload)
      message.success('已创建')
    }
    modalOpen.value = false
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  loadAgents()
})
</script>

<style scoped>
.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #9e9590;
  line-height: 1.5;
}
</style>
