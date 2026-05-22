# Services 目录结构说明

## 目录组织

```
services/
├── api/                    # API路由层
│   ├── routers/           # 路由定义
│   │   ├── user.py        # 用户API路由
│   │   ├── file.py        # 文件API路由
│   │   └── agent.py       # Agent API路由（Job-based架构）
│   ├── schemas.py         # Pydantic请求/响应模型
│   └── __init__.py
│
├── agent/                  # Agent服务（重构后 - Job-based架构）
│   ├── memory/            # 记忆控制模块
│   │   ├── memory_controller.py      # 记忆控制器接口
│   │   └── simple_memory_controller.py  # 简单记忆控制器实现
│   ├── workflows/         # 工作流模块（已迁移到 LangGraph）
│   │   └── orchestrator.py          # 工作流编排器
│   ├── repositories/      # 数据访问层
│   │   └── job_repository.py        # Job数据仓库
│   ├── job_service.py     # Job生命周期管理服务
│   ├── session_service.py # 会话管理服务（已废弃）
│   └── rag_agent_service.py  # RAG Agent服务
│
├── auth/                   # 认证服务
│   ├── auth_service.py    # JWT认证服务
│   └── __init__.py
│
├── user/                   # 用户服务
│   ├── user_service.py    # 用户业务逻辑
│   └── __init__.py
│
├── file/                   # 文件服务
│   ├── file_manager.py    # 文件管理基础服务
│   ├── file_service.py    # 文件业务逻辑
│   └── __init__.py
│
├── data/                   # 数据管理服务
│   ├── mongodb_models.py   # MongoDB数据模型
│   ├── user_data_manager_mongodb.py  # MongoDB用户数据管理器
│   ├── user_data_manager.py           # 用户数据管理器（备用）
│   └── __init__.py
│
├── core/                   # 核心服务
│   ├── config_manager.py  # 配置管理器
│   └── __init__.py
│
├── mcp_spatial_service.py  # MCP空间服务（暂未使用）
├── api_routes.py           # 已废弃（向后兼容）
├── api_service.py          # 已废弃（向后兼容）
└── __init__.py
```

## 服务说明

### API层 (`api/`)
- 定义所有API路由和请求/响应模型
- 当前实现：用户管理、文件管理、Agent服务

### Agent服务 (`agent/`) ⭐ 重构后 - Job-based架构
- **Job-based执行模型**: 每个项目每个用户同时只能有一个活跃的job，支持取消操作
- **多工作流支持**: 支持多个工作流，在路由层选择（默认 RAG 工作流）
- **记忆控制**: 独立的记忆控制模块，可插拔替换
- **工作流解耦**: 工作流通过 callback 机制通信，完全解耦
- **实时进度反馈**: 通过job polling机制获取工作流执行进度

**主要模块**:
- `rag_agent_service.py`: 主服务类，协调各个模块
- `job_service.py`: Job生命周期管理服务
- `workflows/orchestrator.py`: 工作流编排器
- `repositories/job_repository.py`: Job数据仓库
- `memory/`: 记忆控制模块（MemoryController 接口和实现）
- `workflows/`: 工作流模块（已迁移到 LangGraph）

**快速开始**:
```python
from textmsa.services.agent.job_service import get_agent_job_service
from textmsa.services.agent.session_service import get_agent_session_service

job_service = get_agent_job_service()
session_service = get_agent_session_service()

# 启动job
result = job_service.start_job(
    user_id="user-123",
    project_id="project-123",
    conversation_id="conv-123",
    message="用户消息",
)

# 轮询job状态
job = job_service.get_active_job_with_steps("user-123", "project-123")
```

**相关文档**:
- API 文档: `docs/api/agent.md`
- 架构文档: `docs/agent-refactor-code-structure.md`
- 开发指南: `docs/development/agent-extension.md`

### 认证服务 (`auth/`)
- JWT token生成和验证
- 开发模式支持

### 用户服务 (`user/`)
- 用户注册、登录、信息查询
- MongoDB存储

### 文件服务 (`file/`)
- 文件上传、列表、详情、删除
- 整合file_manager和user_data_manager

### 数据管理 (`data/`)
- MongoDB数据模型定义
- 用户数据持久化

### 核心服务 (`core/`)
- 配置管理
- 统一配置加载

---

## Agent 服务重构说明

### 重构亮点

1. **Job-based执行模型**: 从SSE流式响应改为job-based模型，支持job生命周期管理和取消操作
2. **工作流解耦**: 工作流完全解耦，通过 callback 机制通信，不直接依赖外部服务
3. **记忆管理独立**: 记忆控制逻辑独立为可插拔模块，支持多种记忆策略
4. **多工作流支持**: 支持多个工作流，在路由层选择，默认使用 RAG 工作流
5. **代码质量提升**: 代码结构清晰，职责明确，易于维护和扩展

### 架构说明

新的架构使用job-based模型：
- 每个项目每个用户同时只能有一个活跃的job
- 通过轮询机制获取job状态和步骤信息
- 支持取消正在运行的job
- Job状态持久化到MongoDB

详细架构说明请参考 `docs/agent-backend-refactor-plan.md`。

