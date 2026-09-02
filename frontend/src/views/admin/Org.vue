<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">组织机构</h2>
    </div>
    <a-row :gutter="16">
      <a-col :span="12">
        <div class="page-card">
          <h3 class="section-title">部门</h3>
          <a-table :dataSource="depts" :columns="deptCols" rowKey="dept_id" :pagination="false" size="small" />
        </div>
      </a-col>
      <a-col :span="12">
        <div class="page-card">
          <h3 class="section-title">人类员工</h3>
          <a-table :dataSource="users" :columns="userCols" rowKey="user_id" :pagination="false" size="small" />
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { orgApi } from '../../api'

const depts = ref([])
const users = ref([])
const deptCols = [
  { title: '名称', dataIndex: 'name' },
  { title: 'ID', dataIndex: 'dept_id', ellipsis: true },
  { title: '上级', dataIndex: 'parent_id', ellipsis: true },
]
const userCols = [
  { title: '姓名', dataIndex: 'name' },
  { title: '职务', dataIndex: 'title' },
  { title: '角色', dataIndex: 'role' },
  { title: '部门', dataIndex: 'dept_id', ellipsis: true },
]

onMounted(async () => {
  depts.value = await orgApi.departments()
  users.value = await orgApi.users()
})
</script>

<style scoped>
.section-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: #1a1714;
}
</style>
