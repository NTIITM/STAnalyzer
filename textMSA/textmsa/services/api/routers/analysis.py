"""
分析流程API路由
"""
import asyncio
import json
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse, StreamingResponse

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.analysis.analysis_service import get_analysis_service
from textmsa.services.analysis.cascade_deletion_service import get_cascade_deletion_service
from textmsa.services.analysis.file_analysis_service import get_file_analysis_service
from textmsa.services.analysis.tools.file_reader_tool import FileReaderTool
from textmsa.services.file.file_service import get_file_service
from textmsa.services.service.service_service import get_service_service
from textmsa.services.agent.read_agent import astream_read_agent, astream_read_agent_from_execution
from textmsa.services.api.schemas import (
    UpdateAlgorithmStatusRequest,
    ExecutionDeleteResponse,
    FileAnalysisResponse,
)
from textmsa.services.agent.agent_service import get_agent_service
logger = get_logger(__name__)

# 创建路由
analysis_router = APIRouter(prefix="/api/analysis", tags=["分析流程"])


@analysis_router.get("/project/{projectId}/tree")
async def get_project_analysis_tree(
    projectId: str,
    request: Request
):
    """
    获取项目分析流程树形结构（合并多个文件的分析树）
    
    - **projectId**: 项目ID
    
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
        
        # 获取项目分析树
        analysis_service = get_analysis_service()
        tree_data = analysis_service.get_project_analysis_tree(projectId, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": tree_data
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目分析树失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目分析树失败"
        )


@analysis_router.get("/execution/{executionId}")
async def get_execution(
    executionId: str,
    request: Request
):
    """
    获取执行记录详情
    
    - **executionId**: 执行ID
    
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
        
        # 获取执行记录详情
        analysis_service = get_analysis_service()
        execution = analysis_service.get_execution_by_id(executionId, user_id)
        
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
            detail="获取执行记录失败"
        )


@analysis_router.put("/execution/{executionId}/status")
async def update_execution_status(
    executionId: str,
    request: Request,
    status_request: UpdateAlgorithmStatusRequest
):
    """
    更新执行记录状态
    
    - **executionId**: 执行ID
    
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
        
        # 更新执行状态
        analysis_service = get_analysis_service()
        success = analysis_service.update_execution_status_by_id(
            executionId,
            user_id,
            status_request.status,
            status_request.output_file.model_dump() if status_request.output_file else None,
            status_request.error
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新执行状态失败"
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "success": True,
                    "message": "执行状态更新成功"
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新执行状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新执行状态失败"
        )


@analysis_router.delete("/execution/{executionId}", response_model=ExecutionDeleteResponse)
async def delete_execution(
    executionId: str,
    request: Request,
    project_id: Optional[str] = Query(
        None,
        alias="projectId",
        description="限定删除范围的项目ID（可选）",
    ),
):
    """
    删除执行记录及其衍生文件

    - **executionId**: 执行ID
    - **project_id**: 限定删除范围的项目ID（可选）

    需要提供Authorization头或token头
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录",
            )

        user_id = user_info["user_id"]
        cascade_service = get_cascade_deletion_service()
        deletion_result = cascade_service.delete_executions(
            user_id=user_id,
            root_execution_ids=[executionId],
            project_ids=[project_id] if project_id else None,
        )

        if executionId not in deletion_result.get("deleted_execution_ids", []):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除执行失败",
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": deletion_result,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除执行失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除执行失败",
        )


@analysis_router.post("/analyze", response_model=FileAnalysisResponse)
async def analyze_file(
    request: Request,
    file_id: str = Query(..., description="文件ID"),
    query: str = Query("", description="分析查询/问题（可选）")
):
    """
    分析文件
    
    - **file_id**: 文件ID（必填）
    - **query**: 分析查询/问题（可选，用于指导分析）
    
    需要提供Authorization头或token头
    
    根据文件类型自动路由到相应的分析工具：
    - 文本文件（txt, log, md, json）：使用 LLM 解读
    - H5AD 文件（h5ad）：使用 H5AD Agent 进行智能分析
    - 数据文件（csv, excel）：使用 PythonREPL 分析
    - 图片文件（png, jpg, jpeg等）：使用多模态 LLM 解读
    - 其他文件：使用默认预览
    """
    # API 层使用 try-catch 捕获所有异常，转换为统一响应格式
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 调用服务层进行分析
        file_analysis_service = get_file_analysis_service()
        result = file_analysis_service.analyze_file(
            file_id=file_id,
            user_id=user_id,
            query=query,
        )
        
        # 返回成功响应
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "分析成功",
                "data": FileAnalysisResponse(
                    file_id=file_id,
                    query=query,
                    result=result,
                    success=True,
                    error_message=None,
                ).model_dump()
            }
        )
    
    except HTTPException:
        # 重新抛出 HTTPException，保持原有状态码和错误信息
        raise
    
    except Exception as e:
        # 捕获所有其他异常，转换为统一响应格式
        logger.error(
            f"文件分析失败: {e}",
            extra={"file_id": file_id, "query": query},
            exc_info=True,
        )
        
        # 返回错误响应
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 500,
                "message": "分析失败",
                "data": FileAnalysisResponse(
                    file_id=file_id,
                    query=query,
                    result="",
                    success=False,
                    error_message=str(e),
                ).model_dump()
            }
        )


@analysis_router.post("/analyze/stream")
async def analyze_file_stream(
    request: Request,
    file_id: str = Query(..., description="文件ID"),
    query: str = Query("", description="分析查询/问题（可选）"),
):
    """
    流式分析文件，SSE 返回进度和结果
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录",
            )

        user_id = user_info["user_id"]
        file_analysis_service = get_file_analysis_service()

        async def event_stream():
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def progress_cb(progress: dict) -> None:
                queue.put_nowait(
                    f"event: progress\ndata: {json.dumps(progress, ensure_ascii=False)}\n\n"
                )

            async def run_analysis():
                try:
                    await file_analysis_service.analyze_file_async(
                        file_id=file_id,
                        user_id=user_id,
                        query=query,
                        progress_cb=progress_cb,
                    )
                    queue.put_nowait("event: end\ndata: success\n\n")
                except Exception as e:
                    logger.error(
                        f"文件流式分析失败: {e}",
                        extra={"file_id": file_id, "query": query},
                        exc_info=True,
                    )
                    error_payload = {
                        "code": 500,
                        "message": "分析失败",
                        "data": FileAnalysisResponse(
                            file_id=file_id,
                            query=query,
                            result="",
                            success=False,
                            error_message=str(e),
                        ).model_dump(),
                    }
                    queue.put_nowait(
                        f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    )
                finally:
                    queue.put_nowait(None)

            asyncio.create_task(run_analysis())

            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"文件流式分析失败: {e}",
            extra={"file_id": file_id, "query": query},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 500,
                "message": "分析失败",
                "data": FileAnalysisResponse(
                    file_id=file_id,
                    query=query,
                    result="",
                    success=False,
                    error_message=str(e),
                ).model_dump(),
            },
        )


@analysis_router.post("/analyze-execution/stream/deep")
async def analyze_execution_stream(
    request: Request,
    execution_id: str = Query(..., description="执行ID"),
    query: str = Query("", description="分析查询/问题（可选）"),
):
    """
    流式excution中所有文件的分析，SSE 返回进度和结果
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录",
            )

        user_id = user_info["user_id"]

        async def event_stream():
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def progress_cb(progress: dict) -> None:
                queue.put_nowait(
                    f"event: progress\ndata: {json.dumps(progress, ensure_ascii=False)}\n\n"
                )

            async def run_analysis():
                try:
                    # Call Read Agent from execution
                    result = await astream_read_agent_from_execution(
                        execution_id=execution_id,
                        user_id=user_id,
                        query=query,
                        language="en",
                        on_event=progress_cb,
                    )
                    
                    # Send final result
                    # message = await asyncio.to_thread(
                    #     get_agent_service().build_message,
                    #     message=result.get("final_answer", ""),
                    # )
                    # queue.put_nowait(
                    #     f"event: result\ndata: {json.dumps(message, ensure_ascii=False)}\n\n"
                    # )
                except Exception as e:
                    logger.error(
                        f"Failed to execute streaming analysis: {e}",
                        extra={"execution_id": execution_id, "query": query},
                        exc_info=True,
                    )
                    error_payload = {
                        "code": 500,
                        "message": "Analysis failed",
                        "data": {
                            "execution_id": execution_id,
                            "query": query,
                            "error_message": str(e),
                        },
                    }
                    queue.put_nowait(
                        f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    )
                finally:
                    queue.put_nowait(None)

            asyncio.create_task(run_analysis())

            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"执行流式分析失败: {e}",
            extra={"execution_id": execution_id, "query": query},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 500,
                "message": "分析失败",
                "data": {
                    "execution_id": execution_id,
                    "query": query,
                    "error_message": str(e),
                },
            },
        )


@analysis_router.post("/analyze-file/stream/deep")
async def analyze_file_stream_deep(
    request: Request,
    file_id: str = Query(..., description="文件ID"),
    query: str = Query("", description="分析查询/问题（可选）"),
):
    """
    流式深度分析文件（使用 Read Agent），SSE 返回进度和结果
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录",
            )

        user_id = user_info["user_id"]
        file_service = get_file_service()
        file_reader_tool = FileReaderTool()

        async def event_stream():
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def progress_cb(progress: dict) -> None:
                queue.put_nowait(
                    f"event: progress\ndata: {json.dumps(progress, ensure_ascii=False)}\n\n"
                )

            async def run_analysis():
                try:
                    # Get file information
                    progress_cb({"message": "Fetching file information..."})
                    file_info = await asyncio.to_thread(
                        file_service.get_file_info, file_id, user_id
                    )
                    filename = file_info.get("filename", "unknown")
                    file_path = file_info.get("file_path")
                    
                    if not file_path:
                        raise ValueError("File path not found")

                    # Get file type and preview
                    file_ext = os.path.splitext(filename)[1].lower()
                    file_type_name = file_ext[1:] if file_ext else "unknown"
                    
                    progress_cb({"message": "Reading file preview..."})
                    preview = await asyncio.to_thread(
                        file_reader_tool._read_preview,  # type: ignore[attr-defined]
                        file_path,
                        file_type_name,
                        filename,
                    )

                    # 构建文件树节点
                    file_tree_node: dict = {
                        "file_id": file_id,
                        "file_name": filename,
                        "file_path": file_path,
                        "description": file_info.get("description", ""),
                        "preview": json.dumps(preview, ensure_ascii=False),
                        "children": [],
                    }
                    # 添加 file_type_id（如果存在）
                    file_type_id = file_info.get("file_type_id")
                    if file_type_id:
                        file_tree_node["file_type_id"] = file_type_id

                    # Get project_id (from file_id)
                    project_id = None
                    try:
                        from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
                        user_data_manager = get_user_data_manager()
                        project_ids = await asyncio.to_thread(
                            user_data_manager.find_project_ids_by_file,
                            user_id=user_id,
                            file_id=file_id
                        )
                        if project_ids:
                            project_id = project_ids[0]
                    except Exception as e:
                        logger.warning(
                            f"Failed to get project_id: {file_id}, {e}",
                            extra={"file_id": file_id}
                        )
                    
                    # Call Read Agent
                    result = await astream_read_agent(
                        user_query=query or "Please analyze the basic information and content of this file.",
                        file_tree_list=[file_tree_node],
                        user_id=user_id,
                        project_id=project_id,
                        language="en",
                        on_event=progress_cb,
                    )
                    # message = await asyncio.to_thread(
                    #     get_agent_service().build_message,
                    #     message=result.get("final_answer", ""),
                    # )
                    # queue.put_nowait(
                    #     f"event: result\ndata: {json.dumps(message, ensure_ascii=False)}\n\n"
                    # )
                except Exception as e:
                    logger.error(
                        f"Failed to execute streaming file analysis: {e}",
                        extra={"file_id": file_id, "query": query},
                        exc_info=True,
                    )
                    error_payload = {
                        "code": 500,
                        "message": "Analysis failed",
                        "data": FileAnalysisResponse(
                            file_id=file_id,
                            query=query,
                            result="",
                            success=False,
                            error_message=str(e),
                        ).model_dump(),
                    }
                    queue.put_nowait(
                        f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    )
                finally:
                    queue.put_nowait(None)

            asyncio.create_task(run_analysis())

            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to execute streaming file analysis: {e}",
            extra={"file_id": file_id, "query": query},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 500,
                "message": "Analysis failed",
                "data": FileAnalysisResponse(
                    file_id=file_id,
                    query=query,
                    result="",
                    success=False,
                    error_message=str(e),
                ).model_dump(),
            },
        )

