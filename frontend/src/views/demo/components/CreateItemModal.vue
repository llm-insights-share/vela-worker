<template>
  <a-modal
    v-model:open="visible"
    title="新建事项"
    ok-text="创建并委派"
    cancel-text="取消"
    :confirm-loading="loading"
    @ok="submit"
  >
    <a-form layout="vertical">
      <a-form-item label="事项名称" required>
        <a-input v-model:value="form.name" placeholder="请输入事项名称" />
      </a-form-item>
      <a-form-item label="事项描述">
        <a-textarea v-model:value="form.description" :rows="2" placeholder="可选" />
      </a-form-item>
      <a-form-item label="处理人（数字员工）" required>
        <a-select
          v-model:value="form.worker_id"
          placeholder="选择数字员工"
          :options="workerOptions"
        />
      </a-form-item>
      <a-form-item label="执行指令" required>
        <a-textarea
          v-model:value="form.instruction"
          :rows="4"
          placeholder="描述需要数字员工完成的任务…"
        />
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
  projectId: { type: String, default: '' },
})

const emit = defineEmits(['update:open', 'done'])
const store = useWorkbenchStore()
const loading = ref(false)
const form = ref({ name: '', description: '', worker_id: undefined, instruction: '' })

const visible = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
})

const workerOptions = computed(() =>
  store.workers.map((w) => ({ value: w.worker_id, label: w.name }))
)

watch(() => props.open, (open) => {
  if (open) {
    form.value = {
      name: '',
      description: '',
      worker_id: store.selectedWorkerId || store.workers[0]?.worker_id,
      instruction: '',
    }
  }
})

async function submit() {
  if (!props.projectId) {
    message.warning('请先选择项目')
    return
  }
  if (!form.value.name.trim()) {
    message.warning('请输入事项名称')
    return
  }
  if (!form.value.worker_id) {
    message.warning('请选择处理人')
    return
  }
  if (!form.value.instruction.trim()) {
    message.warning('请填写执行指令')
    return
  }
  loading.value = true
  try {
    const item = await projectApi.createItem(props.projectId, {
      name: form.value.name.trim(),
      description: form.value.description.trim(),
    })
    await projectApi.delegate(item.item_id, {
      worker_id: form.value.worker_id,
      instruction: form.value.instruction.trim(),
      auto_start: false,
    })
    message.success('事项已创建并委派，请确认启动')
    visible.value = false
    emit('done', {
      project_id: props.projectId,
      item_id: item.item_id,
      worker_id: form.value.worker_id,
    })
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>
