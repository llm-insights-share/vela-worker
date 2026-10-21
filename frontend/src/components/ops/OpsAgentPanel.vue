<template>
  <div v-if="modelValue" class="ops-panel" role="dialog" aria-label="办公操作助手">
    <div class="ops-hd">
      <div>
        <div class="ops-title">办公操作助手</div>
        <div class="ops-sub">{{ meta?.name || 'vela-worker-ops-assistant' }}</div>
      </div>
      <div class="ops-hd-actions">
        <button type="button" class="ops-icon" title="新对话" @click="newChat">＋</button>
        <button type="button" class="ops-icon" title="关闭" @click="close">×</button>
      </div>
    </div>

    <div v-if="loadError" class="ops-error">{{ loadError }}</div>

    <div v-else class="ops-body" ref="bodyRef">
      <div v-if="!messages.length" class="ops-empty">
        可以问我：列出我的项目、创建事项并委派、启动 / 暂停 / 继续执行。
      </div>
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="ops-msg"
        :class="msg.role === 'user' ? 'is-user' : 'is-assistant'"
      >
        <div class="ops-role">{{ msg.role === 'user' ? '你' : '助手' }}</div>
        <pre class="ops-text">{{ textOf(msg) }}</pre>
      </div>
      <div v-if="running" class="ops-running">执行中…</div>
      <div v-for="ap in approvals" :key="ap.approval_id || ap.id" class="ops-hitl">
        <div class="ops-hitl-title">需要确认：{{ ap.tool_name || ap.title || '写操作' }}</div>
        <pre class="ops-text">{{ briefArgs(ap) }}</pre>
        <div class="ops-hitl-actions">
          <button type="button" class="ops-btn primary" :disabled="acting" @click="decide(ap, true)">批准</button>
          <button type="button" class="ops-btn" :disabled="acting" @click="decide(ap, false)">拒绝</button>
        </div>
      </div>
    </div>

    <form class="ops-input" @submit.prevent="send">
      <input v-model="draft" :disabled="!!loadError || running" placeholder="描述要执行的办公操作…" />
      <button type="submit" class="ops-btn primary" :disabled="!!loadError || running || !draft.trim()">发送</button>
    </form>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { opsAssistantApi } from '../../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const meta = ref(null)
const loadError = ref('')
const sessionId = ref('')
const messages = ref([])
const approvals = ref([])
const draft = ref('')
const running = ref(false)
const acting = ref(false)
const bodyRef = ref(null)
let pollTimer = null

function close() {
  emit('update:modelValue', false)
}

function textOf(msg) {
  const c = msg?.content
  if (typeof c === 'string') return c
  if (c && typeof c === 'object') {
    if (typeof c.text === 'string') return c.text
    if (typeof c.content === 'string') return c.content
    return JSON.stringify(c, null, 2)
  }
  return msg?.text || ''
}

function briefArgs(ap) {
  const args = ap.tool_args || ap.arguments || ap.preview || {}
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
}

async function scrollBottom() {
  await nextTick()
  const el = bodyRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function ensureMeta() {
  loadError.value = ''
  try {
    meta.value = await opsAssistantApi.meta()
  } catch (e) {
    loadError.value = e.message || '未找到办公操作助手，请先运行 seed'
  }
}

async function ensureSession() {
  if (sessionId.value) return
  const created = await opsAssistantApi.createSession()
  sessionId.value = created.session_id
}

async function refresh() {
  if (!sessionId.value) return
  const data = await opsAssistantApi.getSession(sessionId.value)
  messages.value = data.messages || []
  approvals.value = data.pending_approvals || []
  const status = String(data.status || '')
  running.value = status === 'RUNNING' || status === 'QUEUED'
  await scrollBottom()
  if (!running.value && !approvals.value.length) {
    window.dispatchEvent(new CustomEvent('vela-workbench-refresh'))
  }
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(async () => {
    try {
      await refresh()
      if (!running.value) stopPoll()
    } catch {
      stopPoll()
      running.value = false
    }
  }, 1500)
}

async function send() {
  const text = draft.value.trim()
  if (!text || running.value) return
  try {
    await ensureSession()
    draft.value = ''
    running.value = true
    messages.value = [...messages.value, { role: 'user', content: text }]
    await opsAssistantApi.send(sessionId.value, text)
    startPoll()
  } catch (e) {
    running.value = false
    message.error(e.message || '发送失败')
  }
}

async function decide(ap, approved) {
  const id = ap.approval_id || ap.id
  if (!id || !sessionId.value) return
  acting.value = true
  try {
    if (approved) {
      await opsAssistantApi.approve(sessionId.value, id)
      await opsAssistantApi.send(sessionId.value, '审批已通过，请根据工具结果继续完成刚才的请求。')
    } else {
      await opsAssistantApi.reject(sessionId.value, id)
    }
    running.value = true
    startPoll()
  } catch (e) {
    message.error(e.message || '审批失败')
  } finally {
    acting.value = false
  }
}

function newChat() {
  stopPoll()
  sessionId.value = ''
  messages.value = []
  approvals.value = []
  running.value = false
}

watch(() => props.modelValue, async (open) => {
  if (!open) {
    stopPoll()
    return
  }
  await ensureMeta()
})
</script>

<style scoped>
.ops-panel {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 380px;
  height: 560px;
  max-height: calc(100vh - 48px);
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.16);
  z-index: 920;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ops-hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #e2e8f0;
}
.ops-title { font-weight: 650; color: #0f172a; }
.ops-sub { font-size: 12px; color: #64748b; }
.ops-hd-actions { display: flex; gap: 4px; }
.ops-icon {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: #475569;
  width: 28px;
  height: 28px;
}
.ops-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background: #f8fafc;
}
.ops-empty, .ops-running, .ops-error {
  font-size: 13px;
  color: #64748b;
  padding: 8px 0;
}
.ops-error { color: #b91c1c; padding: 12px; }
.ops-msg { margin-bottom: 10px; }
.ops-role { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.ops-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  background: #fff;
  border-radius: 10px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
}
.is-user .ops-text { background: #eef2ff; border-color: #c7d2fe; }
.ops-hitl {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  padding: 8px;
  margin-top: 8px;
}
.ops-hitl-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.ops-hitl-actions { display: flex; gap: 8px; margin-top: 8px; }
.ops-input {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid #e2e8f0;
}
.ops-input input {
  flex: 1;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}
.ops-btn {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}
.ops-btn.primary {
  background: #4f46e5;
  color: #fff;
  border-color: #4f46e5;
}
.ops-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
