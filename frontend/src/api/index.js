import axios from 'axios'

const TOKEN_KEY = 'vela_worker_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      clearToken()
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?redirect=${redirect}`
      }
    }
    const msg = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(typeof msg === 'string' ? msg : JSON.stringify(msg)))
  }
)

export default api

export const authApi = {
  login: (username, password) => {
    const body = new URLSearchParams()
    body.set('username', username)
    body.set('password', password)
    return api.post('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
  updateProfile: (data) => api.patch('/auth/me/profile', data),
  updatePassword: (data) => api.patch('/auth/me/password', data),
  uploadAvatar: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/auth/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export const userApi = {
  list: () => api.get('/users'),
  create: (data) => api.post('/users', data),
  setActive: (id, is_active) => api.patch(`/users/${id}/active`, { is_active }),
  setRoles: (id, role) => api.patch(`/users/${id}/roles`, { role }),
  remove: (id) => api.delete(`/users/${id}`),
}

export const orgApi = {
  me: () => api.get('/org/me'),
  users: () => api.get('/org/users'),
  departments: () => api.get('/org/departments'),
  createDept: (data) => api.post('/org/departments', data),
  createUser: (data) => api.post('/org/users', data),
}

export const roleApi = {
  list: (params) => api.get('/roles', { params }),
  get: (id) => api.get(`/roles/${id}`),
  create: (data) => api.post('/roles', data),
  update: (id, data) => api.put(`/roles/${id}`, data),
  workers: (id) => api.get(`/roles/${id}/workers`),
}

export const dutyApi = {
  list: (params) => api.get('/duties', { params }),
  get: (id) => api.get(`/duties/${id}`),
  create: (data) => api.post('/duties', data),
  update: (id, data) => api.put(`/duties/${id}`, data),
}

export const workerApi = {
  list: (params) => api.get('/workers', { params }),
  get: (id) => api.get(`/workers/${id}`),
  create: (data) => api.post('/workers', data),
  update: (id, data) => api.put(`/workers/${id}`, data),
  spec: (id) => api.get(`/workers/${id}/spec`),
  permissions: (id, data) => api.put(`/workers/${id}/permissions`, data),
  duties: (id) => api.get(`/workers/${id}/duties`),
  addDuty: (id, data) => api.post(`/workers/${id}/duties`, data),
  removeDuty: (id, dutyId) => api.delete(`/workers/${id}/duties/${dutyId}`),
  repairEntry: (id) => api.post(`/workers/${id}/repair-entry`),
  pushRules: (id) => api.get(`/workers/${id}/push-rules`),
  createPushRule: (id, data) => api.post(`/workers/${id}/push-rules`, data),
  updatePushRule: (id, ruleId, data) => api.put(`/workers/${id}/push-rules/${ruleId}`, data),
  deletePushRule: (id, ruleId) => api.delete(`/workers/${id}/push-rules/${ruleId}`),
  runPushRule: (id, ruleId) => api.post(`/workers/${id}/push-rules/${ruleId}/run`),
}

export const catalogApi = {
  modelServices: () => api.get('/catalog/model-services'),
  skills: () => api.get('/catalog/skills'),
  tools: () => api.get('/catalog/tools'),
  knowledgeBases: () => api.get('/catalog/knowledge-bases'),
  agents: () => api.get('/catalog/agents'),
  health: () => api.get('/catalog/agent-health'),
}

export const convApi = {
  list: () => api.get('/conversations'),
  get: (id) => api.get(`/conversations/${id}`),
  create: (data) => api.post('/conversations', data),
  addMembers: (id, members) => api.post(`/conversations/${id}/members`, members),
  markRead: (id) => api.post(`/conversations/${id}/read`),
  messages: (id, params) => api.get(`/conversations/${id}/messages`, { params }),
  send: (id, data) => api.post(`/conversations/${id}/messages`, data),
  approval: (msgId, data) => api.post(`/conversations/messages/${msgId}/approval`, data),
  uploadAttachment: (convId, workerId, file) => {
    const form = new FormData()
    form.append('worker_id', workerId)
    form.append('file', file)
    return api.post(`/conversations/${convId}/agent-attachments`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  infoReply: (taskId, data) => api.post(`/conversations/tasks/${taskId}/info-reply`, data),
}

export const taskApi = {
  list: (params) => api.get('/tasks', { params }),
  get: (id) => api.get(`/tasks/${id}`),
  create: (workerId, data) => api.post(`/tasks?worker_id=${workerId}`, data),
  cancel: (id) => api.post(`/tasks/${id}/cancel`),
}

export const appApi = {
  list: () => api.get('/apps'),
  create: (data) => api.post('/apps', data),
}

export const inboxApi = {
  list: (params) => api.get('/inbox/messages', { params }),
  unreadCount: () => api.get('/inbox/unread-count'),
  markRead: (id) => api.post(`/inbox/messages/${id}/read`),
  markTaskRead: (taskId) => api.post(`/inbox/tasks/${taskId}/read`),
}
