<template>
  <Teleport to="body">
    <div v-if="model" class="cookie-overlay">
      <div class="cookie-banner">
        <div class="cookie-content">
          <div class="cookie-info">
            <el-icon :size="50" class="cookie-icon">
              <Food />
            </el-icon>
            <div class="cookie-text">
              <h3>{{ $t('auth.cookieDialog.title') }}</h3>
              <p>{{ $t('auth.cookieDialog.description') }}</p>
            </div>
          </div>

          <el-alert
            v-if="error"
            :title="error"
            type="error"
            :closable="false"
            show-icon
            class="error-alert"
          />

          <div class="cookie-actions">
            <el-button @click="handleClose" :disabled="loading" class="btn-cancel">
              {{ $t('auth.cookieDialog.cancel') }}
            </el-button>
            <el-button
              type="primary"
              @click="handleConfirm"
              :loading="loading"
              class="btn-accept"
            >
              {{ $t('auth.cookieDialog.accept') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElButton, ElDialog, ElAlert, ElIcon } from 'element-plus'
import { Food } from '@element-plus/icons-vue'
import { loginWithCookie } from '../../api/user'
import { useAuthStore } from '../../stores/authStore'
import { useUserStore } from '../../stores/userStore'

// const props = defineProps<{
//   modelValue: boolean
// }>()

const model = defineModel<boolean>()

const emit = defineEmits<{
  'confirm': [token: string]
}>()

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const userStore = useUserStore()

const loading = ref(false)
const error = ref<string | null>(null)

watch(model, (visible) => {
  if (visible) {
    resetState()
  }
})

function resetState() {
  loading.value = false
  error.value = null
}

function handleClose() {
  if (loading.value) {
    return
  }
  if (!authStore.checkAuth()) {
    router.push('/help')
  }
  model.value = false
}

async function handleConfirm() {
  error.value = null
  loading.value = true

  try {
    const data = await loginWithCookie()
    const token = data.token

    try {
      await userStore.fetchProfile()
    } catch (err) {
      console.warn('获取用户信息失败:', err)
    }

    emit('confirm', token)
    model.value = false
  } catch (err: any) {
    if (err?.status === 401 || err?.code === 401) {
      error.value = t('auth.cookieDialog.error.invalidCookie')
    } else if (err?.message) {
      error.value = err.message
    } else {
      error.value = t('auth.cookieDialog.error.networkError')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cookie-overlay {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 9999;
}

.cookie-banner {
  background: linear-gradient(135deg, #5c867e 0%);
  padding: 36px 24px;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
}

.cookie-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.cookie-info {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 280px;
}

.cookie-icon {
  color: #fcd34d;
  flex-shrink: 0;
}

.cookie-text {
  color: #ffffff;
}

.cookie-text h3 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 600;
}

.cookie-text p {
  margin: 0;
  font-size: 18px;
  line-height: 1.5;
  opacity: 0.9;
}

.error-alert {
  position: absolute;
  top: -60px;
  left: 50%;
  transform: translateX(-50%);
  min-width: 300px;
}

.cookie-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.btn-cancel {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: #ffffff;
  padding: 8px 24px;
  border-radius: 6px;
  font-size: 18px;
  transition: all 0.3s ease;
}

.btn-cancel:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.4);
  color: #b00e0e;
  font-weight: bold;
  font-size: 20px;
}

.btn-accept {
  background: #fcd34d;
  border-color: #fcd34d;
  color: #1f2937;
  padding: 8px 24px;
  border-radius: 6px;
  font-size: 18px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.btn-accept:hover {
  background: #fbbf24;
  border-color: #fbbf24;
  color: #064a05;
  font-weight: bold;
  font-size: 20px;
}

@media (max-width: 768px) {
  .cookie-content {
    flex-direction: column;
    text-align: center;
  }

  .cookie-info {
    justify-content: center;
  }

  .error-alert {
    position: static;
    transform: none;
    margin-bottom: 16px;
    min-width: auto;
  }
}
</style>