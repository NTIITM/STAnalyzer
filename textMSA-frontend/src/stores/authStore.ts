/**
 * 认证状态 Store
 * 管理 Token 认证状态和弹窗显示
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { tokenManager } from '../api/request'

export const useAuthStore = defineStore('auth', () => {
  // 是否显示 Token 认证弹窗
  const showTokenDialog = ref(false)
  // 是否显示 Cookie 认证弹窗
  const showCookieDialog = ref(false)
  
  // 是否正在认证中
  const isAuthenticating = ref(false)

  /**
   * 显示认证弹窗
   */
  function showAuthDialog() {
    showTokenDialog.value = true
  }

  /**
   * 显示 Cookie 认证弹窗
   */
  function showCookieAuthDialog() {
    showCookieDialog.value = true
  }

  /**
   * 隐藏认证弹窗
   */
  function hideAuthDialog() {
    showTokenDialog.value = false
  }

  /**
   * 隐藏 Cookie 认证弹窗
   */
  function hideCookieAuthDialog() {
    showCookieDialog.value = false
  }

  /**
   * 检查认证状态
   * @returns 是否已认证
   */
  function checkAuth(): boolean {
    return tokenManager.isAuthenticated()
  }

  /**
   * 设置 Token（认证成功后调用）
   */
  function setToken(token: string) {
    tokenManager.setToken(token)
  }

  return {
    showTokenDialog,
    showCookieDialog,
    isAuthenticating,
    showAuthDialog,
    showCookieAuthDialog,
    hideAuthDialog,
    hideCookieAuthDialog,
    checkAuth,
    setToken
  }
})

