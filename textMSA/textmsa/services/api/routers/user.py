"""
用户API路由
"""
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.user.user_service import get_user_service
from textmsa.services.api.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserRegisterResponse,
    UserLoginResponse,
    UserInfoResponse,
    UserProfileUpdateRequest,
    UserPasswordChangeRequest
)
from textmsa.utils.session import create_session, serializer, get_user_id

logger = get_logger(__name__)

# 创建路由
user_router = APIRouter(prefix="/api/user", tags=["用户管理"])

@user_router.post("/register", response_model=UserRegisterResponse)
async def register(request: UserRegisterRequest):
    """
    用户注册
    
    - **username**: 用户名（必填）
    - **password**: 密码（必填，至少6位）
    - **email**: 邮箱（必填）
    """
    try:
        user_service = get_user_service()
        result = user_service.register(
            username=request.username,
            password=request.password,
            email=request.email
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "注册成功",
                "data": {
                    "user_id": result["user_id"]
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户注册失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )

# TODO: 刷新cookie接口
@user_router.post("/refresh")
async def refresh(request: Request):
    try:
        user_id = get_user_id(request)
    except HTTPException:
        raise

@user_router.post("/login", response_model=UserLoginResponse)
async def login(request: UserLoginRequest):
    """
    用户登录（token优先，无密码验证）
    
    - **token**: token字符串（可选）
        - 如果提供且token存在：验证token并返回用户信息
        - 如果提供但token不存在：创建新用户并使用该token
        - 如果不提供：自动创建新用户并生成token
    - **username**: 用户名（可选，如果提供则忽略）
    - **password**: 密码（可选，如果提供则忽略）
    
    注意：如果提供的token已被其他用户使用，将返回409冲突错误
    """
    try:
        
        user_service = get_user_service()
        result = user_service.login(token=request.token if hasattr(request, 'token') and request.token else None)
        
        user_id = result["user_id"]
        token = result["token"]
        username = result["username"]
        
        session_id = create_session(user_id)
        signed_session_id = serializer.dumps(session_id)
        
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "登录成功",
                "data": {
                    "token": token,
                    "user_id":  user_id,
                    "username": username
                }
            }
        )
        # 设置认证 Cookie
        response.set_cookie(
            key="session_token",
            value=signed_session_id,
            httponly=True,  # HttpOnly: 防止 XSS
            secure=False,   # 本地开发 False，生产环境 True (HTTPS)
            samesite="lax", # SameSite: 防止 CSRF
            max_age=60 * 60 * 24 * 30 * 12,   # 过期时间 (秒)
            path="/"
        )
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@user_router.get("/info", response_model=UserInfoResponse)
async def get_user_info(request: Request):
    """
    获取当前用户信息
    
    需要提供Authorization头或token头（开发模式下可选）
    """
    try:
        # 从请求头获取用户信息
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        # 开发模式下，如果是test_user_id，直接返回test_user信息
        from textmsa.services.auth.auth_service import DEV_MODE, DEV_TEST_USER_ID, DEV_TEST_USERNAME
        if DEV_MODE and user_info.get("user_id") == DEV_TEST_USER_ID:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "code": 200,
                    "message": "success",
                    "data": {
                        "user_id": DEV_TEST_USER_ID,
                        "username": DEV_TEST_USERNAME,
                        "email": "test_user@example.com"
                    }
                }
            )
        
        # 获取完整用户信息
        user_service = get_user_service()
        user = user_service.get_user_info(user_info["user_id"])
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "email": user.get("email")
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


@user_router.put("/info", response_model=UserInfoResponse)
@user_router.put("/profile", response_model=UserInfoResponse)  # 添加 /profile 路由作为别名
async def update_user_profile(payload: UserProfileUpdateRequest, request: Request):
    """
    更新当前用户的基础信息（用户名 / 邮箱）
    
    - **username**: 新用户名（可选）
    - **email**: 新邮箱（可选）
    
    至少需要提供其中一个字段
    
    支持路径：
    - PUT /api/user/info
    - PUT /api/user/profile
    """
    try:
        user_info = await get_current_user_from_header(request=request)

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )

        user_service = get_user_service()
        updated_user = user_service.update_profile(
            user_id=user_info["user_id"],
            username=payload.username,
            email=payload.email
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "用户信息更新成功",
                "data": updated_user
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户信息失败"
        )


@user_router.put("/password")
async def change_user_password(payload: UserPasswordChangeRequest, request: Request):
    """
    修改当前用户密码
    """
    try:
        user_info = await get_current_user_from_header(request=request)

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )

        user_service = get_user_service()
        user_service.change_password(
            user_id=user_info["user_id"],
            current_password=payload.current_password,
            new_password=payload.new_password
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "密码更新成功",
                "data": {"updated": True}
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改密码失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="修改密码失败"
        )
