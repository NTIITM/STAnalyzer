<template>
  <div class="user-profile-page">
    <header class="page-header">
      <div>
        <p class="page-subtitle">{{ t('profile.subtitle') }}</p>
        <h1 class="page-title">{{ t('profile.title') }}</h1>
        <p class="page-description">{{ t('profile.description') }}</p>
      </div>
      <button class="ghost-button" type="button" @click="refreshProfile" :disabled="userStore.loadingProfile">
        <Icon name="refresh" size="md" />
        <span>{{ userStore.loadingProfile ? t('profile.actions.refreshing') : t('profile.actions.refresh') }}</span>
      </button>
    </header>

    <main class="profile-grid">
      <section class="card profile-summary">
        <div class="card-header">
          <div class="card-title-wrap">
            <Icon name="user" size="lg" class="title-icon" />
            <div>
              <p class="card-eyebrow">{{ t('profile.summary.title') }}</p>
              <h2 class="card-title">{{ displayName }}</h2>
            </div>
          </div>
          <span class="status-chip" :class="{ 'status-loading': userStore.loadingProfile }">
            {{ userStore.loadingProfile ? t('profile.summary.loading') : t('profile.summary.ready') }}
          </span>
        </div>
        <div class="summary-body" v-if="userStore.profile">
          <div class="summary-field">
            <span class="field-label">{{ t('profile.summary.userId') }}</span>
            <span class="field-value mono">{{ userStore.profile.userId }}</span>
          </div>
          <div class="summary-field">
            <span class="field-label">{{ t('profile.summary.username') }}</span>
            <span class="field-value">{{ userStore.profile.username }}</span>
          </div>
          <div class="summary-field">
            <span class="field-label">{{ t('profile.summary.email') }}</span>
            <span class="field-value">{{ userStore.profile.email || t('profile.summary.emailEmpty') }}</span>
          </div>
          <div class="summary-field">
            <span class="field-label">{{ t('profile.summary.cachedAt') }}</span>
            <span class="field-value">{{ cachedAt }}</span>
          </div>
        </div>
        <div class="summary-placeholder" v-else>
          <p>{{ t('profile.summary.placeholder') }}</p>
          <button class="ghost-button" type="button" @click="refreshProfile">
            {{ t('profile.actions.loadProfile') }}
          </button>
        </div>
      </section>

      <section class="card profile-form-card">
        <div class="card-header">
          <div>
            <p class="card-eyebrow">{{ t('profile.form.title') }}</p>
            <h2 class="card-title">{{ t('profile.form.subtitle') }}</h2>
          </div>
          <span class="hint">{{ t('profile.form.hint') }}</span>
        </div>
        <form class="card-form" @submit.prevent="handleProfileSave">
          <label class="form-field">
            <span class="field-label">{{ t('profile.form.username') }}</span>
            <input
              v-model.trim="profileForm.username"
              class="text-input"
              type="text"
              name="username"
              maxlength="50"
              autocomplete="username"
              :placeholder="t('profile.form.usernamePlaceholder')"
            />
          </label>

          <label class="form-field">
            <span class="field-label">{{ t('profile.form.email') }}</span>
            <input
              v-model.trim="profileForm.email"
              class="text-input"
              type="email"
              name="email"
              maxlength="100"
              autocomplete="email"
              :placeholder="t('profile.form.emailPlaceholder')"
            />
          </label>

          <div class="form-actions">
            <span class="form-hint">{{ t('profile.form.disclaimer') }}</span>
            <button
              class="primary-button"
              type="submit"
              :disabled="!profileDirty || userStore.savingProfile"
            >
              {{ userStore.savingProfile ? t('profile.actions.saving') : t('profile.actions.saveProfile') }}
            </button>
          </div>
        </form>
      </section>

      <section class="card security-card">
        <div class="card-header">
          <div>
            <p class="card-eyebrow">{{ t('profile.security.title') }}</p>
            <h2 class="card-title">{{ t('profile.security.subtitle') }}</h2>
          </div>
          <span class="hint">{{ t('profile.security.hint') }}</span>
        </div>
        <form class="card-form" @submit.prevent="handlePasswordChange">
          <label class="form-field">
            <span class="field-label">{{ t('profile.security.currentPassword') }}</span>
            <input
              v-model.trim="passwordForm.currentPassword"
              class="text-input"
              type="password"
              name="currentPassword"
              autocomplete="current-password"
              minlength="6"
              required
            />
          </label>
          <label class="form-field">
            <span class="field-label">{{ t('profile.security.newPassword') }}</span>
            <input
              v-model.trim="passwordForm.newPassword"
              class="text-input"
              type="password"
              name="newPassword"
              autocomplete="new-password"
              minlength="6"
              required
            />
          </label>
          <label class="form-field">
            <span class="field-label">{{ t('profile.security.confirmPassword') }}</span>
            <input
              v-model.trim="passwordForm.confirmPassword"
              class="text-input"
              type="password"
              name="confirmPassword"
              autocomplete="new-password"
              minlength="6"
              required
            />
          </label>

          <p v-if="passwordError" class="form-error">{{ passwordError }}</p>

          <div class="form-actions">
            <span class="form-hint">{{ t('profile.security.disclaimer') }}</span>
            <button
              class="secondary-button"
              type="submit"
              :disabled="userStore.changingPassword"
            >
              {{ userStore.changingPassword ? t('profile.actions.updatingPassword') : t('profile.actions.updatePassword') }}
            </button>
          </div>
        </form>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import { useUserStore } from '../../stores/userStore'
import type { UpdateProfileParams } from '../../api/user'

const { t } = useI18n()
const userStore = useUserStore()

const profileForm = ref({
  username: '',
  email: ''
})

const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const passwordError = ref('')
const cachedAt = ref<string>('')

const displayName = computed(() => userStore.displayName)

const profileDirty = computed(() => {
  if (!userStore.profile) return false
  return (
    profileForm.value.username !== (userStore.profile.username || '') ||
    (profileForm.value.email || '') !== (userStore.profile.email || '')
  )
})

function syncForm() {
  if (!userStore.profile) {
    cachedAt.value = ''
    return
  }
  profileForm.value.username = userStore.profile.username || ''
  profileForm.value.email = userStore.profile.email || ''
  cachedAt.value = new Date().toLocaleString()
}

async function refreshProfile() {
  try {
    await userStore.fetchProfile(true)
    syncForm()
    showToast('success', t('profile.messages.profileLoaded'))
  } catch (error: any) {
    showToast('error', error?.message || t('profile.messages.profileLoadFailed'))
  }
}

async function handleProfileSave() {
  if (!profileDirty.value) {
    showToast('info', t('profile.messages.noChanges'))
    return
  }

  const payload: UpdateProfileParams = {}
  if (profileForm.value.username !== userStore.profile?.username) {
    payload.username = profileForm.value.username
  }
  if ((profileForm.value.email || '') !== (userStore.profile?.email || '')) {
    payload.email = profileForm.value.email
  }

  try {
    await userStore.saveProfile(payload)
    showToast('success', t('profile.messages.profileUpdated'))
  } catch (error: any) {
    showToast('error', error?.message || t('profile.messages.profileFailed'))
  }
}

async function handlePasswordChange() {
  passwordError.value = ''

  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    passwordError.value = t('profile.messages.passwordNotMatch')
    return
  }

  try {
    await userStore.updatePassword({
      currentPassword: passwordForm.value.currentPassword,
      newPassword: passwordForm.value.newPassword
    })
    passwordForm.value.currentPassword = ''
    passwordForm.value.newPassword = ''
    passwordForm.value.confirmPassword = ''
    showToast('success', t('profile.messages.passwordUpdated'))
  } catch (error: any) {
    passwordError.value = error?.message || t('profile.messages.passwordFailed')
    showToast('error', passwordError.value)
  }
}

function showToast(type: 'success' | 'error' | 'info' | 'warning', message: string) {
  const showMessage = (window as any).showMessage
  if (showMessage && typeof showMessage[type] === 'function') {
    showMessage[type](message)
  } else {
    console[type === 'error' ? 'error' : 'log'](message)
  }
}

watch(
  () => userStore.profile,
  () => {
    syncForm()
  },
  { immediate: true }
)

onMounted(() => {
  if (!userStore.profile) {
    refreshProfile()
  } else {
    syncForm()
  }
})
</script>

<style scoped>
.user-profile-page {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 2rem clamp(1.5rem, 5vw, 3rem);
  background: var(--bg-secondary);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.page-subtitle {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.75rem;
  color: var(--text-tertiary);
  margin-bottom: 0.35rem;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.page-description {
  color: var(--text-secondary);
  max-width: 640px;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  align-items: stretch;
}

.card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.card-title-wrap {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.card-eyebrow {
  text-transform: uppercase;
  font-size: 0.75rem;
  color: var(--text-tertiary);
  letter-spacing: 0.08em;
  margin-bottom: 0.25rem;
}

.card-title {
  font-size: 1.15rem;
  font-weight: 600;
}

.title-icon {
  color: var(--accent-primary);
}

.status-chip {
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.status-loading {
  animation: pulse 1.5s infinite;
}

.summary-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.summary-field {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.field-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.field-value {
  font-weight: 500;
  color: var(--text-primary);
}

.field-value.mono {
  font-family: 'JetBrains Mono', 'Fira Mono', monospace;
  font-size: 0.9rem;
}

.summary-placeholder {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  color: var(--text-secondary);
}

.hint {
  font-size: 0.8rem;
  color: var(--text-tertiary);
}

.card-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.text-input {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 0.75rem 1rem;
  font-size: 0.95rem;
  color: var(--text-primary);
  background: var(--bg-primary);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.text-input:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.form-hint {
  font-size: 0.85rem;
  color: var(--text-tertiary);
}

.form-error {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.08);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.85rem;
}

.primary-button,
.secondary-button,
.ghost-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  border-radius: 999px;
  padding: 0.65rem 1.5rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.primary-button {
  background: var(--accent-primary);
  color: #fff;
}

.primary-button:disabled,
.secondary-button:disabled,
.ghost-button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.primary-button:not(:disabled):hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.secondary-button {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.secondary-button:not(:disabled):hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.ghost-button {
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
}

.ghost-button:not(:disabled):hover {
  color: var(--text-primary);
}

@keyframes pulse {
  0% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.6;
  }
}

@media (max-width: 768px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .form-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .primary-button,
  .secondary-button {
    width: 100%;
  }
}
</style>
