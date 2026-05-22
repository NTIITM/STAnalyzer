/**
 * 空间转录组数据 API (TypeScript)
 * 注意：目前所有API只支持单切片，每个fileId对应一个切片，不需要指定sliceId
 * 简化版本：只保留图像、spot位置和基因表达数据
 */
import request from './request'

// 获取切片图像响应（单切片）
export interface GetSliceImageResponse {
  imageUrl: string
  width: number
  height: number
}

// Spot信息（包含位置信息和group对象）
export interface SpatialSpot {
  id: string
  x: number
  y: number
  group: {
    [key: string]: string | number
  }
}

// 获取Spots响应（单切片）
export interface GetSpotsResponse {
  spots: SpatialSpot[]
  totalCount: number
}

/**
 * 获取文件的切片图像URL
 * @param fileId - 文件ID
 * @returns 切片图像信息
 */
export async function getSpatialSliceImage(
  fileId: string
): Promise<GetSliceImageResponse> {
  const response = await request({
    url: `/spatial/${fileId}/image`,
    method: 'GET'
  }) as any
  if (response && response.data) {
    return response.data as GetSliceImageResponse
  }
  return response as GetSliceImageResponse
}

/**
 * 获取文件的Spots位置数据（简化版：只返回位置信息）
 * @param fileId - 文件ID
 * @returns Spots位置数据
 */
export async function getSpatialSpots(
  fileId: string
): Promise<GetSpotsResponse> {
  const response = await request({
    url: `/spatial/${fileId}/spots`,
    method: 'GET'
  }) as any
  console.log('getSpatialSpots response', response)
  if (response && response.data) {
    return response.data as GetSpotsResponse
  }
  return response as GetSpotsResponse
}

/**
 * 获取指定基因在所有Spots中的表达值（用于热力图）
 * @param fileId - 文件ID
 * @param geneName - 基因名称
 * @returns 基因表达数据列表
 */
export interface GeneExpressionItem {
  spotId: string
  value: number
}

export async function getGeneExpression(
  fileId: string,
  geneName: string
): Promise<GeneExpressionItem[]> {
  const response = await request({
    url: `/spatial/${fileId}/gene/${geneName}`,
    method: 'GET'
  }) as any
  
  if (response && response.data) {
    return response.data as GeneExpressionItem[]
  }
  return response as GeneExpressionItem[]
}

/**
 * 获取文件的可用基因列表
 * @param fileId - 文件ID
 * @param query - 搜索关键词（可选，用于过滤基因名称）
 * @returns 基因名称列表
 */
export async function getGeneList(
  fileId: string,
  query?: string
): Promise<string[]> {
  const params = new URLSearchParams()
  if (query) {
    params.append('query', query)
  }
  
  const queryString = params.toString()
  const url = `/spatial/${fileId}/genes${queryString ? `?${queryString}` : ''}`
  
  const response = await request({
    url,
    method: 'GET'
  }) as any
  
  if (response && response.data) {
    return response.data as string[]
  }
  return response as string[]
}

/**
 * ---------------- Raw QC preview (h5ad) ----------------
 */
export interface RawQcRequest {
  fileId: string
  genes: string[]
  max_cells?: number
  return_qc?: boolean
  return_coords?: boolean
  embed_method?: 'pca' | 'umap' | 'tsne'
}

export interface RawQcResponse {
  meta: {
    total_cells: number
    total_genes: number
    genes_found: string[]
    has_mt: boolean
  }
  qc: {
    counts: number[]
    n_genes: number[]
    pct_mt?: number[]
  }
  cells: string[]
  genes: string[]
  expression:
    | {
        rows?: number[]
        cols?: number[]
        values?: number[]
      }
    | number[][]
  coords: [number, number][] | null
}

export async function queryRawH5adGenes(payload: RawQcRequest): Promise<RawQcResponse> {
  const response = (await request({
    url: '/visualization/query_h5ad_genes',
    method: 'POST',
    data: payload
  })) as any
  return (response?.data ?? response) as RawQcResponse
}

export async function downloadRawH5ad(params: { fileId: string; genes?: string[]; cellId?: string }) {
  const searchParams = new URLSearchParams()
  searchParams.append('file_id', params.fileId)
  if (params.genes?.length) {
    searchParams.append('genes', params.genes.join(','))
  }
  if (params.cellId) {
    searchParams.append('cell_id', params.cellId)
  }
  const url = `/visualization/download_h5ad?${searchParams.toString()}`
  const response = (await request({
    url,
    method: 'GET',
    responseType: 'blob'
  })) as any
  return response
}

