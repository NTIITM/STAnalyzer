/**
 * Vue I18n 国际化配置
 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'

// 从 localStorage 读取已保存的语言，默认为英文
const getSavedLocale = (): string => {
  return localStorage.getItem('app_locale') || 'en-US'
}

const savedLocale = getSavedLocale()

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en-US',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS
  },
  // 允许返回对象和数组
  returnObjects: true,
  // 当找不到翻译时，返回 key 本身而不是警告（在开发环境中）
  missingWarn: process.env.NODE_ENV === 'development',
  fallbackWarn: process.env.NODE_ENV === 'development'
})

export default i18n

