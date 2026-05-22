import httpClient from './http'
import type { Service, ServiceListResponse } from '../api/service'

export interface ListProjectServicesParams {
  projectId: string
  skip?: number
  limit?: number
  signal?: AbortSignal
}

export type ProjectService = Service

export interface ProjectServicesResponse extends ServiceListResponse {
  services: ProjectService[]
}

const DEFAULT_SKIP = 0
export const DEFAULT_PROJECT_SERVICES_LIMIT = 100

/**
 * listProjectServices wraps `GET /api/services` and mirrors the ServiceListResponse shape.
 * The endpoint expects `projectId`, `skip`, and `limit` query parameters.
 */
export async function listProjectServices(
  params: ListProjectServicesParams
): Promise<ProjectServicesResponse> {
  const { projectId, skip = DEFAULT_SKIP, limit = DEFAULT_PROJECT_SERVICES_LIMIT, signal } = params

  if (!projectId) {
    throw new Error('listProjectServices requires a projectId')
  }

  return httpClient({
    url: '/service',
    method: 'GET',
    params: {
      projectId,
      skip,
      limit
    },
    signal
  }) as Promise<ProjectServicesResponse>
}

