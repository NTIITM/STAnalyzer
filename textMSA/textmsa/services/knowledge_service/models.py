from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用户查询原文")
    project_id: str = Field(..., alias="projectId", description="项目ID")
    top_k: int = Field(20, ge=1, le=100, alias="topK", description="返回文献数量上限")
    rewrite: bool = Field(True, description="是否启用查询改写")
    sources: Optional[List[str]] = Field(None, description="指定数据源列表，可为空")
    trace: bool = Field(False, description="是否返回调试信息")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class KnowledgeDocument(BaseModel):
    source: str = Field(..., description="数据源标识，如 pubmed/arxiv/crossref")
    title: str = Field(..., description="文献标题")
    snippet: str = Field("", description="摘要或内容片段")
    url: Optional[str] = Field(None, description="文献链接")
    doi: Optional[str] = Field(None, description="DOI，如有")
    published_at: Optional[str] = Field(None, description="发表时间（ISO字符串或年份）")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    journal: Optional[str] = Field(None, description="期刊或会议")
    source_type: Optional[str] = Field(None, description="文献类型")
    score: Optional[float] = Field(None, description="相关性评分")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class KnowledgeSearchResult(BaseModel):
    rewrite_query: str = Field(..., description="最终用于检索的查询")
    datasources_used: List[str] = Field(default_factory=list, description="本次使用的数据源")
    documents: List[KnowledgeDocument] = Field(default_factory=list, description="检索到的文献列表")
    usage: Optional[Dict[str, Any]] = Field(None, description="LLM/请求消耗信息")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="各数据源错误信息")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class KnowledgeSearchResponse(BaseModel):
    code: int = Field(200, description="业务状态码")
    message: str = Field("success", description="提示信息")
    data: KnowledgeSearchResult

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

