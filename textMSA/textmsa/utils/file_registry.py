"""
Simple file registry to track files created by MCP tools across a workflow.

Keeps lightweight metadata and offers helpers to select suitable inputs for
downstream tools (e.g., latest h5ad), and to persist/restore across rounds.
"""

from __future__ import annotations

import json
import mimetypes
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FileMeta(BaseModel):
    path: str
    kind: Optional[str] = Field(None, description="Logical kind (e.g., h5ad/csv)")
    role: Optional[str] = Field(None, description="Semantic role of the file")
    description: Optional[str] = None
    tool: Optional[str] = Field(None, description="Tool id that produced the file")
    from_tool: Optional[str] = None
    from_workflow: Optional[str] = None
    size: Optional[int] = None
    mtime: Optional[str] = None
    mime: Optional[str] = None
    exists: Optional[bool] = None

    def enrich_from_fs(self) -> None:
        try:
            st = os.stat(self.path)
            self.exists = True
            self.size = int(st.st_size)
            self.mtime = datetime.fromtimestamp(st.st_mtime).isoformat()
        except Exception:
            # keep optional
            self.exists = False
            pass
        # best-effort mime detection
        if not self.mime:
            mt, _ = mimetypes.guess_type(self.path)
            if mt:
                self.mime = mt


class FileRegistry(BaseModel):
    files: List[FileMeta] = Field(default_factory=list)

    def add_files(self, files: List[Dict[str, Any]] | List[FileMeta], defaults: Optional[Dict[str, Any]] = None) -> None:
        defaults = defaults or {}
        for f in files or []:
            if isinstance(f, dict):
                meta = {**defaults, **f}
                try:
                    fm = FileMeta(**meta)
                except Exception:
                    continue
            elif isinstance(f, FileMeta):
                fm = f
            else:
                continue
            # fill kind from extension if missing
            if not fm.kind:
                ext = os.path.splitext(fm.path)[1].lower().lstrip('.')
                if ext:
                    fm.kind = ext
            fm.enrich_from_fs()
            # dedupe by (path, role, tool) to keep list small
            key = (fm.path, fm.role or "", fm.tool or "")
            exists = any((x.path, x.role or "", x.tool or "") == key for x in self.files)
            if not exists:
                self.files.append(fm)

    def latest_by_kind(self, kind: str) -> Optional[FileMeta]:
        # prefer newest mtime if available
        candidates = [f for f in self.files if (f.kind == kind or (not f.kind and f.path.endswith(f".{kind}")))]
        if not candidates:
            return None
        def sort_key(f: FileMeta):
            try:
                return os.stat(f.path).st_mtime
            except Exception:
                return 0.0
        return sorted(candidates, key=sort_key, reverse=True)[0]

    def latest_h5ad(self) -> Optional[FileMeta]:
        return self.latest_by_kind("h5ad")

    def to_list(self) -> List[Dict[str, Any]]:
        return [json.loads(f.model_dump_json()) for f in self.files]

    def save(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(self.to_list(), fh, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: str) -> "FileRegistry":
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                arr = json.load(fh)
        except Exception:
            return cls()
        reg = cls()
        if isinstance(arr, list):
            for f in arr:
                try:
                    reg.add_files([f])
                except Exception:
                    continue
        return reg

    # ---- Preview helpers -------------------------------------------------
    def _preview_text(self, path: str, max_bytes: int) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read(max_bytes)
        except Exception:
            return ""

    def _preview_csv(self, path: str, max_rows: int, max_bytes: int) -> Dict[str, Any]:
        import csv
        rows = []
        try:
            with open(path, newline="", encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    rows.append(row)
        except Exception:
            # 若解析失败，退回到文本片段
            return {"rows": [], "snippet": self._preview_text(path, max_bytes)}
        return {"rows": rows}

    def _preview_h5ad(self, path: str) -> Dict[str, Any]:
        try:
            import anndata as ad  # type: ignore
        except Exception:
            return {"note": "anndata not available for preview"}
        try:
            adata = ad.read_h5ad(path)
            obsm_keys = list(getattr(adata, "obsm", {}).keys()) if hasattr(adata, "obsm") else []
            return {
                "n_cells": int(adata.n_obs),
                "n_genes": int(adata.n_vars),
                "shape": [int(adata.shape[0]), int(adata.shape[1])],
                "obsm_keys": obsm_keys,
                "obs_cols": list(adata.obs.columns[:8]) if hasattr(adata, "obs") else [],
                "var_cols": list(adata.var.columns[:8]) if hasattr(adata, "var") else [],
            }
        except Exception as e:
            return {"error": str(e)}

    def build_manifest(
        self,
        include_preview: bool = True,
        max_preview_bytes: int = 4096,
        max_preview_rows: int = 10,
    ) -> List[Dict[str, Any]]:
        manifest: List[Dict[str, Any]] = []
        for f in self.files:
            item = json.loads(f.model_dump_json())
            if include_preview:
                # choose preview by kind or extension
                kind = (f.kind or "").lower()
                ext = os.path.splitext(f.path)[1].lower()
                try:
                    if kind == "csv" or ext in (".csv", ".tsv"):
                        item["preview"] = self._preview_csv(f.path, max_preview_rows, max_preview_bytes)
                    elif kind == "h5ad" or ext == ".h5ad":
                        item["preview"] = self._preview_h5ad(f.path)
                    elif kind in ("json", "txt") or ext in (".json", ".txt", ".log"):
                        item["preview"] = {"snippet": self._preview_text(f.path, max_preview_bytes)}
                except Exception:
                    # ignore preview errors
                    pass
            manifest.append(item)
        return manifest

    # ---- Index/grouping helpers ----------------------------------------
    def group_by_role(self) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in self.files:
            role = f.role or "unknown"
            groups.setdefault(role, []).append(json.loads(f.model_dump_json()))
        return groups

    def group_by_kind(self) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in self.files:
            kind = (f.kind or "unknown").lower()
            groups.setdefault(kind, []).append(json.loads(f.model_dump_json()))
        return groups

    def latest_index(self) -> Dict[str, Optional[Dict[str, Any]]]:
        kinds = { (f.kind or os.path.splitext(f.path)[1].lstrip('.').lower()) for f in self.files }
        out: Dict[str, Optional[Dict[str, Any]]] = {}
        for k in kinds:
            fm = self.latest_by_kind(k)
            out[k] = json.loads(fm.model_dump_json()) if fm else None
        # common convenience entries
        for k in ("h5ad", "csv", "json"):
            if k not in out:
                fm = self.latest_by_kind(k)
                out[k] = json.loads(fm.model_dump_json()) if fm else None
        return out

    def build_index(self) -> Dict[str, Any]:
        return {
            "by_role": self.group_by_role(),
            "by_kind": self.group_by_kind(),
            "latest": self.latest_index(),
        }
