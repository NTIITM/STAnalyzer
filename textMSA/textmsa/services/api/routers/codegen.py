"""
代码生成API路由
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.codegen.codegen_service import get_codegen_service
from textmsa.services.api.schemas import (
    CodegenTemplateResponse,
    CodegenTemplateListResponse,
    CodegenUpdateRequest,
    CodegenExecuteRequest,
    CodegenExecuteResponse,
    CodegenExecutionResponse,
    CodegenExecutionListResponse,
)

logger = get_logger(__name__)

# 创建路由
codegen_router = APIRouter(prefix="/api/codegen", tags=["代码生成"])


@codegen_router.get("/templates/{template_id}", response_model=CodegenTemplateResponse)
async def get_template(
    template_id: str,
    request: Request
):
    """
    获取代码模板信息
    
    - **template_id**: 模板ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 获取模板信息
        codegen_service = get_codegen_service()
        template = codegen_service.get_template(template_id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": template
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板信息失败: {str(e)}"
        )


@codegen_router.get("/templates", response_model=CodegenTemplateListResponse)
async def list_templates(
    request: Request,
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量")
):
    """
    获取代码模板列表
    
    - **skip**: 跳过数量（可选，默认0）
    - **limit**: 返回数量（可选，默认100，最大1000）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 获取模板列表
        codegen_service = get_codegen_service()
        result = codegen_service.list_templates(user_id=user_id, skip=skip, limit=limit)
        
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
        logger.error(f"获取模板列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板列表失败: {str(e)}"
        )


@codegen_router.put("/templates/{template_id}", response_model=CodegenTemplateResponse)
async def update_template(
    template_id: str,
    request: Request,
    update_request: CodegenUpdateRequest
):
    """
    更新代码模板（用于用户确认或修改代码）
    
    - **template_id**: 模板ID
    - **generated_code**: 生成的代码（可选）
    - **status**: 状态（可选，如'confirmed'）
    - **parameters**: 参数（可选）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 构建更新数据
        update_data = {}
        if update_request.generated_code is not None:
            update_data['generated_code'] = update_request.generated_code
        if update_request.status is not None:
            update_data['status'] = update_request.status
        if update_request.parameters is not None:
            update_data['parameters'] = update_request.parameters
        
        # 更新模板
        codegen_service = get_codegen_service()
        template = codegen_service.update_template(template_id, update_data, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "模板更新成功",
                "data": template
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新模板失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新模板失败: {str(e)}"
        )


@codegen_router.post("/templates/{template_id}/confirm", response_model=CodegenTemplateResponse)
async def confirm_template(
    template_id: str,
    request: Request
):
    """
    确认模板（用户确认模板后，状态变为template_confirmed，可以生成代码）
    
    - **template_id**: 模板ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 确认模板
        codegen_service = get_codegen_service()
        template = codegen_service.confirm_template(template_id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "模板确认成功",
                "data": template
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"确认模板失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认模板失败: {str(e)}"
        )


@codegen_router.post("/templates/{template_id}/generate-code", response_model=CodegenTemplateResponse)
async def generate_code(
    template_id: str,
    request: Request
):
    """
    生成代码（模板确认后，生成代码，状态变为code_generated）
    
    - **template_id**: 模板ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 生成代码
        codegen_service = get_codegen_service()
        template = codegen_service.generate_code(template_id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "代码生成成功",
                "data": template
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成代码失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成代码失败: {str(e)}"
        )


@codegen_router.post("/templates/{template_id}/execute", response_model=CodegenExecuteResponse)
async def execute_template(
    template_id: str,
    request: Request,
    execute_request: CodegenExecuteRequest
):
    """
    执行模板代码（代码生成后，执行代码）
    
    - **template_id**: 模板ID
    - **parameters**: 执行参数（可选，覆盖模板默认参数）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 执行模板
        codegen_service = get_codegen_service()
        result = codegen_service.execute_template(
            template_id=template_id,
            user_id=user_id,
            parameters=execute_request.parameters
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "代码执行已启动",
                "data": result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行模板失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行模板失败: {str(e)}"
        )


@codegen_router.get("/executions/{execution_id}", response_model=CodegenExecutionResponse)
async def get_execution(
    execution_id: str,
    request: Request
):
    """
    获取代码执行记录
    
    - **execution_id**: 执行ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 获取执行记录
        codegen_service = get_codegen_service()
        execution = codegen_service.get_execution(execution_id)
        
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


@codegen_router.get("/executions", response_model=CodegenExecutionListResponse)
async def list_executions(
    request: Request,
    template_id: Optional[str] = Query(None, description="模板ID过滤"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量")
):
    """
    获取代码执行记录列表
    
    - **template_id**: 模板ID过滤（可选）
    - **skip**: 跳过数量（可选，默认0）
    - **limit**: 返回数量（可选，默认100，最大1000）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        # 获取执行记录列表
        codegen_service = get_codegen_service()
        result = codegen_service.list_executions(
            template_id=template_id,
            user_id=user_id,
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


@codegen_router.post("/templates/{template_id}/finalize", response_model=CodegenTemplateResponse)
async def finalize_template(
    template_id: str,
    request: Request
):
    """
    最终确认并保存（用户确认执行结果后，保存所有信息，状态变为finalized）
    
    - **template_id**: 模板ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        user_id = user_info.get("user_id") if user_info else None
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要登录"
            )
        
        # 最终确认并保存
        codegen_service = get_codegen_service()
        template = codegen_service.finalize_template(template_id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "模板最终确认并保存成功",
                "data": template
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"最终确认失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"最终确认失败: {str(e)}"
        )


