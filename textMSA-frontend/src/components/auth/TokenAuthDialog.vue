<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('auth.tokenDialog.title')"
    width="520px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    @close="handleClose"
  >
    <div class="token-dialog-content">
      <!-- 模式选择 -->
      <div class="mode-selection">
        <el-radio-group v-model="mode" @change="handleModeChange">
          <el-radio label="input" class="mode-radio">
            {{ $t('auth.tokenDialog.hasToken') }}
          </el-radio>
          <el-radio label="create" class="mode-radio">
            {{ $t('auth.tokenDialog.createToken') }}
          </el-radio>
        </el-radio-group>
      </div>

      <!-- 输入模式 -->
      <div v-if="mode === 'input'" class="input-mode">
        <el-form-item :label="$t('auth.tokenDialog.inputPlaceholder')">
          <el-input
            v-model="inputToken"
            type="textarea"
            :rows="3"
            :placeholder="$t('auth.tokenDialog.inputPlaceholder')"
            :disabled="loading"
            @keydown.enter.prevent
          />
        </el-form-item>
      </div>

      <!-- 创建模式 -->
      <div v-if="mode === 'create'" class="create-mode">
        <el-form-item :label="$t('auth.tokenDialog.newTokenLabel')">
          <div class="token-display">
            <el-input
              v-model="newToken"
              type="textarea"
              :rows="3"
              readonly
              class="token-input-readonly"
            />
            <el-button
              type="primary"
              :icon="copied ? Check : DocumentCopy"
              @click="handleCopyToken"
              :disabled="!newToken || loading"
            >
              {{ copied ? $t('auth.tokenDialog.copied') : $t('auth.tokenDialog.copyButton') }}
            </el-button>
          </div>
        </el-form-item>
      </div>

      <!-- 错误提示 -->
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        show-icon
        class="error-alert"
      />

      <!-- 警告提示 -->
      <el-alert
        :title="$t('auth.tokenDialog.warning')"
        type="warning"
        :closable="false"
        show-icon
        class="warning-alert"
      />
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose" :disabled="loading">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          @click="handleConfirm"
          :loading="loading"
          :disabled="mode === 'input' && !inputToken.trim()"
        >
          {{ $t('auth.tokenDialog.confirm') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog, ElFormItem, ElInput, ElRadioGroup, ElRadio, ElAlert } from 'element-plus'
import { DocumentCopy, Check } from '@element-plus/icons-vue'
import { generateToken } from '../../utils/tokenGenerator'
import { login } from '../../api/user'
import { useAuthStore } from '../../stores/authStore'
import { useUserStore } from '../../stores/userStore'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'confirm': [token: string]
}>()

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const userStore = useUserStore()

const mode = ref<'input' | 'create'>('input')
const inputToken = ref('')
const newToken = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const copied = ref(false)

// 监听弹窗显示，重置状态
watch(() => props.modelValue, (visible) => {
  if (visible) {
    resetState()
  }
})

function resetState() {
  mode.value = 'input'
  inputToken.value = ''
  newToken.value = null
  loading.value = false
  error.value = null
  copied.value = false
}

function handleModeChange() {
  error.value = null
  copied.value = false
  
  // 切换到创建模式时，立即生成 token
  if (mode.value === 'create' && !newToken.value) {
    newToken.value = generateToken()
  }
}

function handleClose() {
  // 如果正在加载，不允许关闭
  if (loading.value) {
    return
  }
  // 关闭弹窗时，如果没有 token，重定向到 HelpPage
  if (!authStore.checkAuth()) {
    router.push('/help')
  }
  emit('update:modelValue', false)
}

async function handleConfirm() {
  error.value = null
  loading.value = true

  try {
    let tokenToUse: string

    if (mode.value === 'input') {
      // 输入模式：使用用户输入的 token
      tokenToUse = inputToken.value.trim()
      if (!tokenToUse) {
        error.value = t('auth.tokenDialog.error.invalidToken')
        loading.value = false
        return
      }
    } else {
      // 创建模式：使用生成的 token
      if (!newToken.value) {
        newToken.value = generateToken()
      }
      tokenToUse = newToken.value
    }

    // 调用登录 API
    await login({ token: tokenToUse })

    // 保存 token 到 store
    authStore.setToken(tokenToUse)

    // 获取用户信息
    try {
      await userStore.fetchProfile()
    } catch (err) {
      // 获取用户信息失败不影响登录
      console.warn('获取用户信息失败:', err)
    }

    // 触发确认事件
    emit('confirm', tokenToUse)
    emit('update:modelValue', false)
  } catch (err: any) {
    // 处理错误
    if (err?.status === 401 || err?.code === 401) {
      error.value = t('auth.tokenDialog.error.invalidToken')
    } else if (err?.message) {
      error.value = err.message
    } else {
      error.value = t('auth.tokenDialog.error.networkError')
    }
  } finally {
    loading.value = false
  }
}

async function handleCopyToken() {
  if (!newToken.value) {
    return
  }

  try {
    await navigator.clipboard.writeText(newToken.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    // 降级方案：使用传统方法
    const textarea = document.createElement('textarea')
    textarea.value = newToken.value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      copied.value = true
      setTimeout(() => {
        copied.value = false
      }, 2000)
    } catch (e) {
      error.value = t('auth.tokenDialog.error.copyFailed')
    } finally {
      document.body.removeChild(textarea)
    }
  }
}
</script>

<style scoped>
.token-dialog-content {
  padding: 8px 0;
}

.mode-selection {
  margin-bottom: 20px;
}

.mode-radio {
  display: block;
  margin-bottom: 12px;
  margin-right: 0;
}

.mode-radio:last-child {
  margin-bottom: 0;
}

.input-mode,
.create-mode {
  margin-bottom: 16px;
}

.token-display {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.token-input-readonly {
  flex: 1;
}

.token-input-readonly :deep(.el-textarea__inner) {
  background-color: #f5f7fa;
  cursor: default;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.error-alert {
  margin-bottom: 16px;
}

.warning-alert {
  margin-top: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

