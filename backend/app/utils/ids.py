"""
BlackBoxRAG Identifier Generation Utilities.

Scheme:
    symbol_key = "{lang}:{rel_path}::{qualname}"   (+ "#2", "#3" for duplicates in one file)
    symbol_id  = uuid5(NAMESPACE, snapshot_id + symbol_key)
    chunk_id   = uuid5(NAMESPACE, symbol_id + ":" + part_index)

Paths are repo-relative with forward slashes. Lines are 1-based inclusive.
Fixed NAMESPACE is used across all environments.
"""

from __future__ import annotations

import uuid

# Fixed namespace UUID for BlackBoxRAG deterministic identifier generation
BLACKBOXRAG_NAMESPACE = uuid.UUID("9b6c0722-1d65-4f40-b6f7-b2f70b77b102")


def normalize_path(rel_path: str) -> str:
    """Normalize repo-relative path to forward slashes with no leading/trailing slashes."""
    normalized = rel_path.replace("\\", "/").strip().lstrip("/")
    return normalized


def make_symbol_key(
    lang: str,
    rel_path: str,
    qualname: str,
    duplicate_index: int = 1,
) -> str:
    """
    Generate stable symbol key: {lang}:{rel_path}::{qualname}
    Appends '#2', '#3', etc. for duplicate qualnames in the same file.
    """
    clean_path = normalize_path(rel_path)
    clean_lang = lang.strip().lower()
    clean_qualname = qualname.strip()

    suffix = f"#{duplicate_index}" if duplicate_index > 1 else ""
    return f"{clean_lang}:{clean_path}::{clean_qualname}{suffix}"


def make_symbol_id(
    snapshot_id: str | uuid.UUID,
    symbol_key: str,
    namespace: uuid.UUID = BLACKBOXRAG_NAMESPACE,
) -> uuid.UUID:
    """
    Generate deterministic snapshot-scoped symbol_id.
    symbol_id = uuid5(NAMESPACE, str(snapshot_id) + symbol_key)
    """
    return uuid.uuid5(namespace, f"{snapshot_id}{symbol_key}")


def make_chunk_id(
    symbol_id: str | uuid.UUID,
    part_index: int = 0,
    namespace: uuid.UUID = BLACKBOXRAG_NAMESPACE,
) -> uuid.UUID:
    """
    Generate deterministic chunk_id:
    chunk_id = uuid5(NAMESPACE, str(symbol_id) + ":" + str(part_index))
    """
    return uuid.uuid5(namespace, f"{symbol_id}:{part_index}")
