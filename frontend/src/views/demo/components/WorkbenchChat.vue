<template>
  <aside class="wb-chat" :class="panelClass">
    <!-- Collapsed rail -->
    <button
      v-if="isCollapsed"
      type="button"
      class="chat-rail"
      title="展开对话"
      @click="store.setChatPanel('side')"
    >
      <MessageOutlined class="rail-icon" />
      <span class="rail-label">对话</span>
    </button>

    <template v-else>
      <div class="chat-hd">
        <div class="chat-hd-side left">
          <div class="chat-avatar" :class="{ worker: !!currentWorker }">
            <RobotOutlined v-if="currentWorker" />
            <span v-else class="sparkles" aria-hidden="true">✦</span>
            <span class="avatar-dot" :class="statusClass" />
          </div>
        </div>

        <div class="chat-hd-center">
          <a-dropdown
            v-model:open="menuOpen"
            :trigger="['click']"
            placement="bottom"
          >
            <button type="button" class="assistant-trigger" :title="headerTitle" @click.stop>
              <span class="assistant-name">{{ headerTitle }}</span>
              <DownOutlined class="assistant-caret" />
            </button>
            <template #overlay>
              <div class="assistant-menu">
                <button
                  type="button"
                  class="assistant-option"
                  :class="{ active: !store.selectedWorkerId }"
                  @click="pickAssistant('ai-assistant')"
                >
                  <span class="opt-name">AI助手</span>
                  <span class="menu-status online"><i class="dot" />在线</span>
                </button>
                <div v-if="store.workers.length" class="assistant-divider" />
                <button
                  v-for="w in store.workers"
                  :key="w.worker_id"
                  type="button"
                  class="assistant-option"
                  :class="{ active: store.selectedWorkerId === w.worker_id }"
                  @click="pickAssistant(w.worker_id)"
                >
                  <span class="opt-name">{{ w.name }}</span>
                  <span class="menu-status" :class="w.activity">
                    <i class="dot" />{{ activityLabel(w.activity) }}
                  </span>
                </button>
              </div>
            </template>
          </a-dropdown>
          <div class="chat-status" :class="statusClass">
            <span class="status-dot" />
            {{ statusLabel }}
          </div>
        </div>

        <div class="chat-hd-side right">
          <button
            type="button"
            class="hd-icon-btn"
            :title="isFullscreen ? '退出全屏' : '全屏对话'"
            @click="store.toggleChatFullscreen()"
          >
            <CompressOutlined v-if="isFullscreen" />
            <ExpandOutlined v-else />
          </button>
          <button
            v-if="!isFullscreen"
            type="button"
            class="hd-icon-btn"
            title="收起对话"
            @click="store.setChatPanel('collapsed')"
          >
            <MenuFoldOutlined />
          </button>
        </div>
      </div>

      <div ref="msgBox" class="chat-msgs">
        <div v-if="showWelcome" class="msg-row left">
          <div class="msg-bubble theirs welcome">
            您好！我是您的智能办公助手。您可以向我委派任务、查询进度或咨询问题。请问有什么可以帮您？
          </div>
        </div>

        <div
          v-for="m in messages"
          :key="m.msg_id"
          :class="['msg-row', isMine(m) ? 'right' : 'left']"
        >
          <div v-if="m.msg_type === 'text'" class="msg-bubble" :class="isMine(m) ? 'mine' : 'theirs'">
            <MsgRichText :text="m.content?.text" :format="m.content?.format" />
          </div>

          <div v-else-if="m.msg_type === 'task_card'" class="card-msg">
            <div><b>任务</b> · {{ m.content?.title }}</div>
            <div class="card-meta">状态：<a-tag>{{ m.content?.status }}</a-tag></div>
          </div>

          <div v-else-if="m.msg_type === 'result_card'" class="card-msg result">
            <div><b>{{ m.content?.success ? '任务完成' : '任务失败' }}</b></div>
            <MsgRichText :text="m.content?.summary" format="markdown" />
          </div>

          <div v-else-if="m.msg_type === 'approval_card'" class="card-msg approval">
            <div><b>需要授权</b> · {{ m.content?.text }}</div>
            <a-button
              v-if="m.content?.status === 'PENDING'"
              type="primary"
              size="small"
              @click="$emit('open-approval', { msg_id: m.msg_id, ...m.content, task_id: m.ref_task_id })"
            >
              前往审核
            </a-button>
            <a-tag v-else>{{ m.content?.status }}</a-tag>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="quick-chips">
          <button type="button" class="chip" @click="draft = '请帮我委派一个新任务'">委派任务</button>
          <button type="button" class="chip" @click="draft = '请帮我查询当前任务进度'">查询进度</button>
          <button type="button" class="chip" @click="draft = '我想咨询一个问题：'">知识问答</button>
        </div>
        <div class="input-row">
          <PaperClipOutlined class="attach-icon" />
          <input
            v-model="draft"
            class="chat-input"
            type="text"
            placeholder="输入消息..."
            @keydown.enter.prevent="send"
          />
          <button
            type="button"
            class="send-btn"
            :disabled="sending"
            :aria-busy="sending"
            @click="send"
          >
            <SendOutlined />
          </button>
        </div>
      </div>
    </template>
  </aside>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import {
  RobotOutlined,
  DownOutlined,
  ExpandOutlined,
  CompressOutlined,
  MenuFoldOutlined,
  MessageOutlined,
  PaperClipOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { convApi } from '../../../api'
import { useAuthStore } from '../../../stores/auth'
import { useWorkbenchStore } from '../store/workbench'
import MsgRichText from '../../../components/im/MsgRichText.vue'

defineEmits(['open-approval'])

const auth = useAuthStore()
const store = useWorkbenchStore()
const messages = ref([])
const draft = ref('')
const sending = ref(false)
const msgBox = ref(null)
const menuOpen = ref(false)

const isCollapsed = computed(() => store.chatPanel === 'collapsed')
const isFullscreen = computed(() => store.chatPanel === 'fullscreen')
const panelClass = computed(() => ({
  collapsed: isCollapsed.value,
  fullscreen: isFullscreen.value,
}))

const currentWorker = computed(() => store.selectedWorker)

const headerTitle = computed(() => currentWorker.value?.name || 'AI助手')

const statusLabel = computed(() => {
  if (!currentWorker.value) return '在线'
  return activityLabel(currentWorker.value.activity)
})

const statusClass = computed(() => {
  if (!currentWorker.value) return 'online'
  return currentWorker.value.activity || 'online'
})

const showWelcome = computed(() =>
  !store.selectedWorkerId || messages.value.length === 0
)

function activityLabel(activity) {
  const map = { online: '空闲', working: '工作中', offline: '离线' }
  return map[activity] || '空闲'
}

function pickAssistant(key) {
  menuOpen.value = false
  if (key === 'ai-assistant') {
    store.clearWorker()
    messages.value = []
    store.activeConvId = null
    return
  }
  store.selectWorker(key)
}

watch(() => store.selectedWorkerId, async (workerId) => {
  if (!workerId) {
    messages.value = []
    store.activeConvId = null
    return
  }
  await ensureConv(workerId)
}, { immediate: true })

async function ensureConv(workerId) {
  const convs = await convApi.list()
  const list = Array.isArray(convs) ? convs : (convs.items || [])
  const existing = list.find((c) =>
    c.type === 'DIRECT' &&
    (c.members || []).some((m) => m.member_type === 'WORKER' && m.member_id === workerId)
  )
  if (existing) {
    store.activeConvId = existing.conv_id
    await loadMessages()
    return
  }
  const created = await convApi.create({
    type: 'DIRECT',
    members: [
      { member_type: 'HUMAN', member_id: auth.user.user_id },
      { member_type: 'WORKER', member_id: workerId },
    ],
  })
  store.activeConvId = created.conv_id
  await loadMessages()
}

async function loadMessages() {
  if (!store.activeConvId) return
  const res = await convApi.messages(store.activeConvId, { limit: 100 })
  messages.value = res.items || res || []
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}

function isMine(m) {
  return m.sender_type === 'HUMAN' && m.sender_id === auth.user?.user_id
}

async function send() {
  const text = draft.value.trim()
  if (!text) return
  if (!store.selectedWorkerId) {
    message.info('请先选择数字员工')
    return
  }
  if (!store.activeConvId) return
  sending.value = true
  try {
    await convApi.send(store.activeConvId, {
      content: text,
      mention_worker_ids: [store.selectedWorkerId],
    })
    draft.value = ''
    await loadMessages()
  } catch (e) {
    message.error(e.message)
  } finally {
    sending.value = false
  }
}

defineExpose({ loadMessages })
</script>

<style scoped>
.wb-chat {
  width: var(--wb-side-width, 300px);
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid var(--line, #e2e8f0);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  min-width: 0;
}

.wb-chat.fullscreen {
  flex: 1;
  width: auto;
}

.wb-chat.collapsed {
  width: 52px;
  align-items: stretch;
}

.chat-rail {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 16px 0;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--ink-2, #475569);
}

.chat-rail:hover {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.rail-icon {
  font-size: 18px;
}

.rail-label {
  writing-mode: vertical-rl;
  letter-spacing: 0.12em;
  font-size: 12px;
  font-weight: 600;
}

.chat-hd {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line, #e2e8f0);
  display: grid;
  grid-template-columns: 40px 1fr auto;
  align-items: center;
  gap: 8px;
}

.chat-hd-side {
  display: flex;
  align-items: center;
  gap: 2px;
}

.chat-hd-side.left {
  justify-content: flex-start;
}

.chat-hd-side.right {
  justify-content: flex-end;
}

.chat-hd-center {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.chat-avatar {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--brand, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.chat-avatar.worker {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.avatar-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid #fff;
  background: #94a3b8;
}

.avatar-dot.online { background: #16a34a; }
.avatar-dot.working { background: #4f46e5; }
.avatar-dot.offline { background: #94a3b8; }

.sparkles {
  font-size: 14px;
  line-height: 1;
}

.assistant-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: none;
  background: transparent;
  padding: 2px 8px;
  border-radius: 6px;
  cursor: pointer;
  max-width: 100%;
}

.assistant-trigger:hover {
  background: var(--surface-2, #f1f5f9);
}

.assistant-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--ink, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.wb-chat.fullscreen .assistant-name {
  max-width: 420px;
}

.assistant-caret {
  font-size: 10px;
  color: var(--ink-3, #94a3b8);
  flex-shrink: 0;
}

.chat-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-top: 2px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
}

.chat-status.online .status-dot { background: #16a34a; }
.chat-status.working .status-dot { background: #4f46e5; }
.chat-status.offline .status-dot { background: #94a3b8; }

.hd-icon-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-3, #94a3b8);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 14px;
  flex-shrink: 0;
}

.hd-icon-btn:hover {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink, #0f172a);
}

.assistant-menu {
  min-width: 200px;
  padding: 6px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  border: 1px solid var(--line, #e2e8f0);
}

.assistant-option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: none;
  background: transparent;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}

.assistant-option:hover,
.assistant-option.active {
  background: var(--brand-light, #eef2ff);
}

.opt-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink, #0f172a);
}

.assistant-divider {
  height: 1px;
  background: var(--line, #e2e8f0);
  margin: 4px 6px;
}

.menu-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #94a3b8;
  flex-shrink: 0;
}

.menu-status .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  display: inline-block;
}

.menu-status.online { color: #16a34a; }
.menu-status.online .dot { background: #16a34a; }
.menu-status.working { color: #4f46e5; }
.menu-status.working .dot { background: #4f46e5; }
.menu-status.offline { color: #94a3b8; }
.menu-status.offline .dot { background: #94a3b8; }

.chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fff;
}

.wb-chat.fullscreen .chat-msgs {
  max-width: 880px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 28px;
}

.msg-row {
  margin-bottom: 12px;
}

.msg-row.right {
  text-align: right;
}

.msg-bubble {
  display: inline-block;
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
  word-break: break-word;
}

.wb-chat.fullscreen .msg-bubble {
  max-width: 720px;
}

.msg-bubble.theirs {
  background: #f3f4f6;
  color: var(--ink, #0f172a);
}

.msg-bubble.mine {
  background: var(--brand-light, #eef2ff);
  color: var(--ink, #0f172a);
}

.card-msg {
  display: inline-block;
  text-align: left;
  background: #fff;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  max-width: 90%;
}

.card-msg.result {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.card-msg.approval {
  border-color: #fde68a;
  background: #fffbeb;
}

.card-meta {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-2, #475569);
}

.chat-input-area {
  padding: 12px 14px 14px;
  border-top: 1px solid var(--line, #e2e8f0);
  background: #fff;
}

.wb-chat.fullscreen .chat-input-area {
  max-width: 880px;
  width: 100%;
  margin: 0 auto;
  padding: 16px 28px 20px;
}

.quick-chips {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.chip {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--ink-2, #475569);
  cursor: pointer;
}

.chip:hover {
  border-color: var(--brand, #4f46e5);
  color: var(--brand, #4f46e5);
}

.input-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.attach-icon {
  color: #9ca3af;
  font-size: 16px;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  min-width: 0;
  height: 36px;
  border: none;
  outline: none;
  background: #f3f4f6;
  border-radius: 999px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--ink, #0f172a);
}

.chat-input::placeholder {
  color: #9ca3af;
}

.send-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: var(--brand, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  font-size: 14px;
}

.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn:hover:not(:disabled) {
  background: var(--brand-hover, #4338ca);
}
</style>
