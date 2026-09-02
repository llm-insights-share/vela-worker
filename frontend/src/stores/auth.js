import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, getToken, setToken, clearToken } from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => {
    const role = user.value?.role || ''
    return role === 'PLATFORM_ADMIN' || role === 'DEPT_ADMIN'
  })
  const isPlatformAdmin = computed(() => (user.value?.role || '') === 'PLATFORM_ADMIN')

  async function login(username, password) {
    const data = await authApi.login(username, password)
    token.value = data.access_token
    setToken(data.access_token)
    await fetchMe()
  }

  async function register(payload) {
    const data = await authApi.register({
      email: payload.email,
      username: payload.username,
      password: payload.password,
      display_name: payload.display_name || '',
    })
    token.value = data.access_token
    setToken(data.access_token)
    await fetchMe()
  }

  async function fetchMe() {
    if (!token.value) return
    user.value = await authApi.me()
  }

  function logout() {
    token.value = null
    user.value = null
    clearToken()
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    isPlatformAdmin,
    login,
    register,
    fetchMe,
    logout,
  }
})
