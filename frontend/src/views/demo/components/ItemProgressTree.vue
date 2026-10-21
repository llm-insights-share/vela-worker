<template>
  <ul class="item-progress-tree">
    <li v-for="item in items" :key="item.item_id">
      <div
        class="item-row"
        :class="{ delegated: isDelegated(item.item_id), active: store.selectedItemId === item.item_id }"
        @click.stop="$emit('select', item)"
      >
        <ItemStatusTag :status="item.status" />
        <div class="item-main">
          <span class="item-name">{{ item.name }}</span>
          <a-progress
            v-if="item.progress_pct > 0 || ['IN_PROGRESS', 'DELEGATED'].includes(item.status)"
            :percent="item.progress_pct || 0"
            :show-info="false"
            size="small"
            stroke-color="var(--brand)"
            class="item-progress"
          />
        </div>
        <span v-if="isDelegated(item.item_id)" class="delegated-tag">已委派</span>
      </div>
      <ItemProgressTree
        v-if="item.children?.length"
        :items="item.children"
        :worker-id="workerId"
        :delegated-ids="delegatedIds"
        @select="$emit('select', $event)"
      />
    </li>
  </ul>
</template>

<script setup>
import { useWorkbenchStore } from '../store/workbench'
import ItemStatusTag from './ItemStatusTag.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  workerId: { type: String, required: true },
  delegatedIds: { type: Array, default: () => [] },
})

defineEmits(['select'])
const store = useWorkbenchStore()

function isDelegated(itemId) {
  return props.delegatedIds.includes(itemId)
}
</script>

<script>
export default { name: 'ItemProgressTree' }
</script>

<style scoped>
.item-progress-tree {
  list-style: none;
  padding-left: 14px;
  margin: 4px 0;
}

.item-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 4px;
}

.item-row:hover {
  background: #f9fafb;
}

.item-row.delegated {
  background: var(--brand-light, #eef2ff);
  border-color: #e0e7ff;
}

.item-row.active {
  border-color: var(--brand, #4f46e5);
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
}

.item-progress {
  margin: 0;
}

.delegated-tag {
  font-size: 10px;
  color: var(--brand, #4f46e5);
  background: var(--brand-light, #eef2ff);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
  margin-top: 2px;
}
</style>
