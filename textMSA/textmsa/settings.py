"""
统一配置管理
所有配置统一从textmsa/config/config.json读取
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from textmsa.services.core.config_manager import get_config, ConfigError

# 包根目录
PACKAGE_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PACKAGE_ROOT / "config"
CONFIG_JSON = CONFIG_DIR / "config.json"


def load_app_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    加载应用配置
    
    Args:
        config_path: 配置文件路径（可选，默认使用config.json）
    
    Returns:
        配置字典
    """
    config = get_config()
    if config_path:
        # 如果指定了路径，创建新的配置实例
        from textmsa.services.core.config_manager import UnifiedConfig
        temp_config = UnifiedConfig(config_path)
        return temp_config._config_cache or {}
    return config._config_cache or {}


def get_llm_config() -> Dict[str, Any]:
    """获取LLM配置"""
    cfg = load_app_config()
    llm = cfg.get("llm")
    if not isinstance(llm, dict):
        raise ConfigError("缺少 llm 配置段，无法创建LLM客户端")
    required = ["model", "api_key", "base_url"]
    missing = [k for k in required if not llm.get(k)]
    if missing:
        raise ConfigError(f"llm 配置缺少必要字段: {', '.join(missing)}")
    return llm


def get_spatial_prompts_module() -> str:
    """获取空间分析prompts模块"""
    cfg = load_app_config()
    prompts = cfg.get("prompts", {}) or {}
    mod = prompts.get("spatial", "textmsa.prompts.spatial")
    if not isinstance(mod, str) or not mod:
        raise ConfigError("prompts.spatial 配置不正确，应为模块路径字符串")
    return mod


def get_knowledge_prompts_module() -> str:
    """获取知识库prompts模块"""
    cfg = load_app_config()
    prompts = cfg.get("prompts", {}) or {}
    mod = prompts.get("knowledge", "textmsa.prompts.knowledge")
    if not isinstance(mod, str) or not mod:
        raise ConfigError("prompts.knowledge 配置不正确，应为模块路径字符串")
    return mod


def get_planner_prompts_module() -> str:
    """获取规划器prompts模块"""
    cfg = load_app_config()
    prompts = cfg.get("prompts", {}) or {}
    mod = prompts.get("planner", "textmsa.prompts.planner")
    if not isinstance(mod, str) or not mod:
        raise ConfigError("prompts.planner 配置不正确，应为模块路径字符串")
    return mod


def get_mcp_config() -> Dict[str, Any]:
    """获取MCP服务器配置"""
    cfg = load_app_config()
    servers = cfg.get("servers")
    if not isinstance(servers, dict) or not servers:
        raise ConfigError("缺少 servers 配置段或为空，无法连接MCP服务器")
    return {"servers": servers}


def get_neo4j_config() -> Dict[str, Any]:
    """获取Neo4j配置"""
    cfg = load_app_config()
    neo = cfg.get("neo4j", {}) or {}
    return {
        "uri": neo.get("uri", ""),
        "user": neo.get("user", ""),
        "password": neo.get("password", ""),
        "database": neo.get("database", "neo4j"),
    }


def get_cache_config() -> Dict[str, Any]:
    """获取缓存配置"""
    cfg = load_app_config()
    cache = cfg.get("cache", {}) or {}
    config_dir = Path(__file__).resolve().parent.parent.parent / "config"
    return {
        "backend": cache.get("backend", "file"),
        "file_path": cache.get("file_path") or str(config_dir / "pmid_cache.json"),
        "max_entries": int(cache.get("max_entries", 50000)),
    }


def get_pubmed_config() -> Dict[str, Any]:
    """获取PubMed配置"""
    cfg = load_app_config()
    pub = cfg.get("pubmed", {}) or {}
    api_key = pub.get("api_key", "")
    email = pub.get("email", "")
    if not isinstance(api_key, str) or not isinstance(email, str):
        raise ConfigError("pubmed 配置不正确，应包含字符串字段 api_key, email (可为空)")
    return {"api_key": api_key, "email": email}


def get_langsmith_config() -> Dict[str, Any]:
    """获取LangSmith配置"""
    cfg = load_app_config()
    ls = cfg.get("langsmith", {}) or {}
    return {
        "tracing": bool(ls.get("tracing", False)),
        "endpoint": ls.get("endpoint", ""),
        "api_key": ls.get("api_key", ""),
        "project": ls.get("project", ""),
    }


def get_mongodb_config() -> Dict[str, Any]:
    """获取MongoDB配置"""
    cfg = load_app_config()
    mongo = cfg.get("mongodb", {}) or {}
    return {
        "uri": mongo.get("uri", "mongodb://localhost:27017/"),
        "database": mongo.get("database", "textmsa"),
        "server_selection_timeout_ms": int(mongo.get("server_selection_timeout_ms", 5000)),
        "connect_timeout_ms": int(mongo.get("connect_timeout_ms", 5000)),
        "socket_timeout_ms": int(mongo.get("socket_timeout_ms", 30000)),
        "max_pool_size": int(mongo.get("max_pool_size", 50)),
        "min_pool_size": int(mongo.get("min_pool_size", 10)),
        "auto_init": bool(mongo.get("auto_init", True)),
    }


def get_storage_config() -> Dict[str, Any]:
    """获取存储配置"""
    cfg = load_app_config()
    storage = cfg.get("storage", {}) or {}
    project_root = Path(__file__).resolve().parent.parent.parent
    
    return {
        "base_dir": storage.get("base_dir") or str(project_root),
        "upload_dir": storage.get("upload_dir") or str(project_root / "uploads"),
        "output_dir": storage.get("output_dir") or str(project_root / "outputs"),
        "data_dir": storage.get("data_dir") or str(project_root / "data"),
    }


def get_server_config() -> Dict[str, Any]:
    """获取服务器配置"""
    import os
    cfg = load_app_config()
    server = cfg.get("server", {}) or {}
    
    # 根据 dev_mode 自动设置 workers 和 reload
    dev_mode = server.get("dev_mode", False)
    if dev_mode:
        # 开发模式：单进程 + 热更新
        workers = None
        reload = True
    else:
        # 生产模式：使用配置的workers或默认的8进程 + 禁用热更新
        workers = server.get("workers", 8)
        reload = False
    
    return {
        "host": server.get("host", "127.0.0.1"),
        "port": int(server.get("port", 8000)),
        "workers": workers,
        "reload": reload,
        "dev_mode": dev_mode,
    }


def get_system_server_config() -> Dict[str, Any]:
    """获取 system_server 配置"""
    import os
    cfg = load_app_config()
    system_server = cfg.get("system_server", {}) or {}
    return {
        "url": os.getenv("SYSTEM_SERVER_URL", system_server.get("url", "http://localhost:9000")),
        "timeout": float(os.getenv("SYSTEM_SERVER_TIMEOUT", str(system_server.get("timeout", 10.0)))),
        "retry_count": int(os.getenv("SYSTEM_SERVER_RETRY_COUNT", str(system_server.get("retry_count", 3)))),
        "enable_registration": _to_bool(os.getenv("SYSTEM_SERVER_ENABLE_REGISTRATION", str(system_server.get("enable_registration", True)))),
    }


def get_codegen_config() -> Dict[str, Any]:
    """获取代码生成配置"""
    cfg = load_app_config()
    codegen = cfg.get("codegen", {}) or {}
    project_root = Path(__file__).resolve().parent.parent.parent
    
    return {
        "work_dir": codegen.get("work_dir") or str(project_root / "gen_code_workdir"),
    }


def get_reranker_llm_config() -> Dict[str, Any]:
    """获取文档精排（reranker）模型配置。

    期望在 config.json 中存在段：
    {
      "reranker_llm": {
        "base_url": "https://dashscope.aliyuncs.com",
        "endpoint": "/api/v1/services/rerank/text-rerank/text-rerank",
        "model": "qwen3-rerank",
        "api_key": "...",
        "provider": "dashscope",
        ...
      }
    }
    
    如果配置中没有 api_key，会尝试从环境变量 DASHSCOPE_API_KEY 读取。
    """
    import os
    
    cfg = load_app_config()
    reranker = cfg.get("reranker_llm", {}) or {}
    if not isinstance(reranker, dict) or not reranker:
        raise ConfigError("缺少 reranker_llm 配置段，无法创建 RerankerClient")

    # API Key 优先级：配置中的 api_key > 环境变量 DASHSCOPE_API_KEY > 默认 llm 的 api_key
    default_llm = cfg.get("llm", {}) or {}
    api_key = reranker.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or default_llm.get("api_key", "")
    
    # 对于 DashScope，如果没有配置 base_url，使用默认值
    base_url = reranker.get("base_url", "https://dashscope.aliyuncs.com")
    model = reranker.get("model", "qwen3-rerank")
    
    # 如果缺少必要字段，抛出错误
    if not api_key:
        raise ConfigError("reranker_llm 配置缺少 api_key，且环境变量 DASHSCOPE_API_KEY 也未设置")
    if not model:
        raise ConfigError("reranker_llm 配置缺少 model 字段")

    # 允许覆盖超时与重试参数，否则使用 llm 的默认值作为回退
    return {
        "base_url": base_url,
        "endpoint": reranker.get("endpoint", "/api/v1/services/rerank/text-rerank/text-rerank"),
        "model": model,
        "api_key": api_key,
        "timeout_seconds": reranker.get(
            "timeout_seconds", default_llm.get("timeout_seconds", 60)
        ),
        "connect_timeout_seconds": reranker.get(
            "connect_timeout_seconds", default_llm.get("connect_timeout_seconds", 10)
        ),
        "write_timeout_seconds": reranker.get(
            "write_timeout_seconds", default_llm.get("write_timeout_seconds", 30)
        ),
        "max_retries": reranker.get("max_retries", default_llm.get("max_retries", 3)),
        "retry_backoff_seconds": reranker.get(
            "retry_backoff_seconds", default_llm.get("retry_backoff_seconds", 1.5)
        ),
        "provider": reranker.get("provider", "dashscope"),
        "instruct": reranker.get("instruct", "Given a web search query, retrieve relevant passages that answer the query."),
    }

def get_multimodal_llm_config() -> Dict[str, Any]:
    """获取多模态LLM配置（用于图片读取）"""
    cfg = load_app_config()
    multimodal_llm = cfg.get("multimodal_llm", {}) or {}
    
    # 从 api_url 中提取 base_url
    api_url = multimodal_llm.get("api_url", "")
    if not api_url:
        # 如果没有配置，使用默认的 llm 配置
        return get_llm_config()
    
    # 解析 api_url: "http://211.87.232.112:8000/v1/chat/completions"
    # 提取 base_url: "http://211.87.232.112:8000/v1"
    if "/v1/chat/completions" in api_url:
        base_url = api_url.replace("/v1/chat/completions", "/v1").rstrip("/")
    elif "/chat/completions" in api_url:
        base_url = api_url.replace("/chat/completions", "").rstrip("/")
    else:
        # 如果格式不符合预期，尝试提取基础 URL
        parsed = urlparse(api_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.path.startswith("/v1"):
            base_url += "/v1"
    
    # 获取其他配置，如果没有则使用默认值或从主 llm 配置继承
    default_llm = cfg.get("llm", {}) or {}
    
    return {
        "base_url": base_url,
        "model": multimodal_llm.get("model", "/model"),
        "api_key": multimodal_llm.get("api_key") or default_llm.get("api_key", ""),
        "timeout_seconds": multimodal_llm.get("timeout_seconds", default_llm.get("timeout_seconds", 180)),
        "connect_timeout_seconds": multimodal_llm.get("connect_timeout_seconds", default_llm.get("connect_timeout_seconds", 30)),
        "write_timeout_seconds": multimodal_llm.get("write_timeout_seconds", default_llm.get("write_timeout_seconds", 30)),
        "max_retries": multimodal_llm.get("max_retries", default_llm.get("max_retries", 3)),
        "retry_backoff_seconds": multimodal_llm.get("retry_backoff_seconds", default_llm.get("retry_backoff_seconds", 1.5)),
    }


def get_codegen_llm_config() -> Dict[str, Any]:
    """获取代码生成LLM配置（用于数据分析代码生成）。
    
    期望在 config.json 中存在段：
    {
      "codegen_llm": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3-coder-plus",
        "api_key": "...",
        ...
      }
    }
    
    如果配置中没有 api_key，会尝试从环境变量 DASHSCOPE_API_KEY 读取。
    """
    import os
    
    cfg = load_app_config()
    codegen_llm = cfg.get("codegen_llm", {}) or {}
    
    # 如果没有配置 codegen_llm，使用默认的 llm 配置
    if not codegen_llm:
        return get_llm_config()
    
    # 允许覆盖超时与重试参数，否则使用 llm 的默认值作为回退
    default_llm = cfg.get("llm", {}) or {}
    
    # API Key 优先级：配置中的 api_key > 环境变量 DASHSCOPE_API_KEY > 默认 llm 的 api_key
    api_key = codegen_llm.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or default_llm.get("api_key", "")
    
    return {
        "base_url": codegen_llm.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model": codegen_llm.get("model", "qwen3-coder-plus"),
        "api_key": api_key,
        "timeout_seconds": codegen_llm.get(
            "timeout_seconds", default_llm.get("timeout_seconds", 180)
        ),
        "connect_timeout_seconds": codegen_llm.get(
            "connect_timeout_seconds", default_llm.get("connect_timeout_seconds", 10)
        ),
        "write_timeout_seconds": codegen_llm.get(
            "write_timeout_seconds", default_llm.get("write_timeout_seconds", 30)
        ),
        "max_retries": codegen_llm.get("max_retries", default_llm.get("max_retries", 3)),
        "retry_backoff_seconds": codegen_llm.get(
            "retry_backoff_seconds", default_llm.get("retry_backoff_seconds", 1.5)
        ),
        "provider": codegen_llm.get("provider", "openai"),
    }


def get_gene_relation_api_config() -> Dict[str, Any]:
    """获取基因关系API配置"""
    cfg = load_app_config()
    api_config = cfg.get("gene_relation_api", {})
    return {
        "base_url": api_config.get("base_url", "http://localhost:8001"),
        "timeout_seconds": api_config.get("timeout_seconds", 300),
        "connect_timeout_seconds": api_config.get("connect_timeout_seconds", 5),
        "enabled": api_config.get("enabled", True),
    }


def _to_bool(val: Any) -> bool:
    """转换为布尔值"""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    return s in {"1", "true", "yes", "on"}


def apply_langsmith_from_config() -> Dict[str, str]:
    """
    应用LangSmith/LangChain追踪环境变量（从配置）
    
    Returns:
        设置的环境变量字典
    """
    applied: Dict[str, str] = {}
    try:
        cfg = get_langsmith_config()
    except Exception:
        return applied
    
    import os
    
    tracing = _to_bool(cfg.get("tracing", False))
    endpoint = cfg.get("endpoint") or ""
    api_key = cfg.get("api_key") or ""
    project = cfg.get("project") or ""
    
    def _setenv(name: str, value: str) -> None:
        if name not in os.environ and value:
            os.environ[name] = value
            applied[name] = value
    
    if tracing:
        _setenv("LANGSMITH_TRACING", "true")
        _setenv("LANGCHAIN_TRACING_V2", "true")
    if endpoint:
        _setenv("LANGSMITH_ENDPOINT", endpoint)
        _setenv("LANGCHAIN_ENDPOINT", endpoint)
    if api_key:
        _setenv("LANGSMITH_API_KEY", api_key)
        _setenv("LANGCHAIN_API_KEY", api_key)
    if project:
        _setenv("LANGSMITH_PROJECT", project)
        _setenv("LANGCHAIN_PROJECT", project)
    
    return applied
