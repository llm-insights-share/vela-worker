<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">数字员工角色</h2>
        <div class="page-desc">岗位模板：关联 1-N 个职责，入职时按职责分别创建独立 Agent</div>
      </div>
      <a-button type="primary" @click="openCreate">新建角色</a-button>
    </div>

    <div class="page-card">
      <a-table :dataSource="roles" :columns="columns" rowKey="role_id" :loading="loading" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'duties'">
            <a-tag v-for="n in (record.duty_names || [])" :key="n">{{ n }}</a-tag>
            <span v-if="!(record.duty_names || []).length" style="color:#9e9590">-</span>
          </template>
          <template v-else-if="column.key === 'task_types'">
            <a-tag v-for="t in (record.task_types || [])" :key="t" color="blue">{{ t }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a @click="openEdit(record)">编辑</a>
              <a style="color:#b5341c" @click="confirmDelete(record)">删除</a>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal v-model:open="modalOpen" :title="editing ? '编辑角色' : '新建角色'" width="640px" @ok="submit" :confirmLoading="saving">
      <a-form layout="vertical">
        <a-form-item label="角色名称" required>
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="角色描述">
          <a-textarea v-model:value="form.description" :rows="2" />
        </a-form-item>
        <a-form-item label="关联职责" required>
          <a-select
            v-model:value="form.duty_ids"
            mode="multiple"
            :options="dutyOptions"
            placeholder="选择一个或多个职责"
          />
        </a-form-item>
        <a-form-item label="职责范围说明（每行一项）">
          <a-textarea v-model:value="dutyText" :rows="3" />
        </a-form-item>
        <a-form-item label="超出范围（每行一项）">
          <a-textarea v-model:value="outText" :rows="2" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item label="默认自治级别">
              <a-select
                v-model:value="form.governance.autonomy_level"
                :options="[{ value: 'L1', label: 'L1' }, { value: 'L2', label: 'L2' }, { value: 'L3', label: 'L3' }]"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="任务 Token 预算">
              <a-input-number v-model:value="form.governance.token_budget_per_task" :min="1000" style="width:100%" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="最大并发任务">
              <a-input-number v-model:value="form.governance.max_concurrent_tasks" :min="1" style="width:100%" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { roleApi, dutyApi } from '../../api'

const loading = ref(false)
const saving = ref(false)
const roles = ref([])
const dutyOptions = ref([])
const modalOpen = ref(false)
const editing = ref(null)
const dutyText = ref('')
const outText = ref('')

const emptyForm = () => ({
  name: '',
  description: '',
  duty_scope: [],
  out_of_scope: [],
  duty_ids: [],
  governance: { autonomy_level: 'L2', token_budget_per_task: 100000, max_concurrent_tasks: 5 },
})
const form = ref(emptyForm())

const columns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '关联职责', key: 'duties' },
  { title: '任务类型', key: 'task_types' },
  { title: '版本', dataIndex: 'version', key: 'version', width: 70 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', key: 'action', width: 120 },
]

async function load() {
  loading.value = true
  try {
    const res = await roleApi.list({ page_size: 100 })
    roles.value = res.items || []
  } finally {
    loading.value = false
  }
}

async function loadDuties() {
  const res = await dutyApi.list({ page_size: 100, status: 'ACTIVE' })
  dutyOptions.value = (res.items || []).map((d) => ({
    value: d.duty_id,
    label: `${d.name}${d.task_types?.length ? ' · ' + d.task_types.join(',') : ''}`,
  }))
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  dutyText.value = ''
  outText.value = ''
  modalOpen.value = true
}

function openEdit(record) {
  editing.value = record
  form.value = {
    ...emptyForm(),
    ...record,
    duty_ids: [...(record.duty_ids || [])],
    governance: { ...emptyForm().governance, ...(record.governance || {}) },
  }
  dutyText.value = (record.duty_scope || []).join('\n')
  outText.value = (record.out_of_scope || []).join('\n')
  modalOpen.value = true
}

function confirmDelete(record) {
  Modal.confirm({
    title: '删除角色',
    content: `确认删除「${record.name}」？若仍有数字员工使用该角色将无法删除。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await roleApi.remove(record.role_id)
        message.success('已删除')
        await load()
      } catch (e) {
        message.error(e.message)
        throw e
      }
    },
  })
}

async function submit() {
  if (!form.value.name) return message.error('请填写角色名称')
  if (!(form.value.duty_ids || []).length) return message.error('请至少关联一个职责')
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      duty_ids: form.value.duty_ids,
      duty_scope: dutyText.value.split('\n').map((s) => s.trim()).filter(Boolean),
      out_of_scope: outText.value.split('\n').map((s) => s.trim()).filter(Boolean),
      governance: form.value.governance,
    }
    if (editing.value) {
      await roleApi.update(editing.value.role_id, payload)
      message.success('已更新')
    } else {
      await roleApi.create(payload)
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
  loadDuties()
})
</script>
