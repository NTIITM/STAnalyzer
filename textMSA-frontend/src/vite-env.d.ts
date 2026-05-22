/// <reference types="vite/client" />

/**
 * 扩展 ImportMeta 接口以支持环境变量
 */
interface ImportMetaEnv {
  readonly MODE: string
  readonly DEV: boolean
  readonly PROD: boolean
  readonly VITE_APP_ENV?: string
  readonly VITE_DEFAULT_FILE_TYPE_ID?: string
  readonly VITE_FALLBACK_FILE_TYPE_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/**
 * Vue 组件模块声明
 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const component: DefineComponent<Record<string, any>, Record<string, any>, any>
  export default component
}
