"""
Service API路由
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.service.service_service import get_service_service
from textmsa.services.api.schemas import (
    ServiceCreateRequest,
    ServiceUpdateRequest,
    ServiceResponse,
    ServiceListResponse,
    ServiceExecuteRequest,
    ServiceExecuteResponse,
    ServiceExecutionResponse,
    ServiceExecutionListResponse
)

logger = get_logger(__name__)

# 创建路由
service_router = APIRouter(prefix="/api/service", tags=["Service管理"])


@service_router.post("/", response_model=ServiceResponse)
async def create_service(
    request: Request,
    service_data: ServiceCreateRequest
):
    """
    创建Service
    
    - **name**: Service名称
    - **description**: Service描述（可选）
    - **version**: Service版本（可选，默认1.0.0）
    - **baseurl**: 基础URL（IP和端口号，如 http://192.168.1.1:8080）
    - **service_suffix**: Service后缀（与baseurl拼接后访问对应的service，如 /api/service）
    - **download_suffix**: Download后缀（可选，如果输出存在文件则需要配置，用于下载生成文件，如 /api/download）
    - **tags**: Service标签集合（可选）
    - **requestConfig**: 请求配置（可选）
    - **parameterTemplate**: 参数模板（可选）
    - **visibility**: Service权限（可选，默认private；可选：private/public/system）
    
    注意：
    - service_id 如果未提供，系统会自动生成 UUID
    - 默认visibility为PRIVATE（仅创建者可见）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        user_id = user_info.get("user_id") if user_info else None
        
        # 创建Service
        service_service = get_service_service()
        service = service_service.create_service(service_data.model_dump(), user_id=user_id)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "code": 201,
                "message": "Service创建成功",
                "data": service
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建Service失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建Service失败: {str(e)}"
        )


@service_router.get("/list", response_model=ServiceListResponse)
@service_router.get("", response_model=ServiceListResponse)
@service_router.get("/", response_model=ServiceListResponse)
async def list_services(
    request: Request,
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    visibility: Optional[str] = Query(None, alias="visibility", description="Service权限（可选，默认private；可选：private/public/system）"),
    project_id: Optional[str] = Query(None, alias="projectId", description="项目ID（用于项目过滤）"),
    input_file_type_id: Optional[str] = Query(None, alias="inputFileTypeId", description="输入文件类型ID（用于筛选接受该文件类型的服务）")
):
    """
    获取Service列表
    
    - **skip**: 跳过数量（可选，默认0）
    - **limit**: 返回数量（可选，默认100，最大1000）
    - **visibility**: Service权限（可选，默认private；可选：private/public/system）
    - **projectId**: 项目ID（可选，用于项目过滤）
    - **inputFileTypeId**: 输入文件类型ID（可选，用于筛选接受该文件类型的服务）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户（可选，用于权限控制）
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        # 获取Service列表（根据权限过滤）
        service_service = get_service_service()
        logger.info(f"获取Service列表，visibility={visibility}, project_id={project_id}, input_file_type_id={input_file_type_id}")
        result = service_service.list_services(
            skip=skip,
            limit=limit,
            user_id=user_id,
            visibility_filter=visibility,
            project_id=project_id,
            input_file_type_id=input_file_type_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Service列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Service列表失败: {str(e)}"
        )


@service_router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    request: Request,
    update_data: ServiceUpdateRequest
):
    """
    更新Service信息
    
    - **service_id**: Service ID（路径参数）
    - **update_data**: 更新数据（只包含要更新的字段）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户（可选，用于权限控制）
        # user_info = await get_current_user_from_header(request=request)
        
        
        # 更新Service
        service_service = get_service_service()
        service = service_service.update_service(service_id, update_data.model_dump(exclude_unset=True))
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "Task更新成功",
                "data": service
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Service失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新Service失败: {str(e)}"
        )


@service_router.delete("/{service_id}")
async def delete_service(
    service_id: str,
    request: Request
):
    """
    删除Service
    
    - **service_id**: Service ID
    
    注意：如果Task存在执行记录，则无法删除
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户（可选，用于权限控制）
        user_info = await get_current_user_from_header(request=request)
        
        # 删除Service
        service_service = get_service_service()
        success = service_service.delete_service(service_id)
        
        if success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "code": 200,
                    "message": "Task删除成功",
                    "data": {"service_id": service_id}
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Task删除失败"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除Service失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除Service失败: {str(e)}"
        )


@service_router.get("/{service_id}", response_model=ServiceResponse)
async def get_service_info(
    service_id: str,
    request: Request
):
    """
    获取Service信息
    
    - **service_id**: Service ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户（可选，用于权限控制）
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        # 获取Service信息（带权限检查）
        service_service = get_service_service()
        service_info = service_service.get_service(service_id, user_id=user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": service_info
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Service信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取Service信息失败: {str(e)}"
        )


@service_router.get("/queue/status")
async def get_queue_status(request: Request):
    """
    获取服务执行队列状态
    
    返回当前运行数、排队数和最大并发数
    """
    try:
        service_service = get_service_service()
        queue_status = service_service.get_queue_status()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": queue_status
            }
        )
    except Exception as e:
        logger.error(f"获取队列状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取队列状态失败: {str(e)}"
        )


@service_router.post("/{service_id}/execute", response_model=ServiceExecuteResponse)
async def execute_service(
    service_id: str,
    request: Request,
    execute_data: ServiceExecuteRequest
):
    """
    执行Service
    
    - **service_id**: Service ID（路径参数）
    - **input_file_ids**: 输入文件ID列表（支持多文件输入）
    - **parameters**: 执行参数（可选，覆盖parameterTemplate）
        
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            logger.warning(f"[API] 用户未授权 - service_id: {service_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 执行Service
        service_service = get_service_service()
        result = service_service.execute_service(
            service_id=service_id,
            input_file_ids=execute_data.input_file_ids,
            user_id=user_id,
            parameters=execute_data.parameters,
            project_id=execute_data.project_id
        )
        
        execution_id = result.get('execution_id') if isinstance(result, dict) else 'unknown'
        logger.info(f"[API] Service执行请求已提交 - execution_id: {execution_id}, service_id: {service_id}, status: {result.get('status')}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "Task执行成功",
                "data": result
            }
        )
    
    except HTTPException as http_ex:
        logger.error(f"[API] HTTP异常 - service_id: {service_id}, status_code: {http_ex.status_code}, detail: {http_ex.detail}")
        raise
    except Exception as e:
        logger.error(f"[API] 执行Service失败 - service_id: {service_id}, error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行Service失败: {str(e)}"
        )


@service_router.get("/executions/{execution_id}", response_model=ServiceExecutionResponse)
async def get_execution(
    execution_id: str,
    request: Request
):
    """
    获取Task执行记录
    
    - **execution_id**: 执行ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户（可选，用于权限控制）
        user_info = await get_current_user_from_header(request=request)
        
        # 获取执行记录
        service_service = get_service_service()
        execution = service_service.get_execution(execution_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": execution
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取执行记录失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取执行记录失败: {str(e)}"
        )


@service_router.get("/executions/", response_model=ServiceExecutionListResponse)
async def list_executions(
    request: Request,
    service_id: Optional[str] = Query(None, description="Service ID过滤"),
    user_id: Optional[str] = Query(None, description="用户ID过滤"),
    status_filter: Optional[str] = Query(None, description="状态过滤", alias="status"),
    project_id: Optional[str] = Query(None, description="Project ID过滤", alias="project"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量")
):
    """
    获取Task执行记录列表
    
    - **service_id**: Service ID过滤（可选）
    - **user_id**: 用户ID过滤（可选）
    - **status**: 状态过滤（可选）
    - **project**: Project ID过滤（可选）
    - **skip**: 跳过数量（可选，默认0）
    - **limit**: 返回数量（可选，默认100，最大1000）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户（可选，用于权限控制）
        user_info = await get_current_user_from_header(request=request)
        
        # 如果用户已登录，默认只返回该用户的执行记录
        if user_info and not user_id:
            user_id = user_info.get("user_id")
        
        # 获取执行记录列表
        service_service = get_service_service()
        result = service_service.list_executions(
            service_id=service_id,
            user_id=user_id,
            status_filter=status_filter,
            project_id=project_id,
            skip=skip,
            limit=limit
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取执行记录列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取执行记录列表失败: {str(e)}"
        )
