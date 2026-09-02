<template>
  <div class="im-layout">
    <!-- left: conversations -->
    <aside class="im-left">
      <div class="im-left-hd">
        <span>会话</span>
        <a-button size="small" type="primary" @click="createOpen = true">
          <template #icon><PlusOutlined /></template>
          新建
        </a-button>
      </div>
      <div class="im-left-search">
        <a-input
          v-model:value="convQuery"
          allow-clear
          placeholder="搜索会话"
          class="conv-search-input"
        >
          <template #prefix><SearchOutlined /></template>
        </a-input>
      </div>
      <div class="im-left-tabs">
        <button
          type="button"
          class="conv-tab"
          :class="{ active: convFilter === 'all' }"
          @click="convFilter = 'all'"
        >全部</button>
        <button
          type="button"
          class="conv-tab"
          :class="{ active: convFilter === 'unread' }"
          @click="convFilter = 'unread'"
        >未读{{ unreadTotal > 0 ? ` ${unreadTotal}` : '' }}</button>
        <button
          type="button"
          class="conv-tab"
          :class="{ active: convFilter === 'read' }"
          @click="convFilter = 'read'"
        >已读</button>
      </div>
      <div class="im-left-list">
        <div
          v-for="c in filteredConversations"
          :key="c.conv_id"
          class="conv-item"
          :class="{ active: c.conv_id === activeId }"
          @click="selectConv(c)"
        >
          <div class="conv-avatar" :style="{ background: convAvatarColor(c) }">
            {{ convAvatarLetter(c) }}
          </div>
          <div class="conv-body">
            <div class="conv-top">
              <div class="conv-title-row">
                <span class="conv-name">{{ c.name || '未命名' }}</span>
                <span v-for="tag in convTags(c)" :key="tag" class="conv-tag" :class="'conv-tag--' + tag.key">{{ tag.label }}</span>
              </div>
              <span class="conv-time">{{ convListTime(c.last_message?.created_at || c.created_at) }}</span>
            </div>
            <div class="conv-bottom">
              <div class="conv-preview">{{ previewText(c) }}</div>
              <span v-if="(c.unread_count || 0) > 0" class="conv-unread">{{ c.unread_count > 99 ? '99+' : c.unread_count }}</span>
            </div>
          </div>
        </div>
        <div v-if="!filteredConversations.length" class="conv-list-empty">暂无会话</div>
      </div>
    </aside>

    <!-- center: messages -->
    <section class="im-center">
      <template v-if="active">
        <div class="im-center-hd">{{ active.name }}</div>
        <div class="im-msgs" ref="msgBox">
          <div v-for="m in messages" :key="m.msg_id" :class="['msg-row', isMine(m) ? 'right' : 'left']">
            <div class="msg-meta">
              {{ m.sender_name }}
              <span v-if="m.sender_type === 'WORKER'" class="worker-badge">AI</span>
              · {{ formatTime(m.created_at) }}
            </div>

            <div v-if="m.msg_type === 'text'" class="msg-bubble" :class="isMine(m) ? 'mine' : 'theirs'">
              <MsgRichText :text="m.content?.text" :format="m.content?.format" />
            </div>

            <div v-else-if="m.msg_type === 'worker_spec_card'" class="card-msg">
              <b>{{ m.content?.spec?.identity?.name || m.sender_name }}</b>
              <span class="worker-badge">AI</span>
              <div class="card-desc">
                <MsgRichText :text="m.content?.text" :format="m.content?.format" />
              </div>
              <div class="card-meta">
                工号 {{ m.content?.spec?.identity?.employee_no }} ·
                {{ m.content?.spec?.identity?.role_name }} ·
                {{ m.content?.spec?.identity?.dept_name }}
              </div>
              <div class="card-tags">
                <a-tag v-for="d in (m.content?.spec?.profile?.duty_scope || []).slice(0,3)" :key="d">{{ d }}</a-tag>
              </div>
            </div>

            <div v-else-if="m.msg_type === 'task_card'" class="card-msg">
              <div><b>任务</b> · {{ m.content?.title }}</div>
              <div class="card-meta">状态：<a-tag>{{ m.content?.status }}</a-tag></div>
              <div class="card-desc">
                <MsgRichText :text="m.content?.instruction" :format="m.content?.format" />
              </div>
            </div>

            <div v-else-if="m.msg_type === 'result_card'" class="card-msg result" :class="m.content?.success ? 'ok' : 'fail'">
              <div><b>{{ m.content?.success ? '任务完成' : '任务失败' }}</b> · {{ m.content?.title }}</div>
              <div class="card-body">
                <MsgRichText :text="m.content?.summary" :format="m.content?.format || 'markdown'" />
              </div>
            </div>

            <div v-else-if="m.msg_type === 'approval_card'" class="card-msg approval">
              <div><b>需要审批</b> · {{ approvalTitle(m) }}</div>
              <div v-if="m.content?.text" class="card-desc">
                <MsgRichText :text="m.content.text" :format="m.content?.format" />
              </div>
              <pre v-if="showApprovalArgs(m)" class="card-pre">{{ JSON.stringify(m.content?.tool_args, null, 2) }}</pre>
              <div v-if="m.content?.status === 'PENDING'" class="card-actions">
                <div v-if="approvalKind(m) === 'otp' && approvalForms[m.msg_id]" class="card-field">
                  <a-input
                    v-model:value="approvalForms[m.msg_id].otp_code"
                    placeholder="请输入验证码"
                    size="small"
                    class="card-input-sm"
                  />
                </div>
                <div v-else-if="approvalKind(m) === 'skill_params' && approvalForms[m.msg_id]" class="card-field">
                  <div v-for="p in (m.content?.missing_params || [])" :key="p" class="card-param">
                    <div class="card-param-label">{{ p }}</div>
                    <a-input
                      v-model:value="approvalForms[m.msg_id].param_values[p]"
                      size="small"
                      :placeholder="`填写 ${p}`"
                    />
                  </div>
                </div>
                <a-space>
                  <a-button type="primary" size="small" @click="doApproval(m, true)">批准</a-button>
                  <a-button danger size="small" @click="doApproval(m, false)">拒绝</a-button>
                </a-space>
              </div>
              <div v-else class="card-status">
                {{ m.content?.status }} · {{ m.content?.reviewer }}
              </div>
            </div>

            <div v-else class="msg-bubble theirs">[{{ m.msg_type }}] {{ JSON.stringify(m.content) }}</div>
          </div>
        </div>
        <div class="im-composer">
          <div class="composer-tools">
            <a-select
              v-model:value="mentionWorkerId"
              allowClear
              placeholder="@数字员工"
              class="composer-select"
              size="small"
              :options="workerMemberOptions"
            />
            <a-checkbox v-model:checked="asTask">指派任务</a-checkbox>
            <a-input v-if="asTask" v-model:value="taskTitle" size="small" placeholder="任务标题" class="composer-input" />
            <a-input v-if="asTask" v-model:value="taskType" size="small" placeholder="task_type" class="composer-input-sm" />
            <a-upload
              v-if="!asTask && mentionWorkerId"
              :show-upload-list="false"
              :before-upload="beforeUpload"
            >
              <a-button size="small">附件</a-button>
            </a-upload>
            <span v-if="pendingAttachments.length" class="composer-hint">
              已选 {{ pendingAttachments.length }} 个附件
              <a class="composer-clear" @click="clearAttachments">清除</a>
            </span>
          </div>
          <div class="composer-row">
            <a-textarea
              v-model:value="draft"
              :rows="2"
              placeholder="输入消息，群聊请 @数字员工 或选择上方提及"
              @pressEnter="onEnter"
            />
            <a-button type="primary" :loading="sending" @click="send">发送</a-button>
          </div>
        </div>
      </template>
      <div v-else class="im-empty">
        <div class="im-empty-icon" aria-hidden="true">
          <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
            <rect x="16" y="18" width="40" height="30" rx="8" stroke="#c9cdd4" stroke-width="2.5"/>
            <path d="M28 48 L36 56 L36 48" stroke="#c9cdd4" stroke-width="2.5" stroke-linejoin="round"/>
            <circle cx="30" cy="33" r="2.2" fill="#c9cdd4"/>
            <circle cx="36" cy="33" r="2.2" fill="#c9cdd4"/>
            <circle cx="42" cy="33" r="2.2" fill="#c9cdd4"/>
          </svg>
        </div>
        <div class="im-empty-text">选择左侧会话开始沟通</div>
      </div>
    </section>

    <!-- right: members -->
    <aside class="im-right" v-if="active">
      <div class="im-right-hd">成员 ({{ active.members?.length || 0 }})</div>
      <div v-for="m in active.members || []" :key="m.member_id" class="member-item" @click="m.member_type==='WORKER' && showWorkerSpec(m)">
        <div class="member-name">
          {{ m.name }}
          <span v-if="m.member_type==='WORKER'" class="worker-badge">AI</span>
        </div>
        <div class="member-sub">{{ m.member_type }}{{ m.employee_no ? ' · ' + m.employee_no : '' }}</div>
      </div>
      <a-button block size="small" class="member-add-btn" @click="addMemberOpen = true">添加成员</a-button>
    </aside>

    <!-- create conversation -->
    <a-modal v-model:open="createOpen" title="新建会话" @ok="createConv" :confirmLoading="sending">
      <a-form layout="vertical">
        <a-form-item label="类型">
          <a-radio-group v-model:value="createForm.type">
            <a-radio value="GROUP">工作组群聊</a-radio>
            <a-radio value="DIRECT">单聊</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="名称" v-if="createForm.type==='GROUP'">
          <a-input v-model:value="createForm.name" />
        </a-form-item>
        <a-form-item label="人类成员">
          <a-select v-model:value="createForm.humanIds" mode="multiple" :options="humanOptions" />
        </a-form-item>
        <a-form-item label="数字员工">
          <a-select v-model:value="createForm.workerIds" mode="multiple" :options="allWorkerOptions" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="addMemberOpen" title="添加成员" @ok="addMembers">
      <a-form layout="vertical">
        <a-form-item label="人类"><a-select v-model:value="addHumans" mode="multiple" :options="humanOptions" /></a-form-item>
        <a-form-item label="数字员工"><a-select v-model:value="addWorkers" mode="multiple" :options="allWorkerOptions" /></a-form-item>
      </a-form>
    </a-modal>

    <a-drawer v-model:open="specDrawer" title="数字员工规格" width="480">
      <pre class="spec-pre">{{ JSON.stringify(workerSpec, null, 2) }}</pre>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { convApi, orgApi, workerApi, getToken } from '../../api'
import { useAuthStore } from '../../stores/auth'
import MsgRichText from '../../components/im/MsgRichText.vue'

const auth = useAuthStore()
const route = useRoute()

const conversations = ref([])
const convQuery = ref('')
const convFilter = ref('all')
const activeId = ref(null)
const active = ref(null)
const messages = ref([])
const draft = ref('')
const sending = ref(false)
const asTask = ref(false)
const taskTitle = ref('')
const taskType = ref('')
const mentionWorkerId = ref(undefined)
const msgBox = ref(null)
const createOpen = ref(false)
const addMemberOpen = ref(false)
const createForm = ref({ type: 'GROUP', name: '', humanIds: [], workerIds: [] })
const addHumans = ref([])
const addWorkers = ref([])
const humanOptions = ref([])
const allWorkerOptions = ref([])
const specDrawer = ref(false)
const workerSpec = ref({})
const approvalForms = ref({})
const pendingAttachments = ref([])
let ws = null

const AVATAR_COLORS = ['#5b8ff9', '#5ad8a6', '#5d7092', '#f6bd16', '#e8684a', '#6dc8ec', '#9270ca', '#ff9d4d']

const workerMemberOptions = computed(() =>
  (active.value?.members || [])
    .filter((m) => m.member_type === 'WORKER')
    .map((m) => ({ value: m.member_id, label: m.name }))
)

const unreadTotal = computed(() =>
  conversations.value.reduce((sum, c) => sum + (c.unread_count || 0), 0)
)

const filteredConversations = computed(() => {
  const q = convQuery.value.trim().toLowerCase()
  return conversations.value.filter((c) => {
    const unread = c.unread_count || 0
    if (convFilter.value === 'unread' && unread <= 0) return false
    if (convFilter.value === 'read' && unread > 0) return false
    if (!q) return true
    const name = (c.name || '').toLowerCase()
    const preview = previewText(c).toLowerCase()
    return name.includes(q) || preview.includes(q)
  })
})

function isMine(m) {
  return m.sender_type === 'HUMAN' && m.sender_id === auth.user?.user_id
}

function previewText(c) {
  const lm = c.last_message
  if (!lm) return ''
  if (lm.msg_type === 'text') return (lm.content?.text || '').replace(/\s+/g, ' ').slice(0, 40)
  if (lm.msg_type === 'push') return (lm.content?.text || '[推送]').replace(/\s+/g, ' ').slice(0, 40)
  const labels = {
    worker_spec_card: '[数字员工名片]',
    task_card: '[任务]',
    result_card: '[任务结果]',
    approval_card: '[审批]',
  }
  return labels[lm.msg_type] || `[${lm.msg_type}]`
}

function formatTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

function convAvatarLetter(c) {
  const name = (c.name || '未').trim()
  return name.charAt(0) || '未'
}

function convAvatarColor(c) {
  const key = c.conv_id || c.name || ''
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function convTags(c) {
  const tags = []
  if ((c.members || []).some((m) => m.member_type === 'WORKER')) {
    tags.push({ key: 'ai', label: 'AI' })
  }
  if (c.last_message?.msg_type === 'push') {
    tags.push({ key: 'push', label: '推送' })
  }
  return tags
}

function convListTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return String(t).slice(0, 10)
  const now = new Date()
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startThat = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.round((startToday - startThat) / 86400000)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (diffDays === 0) return `${hh}:${mm}`
  if (diffDays === 1) return '昨天'
  if (diffDays > 1 && diffDays < 7) {
    return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
  }
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${mo}-${day}`
}

function bumpConvFromMessage(msg) {
  if (!msg?.conv_id) return
  const idx = conversations.value.findIndex((c) => c.conv_id === msg.conv_id)
  if (idx < 0) {
    loadConvs()
    return
  }
  const c = { ...conversations.value[idx], last_message: msg }
  const mine = msg.sender_type === 'HUMAN' && msg.sender_id === auth.user?.user_id
  if (msg.conv_id === activeId.value) {
    c.unread_count = 0
  } else if (!mine) {
    c.unread_count = (c.unread_count || 0) + 1
  }
  const next = conversations.value.slice()
  next.splice(idx, 1)
  next.unshift(c)
  conversations.value = next
}

function approvalKind(m) {
  return m.content?.approval_kind || 'tool'
}

function approvalTitle(m) {
  const kind = approvalKind(m)
  const map = {
    otp: 'ScreenPilot 验证码',
    skill_params: '技能参数确认',
    delivery: '交付审批',
    workflow: '工作流审批',
    tool: m.content?.tool_name || '工具审批',
  }
  return map[kind] || m.content?.tool_name || '审批'
}

function showApprovalArgs(m) {
  const kind = approvalKind(m)
  return kind === 'tool' || kind === 'delivery' || kind === 'workflow'
}

function ensureApprovalForm(msgId, missingParams = []) {
  if (!approvalForms.value[msgId]) {
    const param_values = {}
    for (const p of missingParams) param_values[p] = ''
    approvalForms.value[msgId] = { otp_code: '', param_values }
  }
  return approvalForms.value[msgId]
}

watch(messages, (list) => {
  for (const m of list || []) {
    if (m.msg_type === 'approval_card' && m.content?.status === 'PENDING') {
      ensureApprovalForm(m.msg_id, m.content?.missing_params || [])
    }
  }
}, { deep: true, immediate: true })

function beforeUpload(file) {
  if (!mentionWorkerId.value) {
    message.warning('请先选择 @数字员工 再上传附件')
    return false
  }
  pendingAttachments.value.push(file)
  return false
}

function clearAttachments() {
  pendingAttachments.value = []
}

async function uploadPendingAttachments() {
  const ids = []
  for (const file of pendingAttachments.value) {
    const res = await convApi.uploadAttachment(activeId.value, mentionWorkerId.value, file)
    if (res?.attachment_id) ids.push(res.attachment_id)
  }
  return ids
}

async function loadConvs() {
  const list = await convApi.list()
  conversations.value = (list || []).slice().sort((a, b) => {
    const ta = new Date(a.last_message?.created_at || a.created_at || 0).getTime()
    const tb = new Date(b.last_message?.created_at || b.created_at || 0).getTime()
    return tb - ta
  })
}

async function selectConv(c) {
  activeId.value = c.conv_id
  active.value = await convApi.get(c.conv_id)
  messages.value = await convApi.messages(c.conv_id, { limit: 100 })
  try {
    const updated = await convApi.markRead(c.conv_id)
    const idx = conversations.value.findIndex((x) => x.conv_id === c.conv_id)
    if (idx >= 0) {
      conversations.value[idx] = {
        ...conversations.value[idx],
        ...updated,
        unread_count: 0,
      }
    }
  } catch (_) {
    const idx = conversations.value.findIndex((x) => x.conv_id === c.conv_id)
    if (idx >= 0) conversations.value[idx].unread_count = 0
  }
  await nextTick()
  scrollBottom()
}

function scrollBottom() {
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}

async function send() {
  if (!draft.value.trim() || !activeId.value) return
  sending.value = true
  try {
    let attachmentIds = []
    if (!asTask.value && pendingAttachments.value.length && mentionWorkerId.value) {
      attachmentIds = await uploadPendingAttachments()
    }
    const payload = {
      content: draft.value,
      mention_worker_ids: mentionWorkerId.value ? [mentionWorkerId.value] : [],
      as_task: asTask.value,
      task_title: taskTitle.value,
      task_type: taskType.value,
      attachment_ids: attachmentIds,
    }
    // if group and text contains @name, also add mentions
    const text = draft.value
    for (const m of active.value?.members || []) {
      if (m.member_type === 'WORKER' && text.includes('@' + m.name)) {
        if (!payload.mention_worker_ids.includes(m.member_id)) {
          payload.mention_worker_ids.push(m.member_id)
        }
      }
    }
    await convApi.send(activeId.value, payload)
    draft.value = ''
    asTask.value = false
    taskTitle.value = ''
    pendingAttachments.value = []
    // refresh messages (WS may also push)
    messages.value = await convApi.messages(activeId.value, { limit: 100 })
    await nextTick()
    scrollBottom()
    await loadConvs()
  } catch (e) {
    message.error(e.message)
  } finally {
    sending.value = false
  }
}

function onEnter(e) {
  if (!e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function doApproval(m, approved) {
  try {
    const form = ensureApprovalForm(m.msg_id, m.content?.missing_params || [])
    const payload = {
      approved,
      comment: approved ? '同意' : '拒绝',
    }
    if (approved && approvalKind(m) === 'otp') {
      payload.otp_code = form.otp_code || ''
    }
    if (approved && approvalKind(m) === 'skill_params') {
      payload.param_values = { ...form.param_values }
    }
    await convApi.approval(m.msg_id, payload)
    message.success(approved ? '已批准' : '已拒绝')
    messages.value = await convApi.messages(activeId.value, { limit: 100 })
  } catch (e) {
    message.error(e.message)
  }
}

async function createConv() {
  sending.value = true
  try {
    const members = [
      ...createForm.value.humanIds.map((id) => ({ member_type: 'HUMAN', member_id: id })),
      ...createForm.value.workerIds.map((id) => ({ member_type: 'WORKER', member_id: id })),
    ]
    const conv = await convApi.create({
      type: createForm.value.type,
      name: createForm.value.name,
      members,
    })
    createOpen.value = false
    await loadConvs()
    await selectConv(conv)
  } catch (e) {
    message.error(e.message)
  } finally {
    sending.value = false
  }
}

async function addMembers() {
  try {
    const members = [
      ...addHumans.value.map((id) => ({ member_type: 'HUMAN', member_id: id })),
      ...addWorkers.value.map((id) => ({ member_type: 'WORKER', member_id: id })),
    ]
    active.value = await convApi.addMembers(activeId.value, members)
    addMemberOpen.value = false
    addHumans.value = []
    addWorkers.value = []
    messages.value = await convApi.messages(activeId.value, { limit: 100 })
  } catch (e) {
    message.error(e.message)
  }
}

async function showWorkerSpec(m) {
  workerSpec.value = await workerApi.spec(m.member_id)
  specDrawer.value = true
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const token = getToken()
  if (!token) return
  ws = new WebSocket(`${proto}://${location.host}/api/v1/ws?token=${encodeURIComponent(token)}`)
  ws.onmessage = async (ev) => {
    try {
      const evt = JSON.parse(ev.data)
      if (evt.type === 'message' && evt.data) {
        if (evt.data.conv_id === activeId.value) {
          const exists = messages.value.find((x) => x.msg_id === evt.data.msg_id)
          if (!exists) {
            messages.value.push(evt.data)
            await nextTick()
            scrollBottom()
          } else {
            Object.assign(exists, evt.data)
          }
          try {
            await convApi.markRead(activeId.value)
          } catch (_) {}
        }
        bumpConvFromMessage(evt.data)
      }
      if (evt.type === 'task_update') {
        if (activeId.value) {
          messages.value = await convApi.messages(activeId.value, { limit: 100 })
        }
      }
    } catch (_) {}
  }
  ws.onclose = () => {
    setTimeout(connectWs, 3000)
  }
}

onMounted(async () => {
  const [users, workers] = await Promise.all([orgApi.users(), workerApi.list({ status: 'ON_DUTY', page_size: 100 })])
  humanOptions.value = (users || []).map((u) => ({ value: u.user_id, label: u.name }))
  allWorkerOptions.value = (workers.items || []).map((w) => ({ value: w.worker_id, label: `${w.name} (${w.employee_no})` }))
  await loadConvs()
  const convId = route.query.conv
  if (convId) {
    const target = conversations.value.find((c) => c.conv_id === convId)
    if (target) {
      await selectConv(target)
    }
  }
  connectWs()
})

onUnmounted(() => {
  if (ws) ws.close()
})
</script>

<style scoped>
.im-layout {
  --im-bg: #f5f6f8;
  --im-panel: #fff;
  --im-border: #e8eaed;
  --im-hover: #f3f4f6;
  --im-active: #eef3ff;
  --im-primary: #1677ff;
  --im-text: #1f2329;
  --im-muted: #8f959e;
  display: flex;
  height: 100%;
  background: var(--im-bg);
  color: var(--im-text);
}

.im-left {
  width: 300px;
  background: var(--im-panel);
  border-right: 1px solid var(--im-border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.im-left-hd {
  padding: 14px 16px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 16px;
}
.im-left-search {
  padding: 0 12px 8px;
}
.conv-search-input {
  border-radius: 16px;
}
.im-left-search :deep(.ant-input-affix-wrapper) {
  border-radius: 16px;
  background: #f3f4f6;
  border-color: transparent;
}
.im-left-search :deep(.ant-input-affix-wrapper:hover),
.im-left-search :deep(.ant-input-affix-wrapper-focused) {
  background: #fff;
  border-color: var(--im-primary);
}
.im-left-search :deep(.ant-input) {
  background: transparent;
}
.im-left-tabs {
  display: flex;
  gap: 4px;
  padding: 0 12px;
  border-bottom: 1px solid var(--im-border);
}
.conv-tab {
  appearance: none;
  border: none;
  background: transparent;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--im-muted);
  cursor: pointer;
  position: relative;
  line-height: 1.2;
}
.conv-tab.active {
  color: var(--im-primary);
  font-weight: 600;
}
.conv-tab.active::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 0;
  height: 2px;
  background: var(--im-primary);
  border-radius: 1px;
}
.im-left-list {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.conv-item {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  align-items: flex-start;
}
.conv-item:hover { background: var(--im-hover); }
.conv-item.active { background: var(--im-active); }
.conv-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}
.conv-body {
  flex: 1;
  min-width: 0;
}
.conv-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.conv-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.conv-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--im-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-tag {
  flex-shrink: 0;
  font-size: 10px;
  line-height: 16px;
  padding: 0 5px;
  border-radius: 3px;
  font-weight: 500;
}
.conv-tag--ai {
  background: #ff4d4f;
  color: #fff;
}
.conv-tag--push {
  background: #e8f0fe;
  color: #1677ff;
}
.conv-time {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--im-muted);
}
.conv-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
}
.conv-preview {
  font-size: 12px;
  color: var(--im-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.conv-unread {
  flex-shrink: 0;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--im-primary);
  color: #fff;
  font-size: 11px;
  line-height: 16px;
  text-align: center;
  font-weight: 500;
}
.conv-list-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--im-muted);
  font-size: 13px;
}

.im-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.im-center-hd {
  padding: 12px 16px;
  background: var(--im-panel);
  border-bottom: 1px solid var(--im-border);
  font-weight: 600;
  font-size: 14px;
}
.im-msgs {
  flex: 1;
  overflow: auto;
  padding: 16px;
  background: var(--im-bg);
}
.msg-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 8px;
}
.msg-row.right { align-items: flex-end; }
.msg-row.left { align-items: flex-start; }

.im-composer {
  background: var(--im-panel);
  border-top: 1px solid var(--im-border);
  padding: 10px 14px;
}
.composer-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.composer-select { width: 160px; }
.composer-input { width: 160px; }
.composer-input-sm { width: 140px; }
.composer-hint { font-size: 12px; color: var(--im-muted); }
.composer-clear { margin-left: 6px; }
.composer-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.composer-row :deep(.ant-input) { flex: 1; border-radius: 6px; }

.im-right {
  width: 220px;
  background: var(--im-panel);
  border-left: 1px solid var(--im-border);
  padding: 12px;
  overflow: auto;
}
.im-right-hd {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 10px;
  color: var(--im-text);
}
.member-item {
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}
.member-item:hover { background: var(--im-hover); }
.member-name { font-size: 13px; color: var(--im-text); }
.member-sub { font-size: 11px; color: var(--im-muted); margin-top: 2px; }
.member-add-btn { margin-top: 12px; }

.im-empty {
  margin: auto;
  color: var(--im-muted);
  font-size: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.im-empty-icon {
  opacity: 0.9;
}
.im-empty-text {
  font-size: 14px;
  color: var(--im-muted);
}

.spec-pre {
  white-space: pre-wrap;
  font-size: 12px;
  color: var(--im-text);
}
</style>
