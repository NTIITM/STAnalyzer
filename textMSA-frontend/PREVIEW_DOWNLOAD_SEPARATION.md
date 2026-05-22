# Preview 和 Download 接口分离说明

## 概述

已将前端的文件预览（preview）和下载（download）功能分离为两个独立的接口，以便后端可以针对不同场景进行优化。

## 修改内容

### 1. API 层 (`src/api/file.ts`)

新增了两个独立的函数：

#### `previewFileById(fileId, options?)`
- **用途**: 文件预览
- **接口路径**: `GET /file/preview/{fileId}`
- **参数**:
  - `fileId`: 文件ID
  - `options` (可选):
    - `maxRows`: 最大行数限制（用于表格文件）
    - `imageSize`: 图片尺寸 ('thumbnail' | 'medium' | 'full')
    - `maxSize`: 最大文件大小限制
- **返回**: `Blob`
- **超时**: 2分钟 (120000ms)

#### `downloadFileById(fileId)`
- **用途**: 文件下载
- **接口路径**: `GET /file/download/{fileId}`
- **参数**:
  - `fileId`: 文件ID
- **返回**: `Blob`
- **超时**: 5分钟 (300000ms)
- **说明**: 后端应返回完整文件，并带 `Content-Disposition: attachment` 头

### 2. 预览组件修改

以下组件已更新为使用 `previewFileById`:

#### `SpreadsheetPreview.vue`
- 使用 `previewFileById(fileId, { maxRows: 1000 })`
- 可以让后端只返回前1000行数据，提升预览速度

#### `ImagePreview.vue`
- 使用 `previewFileById(fileId, { imageSize: 'medium' })`
- 可以让后端返回中等尺寸的图片，减少传输量

#### `TextPreview.vue`
- 使用 `previewFileById(fileId, { maxSize: 10485760 })`
- 限制预览文件大小为10MB

### 3. 下载功能保持不变

以下组件继续使用 `downloadFileById`（用于实际下载文件）:

- `AgentMessageContent.vue` - Agent消息中的文件下载
- `DGEResultsVisualization.vue` - 差异基因表达结果加载
- `CellCommunicationVisualization.vue` - 细胞通讯数据加载

**注意**: 这些组件虽然使用 `downloadFileById`，但它们是用于加载完整数据进行分析，而不是触发浏览器下载。如果需要，可以根据具体场景决定是否改用 `previewFileById`。

## 后端需要实现的接口

### 1. Preview 接口

```
GET /file/preview/{fileId}
Query Parameters:
  - maxRows?: number (可选，表格文件的最大行数)
  - imageSize?: 'thumbnail' | 'medium' | 'full' (可选，图片尺寸)
  - maxSize?: number (可选，最大文件大小，单位字节)

Response:
  - Content-Type: 根据文件类型设置
  - Body: 文件内容（可以是优化后的）
```

**优化建议**:
- 对于表格文件（CSV/Excel），可以只返回前 N 行
- 对于图片，可以返回压缩或缩略图
- 对于大文本文件，可以只返回前 N 个字符
- 可以添加缓存机制

### 2. Download 接口（已存在）

```
GET /file/download/{fileId}

Response:
  - Content-Type: 根据文件类型设置
  - Content-Disposition: attachment; filename="文件名"
  - Body: 完整文件内容
```

## 接口对比

| 特性 | Preview 接口 | Download 接口 |
|------|-------------|--------------|
| 路径 | `/file/preview/{fileId}` | `/file/download/{fileId}` |
| 用途 | 在线预览 | 文件下载 |
| 内容 | 可以是优化/截断的 | 必须是完整的 |
| 响应头 | 不需要 attachment | 需要 `Content-Disposition: attachment` |
| 超时 | 2分钟 | 5分钟 |
| 缓存 | 建议启用 | 可选 |
| 参数 | 支持优化参数 | 无额外参数 |

## 前端使用示例

```typescript
// 预览文件
import { previewFileById } from '@/api/file'

// 预览表格（限制行数）
const blob = await previewFileById(fileId, { maxRows: 1000 })

// 预览图片（中等尺寸）
const blob = await previewFileById(fileId, { imageSize: 'medium' })

// 预览文本（限制大小）
const blob = await previewFileById(fileId, { maxSize: 10 * 1024 * 1024 })

// 下载完整文件
import { downloadFileById } from '@/api/file'
const blob = await downloadFileById(fileId)
// 触发浏览器下载
const url = URL.createObjectURL(blob)
const link = document.createElement('a')
link.href = url
link.download = fileName
link.click()
URL.revokeObjectURL(url)
```

## 后续工作

1. **后端实现 `/file/preview/{fileId}` 接口**
   - 支持可选的查询参数（maxRows, imageSize, maxSize）
   - 根据参数返回优化后的内容
   - 添加适当的缓存策略

2. **测试**
   - 测试各种文件类型的预览功能
   - 测试下载功能是否正常
   - 测试参数传递是否正确

3. **可选优化**
   - 考虑是否将 `DGEResultsVisualization.vue` 和 `CellCommunicationVisualization.vue` 也改用 preview 接口
   - 添加进度条显示
   - 添加预览失败时的降级策略

## 注意事项

- 前端已经完成修改，可以直接使用
- 后端需要实现新的 preview 接口
- 在后端实现完成前，可以让 preview 接口暂时返回完整文件（与 download 相同）
- 所有修改都是向后兼容的，不会影响现有功能
