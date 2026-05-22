<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('app.confirmDelete')"
    width="420px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    @close="$emit('update:modelValue', false)"
  >
    <p>{{ $t('app.confirmDeleteText', { name: fileName || $t('file.defaultName') }) }}</p>
    <p class="warning-text">{{ $t('app.confirmDeleteWarning') }}</p>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="danger" @click="handleDelete" :loading="deleting">
          {{ deleting ? $t('app.deleting') : $t('app.confirmDeleteAction') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog } from 'element-plus'

defineProps<{
  modelValue: boolean
  fileName?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'confirm': []
}>()

const deleting = ref(false)

function handleDelete() {
  emit('confirm')
}

// 暴露方法供父组件调用
defineExpose({
  setDeleting: (value: boolean) => {
    deleting.value = value
  },
  close: () => {
    emit('update:modelValue', false)
  }
})
</script>

<style scoped>
.modal-body p {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
}

.warning-text {
  color: #ff4d4f;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  margin-top: var(--spacing-md);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
