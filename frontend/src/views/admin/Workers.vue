<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">数字员工</h2>
        <div class="page-desc">每人一个入口 COMPOSITE Agent；角色职责作为子 Agent，由入口协调调度</div>
      </div>
      <a-button type="primary" @click="openOnboard">+新建</a-button>
    </div>

    <div class="page-card">
      <a-table :dataSource="workers" :columns="columns" rowKey="worker_id" :loading="loading">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'entry'">
            <code v-if="record.entry_agent_id" class="mono-sm">{{ shortId(record.entry_agent_id) }}</code>
            <span v-else style="color:#9e9590">未编排</span>
          </template>
          <template v-else-if="column.key === 'duties'">
            <a-tag v-for="d in (record.duties || [])" :key="d.duty_id" :color="d.is_primary ? 'blue' : undefined">
              {{ d.duty_name }}{{ d.source === 'EXTRA' ? '·增' : '' }}
            </a-tag>
            <span v-if="!(record.duties || []).length" style="color:#9e9590">0</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColor(record.status)">{{ record.status }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a @click="showSpec(record)">规格</a>
              <a @click="openDuties(record)">职责</a>
              <a @click="openPush(record)">推送</a>
              <a @click="openPerm(record)">权限</a>
              <a-dropdown>
                <a>更多</a>
                <template #overlay>
                  <a-menu @click="({key}) => onMore(record, key)">
                    <a-menu-item key="REPAIR">修复编排</a-menu-item>
                    <a-menu-item key="ON_DUTY">设为在岗</a-menu-item>
                    <a-menu-item key="SUSPENDED">停用</a-menu-item>
                    <a-menu-item key="OFFBOARDED">离职</a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal v-model:open="onboardOpen" title="数字员工入职" @ok="doOnboard" :confirmLoading="saving">
      <a-form layout="vertical">
        <a-form-item label="姓名" required><a-input v-model:value="onboard.name" /></a-form-item>
        <a-form-item label="角色" required>
          <a-select v-model:value="onboard.role_id" :options="roleOptions" />
        </a-form-item>
        <a-form-item label="部门">
          <a-select v-model:value="onboard.dept_id" :options="deptOptions" allowClear />
        </a-form-item>
        <a-form-item label="升级联系人">
          <a-select v-model:value="escalationUserId" :options="userOptions" allowClear />
        </a-form-item>
        <a-form-item label="备注"><a-input v-model:value="onboard.remark" /></a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="dutyOpen" title="配置职责" :footer="null" width="560">
      <a-alert
        type="info"
        show-icon
        style="margin-bottom:12px"
        message="追加/移除职责会同步重建入口 COMPOSITE 编排（挂载子 Agent）"
      />
      <div class="duty-toolbar">
        <a-select
          v-model:value="addDutyId"
          :options="availableDutyOptions"
          placeholder="追加角色外职责"
          style="flex:1"
          allowClear
        />
        <a-button type="primary" :loading="saving" :disabled="!addDutyId" @click="doAddDuty">追加</a-button>
      </div>
      <a-table
        :dataSource="currentDuties"
        :columns="dutyColumns"
        rowKey="duty_id"
        size="small"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'source'">
            <a-tag :color="record.source === 'EXTRA' ? 'orange' : 'default'">
              {{ record.source === 'EXTRA' ? '追加' : '角色' }}
            </a-tag>
            <a-tag v-if="record.is_primary" color="blue">主职责</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-popconfirm title="移除该职责并下架对应 Agent？" @confirm="doRemoveDuty(record)">
              <a style="color:#b5341c">移除</a>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-modal>

    <a-drawer v-model:open="specOpen" title="数字员工规格" width="560">
      <a-form layout="vertical" class="spec-form" v-if="spec?.identity">
        <div class="spec-section">组织身份</div>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="姓名"><a-input :value="identity.name" readonly /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="工号"><a-input :value="identity.employee_no" readonly /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="角色"><a-input :value="identity.role_name" readonly /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="部门"><a-input :value="identity.dept_name || '-'" readonly /></a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="状态">
              <a-tag :color="statusColor(identity.status)">{{ identity.status }}</a-tag>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="入职日期">
              <a-input :value="formatDate(identity.onboard_date)" readonly />
            </a-form-item>
          </a-col>
        </a-row>

        <div class="spec-section">职责说明</div>
        <a-form-item label="描述">
          <a-textarea :value="profile.description || '-'" :rows="2" readonly />
        </a-form-item>
        <a-form-item label="职责范围">
          <div v-if="(profile.duty_scope || []).length" class="tag-list">
            <a-tag v-for="(d, i) in profile.duty_scope" :key="'d'+i">{{ d }}</a-tag>
          </div>
          <span v-else class="empty-text">-</span>
        </a-form-item>

        <div class="spec-section">入口 Agent（COMPOSITE）</div>
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item label="入口 Agent ID">
              <a-input :value="entryAgent.agent_id || '-'" readonly />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="类型">
              <a-input :value="entryAgent.agent_type || 'COMPOSITE'" readonly />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="个人记忆">
              <a-tag :color="entryAgent.memory_enabled ? 'green' : 'default'">
                {{ entryAgent.memory_enabled ? '已开启' : '未开启' }}
              </a-tag>
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="说明">
              <a-textarea :value="entryAgent.description || '-'" :rows="2" readonly />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="基础接待子 Agent">
              <a-input :value="receptionAgent.agent_id || '-'" readonly />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="接待说明">
              <a-textarea :value="receptionAgent.description || '-'" :rows="2" readonly />
            </a-form-item>
          </a-col>
        </a-row>

        <div class="spec-section">子能力（职责 Agent）</div>
        <a-form-item label="全部任务类型">
          <div v-if="(capabilities.task_types || []).length" class="tag-list">
            <a-tag v-for="t in capabilities.task_types" :key="t" color="blue">{{ t }}</a-tag>
          </div>
          <span v-else class="empty-text">-</span>
        </a-form-item>
        <div v-if="!(dutyCaps || []).length" class="empty-text">暂无职责</div>
        <div v-for="cap in dutyCaps" :key="cap.duty_id" class="duty-card">
          <div class="duty-card-hd">
            <span class="duty-card-title">{{ cap.duty_name }}</span>
            <a-tag color="cyan">子 Agent</a-tag>
            <a-tag v-if="cap.is_primary" color="blue">主职责</a-tag>
            <a-tag v-if="cap.source === 'EXTRA'" color="orange">追加</a-tag>
          </div>
          <div class="duty-card-row"><span class="lbl">Agent</span><code>{{ cap.agent_id || '-' }}</code></div>
          <div class="duty-card-row">
            <span class="lbl">调度词</span>
            <span class="tag-list">
              <a-tag v-for="k in (cap.keywords || [])" :key="k">{{ k }}</a-tag>
              <span v-if="!(cap.keywords || []).length">-</span>
            </span>
          </div>
          <div class="duty-card-row">
            <span class="lbl">任务类型</span>
            <span class="tag-list">
              <a-tag v-for="t in (cap.task_types || [])" :key="t">{{ t }}</a-tag>
              <span v-if="!(cap.task_types || []).length">-</span>
            </span>
          </div>
          <div class="duty-card-row">
            <span class="lbl">技能</span>
            <span class="tag-list">
              <a-tag v-for="(s, i) in (cap.skills || [])" :key="'s'+i">{{ s.name || s.skill_pack_id }}</a-tag>
              <span v-if="!(cap.skills || []).length">-</span>
            </span>
          </div>
          <div class="duty-card-row">
            <span class="lbl">工具</span>
            <span class="tag-list">
              <a-tag v-for="(t, i) in (cap.tools || [])" :key="'t'+i">{{ t.name || t.tool_id }}</a-tag>
              <span v-if="!(cap.tools || []).length">-</span>
            </span>
          </div>
          <div class="duty-card-row">
            <span class="lbl">知识库</span>
            <span class="tag-list">
              <a-tag v-for="(k, i) in (cap.knowledge_bases || [])" :key="'k'+i">{{ k.name || k.kb_id }}</a-tag>
              <span v-if="!(cap.knowledge_bases || []).length">-</span>
            </span>
          </div>
        </div>

        <div class="spec-section">治理策略</div>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="自治级别">
              <a-input :value="governance.autonomy_level || '-'" readonly />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="Token 预算 / 任务">
              <a-input :value="String(governance.token_budget_per_task ?? '-')" readonly />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="升级联系人">
              <a-input :value="escalationLabel" readonly />
            </a-form-item>
          </a-col>
        </a-row>

        <div class="spec-section">对接入口</div>
        <a-form-item label="任务派发">
          <a-input :value="endpoints.task_dispatch || '-'" readonly />
        </a-form-item>
        <a-form-item label="IM 提及">
          <a-input :value="endpoints.im_mention || '-'" readonly />
        </a-form-item>
        <div class="spec-meta">
          规格版本 {{ spec.spec_version }} · 修订号 {{ spec.spec_revision ?? 0 }}
        </div>
      </a-form>
      <a-spin v-else />
    </a-drawer>

    <a-modal v-model:open="permOpen" title="权限个性化覆盖" @ok="savePerm" :confirmLoading="saving">
      <a-form layout="vertical">
        <a-form-item label="禁用工具（收紧）">
          <a-select v-model:value="denyTools" mode="multiple" :options="toolOptions" />
        </a-form-item>
        <a-form-item label="额外要求审批的工具">
          <a-select v-model:value="extraApproval" mode="multiple" :options="toolOptions" />
        </a-form-item>
        <a-form-item label="Token 预算覆盖">
          <a-input-number v-model:value="tokenBudget" :min="1000" style="width:100%" />
        </a-form-item>
        <a-form-item label="自治级别覆盖">
          <a-select v-model:value="autonomy" allowClear :options="[{value:'L1',label:'L1'},{value:'L2',label:'L2'},{value:'L3',label:'L3'}]" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="pushOpen" title="主动推送规则" :footer="null" width="640">
      <a-form layout="vertical" class="push-form">
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="名称" required>
              <a-input v-model:value="pushForm.name" placeholder="任务完成通知" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="触发类型">
              <a-select v-model:value="pushForm.trigger_type" :options="[
                { value: 'EVENT', label: '事件' },
                { value: 'CRON', label: '定时' },
              ]" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-if="pushForm.trigger_type === 'EVENT'">
            <a-form-item label="事件">
              <a-select v-model:value="pushForm.event_key" :options="[
                { value: 'TASK_COMPLETED', label: '任务完成' },
                { value: 'NEED_HUMAN', label: '待人工确认' },
                { value: 'MANUAL', label: '手动' },
              ]" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-else>
            <a-form-item label="Cron / every:N">
              <a-input v-model:value="pushForm.cron_expr" placeholder="0 9 * * * 或 every:60" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="渠道">
              <a-select v-model:value="pushForm.channel" :options="[
                { value: 'IM', label: 'IM 会话' },
                { value: 'WEBHOOK', label: 'Webhook' },
              ]" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-if="pushForm.channel === 'IM'">
            <a-form-item label="会话 ID">
              <a-input v-model:value="pushForm.conv_id" />
            </a-form-item>
          </a-col>
          <a-col :span="12" v-else>
            <a-form-item label="Callback URL">
              <a-input v-model:value="pushForm.callback_url" />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item label="提示模板">
              <a-textarea
                v-model:value="pushForm.prompt_template"
                :rows="3"
                placeholder="请根据员工 {{worker_name}} 的近况生成一条简洁工作沟通消息。任务：{{title}}"
              />
            </a-form-item>
          </a-col>
        </a-row>
        <a-button type="primary" :loading="saving" @click="doCreatePush">添加规则</a-button>
      </a-form>
      <a-divider />
      <a-table :dataSource="pushRules" :columns="pushColumns" rowKey="rule_id" size="small" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'trigger'">
            <a-tag>{{ record.trigger_type }}</a-tag>
            <span class="mono-sm">{{ record.trigger_type === 'CRON' ? record.cron_expr : record.event_key }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a @click="doRunPush(record)">立即推送</a>
              <a-popconfirm title="删除该规则？" @confirm="doDeletePush(record)">
                <a style="color:#b5341c">删除</a>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { workerApi, roleApi, orgApi, catalogApi, dutyApi } from '../../api'

const loading = ref(false)
const saving = ref(false)
const workers = ref([])
const roleOptions = ref([])
const deptOptions = ref([])
const userOptions = ref([])
const toolOptions = ref([])
const allDuties = ref([])
const onboardOpen = ref(false)
const specOpen = ref(false)
const permOpen = ref(false)
const dutyOpen = ref(false)
const pushOpen = ref(false)
const pushRules = ref([])
const pushForm = ref({
  name: '',
  trigger_type: 'EVENT',
  event_key: 'TASK_COMPLETED',
  cron_expr: '',
  channel: 'IM',
  conv_id: '',
  callback_url: '',
  prompt_template: '请为数字员工 {{worker_name}} 生成一条简洁的主动沟通消息。相关信息：{{title}} {{summary}}',
})
const spec = ref({})
const currentWorker = ref(null)
const currentDuties = ref([])
const addDutyId = ref(undefined)
const escalationUserId = ref(undefined)
const denyTools = ref([])
const extraApproval = ref([])
const tokenBudget = ref(undefined)
const autonomy = ref(undefined)

const onboard = ref({ name: '', role_id: undefined, dept_id: undefined, remark: '' })

const identity = computed(() => spec.value?.identity || {})
const entryAgent = computed(() => spec.value?.entry_agent || {})
const receptionAgent = computed(() => entryAgent.value?.reception_agent || {})
const profile = computed(() => spec.value?.profile || {})
const capabilities = computed(() => spec.value?.capabilities || {})
const dutyCaps = computed(() => capabilities.value?.duties || [])
const governance = computed(() => spec.value?.governance || {})
const endpoints = computed(() => spec.value?.endpoints || {})

const availableDutyOptions = computed(() => {
  const have = new Set((currentDuties.value || []).map((d) => d.duty_id))
  return (allDuties.value || [])
    .filter((d) => d.status === 'ACTIVE' && !have.has(d.duty_id))
    .map((d) => ({ value: d.duty_id, label: d.name }))
})

const escalationLabel = computed(() => {
  const c = governance.value?.escalation_contact || {}
  if (!c || (!c.user_id && !c.name)) return '-'
  return [c.name, c.user_id, c.type].filter(Boolean).join(' · ') || '-'
})

function formatDate(v) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

function shortId(id) {
  if (!id) return '-'
  return id.length > 12 ? `${id.slice(0, 8)}…` : id
}

const columns = [
  { title: '工号', dataIndex: 'employee_no', key: 'employee_no', width: 100 },
  { title: '姓名', dataIndex: 'name', key: 'name', width: 100 },
  { title: '角色', dataIndex: 'role_name', key: 'role_name', width: 120 },
  { title: '部门', dataIndex: 'dept_name', key: 'dept_name', width: 100 },
  { title: '入口 Agent', key: 'entry', width: 110 },
  { title: '职责', key: 'duties' },
  { title: '状态', key: 'status', width: 100 },
  { title: '操作', key: 'action', width: 260 },
]

const dutyColumns = [
  { title: '职责', dataIndex: 'duty_name', key: 'duty_name' },
  { title: '来源', key: 'source', width: 140 },
  { title: 'Agent', dataIndex: 'agent_id', key: 'agent_id', ellipsis: true },
  { title: '操作', key: 'action', width: 70 },
]

const pushColumns = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '触发', key: 'trigger' },
  { title: '渠道', dataIndex: 'channel', key: 'channel', width: 90 },
  { title: '操作', key: 'action', width: 140 },
]

function statusColor(s) {
  return { ON_DUTY: 'green', SUSPENDED: 'orange', OFFBOARDED: 'default' }[s] || 'blue'
}

async function load() {
  loading.value = true
  try {
    const res = await workerApi.list({ page_size: 100 })
    workers.value = res.items || []
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  const [roles, depts, users, duties] = await Promise.all([
    roleApi.list({ page_size: 100 }),
    orgApi.departments(),
    orgApi.users(),
    dutyApi.list({ page_size: 100 }),
  ])
  roleOptions.value = (roles.items || []).map((r) => ({ value: r.role_id, label: r.name }))
  deptOptions.value = (depts || []).map((d) => ({ value: d.dept_id, label: d.name }))
  userOptions.value = (users || []).map((u) => ({ value: u.user_id, label: u.name }))
  allDuties.value = duties.items || []
  try {
    const tools = await catalogApi.tools()
    toolOptions.value = (tools || []).map((t) => ({ value: t.tool_id, label: t.display_name || t.name }))
  } catch (_) {}
}

function openOnboard() {
  onboard.value = { name: '', role_id: undefined, dept_id: undefined, remark: '' }
  escalationUserId.value = 'u-zhang'
  onboardOpen.value = true
}

async function doOnboard() {
  if (!onboard.value.name || !onboard.value.role_id) return message.error('请填写姓名和角色')
  saving.value = true
  try {
    await workerApi.create({
      ...onboard.value,
      escalation_contact: escalationUserId.value
        ? { type: 'HUMAN', user_id: escalationUserId.value }
        : {},
    })
    message.success('入职成功')
    onboardOpen.value = false
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function showSpec(record) {
  spec.value = {}
  specOpen.value = true
  try {
    spec.value = await workerApi.spec(record.worker_id)
  } catch (e) {
    message.error(e.message)
    specOpen.value = false
  }
}

function openDuties(record) {
  currentWorker.value = record
  currentDuties.value = [...(record.duties || [])]
  addDutyId.value = undefined
  dutyOpen.value = true
}

async function doAddDuty() {
  if (!addDutyId.value || !currentWorker.value) return
  saving.value = true
  try {
    const res = await workerApi.addDuty(currentWorker.value.worker_id, { duty_id: addDutyId.value })
    currentDuties.value = res.duties || []
    currentWorker.value = res
    addDutyId.value = undefined
    message.success('已追加职责')
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function doRemoveDuty(record) {
  saving.value = true
  try {
    const res = await workerApi.removeDuty(currentWorker.value.worker_id, record.duty_id)
    currentDuties.value = res.duties || []
    currentWorker.value = res
    message.success('已移除')
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

function openPerm(record) {
  currentWorker.value = record
  const ov = record.permission_overrides || {}
  denyTools.value = (ov.tool_overrides || []).filter((t) => t.permission === 'denied').map((t) => t.tool_id)
  extraApproval.value = (ov.tool_overrides || []).filter((t) => t.require_approval).map((t) => t.tool_id)
  tokenBudget.value = (record.governance_overrides || {}).token_budget_per_task
  autonomy.value = (record.governance_overrides || {}).autonomy_level
  permOpen.value = true
}

async function savePerm() {
  saving.value = true
  try {
    const tool_overrides = []
    denyTools.value.forEach((id) => tool_overrides.push({ tool_id: id, permission: 'denied' }))
    extraApproval.value.forEach((id) => {
      if (!denyTools.value.includes(id)) tool_overrides.push({ tool_id: id, require_approval: true })
    })
    const governance_overrides = {}
    if (tokenBudget.value) governance_overrides.token_budget_per_task = tokenBudget.value
    if (autonomy.value) governance_overrides.autonomy_level = autonomy.value
    await workerApi.permissions(currentWorker.value.worker_id, { tool_overrides, governance_overrides })
    message.success('权限已更新')
    permOpen.value = false
    await load()
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function onMore(record, key) {
  if (key === 'REPAIR') {
    try {
      await workerApi.repairEntry(record.worker_id)
      message.success('入口编排已重建')
      await load()
    } catch (e) {
      message.error(e.message)
    }
    return
  }
  try {
    await workerApi.update(record.worker_id, { status: key })
    message.success('状态已更新')
    await load()
  } catch (e) {
    message.error(e.message)
  }
}

async function openPush(record) {
  currentWorker.value = record
  pushForm.value = {
    name: '任务完成通知',
    trigger_type: 'EVENT',
    event_key: 'TASK_COMPLETED',
    cron_expr: '',
    channel: 'IM',
    conv_id: '',
    callback_url: '',
    prompt_template: '请为数字员工 {{worker_name}} 生成一条简洁的主动沟通消息。任务「{{title}}」已完成。摘要：{{summary}}',
  }
  pushOpen.value = true
  try {
    pushRules.value = await workerApi.pushRules(record.worker_id)
  } catch (e) {
    message.error(e.message)
    pushRules.value = []
  }
}

async function doCreatePush() {
  if (!currentWorker.value) return
  if (!pushForm.value.name || !pushForm.value.prompt_template) {
    return message.error('请填写名称与提示模板')
  }
  saving.value = true
  try {
    await workerApi.createPushRule(currentWorker.value.worker_id, {
      ...pushForm.value,
      enabled: true,
    })
    message.success('已添加推送规则')
    pushRules.value = await workerApi.pushRules(currentWorker.value.worker_id)
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function doDeletePush(record) {
  try {
    await workerApi.deletePushRule(currentWorker.value.worker_id, record.rule_id)
    pushRules.value = await workerApi.pushRules(currentWorker.value.worker_id)
    message.success('已删除')
  } catch (e) {
    message.error(e.message)
  }
}

async function doRunPush(record) {
  try {
    await workerApi.runPushRule(currentWorker.value.worker_id, record.rule_id)
    message.success('已触发推送')
  } catch (e) {
    message.error(e.message)
  }
}

onMounted(() => { load(); loadMeta() })
</script>

<style scoped>
.spec-section {
  font-family: 'Noto Serif SC', serif;
  font-size: 15px;
  font-weight: 700;
  color: #1a1714;
  margin: 8px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8e2d8;
}
.spec-section:first-child { margin-top: 0; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.empty-text { color: #9e9590; }
.spec-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #9e9590;
  font-family: 'JetBrains Mono', monospace;
}
.spec-form :deep(.ant-input[readonly]),
.spec-form :deep(.ant-input-textarea textarea[readonly]) {
  background: #faf8f4;
  color: #1a1714;
  cursor: default;
}
.duty-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.duty-card {
  background: #faf8f4;
  border: 1px solid #e8e2d8;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}
.duty-card-hd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.duty-card-title {
  font-weight: 600;
  font-size: 14px;
}
.duty-card-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
  margin-top: 6px;
  align-items: flex-start;
}
.duty-card-row .lbl {
  flex: 0 0 64px;
  color: #9e9590;
}
.duty-card-row code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  word-break: break-all;
}
.mono-sm {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}
.push-form { margin-bottom: 8px; }
</style>
