"""
JWT认证服务
负责token的生成和验证
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from textmsa.logging_config import get_logger
from textmsa.services.core.config_manager import get_config
from textmsa.utils.session import get_user_id



logger = get_logger(__name__)

# 从配置读取设置
_config = get_config()
server_config = _config.get("server") or {}
DEV_MODE = bool(server_config.get("dev_mode", True))
DEV_TEST_USER_ID = str(server_config.get("dev_test_user_id", "test_user_id"))
DEV_TEST_USERNAME = str(server_config.get("dev_test_username", "test_user"))
DEV_TEST_TOKEN = str(server_config.get("dev_test_token", "test_123"))

# JWT配置
jwt_secret_key = server_config.get("jwt_secret_key")
if jwt_secret_key:
    SECRET_KEY = jwt_secret_key
else:
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(server_config.get("access_token_expire_minutes", 1440))  # 默认24小时

# HTTP Bearer认证
security = HTTPBearer()


def resolve_test_user_id(user_id: str) -> str:
    """
    解析测试用户ID（开发模式下将test_user_id映射到实际用户ID）
    
    Args:
        user_id: 原始用户ID
    
    Returns:
        解析后的用户ID（如果是test_user_id且开发模式开启，返回实际用户ID；否则返回原ID）
    """
    if DEV_MODE and user_id == DEV_TEST_USER_ID:
        try:
            from textmsa.services.user.user_service import get_user_service
            user_service = get_user_service()
            test_user = user_service.get_user_by_username(DEV_TEST_USERNAME)
            if test_user:
                resolved_id = test_user.get("user_id") or test_user.get("userId") or test_user.get("_id")
                if resolved_id:
                    logger.debug(f"开发模式：映射test_user_id到实际用户ID: {resolved_id}")
                    return resolved_id
        except Exception as e:
            logger.debug(f"开发模式：无法获取test_user的实际ID: {e}")
            # 如果获取失败，继续使用原ID
            pass
    return user_id


class AuthService:
    """认证服务类"""
    
    def __init__(self, secret_key: str = SECRET_KEY, algorithm: str = ALGORITHM):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(self, user_id: str, username: str = None, expires_delta: Optional[timedelta] = None) -> str:
        """
        创建访问token（已废弃，请使用UserService.login()）
        
        注意：此方法保留用于向后兼容，但实际应该使用UserService.login()
        来生成和存储token。
        
        Args:
            user_id: 用户ID
            username: 用户名（已废弃，不再使用）
            expires_delta: 过期时间增量（已废弃，不再使用）
        
        Returns:
            token字符串
        """
        # 为了向后兼容，这里仍然生成一个token，但不存储
        # 实际应该使用UserService.login()来生成token
        logger.warning("create_access_token()已废弃，请使用UserService.login()")
        return secrets.token_urlsafe(32)
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        验证token并返回用户信息
        
        Args:
            token: token字符串
        
        Returns:
            包含用户信息的字典
        
        Raises:
            HTTPException: 如果token无效
        """
        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token无效"
            )
        
        # 调用UserService根据token查询用户
        from textmsa.services.user.user_service import get_user_service
        user_service = get_user_service()
        user = user_service.get_user_by_token(token.strip())
        
        if not user:
            logger.warning(f"Token验证失败: token无效")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token无效或已过期"
            )
        
        return {
            "user_id": user["user_id"],
            "username": user.get("username")
        }


# 全局认证服务实例
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """获取全局认证服务实例"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def create_access_token(user_id: str, username: str = None, expires_delta: Optional[timedelta] = None) -> str:
    """便捷函数：创建访问token（已废弃，请使用UserService.login()）"""
    return get_auth_service().create_access_token(user_id, username, expires_delta)


def verify_token(token: str) -> Dict[str, Any]:
    """便捷函数：验证token"""
    return get_auth_service().verify_token(token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    FastAPI依赖：从请求头获取当前用户
    
    Args:
        credentials: HTTP Bearer认证凭证
    
    Returns:
        包含用户信息的字典
    
    Raises:
        HTTPException: 如果token无效或过期
    """
    token = credentials.credentials
    return verify_token(token)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict[str, Any]]:
    """
    FastAPI依赖：从请求头获取当前用户（可选）
    
    Args:
        credentials: HTTP Bearer认证凭证（可选）
    
    Returns:
        包含用户信息的字典，如果未提供token则返回None
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        return verify_token(token)
    except HTTPException:
        return None


async def get_current_user_from_header(
    request: Any = None,
    token: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    从请求头获取当前用户（支持多种token格式）
    
    Args:
        request: FastAPI Request对象（可选）
        token: token字符串（可选，直接提供）
    
    Returns:
        包含用户信息的字典，如果未提供token则返回None（测试环境下直接返回test_user）
    """
    # 测试环境：直接返回test_user
    if DEV_MODE:
        # 尝试从数据库获取test_user的实际ID
        try:
            from textmsa.services.user.user_service import get_user_service
            user_service = get_user_service()
            test_user = user_service.get_user_by_username(DEV_TEST_USERNAME)
            if test_user:
                logger.debug(f"测试环境：返回test_user，实际ID: {test_user.get('user_id') or test_user.get('userId')}")
                return {
                    "user_id": test_user.get("user_id") or test_user.get("userId") or test_user.get("_id") or DEV_TEST_USER_ID,
                    "username": DEV_TEST_USERNAME
                }
        except Exception as e:
            logger.debug(f"测试环境：无法获取test_user的实际ID，使用默认ID: {e}")
        
        # 如果获取失败，使用默认ID
        logger.debug(f"测试环境：返回test_user，默认ID: {DEV_TEST_USER_ID}")
        return {
            "user_id": DEV_TEST_USER_ID,
            "username": DEV_TEST_USERNAME
        }
    
    # 生产模式：正常验证token
    if token:
        try:
            return verify_token(token)
        except HTTPException as e:
            logger.warning(f"Token验证失败（直接提供）: {e.detail}")
            return None
    
    if request is not None:

        # 从cookie中获取
        user_id = get_user_id(request=request)
        if user_id:
            return {"user_id": user_id}

        # 尝试从Authorization头获取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                return verify_token(token)
            except HTTPException as e:
                logger.warning(f"Token验证失败（Authorization头）: {e.detail}")
        
        # 尝试从token头获取
        token_header = request.headers.get("token")
        if token_header:
            try:
                return verify_token(token_header)
            except HTTPException as e:
                logger.warning(f"Token验证失败（token头）: {e.detail}")

        # 尝试从查询参数获取（支持 ?token= 或 ?access_token=）
        try:
            query_token = request.query_params.get("token") or request.query_params.get("access_token")
        except Exception:
            query_token = None

        if query_token:
            try:
                return verify_token(query_token)
            except HTTPException as e:
                logger.warning(f"Token验证失败（查询参数）: {e.detail}")
        
        # 记录未找到token的情况
        if not auth_header and not token_header and not query_token:
            logger.warning(f"未找到token（请求路径: {request.url.path}）")
    
    return None

