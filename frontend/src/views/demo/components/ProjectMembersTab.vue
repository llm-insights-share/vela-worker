<template>
  <div class="members-tab">
    <div v-if="!members.length" class="empty-hint">暂无成员</div>
    <div v-for="m in members" :key="m.key" class="member-card">
      <div class="avatar" :class="{ ai: m.is_worker, soft: m.is_worker && m.tag === '已参与' }">
        <RobotOutlined v-if="m.is_worker" />
        <template v-else>{{ (m.name || '?').slice(0, 1) }}</template>
      </div>
      <div class="info">
        <div class="name-row">
          <span class="name">{{ m.name }}</span>
          <span v-if="m.is_worker" class="ai-pill">AI</span>
        </div>
        <div class="sub">{{ m.subtitle || m.role }}</div>
      </div>
      <span class="tag" :class="tagClass(m)">{{ m.tag }}</span>
    </div>
  </div>
</template>

<script setup>
import { RobotOutlined } from '@ant-design/icons-vue'

defineProps({
  members: { type: Array, default: () => [] },
})

function tagClass(m) {
  if (!m.is_worker) return 'tag-owner'
  if (m.tag === '执行中' || m.activity === 'working') return 'tag-working'
  return 'tag-joined'
}
</script>

<style scoped>
.members-tab {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.member-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 12px;
  background: var(--surface, #fff);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--brand, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
}

.avatar.ai {
  font-size: 18px;
}

.avatar.soft {
  background: #94a3b8;
}

.info {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.name {
  font-size: 14px;
  font-weight: 650;
  color: var(--ink, #0f172a);
}

.ai-pill {
  font-size: 10px;
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
}

.sub {
  font-size: 12px;
  color: var(--ink-3, #94a3b8);
  margin-top: 2px;
}

.tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 500;
  white-space: nowrap;
}

.tag-owner {
  background: var(--brand-light, #eef2ff);
  color: var(--brand, #4f46e5);
}

.tag-working {
  background: #eff6ff;
  color: #2563eb;
}

.tag-joined {
  background: var(--surface-2, #f1f5f9);
  color: var(--ink-2, #475569);
}

.empty-hint {
  font-size: 13px;
  color: var(--ink-3, #94a3b8);
  padding: 12px 0;
}
</style>
