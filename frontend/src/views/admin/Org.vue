<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">组织机构</h2>
        <div class="page-desc">管理部门列表</div>
      </div>
      <a-button type="primary" @click="openCreate">+ 新增部门</a-button>
    </div>

    <div class="page-card">
      <a-table
        :dataSource="depts"
        :columns="deptCols"
        rowKey="dept_id"
        :loading="loading"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'parent'">
            {{ parentName(record.parent_id) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a @click="openEdit(record)">修改</a>
              <a style="color:#b5341c" @click="confirmDelete(record)">删除</a>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="editing ? '修改部门' : '新增部门'"
      :confirmLoading="saving"
      :okText="editing ? '保存' : '创建'"
      @ok="submit"
    >
      <a-form layout="vertical">
        <a-form-item label="部门名称" required>
          <a-input v-model:value="form.name" placeholder="请输入部门名称" />
        </a-form-item>
        <a-form-item label="上级部门">
          <a-select
            v-model:value="form.parent_id"
            allowClear
            placeholder="无（顶级部门）"
            :options="parentOptions"
          />
        </a-form-item>
        <a-form-item label="排序">
          <a-input-number v-model:value="form.sort" :min="0" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { orgApi } from '../../api'

const loading = ref(false)
const saving = ref(false)
const depts = ref([])
const modalOpen = ref(false)
const editing = ref(null)
const form = ref({ name: '', parent_id: undefined, sort: 0 })

const deptCols = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '上级部门', key: 'parent' },
  { title: '排序', dataIndex: 'sort', key: 'sort', width: 80 },
  { title: 'ID', dataIndex: 'dept_id', key: 'dept_id', ellipsis: true },
  { title: '操作', key: 'action', width: 120 },
]

const parentOptions = computed(() =>
  (depts.value || [])
    .filter((d) => !editing.value || d.dept_id !== editing.value.dept_id)
    .map((d) => ({ value: d.dept_id, label: d.name }))
)

function parentName(parentId) {
  if (!parentId) return '—'
  const p = depts.value.find((d) => d.dept_id === parentId)
  return p?.name || parentId
}

async function load() {
  loading.value = true
  try {
    depts.value = await orgApi.departments()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', parent_id: undefined, sort: (depts.value?.length || 0) }
  modalOpen.value = true
}

function openEdit(record) {
  editing.value = record
  form.value = {
    name: record.name || '',
    parent_id: record.parent_id || undefined,
    sort: record.sort ?? 0,
  }
  modalOpen.value = true
}

function confirmDelete(record) {
  Modal.confirm({
    title: '删除部门',
    content: `确认删除「${record.name}」？若存在子部门或仍有人员归属将无法删除。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await orgApi.removeDept(record.dept_id)
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
  if (!(form.value.name || '').trim()) {
    return message.error('请填写部门名称')
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      parent_id: form.value.parent_id || null,
      sort: form.value.sort ?? 0,
    }
    if (editing.value) {
      await orgApi.updateDept(editing.value.dept_id, payload)
      message.success('已更新')
    } else {
      await orgApi.createDept(payload)
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

onMounted(load)
</script>
