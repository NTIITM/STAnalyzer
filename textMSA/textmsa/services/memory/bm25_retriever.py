from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from rank_bm25 import BM25Okapi

from textmsa.logging_config import get_logger
from textmsa.services.data.mongodb_models import Memory

logger = get_logger(__name__)


class BaseTokenizer:
    """分词器基类。"""

    def tokenize(self, text: str) -> List[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def get_stopwords(self) -> set:  # pragma: no cover - interface
        raise NotImplementedError


class ChineseTokenizer(BaseTokenizer):
    """简单的中文分词器，基于 jieba。"""

    def __init__(self) -> None:
        try:
            import jieba  # type: ignore[import]

            self._jieba = jieba
        except Exception as exc:  # pragma: no cover - 环境问题
            logger.error("初始化 jieba 失败，中文 BM25 检索可能不可用: %s", exc)
            self._jieba = None
        self._stopwords = self._load_stopwords()

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        if self._jieba is None:
            # 退化为按字符切分
            return [ch for ch in text if ch.strip()]
        words = self._jieba.cut(text, cut_all=False)
        return [w for w in words if w not in self._stopwords and len(w.strip()) > 1]

    def get_stopwords(self) -> set:
        return self._stopwords

    def _load_stopwords(self) -> set:
        # 这里使用一个非常小的内置停用词集合，后续可从文件扩展
        return {"的", "了", "在", "是", "我", "你", "他", "她", "它"}


class EnglishTokenizer(BaseTokenizer):
    """英文分词器，基于 nltk。"""

    def __init__(self) -> None:
        try:
            import nltk  # type: ignore[import]
            from nltk.corpus import stopwords  # type: ignore[import]

            self._nltk = nltk
            try:
                nltk.data.find("tokenizers/punkt")
            except LookupError:  # pragma: no cover - 下载路径依赖环境
                nltk.download("punkt")
            try:
                nltk.data.find("corpora/stopwords")
            except LookupError:  # pragma: no cover
                nltk.download("stopwords")
            self._stopwords = set(stopwords.words("english"))
        except Exception as exc:  # pragma: no cover - 环境问题
            logger.error("初始化 nltk 失败，英文 BM25 检索可能不可用: %s", exc)
            self._nltk = None
            self._stopwords = set()

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        if self._nltk is None:
            # 简单按空格切分
            tokens = text.lower().split()
        else:
            from nltk.tokenize import word_tokenize  # type: ignore[import]

            tokens = word_tokenize(text.lower())
        return [
            w for w in tokens if w.isalnum() and w not in self._stopwords and len(w) > 1
        ]

    def get_stopwords(self) -> set:
        return self._stopwords


class UniversalTokenizer(BaseTokenizer):
    """通用分词器，用于未特别支持的语言。"""

    def __init__(self) -> None:
        import re

        self._re = re
        self._stopwords: set = set()

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        # 提取单词或连续 CJK 字符
        tokens = self._re.findall(r"\b\w+\b|[\u4e00-\u9fff]+", text)
        return [t.lower() for t in tokens if len(t.strip()) > 1]

    def get_stopwords(self) -> set:
        return self._stopwords


class TokenizerFactory:
    """分词器工厂，根据语言代码返回对应的分词器。"""

    _tokenizers: Dict[str, BaseTokenizer] = {}

    @classmethod
    def get_tokenizer(cls, language: str) -> BaseTokenizer:
        key = (language or "auto").lower()
        if key not in cls._tokenizers:
            cls._tokenizers[key] = cls._create_tokenizer(key)
        return cls._tokenizers[key]

    @classmethod
    def _create_tokenizer(cls, language: str) -> BaseTokenizer:
        if language.startswith("zh"):
            return ChineseTokenizer()
        if language.startswith("en"):
            return EnglishTokenizer()
        # 其他语言暂时使用通用分词器
        return UniversalTokenizer()


class LanguageDetector:
    """轻量级语言检测封装。"""

    def __init__(self, default: str = "zh") -> None:
        self.default = default
        try:
            from langdetect import detect  # type: ignore[import]

            self._detect = detect
        except Exception as exc:  # pragma: no cover - 环境问题
            logger.error("初始化 langdetect 失败，将总是返回默认语言: %s", exc)
            self._detect = None

    def detect(self, text: str) -> str:
        if not text or self._detect is None:
            return self.default
        try:
            code = self._detect(text)
        except Exception:  # pragma: no cover - 探测失败兜底
            return self.default
        code = (code or "").lower()
        if code.startswith("zh"):
            return "zh"
        if code.startswith("en"):
            return "en"
        return self.default


@dataclass
class BM25Result:
    memory: Memory
    bm25_score: float
    final_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory.memory_id,
            "content": self.memory.content,
            "importance": self.memory.importance,
            "bm25_score": self.bm25_score,
            "final_score": self.final_score,
            "memory": self.memory,
        }


class MultiLanguageBM25Retriever:
    """多语言 BM25 检索器。"""

    def __init__(self, default_language: str | None = None) -> None:
        self.default_language = (default_language or "zh").lower()
        self._tokenizer_factory = TokenizerFactory()
        self._language_detector = LanguageDetector(default=self.default_language)

    def retrieve(
        self,
        *,
        query: str,
        memories: Sequence[Memory],
        top_k: int = 50,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """使用 BM25 检索相关记忆，并结合 importance 做加权排序。"""
        if not memories:
            return []
        query = (query or "").strip()
        if not query:
            # 没有 query 时，不做 BM25，仅按 importance 排序
            ranked = sorted(
                memories, key=lambda m: float(m.importance or 0.0), reverse=True
            )
            return [
                BM25Result(memory=m, bm25_score=0.0, final_score=float(m.importance))
                .to_dict()
                for m in ranked[:top_k]
            ]

        detected_lang = (language or "").strip().lower() or self._language_detector.detect(
            query
        )
        tokenizer = self._tokenizer_factory.get_tokenizer(detected_lang)

        query_tokens = tokenizer.tokenize(query)
        if not query_tokens:
            logger.debug("BM25 查询分词结果为空，退化为 importance 排序")
            ranked = sorted(
                memories, key=lambda m: float(m.importance or 0.0), reverse=True
            )
            return [
                BM25Result(memory=m, bm25_score=0.0, final_score=float(m.importance))
                .to_dict()
                for m in ranked[:top_k]
            ]

        corpus_tokens: List[List[str]] = [
            tokenizer.tokenize(m.content or "") for m in memories
        ]
        bm25 = BM25Okapi(corpus_tokens)
        scores = bm25.get_scores(query_tokens)

        results: List[BM25Result] = []
        for mem, score in zip(memories, scores):
            bm25_score = float(score)
            importance = float(mem.importance or 0.0)
            final_score = bm25_score * (1.0 + importance)
            results.append(
                BM25Result(
                    memory=mem,
                    bm25_score=bm25_score,
                    final_score=final_score,
                )
            )

        results.sort(key=lambda r: r.final_score, reverse=True)
        return [r.to_dict() for r in results[:top_k]]


