"""
用户服务
负责用户注册、登录、信息查询等业务逻辑
"""
import secrets
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status
import bcrypt

from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config
from textmsa.services.file.file_manager import get_file_manager

logger = get_logger(__name__)


class UserService:
    """用户服务类"""
    
    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        """
        初始化用户服务
        
        Args:
            connection_string: MongoDB连接字符串（可选）
            database_name: 数据库名称（可选）
        """
        # 从配置文件读取MongoDB配置
        mongo_config = get_mongodb_config()
        
        connection_string = connection_string or mongo_config["uri"]
        database_name = database_name or mongo_config["database"]
        
        # 连接MongoDB
        try:
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
                connectTimeoutMS=mongo_config["connect_timeout_ms"],
                socketTimeoutMS=mongo_config["socket_timeout_ms"],
                maxPoolSize=mongo_config["max_pool_size"],
                minPoolSize=mongo_config["min_pool_size"]
            )
            self.client.admin.command('ping')
            logger.info("用户服务：成功连接到MongoDB")
        except Exception as e:
            logger.error(f"用户服务：无法连接到MongoDB: {e}")
            raise
        
        # 选择数据库和集合
        self.db = self.client[database_name]
        self.users_collection = self.db.users
        
        # 创建索引
        self._create_indexes()
    
    def _create_indexes(self):
        """创建数据库索引"""
        try:
            self.users_collection.create_index("email", unique=True, name="email_unique")
            self.users_collection.create_index("user_id", unique=True, name="user_id_unique")
            self.users_collection.create_index("token", unique=True, name="token_unique")
            logger.debug("用户服务：数据库索引创建完成")
        except Exception as e:
            logger.warning(f"用户服务：创建索引时出错（可能已存在）: {e}")
    
    def _hash_password(self, password: str) -> str:
        """
        使用bcrypt哈希密码
        
        Args:
            password: 明文密码
        
        Returns:
            bcrypt哈希后的密码（字符串格式）
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """
        验证密码
        
        Args:
            password: 明文密码
            hashed: 哈希后的密码
        
        Returns:
            是否匹配
        """
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def _generate_user_id(self) -> str:
        """
        生成用户ID（UUID格式）
        
        Returns:
            唯一的用户ID
        """
        return str(uuid.uuid4())
    
    def _generate_token(self) -> str:
        """
        生成安全随机token
        
        Returns:
            32字节的URL安全base64编码token字符串
        """
        return secrets.token_urlsafe(32)

    def get_user_work_dir_path(self, user_id: str) -> str:
        """
        获取用户的工作目录路径（位于输出目录下的用户子目录）
        """
        if not user_id:
            raise ValueError("user_id为空，无法获取工作目录")
        file_manager = get_file_manager()
        work_dir = file_manager.output_dir / user_id
        work_dir.mkdir(parents=True, exist_ok=True)
        return str(work_dir)
    
    def register(self, username: str, password: str, email: str) -> Dict[str, Any]:
        """
        注册新用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱
        
        Returns:
            包含用户信息的字典
        
        Raises:
            HTTPException: 如果用户名或邮箱已存在，或验证失败
        """
        # 清理输入
        username = username.strip() if username else ""
        email = email.strip().lower() if email else ""
        password = password.strip() if password else ""
        
        # 使用User模型进行验证（会抛出ValidationError）
        try:
            user_id = self._generate_user_id()
            now = datetime.utcnow()
            
            # 创建User模型实例进行验证
            user = User(
                user_id=user_id,
                username=username,
                password=password,  # 验证后会哈希
                email=email,
                created_at=now,
                updated_at=now
            )
        except Exception as e:
            error_msg = str(e)
            if "用户名不能为空" in error_msg or "min_length" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户名不能为空"
                )
            elif "密码长度至少6位" in error_msg or "min_length" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密码长度至少6位"
                )
            elif "email" in error_msg.lower() or "value is not a valid email" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱格式无效"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"验证失败: {error_msg}"
                )
        
        # 哈希密码
        hashed_password = self._hash_password(password)
        
        # 创建用户文档
        user_doc = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "password": hashed_password,  # 存储为password字段（与User模型一致）
            "created_at": now,
            "updated_at": now
        }
        
        try:
            # 插入用户
            self.users_collection.insert_one(user_doc)
            
            logger.info(f"用户注册成功: {username} ({user_id})")
            
            return {
                "user_id": user_id,
                "username": username,
                "email": email
            }
        
        except DuplicateKeyError as e:
            # 检查是用户名还是邮箱重复
            existing_user = self.users_collection.find_one({
                "$or": [
                    {"username": username},
                    {"email": email}
                ]
            })
            
            if existing_user and existing_user.get("username") == username:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户名已存在"
                )
            elif existing_user and existing_user.get("email") == email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="邮箱已被注册"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户已存在"
                )
        
        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="注册失败，请稍后重试"
            )
    
    def login(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        用户登录（token优先，无密码验证）
        
        Args:
            token: token字符串（可选）
                - 如果提供：根据token查询用户，如果存在则返回用户信息，如果不存在则创建新用户并使用该token
                - 如果不提供：自动创建新用户并生成token
        
        Returns:
            包含token和用户信息的字典
        
        Raises:
            HTTPException: 如果token已被使用或创建用户失败
        """
        # 如果提供了token，先验证是否存在
        if token:
            token = token.strip()
            if not token:
                # token为空或只有空格，当作未提供token处理
                token = None
            else:
                user = self.get_user_by_token(token)
                if user:
                    # Token存在，返回用户信息
                    logger.info(f"用户登录成功（token验证）: {user['username']} ({user['user_id']})")
                    return {
                        "token": token,
                        "user_id": user["user_id"],
                        "username": user["username"],
                        "email": user.get("email")
                    }
                else:
                    # Token不存在，创建新用户并使用这个token
                    logger.info(f"Token不存在，创建新用户并使用提供的token")
                    return self._create_user_with_token(token)
        
        # 如果没有提供token，自动创建新用户
        # 使用循环重试，避免递归导致栈溢出
        max_retries = 10  # 最大重试次数
        default_username = "default user"
        
        for attempt in range(max_retries):
            try:
                now = datetime.utcnow()
                user_id = self._generate_user_id()
                new_token = self._generate_token()
                
                # 创建用户文档
                user_doc = {
                    "user_id": user_id,
                    "username": default_username,
                    "email": f"{user_id}@default.local",  # 生成默认邮箱
                    "password": "",  # 保留字段但不使用
                    "token": new_token,
                    "created_at": now,
                    "updated_at": now
                }
                
                # 插入新用户
                self.users_collection.insert_one(user_doc)
                logger.info(f"自动创建新用户并登录: {default_username} ({user_id})")
                
                return {
                    "token": new_token,
                    "user_id": user_id,
                    "username": default_username,
                    "email": user_doc["email"]
                }
            
            except DuplicateKeyError as e:
                # 检查冲突的具体字段
                error_msg = str(e)
                if "token" in error_msg.lower():
                    logger.warning(f"Token冲突，重试生成 (尝试 {attempt + 1}/{max_retries})")
                elif "user_id" in error_msg.lower():
                    logger.warning(f"User ID冲突，重试生成 (尝试 {attempt + 1}/{max_retries})")
                else:
                    logger.warning(f"唯一键冲突，重试生成 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                
                # 如果达到最大重试次数，抛出错误
                if attempt == max_retries - 1:
                    logger.error(f"自动创建用户失败：达到最大重试次数 ({max_retries})，可能存在系统问题")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="登录失败：无法生成唯一标识，请稍后重试"
                    )
                # 否则继续下一次循环重试
                continue
        
        # 理论上不会到达这里，但为了安全起见
        logger.error("自动创建用户失败：未知错误")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )

    def _create_user_with_token(self, token: str) -> Dict[str, Any]:
        """
        使用指定的token创建新用户
        
        Args:
            token: 前端提供的token字符串
        
        Returns:
            包含token和用户信息的字典
        
        Raises:
            HTTPException: 如果token已被使用或创建用户失败
        """
        # 再次检查token是否已被使用（防止并发情况）
        user = self.get_user_by_token(token)
        if user:
            # Token已被使用，返回错误
            logger.warning(f"创建用户失败：提供的token已被使用")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Token已被使用，请使用其他token或重新生成"
            )
        
        # 使用循环重试，避免user_id冲突
        max_retries = 10  # 最大重试次数
        default_username = "default user"
        
        for attempt in range(max_retries):
            try:
                now = datetime.utcnow()
                user_id = self._generate_user_id()
                
                # 创建用户文档，使用提供的token
                user_doc = {
                    "user_id": user_id,
                    "username": default_username,
                    "email": f"{user_id}@default.local",  # 生成默认邮箱
                    "password": "",  # 保留字段但不使用
                    "token": token,  # 使用前端提供的token
                    "created_at": now,
                    "updated_at": now
                }
                
                # 插入新用户
                self.users_collection.insert_one(user_doc)
                logger.info(f"使用提供的token创建新用户并登录: {default_username} ({user_id})")
                
                return {
                    "token": token,
                    "user_id": user_id,
                    "username": default_username,
                    "email": user_doc["email"]
                }
            
            except DuplicateKeyError as e:
                # 检查冲突的具体字段
                error_msg = str(e)
                if "token" in error_msg.lower():
                    # Token冲突：说明在检查和插入之间，token被其他请求使用了
                    logger.warning(f"Token冲突：提供的token在创建过程中已被使用")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Token已被使用，请使用其他token或重新生成"
                    )
                elif "user_id" in error_msg.lower():
                    logger.warning(f"User ID冲突，重试生成 (尝试 {attempt + 1}/{max_retries})")
                else:
                    logger.warning(f"唯一键冲突，重试生成 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                
                # 如果达到最大重试次数，抛出错误
                if attempt == max_retries - 1:
                    logger.error(f"使用提供的token创建用户失败：达到最大重试次数 ({max_retries})，可能存在系统问题")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="登录失败：无法生成唯一标识，请稍后重试"
                    )
                # 否则继续下一次循环重试
                continue
        
        # 理论上不会到达这里，但为了安全起见
        logger.error("使用提供的token创建用户失败：未知错误")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )

    def update_profile(self, user_id: str, username: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        """
        更新用户的基础资料

        Args:
            user_id: 用户ID
            username: 新用户名（可选，trim后更新）
            email: 新邮箱（可选，lowercase后更新）

        Returns:
            更新后的用户信息

        Raises:
            HTTPException: 如果用户不存在、验证失败或用户名/邮箱已存在
        """
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少用户ID"
            )

        # 查找用户
        user_doc = self.users_collection.find_one({"user_id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        update_fields = {}
        current_username = user_doc.get("username")
        current_email = user_doc.get("email")

        if username is not None:
            username = username.strip()
            # 使用User模型验证用户名
            try:
                # 创建临时User实例验证（使用现有值作为占位符）
                temp_user = User(
                    user_id=user_id,
                    username=username,
                    password="dummy123",  # 占位符，仅用于验证username
                    email=current_email or "dummy@example.com",
                    created_at=user_doc.get("created_at", datetime.utcnow()),
                    updated_at=datetime.utcnow()
                )
            except Exception as e:
                error_msg = str(e)
                if "用户名不能为空" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="用户名不能为空"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"用户名验证失败: {error_msg}"
                    )

            # 检查用户名是否已存在（排除当前用户）
            existing = self.users_collection.find_one({
                "username": username,
                "user_id": {"$ne": user_id}
            })
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="用户名已存在"
                )
            update_fields["username"] = username

        if email is not None:
            email = email.strip().lower()
            # 使用User模型验证邮箱
            try:
                temp_user = User(
                    user_id=user_id,
                    username=current_username or "dummy",
                    password="dummy123",
                    email=email,
                    created_at=user_doc.get("created_at", datetime.utcnow()),
                    updated_at=datetime.utcnow()
                )
            except Exception as e:
                error_msg = str(e)
                if "email" in error_msg.lower() or "value is not a valid email" in error_msg.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="邮箱格式无效"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"邮箱验证失败: {error_msg}"
                    )

            # 检查邮箱是否已存在（排除当前用户）
            existing = self.users_collection.find_one({
                "email": email,
                "user_id": {"$ne": user_id}
            })
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="邮箱已被注册"
                )
            update_fields["email"] = email

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有可更新的字段"
            )

        update_fields["updated_at"] = datetime.utcnow()

        updated_user = self.users_collection.find_one_and_update(
            {"user_id": user_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        logger.info(f"用户资料更新成功: {user_id}")
        
        return {
            "user_id": user_id,
            "username": updated_user.get("username"),
            "email": updated_user.get("email")
        }

    def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        """
        修改用户密码

        Args:
            user_id: 用户ID
            current_password: 当前密码
            new_password: 新密码（至少6位，且不同于当前密码）

        Raises:
            HTTPException: 如果验证失败
        """
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少用户ID"
            )

        # 验证新密码长度
        new_password = new_password.strip() if new_password else ""
        if not new_password or len(new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度至少6位"
            )

        if len(new_password) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度不能超过100位"
            )

        # 查找用户
        user_doc = self.users_collection.find_one({"user_id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 验证当前密码（支持旧格式password_hash和新格式password）
        stored_password = user_doc.get("password") or user_doc.get("password_hash")
        if not stored_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="当前密码不正确"
            )

        # 验证当前密码（支持bcrypt和旧sha256格式）
        current_password_valid = False
        if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
            # bcrypt格式
            current_password_valid = self._verify_password(current_password, stored_password)
        else:
            # 旧sha256格式（向后兼容）
            import hashlib
            hashed_current = hashlib.sha256(current_password.encode()).hexdigest()
            current_password_valid = (hashed_current == stored_password)

        if not current_password_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="当前密码不正确"
            )

        # 验证新密码不同于当前密码
        if new_password == current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与旧密码相同"
            )

        # 哈希新密码
        hashed_new = self._hash_password(new_password)

        # 更新密码
        result = self.users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "password": hashed_new,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count != 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新密码失败，请稍后重试"
            )

        logger.info(f"用户密码更新成功: {user_id}")
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            包含用户信息的字典
        
        Raises:
            HTTPException: 如果用户不存在
        """
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少用户ID"
            )

        # 查找用户
        user_doc = self.users_collection.find_one({"user_id": user_id})
        
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return {
            "user_id": user_id,
            "username": user_doc.get("username"),
            "email": user_doc.get("email")
        }
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根据用户ID获取用户信息（向后兼容方法）
        
        Args:
            user_id: 用户ID
        
        Returns:
            包含用户信息的字典，如果不存在则返回None
        """
        try:
            return self.get_user_info(user_id)
        except HTTPException:
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
        
        Returns:
            包含用户信息的字典，如果不存在则返回None
        """
        user = self.users_collection.find_one({"username": username})
        
        if not user:
            return None
        
        # 优先使用userId字段，如果没有则使用user_id字段
        user_id = user.get("userId") or user.get("user_id") or str(user.get("_id", ""))
        return {
            "user_id": user_id,
            "username": user.get("username"),
            "email": user.get("email")
        }
    
    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        根据token获取用户信息
        
        Args:
            token: token字符串
        
        Returns:
            包含用户信息的字典，如果不存在则返回None
        """
        if not token or not token.strip():
            return None
        
        user = self.users_collection.find_one({"token": token.strip()})
        
        if not user:
            return None
        
        user_id = user.get("user_id") or user.get("userId") or str(user.get("_id", ""))
        return {
            "user_id": user_id,
            "username": user.get("username"),
            "email": user.get("email")
        }
    
    def close(self):
        """关闭数据库连接"""
        if self.client:
            self.client.close()
            logger.info("用户服务：MongoDB连接已关闭")


# 全局用户服务实例
_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """获取全局用户服务实例"""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service


def register_user(username: str, password: str, email: str) -> Dict[str, Any]:
    """便捷函数：注册用户"""
    return get_user_service().register(username, password, email)


def login_user(username: str, password: str) -> Dict[str, Any]:
    """便捷函数：用户登录"""
    return get_user_service().login(username, password)

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """便捷函数：验证用户身份（向后兼容，已废弃，请使用login_user）"""
    try:
        result = get_user_service().login(username, password)
        return {
            "user_id": result["user_id"],
            "username": result["username"],
            "email": result.get("email")
        }
    except HTTPException:
        return None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """便捷函数：根据用户ID获取用户信息"""
    return get_user_service().get_user_by_id(user_id)


def update_user_profile(user_id: str, username: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：更新用户资料"""
    return get_user_service().update_profile(user_id, username=username, email=email)


def change_user_password(user_id: str, current_password: str, new_password: str) -> None:
    """便捷函数：修改用户密码"""
    return get_user_service().change_password(user_id, current_password, new_password)

