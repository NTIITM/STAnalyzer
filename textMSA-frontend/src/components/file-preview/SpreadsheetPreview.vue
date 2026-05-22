<template>
  <div class="spreadsheet-preview">
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>{{ t('filePreview.loading') }}</p>
    </div>
    <div v-else-if="error" class="error-container">
      <p class="error-message">{{ error }}</p>
      <button @click="loadFile" class="retry-btn">{{ t('common.retry') }}</button>
    </div>
    <div v-else-if="data.length === 0" class="empty-container">
      <p>{{ t('filePreview.empty') }}</p>
    </div>
    <div v-else class="table-container">
      <div v-if="isLargeFile" class="file-size-notice">
        <span>⚠️ {{ t('filePreview.largeNotice', { count: maxRows }) }}</span>
      </div>
      <div class="table-wrapper">
        <table class="spreadsheet-table">
          <thead>
            <tr>
              <th v-for="(header, index) in headers" :key="index" class="table-header">
                {{ header || t('filePreview.defaultColumn', { index: index + 1 }) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in displayData" :key="rowIndex" :class="{ 'table-row-even': rowIndex % 2 === 0 }">
              <td v-for="(cell, cellIndex) in row" :key="cellIndex" class="table-cell">
                {{ formatCell(cell) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="totalPages > 1" class="pagination">
        <button 
          @click="prevPage" 
          :disabled="currentPage === 1"
          class="pagination-btn"
        >
          {{ t('filePreview.prev') }}
        </button>
        <span class="pagination-info">
          {{ t('filePreview.pageInfo', { current: currentPage, total: totalPages, rows: totalRows }) }}
        </span>
        <button 
          @click="nextPage" 
          :disabled="currentPage === totalPages"
          class="pagination-btn"
        >
          {{ t('filePreview.next') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as XLSX from 'xlsx'
import Papa from 'papaparse'
import { previewFileById } from '../../api/file'

const props = defineProps<{
  fileId: string
  fileName: string
}>()

const { t } = useI18n()
const loading = ref(false)
const error = ref<string | null>(null)
const headers = ref<string[]>([])
const data = ref<any[][]>([])
const currentPage = ref(1)
const rowsPerPage = ref(100)
const maxRows = ref(1000) // 最大显示行数

const extension = computed(() => {
  const parts = props.fileName.toLowerCase().split('.')
  return parts[parts.length - 1] || ''
})

const isLargeFile = computed(() => data.value.length > maxRows.value)

const totalRows = computed(() => data.value.length)

const displayRows = computed(() => {
  return isLargeFile.value ? maxRows.value : totalRows.value
})

const totalPages = computed(() => {
  return Math.ceil(displayRows.value / rowsPerPage.value)
})

const displayData = computed(() => {
  const start = (currentPage.value - 1) * rowsPerPage.value
  const end = start + rowsPerPage.value
  return data.value.slice(start, end)
})

const formatCell = (cell: any): string => {
  if (cell === null || cell === undefined) return ''
  if (typeof cell === 'object') return JSON.stringify(cell)
  return String(cell)
}

const loadFile = async () => {
  loading.value = true
  error.value = null
  
  try {
    // 使用 previewFileById 替代 downloadFileById
    const blob = await previewFileById(props.fileId, { maxRows: maxRows.value })
    
    if (extension.value === 'csv' || extension.value === 'tsv') {
      await parseCSV(blob)
    } else if (extension.value === 'xlsx' || extension.value === 'xls') {
      await parseXLSX(blob)
    } else {
      throw new Error(t('filePreview.unsupported', { ext: extension.value }))
    }
  } catch (err: any) {
    console.error('加载文件失败:', err)
    error.value = err.message || t('filePreview.loadFailed')
  } finally {
    loading.value = false
  }
}

const parseCSV = async (blob: Blob): Promise<void> => {
  return new Promise((resolve, reject) => {
    const text = blob.text()
    text.then((csvText) => {
      const delimiter = extension.value === 'tsv' ? '\t' : undefined
      
      Papa.parse(csvText, {
        header: false,
        delimiter: delimiter,
        skipEmptyLines: 'greedy',
        complete: (results: Papa.ParseResult<any[]>) => {
          if (results.errors.length > 0) {
            console.warn('CSV parse warnings:', results.errors)
          }
          
          if (results.data.length === 0) {
            headers.value = []
            data.value = []
            resolve()
            return
          }
          
          // 第一行作为表头
          headers.value = (results.data[0] as any[]).map((h, i) => 
            h ? String(h) : t('filePreview.defaultColumn', { index: i + 1 })
          )
          
          // 其余行作为数据
          data.value = results.data.slice(1) as any[][]
          
          resolve()
        },
        error: (err: Error) => {
          reject(new Error(t('filePreview.csvFailed', { error: err.message })))
        }
      })
    }).catch(reject)
  })
}

const parseXLSX = async (blob: Blob): Promise<void> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    
    reader.onload = (e) => {
      try {
        const arrayBuffer = e.target?.result as ArrayBuffer
        const uint8Array = new Uint8Array(arrayBuffer)
        const workbook = XLSX.read(uint8Array, { type: 'array' })
        
        // 读取第一个工作表
        const firstSheetName = workbook.SheetNames[0]
        const worksheet = workbook.Sheets[firstSheetName]
        
        // 转换为 JSON 数组（二维数组格式）
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { 
          header: 1,
          defval: '' // 空单元格默认值
        }) as any[][]
        
        if (jsonData.length === 0) {
          headers.value = []
          data.value = [] as any[][]
          resolve()
          return
        }
        
        // 第一行作为表头
        headers.value = (jsonData[0] || []).map((h, i) => 
          h ? String(h) : t('filePreview.defaultColumn', { index: i + 1 })
        )
        
        // 其余行作为数据
        data.value = jsonData.slice(1) as any[][]
        
        resolve()
      } catch (err: any) {
        reject(new Error(t('filePreview.xlsxFailed', { error: err.message })))
      }
    }
    
    reader.onerror = () => {
      reject(new Error(t('filePreview.readFailed')))
    }
    
    reader.readAsArrayBuffer(blob)
  })
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

onMounted(() => {
  loadFile()
})
</script>

<style scoped>
.spreadsheet-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.loading-container,
.error-container,
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  min-height: 300px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-color, rgba(200, 200, 210, 0.3));
  border-top-color: var(--accent-primary, #1890ff);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-message {
  color: var(--text-danger, #ff4d4f);
  margin-bottom: 1rem;
  text-align: center;
}

.retry-btn {
  padding: 0.5rem 1rem;
  background: var(--accent-primary, #1890ff);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.2s ease;
}

.retry-btn:hover {
  background: var(--accent-hover, #40a9ff);
}

.table-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.file-size-notice {
  padding: 0.75rem 1rem;
  background: rgba(255, 193, 7, 0.1);
  border-bottom: 1px solid rgba(255, 193, 7, 0.3);
  color: #856404;
  font-size: 0.875rem;
}

.table-wrapper {
  flex: 1;
  overflow: auto;
  padding: 1rem;
}

.spreadsheet-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table-header {
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  border-bottom: 2px solid var(--border-color, rgba(200, 200, 210, 0.5));
  position: sticky;
  top: 0;
  z-index: 10;
}

.table-cell {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.3));
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  word-break: break-word;
  max-width: 300px;
}

.table-row-even {
  background: var(--bg-tertiary, rgba(250, 250, 250, 0.5));
}

.spreadsheet-table tbody tr:hover {
  background: rgba(24, 144, 255, 0.05);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
  border-top: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
}

.pagination-btn {
  padding: 0.5rem 1rem;
  background: var(--bg-primary, white);
  border: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  transition: all 0.2s ease;
}

.pagination-btn:hover:not(:disabled) {
  background: var(--bg-tertiary, rgba(250, 250, 250, 0.5));
  border-color: var(--accent-primary, #1890ff);
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-info {
  font-size: 0.875rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
}
</style>
