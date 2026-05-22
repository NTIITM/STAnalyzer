<template>
  <div class="markdown-renderer" v-html="renderedContent"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{
  content: string
}>()

// 配置 marked 选项
marked.setOptions({
  breaks: true, // 支持 GitHub 风格的换行
  gfm: true, // 启用 GitHub Flavored Markdown
})

const renderedContent = computed(() => {
  if (!props.content || props.content.trim().length === 0) {
    return ''
  }
  
  try {
    // 将 Markdown 转换为 HTML
    const html = marked.parse(props.content)
    
    // 使用 DOMPurify 清理 HTML，防止 XSS 攻击
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [
        'p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote',
        'a', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'hr', 'del', 'ins'
      ],
      ALLOWED_ATTR: ['href', 'title', 'alt', 'src', 'target', 'rel'],
      ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
    })
  } catch (error) {
    console.error('Markdown rendering error:', error)
    // 如果解析失败，返回转义的原始文本
    return DOMPurify.sanitize(props.content.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
  }
})
</script>

<style scoped>
.markdown-renderer {
  font-size: 14px;
  line-height: 1.6;
  color: inherit;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* 段落 */
.markdown-renderer :deep(p) {
  margin: 0 0 0.75em 0;
}

.markdown-renderer :deep(p:last-child) {
  margin-bottom: 0;
}

/* 标题 */
.markdown-renderer :deep(h1),
.markdown-renderer :deep(h2),
.markdown-renderer :deep(h3),
.markdown-renderer :deep(h4),
.markdown-renderer :deep(h5),
.markdown-renderer :deep(h6) {
  margin-top: 1em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-renderer :deep(h1) {
  font-size: 1.5em;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  padding-bottom: 0.3em;
}

.markdown-renderer :deep(h2) {
  font-size: 1.3em;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  padding-bottom: 0.3em;
}

.markdown-renderer :deep(h3) {
  font-size: 1.1em;
}

.markdown-renderer :deep(h4) {
  font-size: 1em;
}

.markdown-renderer :deep(h5) {
  font-size: 0.9em;
}

.markdown-renderer :deep(h6) {
  font-size: 0.85em;
  color: rgba(0, 0, 0, 0.65);
}

/* 列表 */
.markdown-renderer :deep(ul),
.markdown-renderer :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.markdown-renderer :deep(li) {
  margin: 0.25em 0;
}

.markdown-renderer :deep(ul) {
  list-style-type: disc;
}

.markdown-renderer :deep(ol) {
  list-style-type: decimal;
}

.markdown-renderer :deep(li > p) {
  margin-top: 0;
  margin-bottom: 0;
}

/* 代码 */
.markdown-renderer :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace;
}

.markdown-renderer :deep(pre) {
  background: rgba(0, 0, 0, 0.05);
  padding: 0.75em 1em;
  border-radius: 4px;
  overflow-x: auto;
  margin: 0.75em 0;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.markdown-renderer :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 0.85em;
  line-height: 1.5;
  display: block;
  white-space: pre;
}

/* 引用 */
.markdown-renderer :deep(blockquote) {
  margin: 0.75em 0;
  padding: 0 1em;
  border-left: 3px solid rgba(0, 0, 0, 0.2);
  color: rgba(0, 0, 0, 0.7);
}

.markdown-renderer :deep(blockquote > :first-child) {
  margin-top: 0;
}

.markdown-renderer :deep(blockquote > :last-child) {
  margin-bottom: 0;
}

/* 链接 */
.markdown-renderer :deep(a) {
  color: var(--accent-primary, #5d87ff);
  text-decoration: none;
}

.markdown-renderer :deep(a:hover) {
  text-decoration: underline;
}

/* 图片 */
.markdown-renderer :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 0.5em 0;
}

/* 表格 */
.markdown-renderer :deep(table) {
  border-collapse: collapse;
  margin: 0.75em 0;
  width: 100%;
  overflow-x: auto;
  display: block;
}

.markdown-renderer :deep(thead) {
  background: rgba(0, 0, 0, 0.05);
}

.markdown-renderer :deep(th),
.markdown-renderer :deep(td) {
  border: 1px solid rgba(0, 0, 0, 0.1);
  padding: 0.5em 0.75em;
  text-align: left;
}

.markdown-renderer :deep(th) {
  font-weight: 600;
}

/* 水平线 */
.markdown-renderer :deep(hr) {
  border: none;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  margin: 1em 0;
}

/* 强调 */
.markdown-renderer :deep(strong) {
  font-weight: 600;
}

.markdown-renderer :deep(em) {
  font-style: italic;
}

.markdown-renderer :deep(del) {
  text-decoration: line-through;
  opacity: 0.7;
}

/* 在深色背景下的适配（如 user 消息） */
.message.user .markdown-renderer {
  color: rgba(255, 255, 255, 0.95);
}

.message.user .markdown-renderer :deep(code) {
  background: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.95);
}

.message.user .markdown-renderer :deep(pre) {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.2);
}

.message.user .markdown-renderer :deep(pre code) {
  color: rgba(255, 255, 255, 0.95);
}

.message.user .markdown-renderer :deep(blockquote) {
  border-left-color: rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.85);
}

.message.user .markdown-renderer :deep(h1),
.message.user .markdown-renderer :deep(h2) {
  border-bottom-color: rgba(255, 255, 255, 0.2);
}

.message.user .markdown-renderer :deep(a) {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: underline;
}

.message.user .markdown-renderer :deep(hr) {
  border-top-color: rgba(255, 255, 255, 0.2);
}

.message.user .markdown-renderer :deep(table),
.message.user .markdown-renderer :deep(thead) {
  background: rgba(255, 255, 255, 0.1);
}

.message.user .markdown-renderer :deep(th),
.message.user .markdown-renderer :deep(td) {
  border-color: rgba(255, 255, 255, 0.2);
}
</style>



