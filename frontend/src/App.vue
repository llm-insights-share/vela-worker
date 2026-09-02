<template>
  <a-config-provider :locale="zhCN">
    <router-view v-if="isAuthPage" />
    <a-layout v-else style="min-height: 100vh">
      <a-layout-sider v-model:collapsed="collapsed" collapsible theme="dark" width="220">
        <div class="logo">
          <div class="logo-dot"></div>
          <span v-if="!collapsed" class="logo-text">Vela · Worker</span>
        </div>
        <a-menu
          v-model:selectedKeys="selectedKeys"
          theme="dark"
          mode="inline"
          @click="onMenuClick"
        >
          <a-menu-item key="/admin/workers">
            <RobotOutlined />
            <span>数字员工</span>
          </a-menu-item>
          <a-menu-item key="/admin/duties">
            <ProfileOutlined />
            <span>职责管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/roles">
            <TeamOutlined />
            <span>角色管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/org">
            <ApartmentOutlined />
            <span>组织机构</span>
          </a-menu-item>
          <a-menu-item key="/admin/tasks">
            <ScheduleOutlined />
            <span>任务中心</span>
          </a-menu-item>
          <a-menu-item key="/admin/apps">
            <ApiOutlined />
            <span>开放应用</span>
          </a-menu-item>
          <a-menu-item v-if="auth.isPlatformAdmin" key="/admin/users">
            <UserOutlined />
            <span>用户管理</span>
          </a-menu-item>
          <a-menu-item key="/im">
            <MessageOutlined />
            <span>工作沟通</span>
          </a-menu-item>
        </a-menu>
      </a-layout-sider>
      <a-layout>
        <a-layout-header class="header">
          <span class="header-title">数字员工服务</span>
          <div class="user-area">
            <a-popover
              v-model:open="inboxOpen"
              trigger="click"
              placement="bottomRight"
              overlay-class-name="inbox-popover"
            >
              <template #content>
                <div class="inbox-panel">
                  <div class="inbox-panel-title">站内消息</div>
                  <a-spin :spinning="inboxLoading">
                    <div v-if="!inboxItems.length" class="inbox-empty">暂无消息</div>
                    <div
                      v-for="msg in inboxItems"
                      :key="msg.message_id"
                      class="inbox-item"
                      :class="{ unread: !msg.is_read }"
                      @click="onInboxItemClick(msg)"
                    >
                      <div class="inbox-item-title">{{ msg.title }}</div>
                      <div class="inbox-item-body">{{ msg.body }}</div>
                      <div class="inbox-item-time">{{ formatDateTimeShort(msg.created_at) }}</div>
                    </div>
                  </a-spin>
                </div>
              </template>
              <a-badge :count="inboxUnread" :overflow-count="99" color="#b5341c">
                <BellOutlined class="inbox-bell" />
              </a-badge>
            </a-popover>
            <a-dropdown>
              <a class="user-link" @click.prevent>
                <a-avatar :size="24" :src="auth.user?.avatar || undefined" style="margin-right: 8px">
                  {{ (auth.user?.name || auth.user?.username || '?').slice(0, 1) }}
                </a-avatar>
                {{ auth.user?.name || auth.user?.username || '用户' }}
              </a>
              <template #overlay>
                <a-menu @click="onUserMenu">
                  <a-menu-item key="settings">个人设置</a-menu-item>
                  <a-menu-item key="logout">退出登录</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
        </a-layout-header>
        <a-layout-content :class="['content', { 'content-flush': isIm }]">
          <router-view />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  RobotOutlined,
  TeamOutlined,
  ApartmentOutlined,
  ScheduleOutlined,
  ApiOutlined,
  MessageOutlined,
  ProfileOutlined,
  UserOutlined,
  BellOutlined,
} from '@ant-design/icons-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { useAuthStore } from './stores/auth'
import { inboxApi } from './api'
import { formatDateTimeShort } from './utils/datetime'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const selectedKeys = ref(['/admin/workers'])
const inboxUnread = ref(0)
const inboxItems = ref([])
const inboxOpen = ref(false)
const inboxLoading = ref(false)
let inboxTimer = null

const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
const isIm = computed(() => route.path.startsWith('/im'))

async function fetchInboxUnread() {
  try {
    const res = await inboxApi.unreadCount()
    inboxUnread.value = res.unread_count || 0
  } catch (e) {
    console.error('[inbox] unread-count failed:', e)
  }
}

async function fetchInboxList() {
  inboxLoading.value = true
  try {
    const res = await inboxApi.list({ limit: 20 })
    inboxItems.value = res.items || []
  } catch (e) {
    console.error('[inbox] list failed:', e)
  } finally {
    inboxLoading.value = false
  }
}

function startInboxWatcher() {
  if (inboxTimer) return
  fetchInboxUnread()
  inboxTimer = setInterval(fetchInboxUnread, 8000)
}

function stopInboxWatcher() {
  if (inboxTimer) {
    clearInterval(inboxTimer)
    inboxTimer = null
  }
}

async function onInboxItemClick(msg) {
  try {
    if (!msg.is_read) {
      await inboxApi.markRead(msg.message_id)
      msg.is_read = true
      inboxUnread.value = Math.max(0, inboxUnread.value - 1)
    }
    inboxOpen.value = false
    if (msg.link_path) {
      router.push(msg.link_path)
    }
  } catch (e) {
    console.error('[inbox] mark-read failed:', e)
  }
}

onMounted(() => {
  if (!isAuthPage.value) {
    startInboxWatcher()
  }
})

onUnmounted(() => {
  stopInboxWatcher()
})

watch(inboxOpen, (open) => {
  if (open) {
    fetchInboxList()
  }
})

watch(
  () => route.path,
  (path) => {
    selectedKeys.value = [path]
    if (path === '/login' || path === '/register') {
      stopInboxWatcher()
    } else {
      startInboxWatcher()
    }
  },
  { immediate: true }
)

function onMenuClick({ key }) {
  router.push(key)
}

function onUserMenu({ key }) {
  if (key === 'settings') {
    router.push('/me/settings')
  } else if (key === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.logo-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #c2410c;
  flex-shrink: 0;
}
.logo-text {
  font-family: 'Noto Serif SC', serif;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}
.header {
  background: #3a342e;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.header-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 0.1em;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 16px;
}
.inbox-bell {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  padding: 4px;
}
.inbox-panel {
  width: 320px;
  max-height: 420px;
  overflow-y: auto;
}
.inbox-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #1a1714;
  margin-bottom: 8px;
}
.inbox-empty {
  color: #8c8780;
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}
.inbox-item {
  padding: 10px 8px;
  border-radius: 6px;
  cursor: pointer;
  border-bottom: 1px solid #f0ebe3;
}
.inbox-item:hover {
  background: #faf8f4;
}
.inbox-item.unread .inbox-item-title {
  font-weight: 600;
}
.inbox-item-title {
  font-size: 13px;
  color: #1a1714;
  margin-bottom: 2px;
}
.inbox-item-body {
  font-size: 12px;
  color: #6b6560;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.inbox-item-time {
  font-size: 11px;
  color: #a39e97;
  margin-top: 4px;
}
.user-link {
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  display: flex;
  align-items: center;
}
.content {
  padding: 24px;
  background: #faf8f4;
  min-height: calc(100vh - 64px);
}
.content-flush {
  padding: 0;
  overflow: hidden;
  height: calc(100vh - 64px);
  min-height: calc(100vh - 64px);
}
</style>
