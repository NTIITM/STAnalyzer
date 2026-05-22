"""
项目 API 路由
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.project.project_service import get_project_service
from textmsa.services.api.schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectListResponse,
    ProjectKnowledgeConfigRequest,
    ProjectServiceConfigRequest,
    AddFileToProjectRequest
)

logger = get_logger(__name__)

# 创建路由
project_router = APIRouter(prefix="/api/project", tags=["项目管理"])


def _dict_to_project_response(project_dict: dict) -> ProjectResponse:
    """将项目字典转换为API响应"""
    # ProjectService 返回的字典使用蛇形命名
    return ProjectResponse(
        project_id=project_dict["project_id"],
        user_id=project_dict["user_id"],
        name=project_dict["name"],
        description=project_dict.get("description"),
        knowledge_ids=project_dict.get("knowledge_ids", []),
        service_ids=project_dict.get("service_ids", []),
        knowledge_prompt_config_id=project_dict.get("knowledge_prompt_config_id", None),
        conversation_id=project_dict.get("conversation_id", None),
        file_ids=project_dict.get("file_ids", []),
        execution_ids=project_dict.get("execution_ids", []),
        created_at=project_dict["created_at"].isoformat() if hasattr(project_dict.get("created_at"), "isoformat") else project_dict.get("created_at"),
        updated_at=project_dict["updated_at"].isoformat() if hasattr(project_dict.get("updated_at"), "isoformat") else project_dict.get("updated_at")
    )


@project_router.post("/", response_model=ProjectResponse)
async def create_project(
    request: Request,
    project_data: ProjectCreateRequest
):
    """
    创建项目
    
    - **name**: 项目名称（必填）
    - **description**: 项目描述（可选）
    
    注意：创建项目时默认使用 "all" 模式的知识和服务配置
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 创建项目（ProjectService 会自动设置默认的 all 模式配置）
        project_service = get_project_service()
        project_dict = project_service.create_project(
            user_id=user_id,
            name=project_data.name,
            description=project_data.description
        )
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "code": 201,
                "message": "项目创建成功",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建项目失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建项目失败: {str(e)}"
        )


@project_router.get("/list", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制")
):
    """
    获取项目列表
    
    - **skip**: 跳过数量（默认0）
    - **limit**: 返回数量限制（默认100，最大1000）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取项目列表
        project_service = get_project_service()
        projects = project_service.list_projects(user_id=user_id, skip=skip, limit=limit)
        
        # 转换为响应格式
        project_responses = [_dict_to_project_response(p) for p in projects]
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": [p.model_dump() for p in project_responses],
                "total": len(project_responses)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目列表失败"
        )


@project_router.get("/service-filetype-graph")
async def get_project_service_file_type_graph(
    request: Request,
    project_id: Optional[str] = Query(
        default=None,
        description="项目ID（可选）。若提供，则只返回该项目内的服务；若不提供，则返回所有可见服务。",
    ),
    file_type_id: Optional[str] = Query(
        default=None,
        description="起始文件类型ID（可选）。若提供，则从该文件类型开始裁剪子图。",
    ),
    depth: Optional[int] = Query(
        default=None,
        ge=0,
        description="从起始文件类型出发的最大搜索深度（按节点层级计，0 表示仅包含起点本身）。仅在提供 file_type_id 时生效。",
    ),
):
    """
    获取 Service 与 FileType 的树状关系结构。

    - **project_id**: 可选，项目ID。若提供，则只返回该项目内的服务；若不提供，则返回所有可见服务。
    - **file_type_id**: 可选，起始文件类型ID，用于从该类型出发裁剪子树
    - **depth**: 可选，BFS 深度限制，仅在提供 file_type_id 时生效

    返回的数据结构大致为：
    {
        "code": 200,
        "message": "success",
        "data": {
            "roots": [
                {
                    "node_type": "file_type" | "service",
                    "file_type_id": "..." | "service_id": "...",
                    "name": "...",
                    "description": "...",
                    "children": [ ... 同结构 ... ]
                }
            ]
        }
    }
    """
    # 获取当前用户
    user_info = await get_current_user_from_header(request=request)

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权，请先登录",
        )

    user_id = user_info["user_id"]

    project_service = get_project_service()
    tree_data = project_service.get_service_file_type_graph(
        project_id=project_id,
        user_id=user_id,
        file_type_id=file_type_id,
        depth=depth,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": "success",
            "data": tree_data,
        },
    )


@project_router.get("/{project_id}/detail")
async def get_project_detail(
    project_id: str,
    request: Request
):
    """
    获取项目详细信息（简化版）
    
    - **project_id**: 项目ID
    
    返回项目的基本信息和关联资源（files、executions、knowledges暂时留位置）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取项目详细信息（通过service层）
        project_service = get_project_service()
        detail_data = project_service.get_project_detail(project_id=project_id, user_id=user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": detail_data
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目详细信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目详细信息失败"
        )

@project_router.get("/{project_id}/files-relations")
async def get_project_files_relations(
    project_id: str,
    request: Request
):
    """
    获取项目下的所有文件信息及文件关系
    
    - **project_id**: 项目ID
    
    返回：
    - files: 项目包含的文件详细信息
    - relations: 文件间的父子关系（parent_file_id, child_file_id, project_id, description, created_at）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取项目文件信息与关系
        project_service = get_project_service()
        data = project_service.get_project_files_relations(
            project_id=project_id,
            user_id=user_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": data
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目文件关系失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目文件关系失败"
        )


@project_router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    request: Request
):
    """
    获取项目详情
    
    - **project_id**: 项目ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取项目
        project_service = get_project_service()
        project_dict = project_service.get_project(project_id=project_id, user_id=user_id)
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目详情失败"
        )


@project_router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: Request,
    project_data: ProjectUpdateRequest
):
    """
    更新项目信息
    
    - **project_id**: 项目ID
    - **name**: 项目名称（可选）
    - **description**: 项目描述（可选）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 更新项目
        project_service = get_project_service()
        project_dict = project_service.update_project(
            project_id=project_id,
            user_id=user_id,
            name=project_data.name,
            description=project_data.description
        )
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "项目更新成功",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新项目失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新项目失败"
        )


@project_router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    request: Request
):
    """
    删除项目
    
    - **project_id**: 项目ID
    
    注意：删除项目不会删除项目中的文件，只会移除项目与文件的关联
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 删除项目
        project_service = get_project_service()
        project_service.delete_project(project_id=project_id, user_id=user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "项目删除成功"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除项目失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除项目失败"
        )


@project_router.post("/{project_id}/file", response_model=ProjectResponse)
async def add_file_to_project(
    project_id: str,
    request: Request,
    file_data: AddFileToProjectRequest
):
    """
    向项目添加文件
    
    - **project_id**: 项目ID
    - **file_id**: 文件ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 添加文件到项目
        project_service = get_project_service()
        project_dict = project_service.add_file_to_project(
            project_id=project_id,
            file_id=file_data.file_id,
            user_id=user_id
        )
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "文件添加成功",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加文件到项目失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="添加文件到项目失败"
        )


@project_router.delete("/{project_id}/file/{file_id}", response_model=ProjectResponse)
async def remove_file_from_project(
    project_id: str,
    file_id: str,
    request: Request
):
    """
    从项目移除文件
    
    - **project_id**: 项目ID
    - **file_id**: 文件ID
    
    注意：移除文件不会删除文件本身，只会移除项目与文件的关联
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 从项目移除文件
        project_service = get_project_service()
        project_dict = project_service.remove_file_from_project(
            project_id=project_id,
            file_id=file_id,
            user_id=user_id
        )
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "文件移除成功",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从项目移除文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="从项目移除文件失败"
        )


@project_router.get("/{project_id}/files")
async def get_project_files(
    project_id: str,
    request: Request
):
    """
    获取项目的文件列表
    
    - **project_id**: 项目ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取项目文件列表
        project_service = get_project_service()
        file_ids = project_service.get_project_files(project_id=project_id, user_id=user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": file_ids
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目文件列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目文件列表失败"
        )


@project_router.put("/{project_id}/knowledge-config", response_model=ProjectResponse)
async def update_knowledge_config(
    project_id: str,
    request: Request,
    config: ProjectKnowledgeConfigRequest
):
    """
    更新项目知识配置
    
    - **project_id**: 项目ID
    - **mode**: 配置模式（all/whitelist/blacklist）
    - **whitelist**: 知识ID白名单（mode=whitelist时生效）
    - **blacklist**: 知识ID黑名单（mode=blacklist时生效）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 更新知识配置
        project_service = get_project_service()
        project_dict = project_service.update_knowledge_config(
            project_id=project_id,
            user_id=user_id,
            mode=config.mode,
            whitelist=config.whitelist if config.mode == "whitelist" else None,
            blacklist=config.blacklist if config.mode == "blacklist" else None
        )
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "知识配置更新成功",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新知识配置失败"
        )


@project_router.put("/{project_id}/service-config", response_model=ProjectResponse)
async def update_service_config(
    project_id: str,
    request: Request,
    config: ProjectServiceConfigRequest
):
    """
    更新项目服务配置
    
    - **project_id**: 项目ID
    - **mode**: 配置模式（all/whitelist/blacklist）
    - **whitelist**: 服务ID白名单（mode=whitelist时生效）
    - **blacklist**: 服务ID黑名单（mode=blacklist时生效）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 更新服务配置
        project_service = get_project_service()
        project_dict = project_service.update_service_config(
            project_id=project_id,
            user_id=user_id,
            mode=config.mode,
            whitelist=config.whitelist if config.mode == "whitelist" else None,
            blacklist=config.blacklist if config.mode == "blacklist" else None
        )
        
        # 转换为响应格式
        response_data = _dict_to_project_response(project_dict)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "服务配置更新成功",
                "data": response_data.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新服务配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新服务配置失败"
        )
