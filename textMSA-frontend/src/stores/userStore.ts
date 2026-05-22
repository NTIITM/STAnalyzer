/**
 * 用户信息 Store
 * 负责缓存用户资料并提供更新/修改密码操作
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getUserInfo, updateUserProfile, changePassword, type UpdateProfileParams, type ChangePasswordParams, type UserInfoResponse } from '../api/user'
import { tokenManager, type UserInfo } from '../api'

export const useUserStore = defineStore('user', () => {
  const profile = ref<UserInfo | null>(tokenManager.getUserInfo())
  const loadingProfile = ref(false)
  const savingProfile = ref(false)
  const changingPassword = ref(false)
  const lastError = ref<string | null>(null)

  const hasProfile = computed(() => !!profile.value)
  const displayName = computed(() => profile.value?.username || '用户')

  async function fetchProfile(force = false): Promise<UserInfoResponse | null> {
    if (loadingProfile.value) {
      return profile.value
    }

    if (profile.value && !force) {
      return profile.value as UserInfoResponse
    }

    loadingProfile.value = true
    lastError.value = null

    try {
      const data = await getUserInfo()
      profile.value = {
        userId: data.userId,
        username: data.username,
        email: data.email
      }
      tokenManager.setUserInfo(profile.value)
      return data
    } catch (error: any) {
      lastError.value = error?.message || '获取用户信息失败'
      throw error
    } finally {
      loadingProfile.value = false
    }
  }

  async function saveProfile(payload: UpdateProfileParams): Promise<UserInfoResponse> {
    savingProfile.value = true
    lastError.value = null

    try {
      const data = await updateUserProfile(payload)
      profile.value = {
        userId: data.userId,
        username: data.username,
        email: data.email
      }
      return data
    } catch (error: any) {
      lastError.value = error?.message || '更新用户信息失败'
      throw error
    } finally {
      savingProfile.value = false
    }
  }

  async function updatePassword(payload: ChangePasswordParams): Promise<void> {
    changingPassword.value = true
    lastError.value = null

    try {
      await changePassword(payload)
    } catch (error: any) {
      lastError.value = error?.message || '修改密码失败'
      throw error
    } finally {
      changingPassword.value = false
    }
  }

  function resetProfile() {
    profile.value = null
    tokenManager.setUserInfo(null)
  }

  return {
    profile,
    loadingProfile,
    savingProfile,
    changingPassword,
    lastError,
    hasProfile,
    displayName,
    fetchProfile,
    saveProfile,
    updatePassword,
    resetProfile
  }
})
