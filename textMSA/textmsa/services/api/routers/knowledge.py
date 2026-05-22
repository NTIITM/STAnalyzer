"""
Knowledge API 路由
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from textmsa.logging_config import get_logger
from textmsa.services.api.schemas import (
    KnowledgeCreateRequest,
    KnowledgeListResponse,
    KnowledgePromptConfigRequest,
    KnowledgePromptConfigResponse,
    KnowledgeShareRequest,
    KnowledgeUpdateRequest,
    KnowledgeItemResponse,
    KnowledgeExtractTextRequest,
    KnowledgeExtractLiteratureRequest,
    KnowledgeExtractPromptRequest,
    KnowledgePromptApproveRequest,
    KnowledgeDocumentDictCreateRequest,
    KnowledgeDocumentDictResponse,
    KnowledgeDocumentDictDeleteResponse,
    KnowledgeDocumentDictListByProjectResponse,
    KnowledgeDocumentDictGroupedResponse,
)
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.knowledge import get_knowledge_service
from textmsa.services.knowledge_service import get_knowledge_search_service
from textmsa.services.knowledge_service.knowledge_document_dict_service import (
    get_knowledge_document_dict_service,
)
from textmsa.services.knowledge_service.models import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from textmsa.services.data.mongodb_models import KnowledgeDocumentDict

logger = get_logger(__name__)

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["知识管理"])



@knowledge_router.get("/list", response_model=KnowledgeListResponse)
@knowledge_router.get("", response_model=KnowledgeListResponse)  # 处理不带尾部斜杠的路径
@knowledge_router.get("/", response_model=KnowledgeListResponse)  # 处理带尾部斜杠的路径
async def list_knowledge(
    request: Request,
    scope: Optional[str] = Query(None, description="范围过滤"),
    keyword: Optional[str] = Query(None, description="关键词"),
    edited_only: bool = Query(False, alias="editedOnly", description="仅查看用户编辑"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize", description="每页数量"),
    sort: str = Query("latest", description="排序（latest/oldest）"),
    project_id: Optional[str] = Query(None, alias="projectId", description="项目ID（用于项目过滤）"),
):
    """获取知识列表"""
    try:
        user_info = await get_current_user_from_header(request=request)
        service = get_knowledge_service()
        result = service.list_knowledge(
            scope=scope,
            keyword=keyword,
            edited_only=edited_only,
            page=page,
            page_size=page_size,
            sort=sort,
            user_id=user_info.get("user_id") if user_info else None,
            project_id=project_id,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取知识列表失败"
        )


@knowledge_router.get("/{knowledge_id}", response_model=KnowledgeItemResponse)
async def get_knowledge_detail(knowledge_id: str, request: Request):
    """获取知识详情"""
    try:
        user_info = await get_current_user_from_header(request=request)
        service = get_knowledge_service()
        item = service.get_knowledge(knowledge_id, user_info.get("user_id") if user_info else None)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": item,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取知识详情失败"
        )


@knowledge_router.post("/", response_model=KnowledgeItemResponse, status_code=201)
async def create_knowledge(payload: KnowledgeCreateRequest, request: Request):
    """创建知识"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        item = service.create_knowledge(payload.model_dump(), user_info.get("user_id"))
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "code": 201,
                "message": "知识创建成功",
                "data": item,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建知识失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建知识失败"
        )


@knowledge_router.put("/{knowledge_id}", response_model=KnowledgeItemResponse)
async def update_knowledge(knowledge_id: str, payload: KnowledgeUpdateRequest, request: Request):
    """更新知识"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        item = service.update_knowledge(knowledge_id, payload.model_dump(exclude_unset=True), user_info.get("user_id"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "知识更新成功",
                "data": item,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新知识失败"
        )


@knowledge_router.delete("/{knowledge_id}")
async def delete_knowledge(knowledge_id: str, request: Request):
    """删除知识"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        service.delete_knowledge(knowledge_id, user_info.get("user_id"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "知识删除成功",
                "data": {"deleted": True},
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除知识失败"
        )


@knowledge_router.put("/{knowledge_id}/share", response_model=KnowledgeItemResponse)
@knowledge_router.post("/{knowledge_id}/share", response_model=KnowledgeItemResponse)
async def share_knowledge(knowledge_id: str, payload: KnowledgeShareRequest, request: Request):
    """分享知识"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        item = service.share_knowledge(
            knowledge_id,
            note=payload.note,
            user_id=user_info.get("user_id"),
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "分享成功",
                "data": item,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分享知识失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="分享知识失败"
        )


# @knowledge_router.get("/prompts/templates", response_model=List[Dict[str, Any]])
# async def list_prompt_templates():
#     """获取系统预设的 Prompt 模板列表（保留用于兼容）"""
#     try:
#         service = get_knowledge_service()
#         templates = service.get_prompt_templates()
#         return JSONResponse(
#             status_code=status.HTTP_200_OK,
#             content={
#                 "code": 200,
#                 "message": "success",
#                 "data": templates,
#             },
#         )
#     except Exception as e:
#         logger.error(f"获取Prompt模板列表失败: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="获取Prompt模板列表失败"
#         )


@knowledge_router.get("/prompts/templates", response_model=List[KnowledgePromptConfigResponse])
async def list_prompt_configs(request: Request):
    """列出用户的所有 Prompt 配置模板"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.list_prompt_configs(user_info.get("user_id"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Prompt配置列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Prompt配置列表失败"
        )


@knowledge_router.get("/prompts/current", response_model=KnowledgePromptConfigResponse)
async def get_prompt_config(
    request: Request,
    template_id: Optional[str] = Query(None, description="模板ID（可选，不指定则返回默认模板）")
):
    """获取当前 Prompt 配置（如果指定 template_id 则获取指定模板，否则获取默认模板）"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.get_prompt_config(
            user_info.get("user_id"),
            template_id=template_id
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Prompt配置失败"
        )


@knowledge_router.post("/prompts/configs", response_model=KnowledgePromptConfigResponse)
async def create_prompt_config(payload: KnowledgePromptConfigRequest, request: Request):
    """创建新的 Prompt 配置模板"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.create_prompt_config(
            user_info.get("user_id"),
            payload.model_dump()
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "创建成功",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建Prompt配置失败"
        )


@knowledge_router.put("/prompts/configs/{template_id}", response_model=KnowledgePromptConfigResponse)
async def update_prompt_config(
    template_id: str,
    payload: KnowledgePromptConfigRequest,
    request: Request
):
    """更新指定的 Prompt 配置模板"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.update_prompt_config(
            user_info.get("user_id"),
            template_id,
            payload.model_dump()
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "更新成功",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新Prompt配置失败"
        )


@knowledge_router.delete("/prompts/configs/{template_id}")
async def delete_prompt_config(template_id: str, request: Request):
    """删除指定的 Prompt 配置模板"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        service.delete_prompt_config(
            user_info.get("user_id"),
            template_id
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "删除成功",
                "data": None,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除Prompt配置失败"
        )


@knowledge_router.put("/prompts/current", response_model=KnowledgePromptConfigResponse)
async def save_prompt_config(payload: KnowledgePromptConfigRequest, request: Request):
    """保存 Prompt 配置（兼容旧接口，如果 template_id 存在则更新，否则创建）"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.save_prompt_config(
            user_info.get("user_id"),
            payload.model_dump()
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "保存成功",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存Prompt配置失败"
        )


# ============= 三种提取模式端点 =============

@knowledge_router.post("/extract/text")
async def extract_from_text(payload: KnowledgeExtractTextRequest, request: Request):
    """从文本提取知识（文本提取模式）"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        triplets = service.extract_from_text(
            text=payload.text,
            user_id=user_info.get("user_id"),
            template_id=payload.template_id,
            source=payload.source
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "提取成功",
                "data": triplets,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从文本提取知识失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="从文本提取知识失败"
        )


@knowledge_router.post("/extract/literature")
async def extract_from_literature(payload: KnowledgeExtractLiteratureRequest, request: Request):
    """从文献提取知识（文献提取模式）"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        triplets = service.extract_from_literature(
            query=payload.query,
            user_id=user_info.get("user_id"),
            template_id=payload.template_id,
            max_results=payload.max_results
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "提取成功",
                "data": triplets,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从文献提取知识失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="从文献提取知识失败"
        )


@knowledge_router.post("/extract/prompt")
async def extract_prompt(payload: KnowledgeExtractPromptRequest, request: Request):
    """生成提示词（提示词生成模式）"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.generate_prompt(
            query=payload.query,
            user_id=user_info.get("user_id"),
            description=payload.description
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "提示词生成成功",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成提示词失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成提示词失败"
        )


# ============= Prompt管理端点（别名） =============

@knowledge_router.get("/prompt/templates", response_model=List[Dict[str, Any]])
async def get_prompt_templates_alias():
    """获取系统预设的 Prompt 模板列表"""
    try:
        service = get_knowledge_service()
        templates = service.get_prompt_templates()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": templates,
            },
        )
    except Exception as e:
        logger.error(f"获取Prompt模板列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Prompt模板列表失败"
        )


@knowledge_router.get("/prompt/config", response_model=KnowledgePromptConfigResponse)
async def get_prompt_config_endpoint(
    request: Request,
    template_id: Optional[str] = Query(None, description="模板ID（可选，不指定则返回默认模板）")
):
    """获取当前 Prompt 配置"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.get_prompt_config(
            user_info.get("user_id"),
            template_id=template_id
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Prompt配置失败"
        )


@knowledge_router.put("/prompt/config", response_model=KnowledgePromptConfigResponse)
async def update_prompt_config_endpoint(payload: KnowledgePromptConfigRequest, request: Request):
    """保存 Prompt 配置"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.save_prompt_config(
            user_info.get("user_id"),
            payload.model_dump()
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "保存成功",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存Prompt配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存Prompt配置失败"
        )


@knowledge_router.post("/prompt/approve", response_model=KnowledgePromptConfigResponse)
async def approve_prompt(payload: KnowledgePromptApproveRequest, request: Request):
    """审批并保存生成的提示词"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        service = get_knowledge_service()
        result = service.approve_prompt(
            pending_prompt_id=payload.pending_prompt_id,
            user_id=user_info.get("user_id"),
            template_id=payload.template_id,
            name=payload.name,
            is_default=payload.is_default
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "审批成功",
                "data": result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审批提示词失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="审批提示词失败"
        )


@knowledge_router.post("/document-dict", response_model=KnowledgeDocumentDictResponse)
async def create_document_dict(payload: KnowledgeDocumentDictCreateRequest, request: Request):
    """创建或更新知识文档字典（以 title 为主键）"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        service = get_knowledge_document_dict_service()
        
        # 创建 KnowledgeDocumentDict 对象
        document = KnowledgeDocumentDict(
            title=payload.title,
            project_id=payload.project_id,
            query=payload.query,
            source=payload.source,
            snippet=payload.snippet,
            url=payload.url,
            doi=payload.doi,
            published_at=payload.published_at,
            authors=payload.authors,
            journal=payload.journal,
            source_type=payload.source_type,
            score=payload.score,
            metadata=payload.metadata,
        )
        
        # 创建或更新文档
        result = service.create_or_update_document_dict(document)
        
        # 转换为响应格式
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "title": result.title,
                    "project_id": result.project_id,
                    "query": result.query,
                    "source": result.source,
                    "snippet": result.snippet,
                    "url": result.url,
                    "doi": result.doi,
                    "published_at": result.published_at,
                    "authors": result.authors,
                    "journal": result.journal,
                    "source_type": result.source_type,
                    "score": result.score,
                    "metadata": result.metadata,
                    "created_at": result.created_at.isoformat() if result.created_at else None,
                    "updated_at": result.updated_at.isoformat() if result.updated_at else None,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建或更新文档字典失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建或更新文档字典失败: {str(e)}"
        )


@knowledge_router.get("/document-dict", response_model=KnowledgeDocumentDictResponse)
async def get_document_dict(request: Request, title: str = Query(..., description="文档标题")):
    """根据 title 获取知识文档字典"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        service = get_knowledge_document_dict_service()
        
        # 查询文档
        document = service.get_document_dict_by_title(title)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档标题 '{title}' 不存在"
            )
        
        # 转换为响应格式
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "title": document.title,
                    "project_id": document.project_id,
                    "query": document.query,
                    "source": document.source,
                    "snippet": document.snippet,
                    "url": document.url,
                    "doi": document.doi,
                    "published_at": document.published_at,
                    "authors": document.authors,
                    "journal": document.journal,
                    "source_type": document.source_type,
                    "score": document.score,
                    "metadata": document.metadata,
                    "created_at": document.created_at.isoformat() if document.created_at else None,
                    "updated_at": document.updated_at.isoformat() if document.updated_at else None,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档字典失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档字典失败: {str(e)}"
        )


@knowledge_router.delete("/document-dict", response_model=KnowledgeDocumentDictDeleteResponse)
async def delete_document_dict(request: Request, title: str = Query(..., description="文档标题")):
    """根据 title 删除知识文档字典"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        service = get_knowledge_document_dict_service()
        
        # 删除文档
        deleted = service.delete_document_dict_by_title(title)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档标题 '{title}' 不存在"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "删除成功",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档字典失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档字典失败: {str(e)}"
        )


@knowledge_router.get("/document-dict/project/{project_id}", response_model=KnowledgeDocumentDictListByProjectResponse)
async def list_document_dicts_by_project(project_id: str, request: Request):
    """根据 project_id 查询所有文档，并按 query 分组"""
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        service = get_knowledge_document_dict_service()
        
        # 查询并按 query 分组
        grouped_documents = service.get_document_dicts_by_project_grouped_by_query(project_id)
        
        # 转换为响应格式
        groups = []
        total_documents = 0
        for query, documents in grouped_documents.items():
            total_documents += len(documents)
            groups.append(
                KnowledgeDocumentDictGroupedResponse(
                    query=query,
                    documents=[
                        KnowledgeDocumentDictResponse(
                            title=doc.title,
                            project_id=doc.project_id,
                            query=doc.query,
                            source=doc.source,
                            snippet=doc.snippet,
                            url=doc.url,
                            doi=doc.doi,
                            published_at=doc.published_at,
                            authors=doc.authors,
                            journal=doc.journal,
                            source_type=doc.source_type,
                            score=doc.score,
                            metadata=doc.metadata,
                            created_at=doc.created_at.isoformat() if doc.created_at else None,
                            updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
                        )
                        for doc in documents
                    ]
                )
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "project_id": project_id,
                    "groups": [group.model_dump() for group in groups],
                    "total_queries": len(groups),
                    "total_documents": total_documents,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"根据项目ID查询文档字典失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"根据项目ID查询文档字典失败: {str(e)}"
        )


@knowledge_router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(payload: KnowledgeSearchRequest, request: Request):
    """面向真实数据源的知识检索入口（PubMed/ArXiv/CrossRef）。"""
    try:
        # 鉴权可选，允许匿名检索；获取用户信息便于后续项目配置扩展
        user_info = await get_current_user_from_header(request=request)
    except HTTPException:
        raise
    except Exception:
        user_info = None

    try:
        service = get_knowledge_search_service()
        result = await service.run(
            query=payload.query,
            project_id=payload.project_id,
            top_k=payload.top_k,
            rewrite=payload.rewrite,
            sources=payload.sources,
            trace=payload.trace,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result.model_dump(),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识检索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="知识检索失败"
        )
