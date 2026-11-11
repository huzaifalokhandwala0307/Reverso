from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_migrations_upgrade_and_downgrade():
    """Verify that Alembic migrations run up to head and downgrade cleanly."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"
    test_db_path = backend_dir / "test_migration.db"

    # Clean up any leftover test db
    if test_db_path.exists():
        test_db_path.unlink()

    test_db_url = f"sqlite:///{test_db_path.as_posix()}"

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(test_db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "repositories" in tables
    assert "snapshots" in tables
    assert "alembic_version" in tables

    # Verify columns in repositories table
    repo_cols = {col["name"] for col in inspector.get_columns("repositories")}
    expected_repo_cols = {
        "id",
        "owner_id",
        "source",
        "name",
        "url",
        "installation_id",
        "default_branch",
        "allow_external_embeddings",
        "allow_external_llm",
        "created_at",
    }
    assert expected_repo_cols.issubset(repo_cols)

    # Verify columns in snapshots table
    snap_cols = {col["name"] for col in inspector.get_columns("snapshots")}
    expected_snap_cols = {
        "id",
        "repository_id",
        "ref",
        "commit_sha",
        "status",
        "embed_model",
        "embed_dim",
        "indexed_at",
        "error",
        "created_at",
    }
    assert expected_snap_cols.issubset(snap_cols)

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(engine)
    tables_after_downgrade = inspector.get_table_names()
    assert "repositories" not in tables_after_downgrade
    assert "snapshots" not in tables_after_downgrade

    # 3. Clean up
    engine.dispose()
    if test_db_path.exists():
        test_db_path.unlink()
