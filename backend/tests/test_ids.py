from __future__ import annotations

import uuid

from backend.app.utils.ids import (
    BLACKBOXRAG_NAMESPACE,
    make_chunk_id,
    make_symbol_id,
    make_symbol_key,
    normalize_path,
)


def test_normalize_path():
    assert normalize_path("src\\models.py") == "src/models.py"
    assert normalize_path("/app/api/repositories.py") == "app/api/repositories.py"
    assert normalize_path("\\app\\utils\\ids.py") == "app/utils/ids.py"
    assert normalize_path("simple.py") == "simple.py"


def test_make_symbol_key_format():
    key = make_symbol_key(
        lang="python",
        rel_path="backend/app/auth.py",
        qualname="AuthService.authenticate",
    )
    assert key == "python:backend/app/auth.py::AuthService.authenticate"

    # Test normalization of path and lang
    key2 = make_symbol_key(
        lang="PYTHON ",
        rel_path="\\backend\\app\\auth.py",
        qualname="AuthService.authenticate",
    )
    assert key2 == "python:backend/app/auth.py::AuthService.authenticate"


def test_make_symbol_key_duplicates():
    key1 = make_symbol_key("python", "test.py", "helper", duplicate_index=1)
    key2 = make_symbol_key("python", "test.py", "helper", duplicate_index=2)
    key3 = make_symbol_key("python", "test.py", "helper", duplicate_index=3)

    assert key1 == "python:test.py::helper"
    assert key2 == "python:test.py::helper#2"
    assert key3 == "python:test.py::helper#3"


def test_symbol_id_determinism_and_namespace():
    snapshot_id = uuid.uuid4()
    symbol_key = "python:src/utils.py::format_date"

    id1 = make_symbol_id(snapshot_id, symbol_key)
    id2 = make_symbol_id(snapshot_id, symbol_key)

    assert isinstance(id1, uuid.UUID)
    assert id1 == id2
    # Verify generated with fixed namespace
    expected = uuid.uuid5(BLACKBOXRAG_NAMESPACE, f"{snapshot_id}{symbol_key}")
    assert id1 == expected


def test_symbol_id_snapshot_scoping():
    snapshot_1 = uuid.uuid4()
    snapshot_2 = uuid.uuid4()
    symbol_key = "python:src/utils.py::format_date"

    id_snap1 = make_symbol_id(snapshot_1, symbol_key)
    id_snap2 = make_symbol_id(snapshot_2, symbol_key)

    # Identical symbol in different snapshots MUST NOT collide
    assert id_snap1 != id_snap2


def test_chunk_id_determinism():
    symbol_id = uuid.uuid4()

    chunk_0 = make_chunk_id(symbol_id, part_index=0)
    chunk_0_again = make_chunk_id(symbol_id, part_index=0)
    chunk_1 = make_chunk_id(symbol_id, part_index=1)

    assert chunk_0 == chunk_0_again
    assert chunk_0 != chunk_1
