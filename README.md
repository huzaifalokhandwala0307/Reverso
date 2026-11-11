
# BlackBoxRAG


> **Structure-Aware Repository Intelligence & Reverse-Engineering Platform**

BlackBoxRAG analyzes software repositories, reconstructs their architecture, traces static execution and dependency relationships, investigates failures with line-cited reports, and verifies claims against source code.

---


## Current Status: Milestone 1 (Backend Foundation)


### What Works Now

- **FastAPI REST API**: Core application structure (`backend/app/`) with health endpoints, strict GitHub URL validation, and standard error envelopes (`{"error": {"code", "message", "details"}}`).
- **Data Models & Schema**: SQLAlchemy 2.0 ORM models and Alembic migration `0001` for `repositories` and `snapshots`. Supports both SQLite (local/testing) and PostgreSQL (production).
- **Snapshot Scoping**: All repository data is architected to hang off unique `snapshot_id` identifiers (repository + commit SHA).
- **Deterministic ID Generation**: `backend/app/utils/ids.py` implements RFC 4122 UUIDv5 hashing for `symbol_key`, `symbol_id`, and `chunk_id` under a fixed namespace.
- **REST Endpoints**:
  - `GET /health` (liveness)
  - `GET /health/ready` (readiness with database connectivity check)
  - `POST /api/repositories` (register repository via GitHub URL)
  - `GET /api/repositories` (cursor-based pagination)
  - `GET /api/repositories/{id}` (repository details)
  - `PATCH /api/repositories/{id}` (update default branch and privacy flags)
  - `POST /api/repositories/{id}/snapshots` (create snapshot; returns 409 `duplicate_snapshot` if commit SHA already exists)
  - `GET /api/repositories/{id}/snapshots` (list snapshots for repository)
  - `GET /api/snapshots/{id}` (snapshot details)
- **Privacy Gating by Default**: Per-repository privacy flags `allow_external_embeddings` and `allow_external_llm` default to `false`.
- **Docker Compose**: Production compose specification with PostgreSQL 16 and backend API running automated database migrations.
- **Continuous Integration**: GitHub Actions workflow running Ruff linting, formatting check, and Pytest with a live PostgreSQL service.


### What Does NOT Work Yet (Targeted for Later Milestones)

- **Repository Ingestion & Cloning**: Git cloning, ZIP extraction, and file discovery (Milestone 3).
- **Static Code Parsing**: AST / Tree-sitter extraction of symbols, calls, imports, and tests (Milestone 4).
- **Multi-Index Construction**: Vector indexing in Qdrant, BM25 lexical indexing, and NetworkX graph generation (Milestones 4–5).
- **Search & Retrieval**: Hybrid dense/sparse retrieval and cross-encoder reranking (Milestone 6).
- **Investigation & Verification**: Failure investigation, citation verification, and report generation (Milestone 7).
- **Web UI**: Frontend dashboard and Monaco code viewer (Milestone 8).

---

## Getting Started


### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for PostgreSQL)

### Running Locally with Docker Compose

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000` with interactive OpenAPI documentation at `http://localhost:8000/docs`.

### Running Locally with Virtual Environment

```bash
# 1. Create and activate virtual environment

python -m venv .venv
source .venv/bin/activate # On Windows: .venv\Scripts\activate

# 2. Install backend dependencies

pip install -r backend/requirements.txt


# 3. Configure environment

cp backend/.env.example backend/.env

# 4. Run database migrations

cd backend
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests and Linting

```bash
cd backend
ruff check .
ruff format --check .
pytest -v
```

---


## Legacy Reference Code

The original educational document RAG tutorial code from which this project evolved is preserved for reference under `legacy/` (unmaintained). See [`NOTICE`](./NOTICE) for attribution and licensing details.
