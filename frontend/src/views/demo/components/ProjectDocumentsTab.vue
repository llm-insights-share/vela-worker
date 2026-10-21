<template>
  <div class="docs-tab">
    <div class="docs-toolbar">
      <input ref="fileInput" type="file" class="hidden-file" @change="onFileChange" />
      <a-button size="small" :loading="uploading" @click="triggerUpload">
        <UploadOutlined />
        上传文档
      </a-button>
    </div>

    <div v-if="!documents.length" class="empty-hint">暂无项目资料</div>
    <table v-else class="docs-table">
      <thead>
        <tr>
          <th>文档名称</th>
          <th>所有者</th>
          <th>修改时间</th>
          <th>来源</th>
          <th>大小</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in documents" :key="doc.doc_id">
          <td class="name-cell">
            <span class="file-icon" :class="extClass(doc.name)">{{ extLabel(doc.name) }}</span>
            <span class="file-name">{{ doc.name }}</span>
          </td>
          <td>
            <div class="owner">
              <span class="owner-avatar" :class="{ ai: doc.owner_type === 'WORKER' }">
                <RobotOutlined v-if="doc.owner_type === 'WORKER'" />
                <template v-else>{{ (doc.owner_name || '?').slice(0, 1) }}</template>
              </span>
              {{ doc.owner_name || '—' }}
            </div>
          </td>
          <td>{{ formatTime(doc.updated_at || doc.created_at) }}</td>
          <td>
            <span class="src" :class="doc.source === 'AI_GENERATED' ? 'ai' : 'upload'">
              {{ doc.source === 'AI_GENERATED' ? 'AI 生成' : '手动上传' }}
            </span>
          </td>
          <td>{{ formatSize(doc.size_bytes) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RobotOutlined, UploadOutlined } from '@ant-design/icons-vue'

defineProps({
  documents: { type: Array, default: () => [] },
  uploading: { type: Boolean, default: false },
})

const emit = defineEmits(['upload'])
const fileInput = ref(null)

function triggerUpload() {
  fileInput.value?.click()
}

function onFileChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (file) emit('upload', file)
}

function extOf(name) {
  const m = String(name || '').match(/\.([a-z0-9]+)$/i)
  return (m?.[1] || '').toLowerCase()
}

function extLabel(name) {
  const e = extOf(name)
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'X'
  if (e === 'pdf') return 'P'
  if (['doc', 'docx'].includes(e)) return 'W'
  if (['ppt', 'pptx'].includes(e)) return 'P'
  return 'F'
}

function extClass(name) {
  const e = extOf(name)
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'xls'
  if (e === 'pdf') return 'pdf'
  if (['doc', 'docx'].includes(e)) return 'doc'
  if (['ppt', 'pptx'].includes(e)) return 'ppt'
  return 'file'
}

function parseUtc(ts) {
  if (!ts) return null
  const s = String(ts)
  const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function formatTime(ts) {
  const d = parseUtc(ts)
  if (!d) return '—'
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diff = Math.round((today.getTime() - day.getTime()) / 86400000)
  const hm = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
  if (diff === 0) return `今天 ${hm}`
  if (diff === 1) return `昨天 ${hm}`
  if (diff === 2) return `前天 ${hm}`
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${hm}`
}

function formatSize(bytes) {
  const n = Number(bytes) || 0
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`
  if (n >= 1024) return `${Math.round(n / 1024)} KB`
  return `${n} B`
}
</script>

<style scoped>
.docs-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.hidden-file {
  display: none;
}

.docs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.docs-table th {
  text-align: left;
  font-weight: 500;
  color: var(--ink-3, #94a3b8);
  padding: 0 12px 10px 0;
  border-bottom: 1px solid var(--line, #e2e8f0);
}

.docs-table td {
  padding: 12px 12px 12px 0;
  border-bottom: 1px solid var(--line, #e2e8f0);
  color: var(--ink-2, #475569);
  vertical-align: middle;
}

.docs-table tr:last-child td {
  border-bottom: none;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink, #0f172a);
  font-weight: 500;
}

.file-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.file-icon.xls { background: #2563eb; }
.file-icon.pdf { background: #16a34a; }
.file-icon.doc { background: #ea580c; }
.file-icon.ppt { background: #7c3aed; }
.file-icon.file { background: #64748b; }

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.owner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.owner-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}

.owner-avatar.ai {
  background: var(--brand, #4f46e5);
  font-size: 12px;
}

.src {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 500;
}

.src.upload {
  background: #eff6ff;
  color: #2563eb;
}

.src.ai {
  background: var(--state-success-light, #f0fdf4);
  color: var(--state-success, #16a34a);
}

.empty-hint {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  padding: 12px 0;
}
</style>
