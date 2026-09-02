import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    component: () => import('../views/auth/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/register',
    component: () => import('../views/auth/Register.vue'),
    meta: { public: true },
  },
  { path: '/', redirect: '/admin/workers' },
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/admin/workers' },
      { path: 'roles', component: () => import('../views/admin/Roles.vue') },
      { path: 'duties', component: () => import('../views/admin/Duties.vue') },
      { path: 'workers', component: () => import('../views/admin/Workers.vue') },
      { path: 'org', component: () => import('../views/admin/Org.vue') },
      { path: 'tasks', component: () => import('../views/admin/Tasks.vue') },
      { path: 'apps', component: () => import('../views/admin/Apps.vue') },
      {
        path: 'users',
        component: () => import('../views/users/UserList.vue'),
        meta: { requiresPlatformAdmin: true },
      },
    ],
  },
  {
    path: '/im',
    component: () => import('../views/im/ImLayout.vue'),
  },
  {
    path: '/me/settings',
    component: () => import('../views/settings/UserSettings.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const token = getToken()
  if (to.meta.public) {
    if (token && (to.path === '/login' || to.path === '/register')) {
      return '/'
    }
    return true
  }
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  const auth = useAuthStore()
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  if (to.meta.requiresPlatformAdmin && !auth.isPlatformAdmin) {
    return '/'
  }
  return true
})

export default router
