"""initial repositories and snapshots

Revision ID: 0001
Revises:
Create Date: 2026-11-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUS_CONSTRAINT = (
    "status IN ('created', 'cloning', 'parsing', 'chunking', 'embedding', "
    "'graph_building', 'indexed', 'failed')"
)


def upgrade() -> None:
    # ── 1. Create repositories table ──────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="github"),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column(
            "allow_external_embeddings",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.false(),
        ),
        sa.Column(
            "allow_external_llm",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(op.f("ix_repositories_owner_id"), "repositories", ["owner_id"], unique=False)
    op.create_index(op.f("ix_repositories_name"), "repositories", ["name"], unique=False)

    # ── 2. Create snapshots table ─────────────────────────────────────────────
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("commit_sha", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="created"),
        sa.Column("embed_model", sa.String(length=255), nullable=True),
        sa.Column("embed_dim", sa.Integer(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_snapshots_repository_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            STATUS_CONSTRAINT,
            name="ck_snapshots_status",
        ),
        sa.UniqueConstraint(
            "repository_id",
            "commit_sha",
            name="uq_snapshots_repository_commit",
        ),
    )
    op.create_index(
        op.f("ix_snapshots_repository_id"),
        "snapshots",
        ["repository_id"],
        unique=False,
    )
    op.create_index(op.f("ix_snapshots_commit_sha"), "snapshots", ["commit_sha"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_snapshots_commit_sha"), table_name="snapshots")
    op.drop_index(op.f("ix_snapshots_repository_id"), table_name="snapshots")
    op.drop_table("snapshots")

    op.drop_index(op.f("ix_repositories_name"), table_name="repositories")
    op.drop_index(op.f("ix_repositories_owner_id"), table_name="repositories")
    op.drop_table("repositories")
