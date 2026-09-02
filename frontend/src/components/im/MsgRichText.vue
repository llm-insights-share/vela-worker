<template>
  <div v-if="resolved === 'txt'" class="msg-rich msg-rich--txt">{{ displayText }}</div>
  <div v-else class="msg-rich msg-rich--md" v-html="safeHtml"></div>
</template>

<script setup>
import { computed } from 'vue'
import { resolveFormat, renderMessageHtml } from '../../utils/msgFormat'

const props = defineProps({
  text: { type: String, default: '' },
  format: { type: String, default: '' },
})

const displayText = computed(() => props.text ?? '')

const resolved = computed(() =>
  resolveFormat({ text: props.text, format: props.format || undefined })
)

const safeHtml = computed(() => {
  if (resolved.value === 'txt') return ''
  return renderMessageHtml(props.text, resolved.value)
})
</script>
