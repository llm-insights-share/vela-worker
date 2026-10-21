<template>
  <div class="auth-backdrop" @click.self="$emit('close')">
    <div class="auth-card">
      <div class="auth-hd">
        <div class="auth-icon">!</div>
        <div>
          <h2>操作授权审核</h2>
          <p>数字员工请求执行高风险操作</p>
        </div>
      </div>

      <div class="auth-body">
        <section class="block">
          <h3>操作概要</h3>
          <div class="summary-grid">
            <div>
              <div class="label">操作</div>
              <div class="value">{{ operationTitle }}</div>
            </div>
            <div>
              <div class="label">发起方</div>
              <div class="value">{{ approval.worker_name || '数字员工' }}</div>
            </div>
            <div>
              <div class="label">所属项目</div>
              <div class="value">
                {{ approval.project_name || '—' }}
                <template v-if="approval.item_name"> › {{ approval.item_name }}</template>
              </div>
            </div>
            <div>
              <div class="label">风险</div>
              <div class="value"><span class="risk-pill">高风险</span></div>
            </div>
          </div>
        </section>

        <section class="block">
          <h3>风险评估</h3>
          <p class="risk-text">
            {{ riskText }}
          </p>
          <div class="risk-tags">
            <span v-for="t in riskTags" :key="t" class="risk-tag">{{ t }}</span>
          </div>
        </section>

        <section v-if="execSteps.length" class="block">
          <h3>执行步骤预览</h3>
          <div class="step-list">
            <div v-for="(s, i) in execSteps" :key="i" class="step-row">
              <div class="step-num">{{ i + 1 }}</div>
              <div class="step-text">{{ s.title || s }}</div>
              <div v-if="s.eta" class="step-eta">{{ s.eta }}</div>
            </div>
          </div>
        </section>

        <section v-if="previewRows.length" class="block">
          <h3>数据预览</h3>
          <div class="preview-hint">共 {{ previewTotal }} 条 · 显示前 {{ previewRows.length }} 条</div>
          <a-table
            :data-source="previewRows"
            :columns="previewColumns"
            :pagination="false"
            size="small"
            row-key="name"
          />
        </section>
      </div>

      <div class="auth-footer">
        <div class="footer-hint">授权后将记录审计日志</div>
        <div class="footer-actions">
          <a-button danger :loading="loading" @click="submit(false)">拒绝</a-button>
          <a-button type="primary" :loading="loading" @click="submit(true)">授权执行</a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { convApi } from '../../../api'

const props = defineProps({
  approval: { type: Object, required: true },
})

const emit = defineEmits(['close', 'done'])
const loading = ref(false)

const content = computed(() => props.approval.content || props.approval)

const operationTitle = computed(() =>
  content.value.tool_name || content.value.text || props.approval.title || '批量数据操作'
)

const riskText = computed(() =>
  content.value.risk_text ||
  '此操作可能直接修改业务系统数据。执行前请确认数据正确性，操作完成后可能无法自动回滚。'
)

const riskTags = computed(() => {
  if (Array.isArray(content.value.risk_tags) && content.value.risk_tags.length) {
    return content.value.risk_tags
  }
  return ['批量数据写入', '直接操作系统', '敏感数据']
})

const execSteps = computed(() => {
  const steps = content.value.exec_steps || content.value.tool_args?.exec_steps || []
  return Array.isArray(steps) ? steps : []
})

const previewRows = computed(() => {
  const args = content.value.tool_args || {}
  if (Array.isArray(args.preview_rows)) return args.preview_rows.slice(0, 5)
  if (Array.isArray(args.rows)) return args.rows.slice(0, 5)
  return []
})

const previewTotal = computed(() => {
  const args = content.value.tool_args || {}
  return args.total || args.count || previewRows.value.length
})

const previewColumns = computed(() => {
  const row = previewRows.value[0]
  if (!row) return [
    { title: '字段', dataIndex: 'name', key: 'name' },
    { title: '值', dataIndex: 'value', key: 'value' },
  ]
  if (row.value !== undefined && row.name !== undefined) {
    return [
      { title: '字段', dataIndex: 'name', key: 'name' },
      { title: '值', dataIndex: 'value', key: 'value' },
    ]
  }
  return Object.keys(row).map((k) => ({ title: k, dataIndex: k, key: k }))
})

async function submit(approved) {
  loading.value = true
  try {
    await convApi.approval(props.approval.msg_id, {
      approved,
      comment: approved ? '已授权' : '已拒绝',
    })
    message.success(approved ? '已授权执行' : '已拒绝')
    emit('done')
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.auth-card {
  width: min(720px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  background: var(--surface, #fff);
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.2);
}

.auth-hd {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 22px 24px 16px;
  border-bottom: 1px solid var(--line, #e2e8f0);
}

.auth-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--state-warning-light, #fffbeb);
  color: var(--state-warning, #d97706);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
  flex-shrink: 0;
}

.auth-hd h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.auth-hd p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-2, #475569);
}

.auth-body {
  padding: 8px 24px 16px;
}

.block {
  padding: 14px 0;
  border-bottom: 1px solid var(--line, #e2e8f0);
}

.block:last-child {
  border-bottom: none;
}

.block h3 {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink, #0f172a);
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 20px;
}

.label {
  font-size: 11px;
  color: var(--ink-3, #94a3b8);
  margin-bottom: 2px;
}

.value {
  font-size: 13px;
  color: var(--ink, #0f172a);
  font-weight: 500;
}

.risk-pill {
  display: inline-block;
  background: var(--state-error-light, #fef2f2);
  color: var(--state-error, #dc2626);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.risk-text {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--ink-2, #475569);
  line-height: 1.55;
  background: var(--state-warning-light, #fffbeb);
  border-radius: 8px;
  padding: 10px 12px;
}

.risk-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.risk-tag {
  font-size: 12px;
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
  padding: 4px 10px;
  border-radius: 999px;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--surface-2, #f1f5f9);
  border-radius: 8px;
}

.step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-text {
  flex: 1;
  font-size: 13px;
}

.step-eta {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.preview-hint {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-bottom: 8px;
}

.auth-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--line, #e2e8f0);
}

.footer-hint {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
}

.footer-actions {
  display: flex;
  gap: 8px;
}
</style>
