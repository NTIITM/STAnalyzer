#!/usr/bin/env python
"""
Populate missing file_type_* fields in historical `files` documents.

Usage:
    poetry run python scripts/migrate_files_set_unknown_type.py
    poetry run python scripts/migrate_files_set_unknown_type.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from textmsa.services.data.user_data_manager_mongodb import UserDataManagerMongoDB

logger = logging.getLogger("textmsa.migrate_unknown_file_type")

UNKNOWN_TYPE_PAYLOAD: Dict[str, object] = {
    "name": "unknown",
    "display_name": "未知文件类型",
    "description": "用于补齐历史文件或无法识别的文件类型",
    "category": "generic",
    "extensions": [".unknown"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set missing file_type fields to the fallback 'unknown' type."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report the number of affected documents without updating.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def ensure_unknown_file_type(manager: UserDataManagerMongoDB) -> Dict[str, object]:
    existing = manager.get_file_type_by_name(UNKNOWN_TYPE_PAYLOAD["name"])
    if existing:
        logger.info(
            "Found existing 'unknown' file type (id=%s)", existing.get("file_type_id")
        )
        return existing
    created = manager.create_file_type(UNKNOWN_TYPE_PAYLOAD)
    logger.info("Created fallback 'unknown' file type (id=%s)", created.get("file_type_id"))
    return created


def build_missing_filter() -> Dict[str, object]:
    """匹配缺少 file_type 字段或值为空的文档。"""
    return {
        "$or": [
            {"file_type_id": {"$exists": False}},
            {"file_type_id": None},
            {"file_type_id": ""},
            {"file_type_name": {"$exists": False}},
            {"file_type_display_name": {"$exists": False}},
        ]
    }


def migrate(manager: UserDataManagerMongoDB, dry_run: bool = False) -> None:
    unknown = ensure_unknown_file_type(manager)
    files_collection = manager.files_collection
    query = build_missing_filter()

    missing_count = files_collection.count_documents(query)
    if missing_count == 0:
        logger.info("All files already contain file_type metadata. Nothing to do.")
        return

    logger.info("Found %d file(s) missing file_type metadata.", missing_count)
    if dry_run:
        logger.info("[DRY-RUN] Skipping update. Re-run without --dry-run to apply changes.")
        return

    update_doc = {
        "$set": {
            "file_type_id": unknown["file_type_id"],
            "file_type_name": unknown["name"],
            "file_type_display_name": unknown["display_name"],
        }
    }
    result = files_collection.update_many(query, update_doc)
    logger.info(
        "Migration completed. matched=%d, modified=%d",
        result.matched_count,
        result.modified_count,
    )


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    manager = UserDataManagerMongoDB()
    migrate(manager, dry_run=args.dry_run)


if __name__ == "__main__":
    main()


