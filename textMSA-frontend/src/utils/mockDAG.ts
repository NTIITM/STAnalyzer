/**
 * Mock 文件分析流程数据（树形结构）
 * 节点：文件（显示文件名）
 * 边：算法（显示方法名，包含执行状态和关键参数）
 */
import type { FileAnalysisTree, AnalysisDAG } from '../api/analysis'
import { convertTreeToDAG } from '../api/analysis'

/**
 * 生成mock文件分析流程树形数据
 * @param fileId - 文件ID
 */
export function createMockDAG(fileId: string): AnalysisDAG {
  // 树形结构数据（节点为文件，边为算法）
  const treeData: FileAnalysisTree = {
    fileId,
    root: {
      id: `original_${fileId}`,
      fileName: '空转数据.h5ad',
      fileType: 'h5ad',
      description: '原始的空间转录组数据文件',
      size: 52428800,
      path: `/data/${fileId}/original.h5ad`,
      url: `/api/files/${fileId}/download`,
      status: 'completed',
      createdAt: '2024-01-15T09:00:00Z',
      children: [
        {
          id: `qc_${fileId}`,
          fileName: '质控空转数据.h5ad',
          fileType: 'h5ad',
          description: '经过质量控制的空间转录组数据',
          size: 47185920,
          path: `/results/${fileId}/qc/quality_controlled.h5ad`,
          status: 'completed',
          createdAt: '2024-01-15T09:05:00Z',
          algorithm: {
            algorithmId: 'quality_control',
            algorithmName: '质量控制',
            description: '检测和过滤低质量spot',
            algorithmType: 'quality_control',
            icon: '✅',
            keyParams: {
              minGenes: 200,
              maxGenes: 5000,
              minCells: 3,
              mtPercent: 5
            },
            status: 'completed',
            startTime: '2024-01-15T09:00:00Z',
            endTime: '2024-01-15T09:05:00Z',
            duration: 300000,
            summary: '完成质量控制，过滤了10%的低质量spot'
          },
          children: [
            {
              id: `spatial_domain_${fileId}`,
              fileName: '空间域识别结果.h5ad',
              fileType: 'h5ad',
              description: '空间域识别分析结果文件',
              size: 5242880,
              path: `/results/${fileId}/spatial_domain/spatial_domain.h5ad`,
              status: 'completed',
              createdAt: '2024-01-15T10:00:00Z',
              algorithm: {
                algorithmId: 'spatial_domain_identification',
                algorithmName: '空间域识别',
                description: '识别空间转录组数据中的空间域',
                algorithmType: 'spatial_analysis',
                icon: '🔬',
                keyParams: {
                  method: 'leiden',
                  resolution: 1.0,
                  nNeighbors: 15
                },
                status: 'completed',
                startTime: '2024-01-15T09:05:00Z',
                endTime: '2024-01-15T10:00:00Z',
                duration: 3300000,
                summary: '成功识别了5个空间域'
              },
              children: [
                {
                  id: `umap_2d_${fileId}`,
                  fileName: 'UMAP_2D结果.png',
                  fileType: 'png',
                  description: '2D UMAP降维可视化结果',
                  size: 204800,
                  path: `/results/${fileId}/umap/umap_2d.png`,
                  status: 'completed',
                  createdAt: '2024-01-15T10:02:00Z',
                  algorithm: {
                    algorithmId: 'umap_2d',
                    algorithmName: 'UMAP降维(2D)',
                    description: '生成2D UMAP降维可视化',
                    algorithmType: 'dimensionality_reduction',
                    icon: '📊',
                    keyParams: {
                      nComponents: 2,
                      nNeighbors: 15,
                      minDist: 0.1
                    },
                    status: 'completed',
                    startTime: '2024-01-15T10:00:00Z',
                    endTime: '2024-01-15T10:02:00Z',
                    duration: 120000,
                    summary: '完成2D UMAP降维可视化'
                  }
                },
                {
                  id: `umap_3d_${fileId}`,
                  fileName: 'UMAP_3D结果.png',
                  fileType: 'png',
                  description: '3D UMAP降维可视化结果',
                  size: 307200,
                  path: `/results/${fileId}/umap/umap_3d.png`,
                  status: 'completed',
                  createdAt: '2024-01-15T10:03:00Z',
                  algorithm: {
                    algorithmId: 'umap_3d',
                    algorithmName: 'UMAP降维(3D)',
                    description: '生成3D UMAP降维可视化',
                    algorithmType: 'dimensionality_reduction',
                    icon: '📈',
                    keyParams: {
                      nComponents: 3,
                      nNeighbors: 15,
                      minDist: 0.1
                    },
                    status: 'completed',
                    startTime: '2024-01-15T10:00:00Z',
                    endTime: '2024-01-15T10:03:00Z',
                    duration: 180000,
                    summary: '完成3D UMAP降维可视化'
                  }
                },
                {
                  id: `de_genes_${fileId}`,
                  fileName: '差异表达基因.csv',
                  fileType: 'csv',
                  description: '不同空间域间的差异表达基因列表',
                  size: 102400,
                  path: `/results/${fileId}/differential_expression/de_genes.csv`,
                  status: 'completed',
                  createdAt: '2024-01-15T10:12:00Z',
                  algorithm: {
                    algorithmId: 'differential_expression',
                    algorithmName: '差异表达分析',
                    description: '分析不同空间域间的基因表达差异',
                    algorithmType: 'differential_expression',
                    icon: '📊',
                    keyParams: {
                      method: 'wilcoxon',
                      pValueThreshold: 0.05,
                      logFcThreshold: 0.5
                    },
                    status: 'completed',
                    startTime: '2024-01-15T10:05:00Z',
                    endTime: '2024-01-15T10:12:00Z',
                    duration: 420000,
                    summary: '识别了342个显著差异表达基因'
                  },
                  children: [
                    {
                      id: `pathway_go_${fileId}`,
                      fileName: 'GO富集结果.csv',
                      fileType: 'csv',
                      description: 'GO通路富集分析结果',
                      size: 51200,
                      path: `/results/${fileId}/pathway_enrichment/go_results.csv`,
                      status: 'completed',
                      createdAt: '2024-01-15T10:18:00Z',
                      algorithm: {
                        algorithmId: 'pathway_enrichment',
                        algorithmName: 'GO通路富集',
                        description: '对差异基因进行GO通路富集分析',
                        algorithmType: 'pathway_enrichment',
                        icon: '🧬',
                        keyParams: {
                          database: 'GO',
                          pValueCutoff: 0.05,
                          qValueCutoff: 0.2
                        },
                        status: 'completed',
                        startTime: '2024-01-15T10:12:00Z',
                        endTime: '2024-01-15T10:18:00Z',
                        duration: 360000,
                        summary: '富集到45个GO term'
                      }
                    }
                  ]
                },
                {
                  id: `trajectory_${fileId}`,
                  fileName: '空间轨迹结果.h5ad',
                  fileType: 'h5ad',
                  description: '空间轨迹分析结果文件',
                  size: 3145728,
                  path: `/results/${fileId}/trajectory/trajectory_result.h5ad`,
                  status: 'running',
                  createdAt: '2024-01-15T10:18:00Z',
                  algorithm: {
                    algorithmId: 'spatial_trajectory',
                    algorithmName: '空间轨迹分析',
                    description: '分析细胞空间分布的演化轨迹',
                    algorithmType: 'trajectory',
                    icon: '🔄',
                    keyParams: {
                      method: 'slingshot',
                      startCluster: 'domain_0',
                      endCluster: 'domain_4'
                    },
                    status: 'running',
                    startTime: '2024-01-15T10:18:00Z'
                  }
                },
                {
                  id: `cell_communication_${fileId}`,
                  fileName: '细胞通讯结果.csv',
                  fileType: 'csv',
                  description: '空间域间细胞通讯分析结果',
                  size: 25600,
                  path: `/results/${fileId}/cell_communication/communication_results.csv`,
                  status: 'pending',
                  algorithm: {
                    algorithmId: 'cell_communication',
                    algorithmName: '细胞通讯分析',
                    description: '分析不同空间域间的细胞通讯网络',
                    algorithmType: 'cell_communication',
                    icon: '📡',
                    keyParams: {
                      database: 'CellChat',
                      minCells: 10
                    },
                    status: 'pending'
                  }
                }
              ]
            }
          ]
        }
      ]
    },
    createdAt: '2024-01-15T09:00:00Z',
    updatedAt: '2024-01-15T10:18:00Z',
    status: 'running',
    progress: 75,
    totalNodes: 11,
    completedNodes: 8
  }
  
  // 将树形结构转换为 DAG 格式（扁平化的节点和边）
  return convertTreeToDAG(treeData)
}
