"""
Compatibility module exposing the FastAPI application for tests and legacy imports.

Historically the app lived under ``textmsa.main``; the implementation moved to
``server.app`` but some tests (and potentially external scripts) still import
``textmsa.main``.  Re-exporting the FastAPI ``app`` keeps that contract without
duplicating logic.
"""

from server.app import app  # re-export for TestClient and legacy tooling

__all__ = ["app"]

