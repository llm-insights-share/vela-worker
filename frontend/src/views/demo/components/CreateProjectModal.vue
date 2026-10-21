<template>
  <a-modal
    v-model:open="visible"
    title="新建项目"
    ok-text="创建"
    cancel-text="取消"
    :confirm-loading="loading"
    @ok="submit"
  >
    <a-form layout="vertical">
      <a-form-item label="项目名称" required>
        <a-input v-model:value="form.name" placeholder="请输入项目名称" />
      </a-form-item>
      <a-form-item label="项目描述">
        <a-textarea v-model:value="form.description" :rows="3" placeholder="可选" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { projectApi } from '../../../api'

const props = defineProps({
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['update:open', 'done'])
const loading = ref(false)
const form = ref({ name: '', description: '' })

const visible = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
})

watch(() => props.open, (open) => {
  if (open) form.value = { name: '', description: '' }
})

async function submit() {
  if (!form.value.name.trim()) {
    message.warning('请输入项目名称')
    return
  }
  loading.value = true
  try {
    const created = await projectApi.create({
      name: form.value.name.trim(),
      description: form.value.description.trim(),
    })
    message.success('项目已创建')
    visible.value = false
    emit('done', { project_id: created.project_id })
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>
