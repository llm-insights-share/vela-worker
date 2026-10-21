<template>
  <a-modal
    v-model:open="visible"
    title="委派给数字员工"
    ok-text="确认委派"
    cancel-text="取消"
    :confirm-loading="loading"
    @ok="submit"
  >
    <a-form layout="vertical">
      <a-form-item label="数字员工" required>
        <a-select
          v-model:value="form.worker_id"
          placeholder="选择数字员工"
          :options="workerOptions"
        />
      </a-form-item>
      <a-form-item label="事项">
        <a-input :value="item?.name || project?.name" disabled />
      </a-form-item>
      <a-form-item label="指令" required>
        <a-textarea v-model:value="form.instruction" :rows="4" placeholder="描述需要数字员工完成的任务…" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { projectApi } from '../../../api'
import { useWorkbenchStore } from '../store/workbench'

const props = defineProps({
  open: { type: Boolean, default: false },
  item: { type: Object, default: null },
  project: { type: Object, default: null },
})

const emit = defineEmits(['update:open', 'done'])
const store = useWorkbenchStore()
const loading = ref(false)
const form = ref({ worker_id: undefined, instruction: '' })

const visible = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
})

const workerOptions = computed(() =>
  store.workers.map((w) => ({ value: w.worker_id, label: w.name }))
)

const targetItemId = computed(() => props.item?.item_id)

watch(() => props.open, (open) => {
  if (open) {
    form.value = {
      worker_id: store.selectedWorkerId || store.workers[0]?.worker_id,
      instruction: props.item?.description || `请处理事项：${props.item?.name || props.project?.name || ''}`,
    }
  }
})

async function submit() {
  if (!targetItemId.value) {
    message.warning('请先选择具体事项')
    return
  }
  if (!form.value.worker_id || !form.value.instruction.trim()) {
    message.warning('请填写完整信息')
    return
  }
  loading.value = true
  try {
    await projectApi.delegate(targetItemId.value, {
      worker_id: form.value.worker_id,
      instruction: form.value.instruction.trim(),
      auto_start: false,
    })
    message.success('已委派，请在事项详情中确认启动')
    visible.value = false
    emit('done')
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>
