"""
textMSA package initialisation.
"""

from textmsa.logging_config import setup_logging
from textmsa.settings import apply_langsmith_from_config

# Configure default logging as soon as the package is imported.
setup_logging()

# Apply LangSmith/LangChain tracing envs from config when present.
try:  # best-effort; do not fail import
    apply_langsmith_from_config()
except Exception:
    pass

__all__ = ["setup_logging", "apply_langsmith_from_config"]
