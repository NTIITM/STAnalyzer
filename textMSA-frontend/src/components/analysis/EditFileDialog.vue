<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('app.editFileInfo')"
    width="480px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    @close="$emit('update:modelValue', false)"
  >
    <el-form label-position="top">
      <el-form-item :label="$t('app.editFileName')">
        <el-input
          v-model="form.name"
          :placeholder="$t('app.editFileNamePlaceholder')"
        />
      </el-form-item>
      <el-form-item :label="$t('app.description')">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          :placeholder="$t('app.descriptionPlaceholder')"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" @click="handleSave" :loading="updating">
          {{ updating ? $t('app.saving') : $t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus'
import type { FileInfo } from '../../api/file'

const props = defineProps<{
  modelValue: boolean
  fileInfo?: FileInfo | null
  fileName?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'save': [name: string, description: string]
}>()

const { t } = useI18n()

const form = ref({ name: '', description: '' })
const updating = ref(false)

// 当对话框打开或文件信息变化时，更新表单
watch([() => props.modelValue, () => props.fileInfo, () => props.fileName], ([isOpen, fileInfo, fileName]) => {
  if (isOpen) {
    form.value = {
      name: fileInfo?.name || fileName || '',
      description: fileInfo?.description || ''
    }
  } else {
    form.value = { name: '', description: '' }
  }
}, { immediate: true })

function handleSave() {
  emit('save', form.value.name, form.value.description)
}

// 暴露方法供父组件调用
defineExpose({
  setUpdating: (value: boolean) => {
    updating.value = value
  },
  close: () => {
    emit('update:modelValue', false)
  }
})
</script>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
