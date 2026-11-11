# BlackBoxRAG: API Endpoints (v1)

Base URL: `/api` (health endpoints are unprefixed). Framework: FastAPI. Format: JSON unless stated.

Design rules:

- **Snapshot-scoped analysis.** Everything about code (files, symbols, graph, search, investigations) hangs off a `snapshot_id`, so results never mix commits. A repository is just the owner of snapshots.
- **Long work is asynchronous.** Ingestion, indexing and investigations return `202 Accepted` with a job or resource to poll.
- **Auth:** Supabase JWT in `Authorization: Bearer <token>`, validated in FastAPI. All `/api` routes require it except where marked _public_.
- **Ownership:** every resource is checked against the caller's `owner_id`.

---

## 1. Endpoint Index

| #   | Method | Path                                                       | Purpose                                    | Milestone                |
| --- | ------ | ---------------------------------------------------------- | ------------------------------------------ | ------------------------ |
| 1   | GET    | `/health`                                                  | Liveness                                   | M1                       |
| 2   | GET    | `/health/ready`                                            | Readiness (DB, Qdrant)                     | M1                       |
| 3   | GET    | `/api/me`                                                  | Current user                               | M3                       |
| 4   | POST   | `/api/repositories`                                        | Register repository (GitHub URL)           | M1                       |
| 5   | POST   | `/api/repositories/upload`                                 | Register repository from ZIP               | M3                       |
| 6   | GET    | `/api/repositories`                                        | List repositories                          | M1                       |
| 7   | GET    | `/api/repositories/{repository_id}`                        | Repository details                         | M1                       |
| 8   | PATCH  | `/api/repositories/{repository_id}`                        | Update settings and privacy flags          | M1                       |
| 9   | DELETE | `/api/repositories/{repository_id}`                        | Delete repository and all data             | M3                       |
| 10  | POST   | `/api/repositories/{repository_id}/snapshots`              | Create snapshot and start ingestion        | M1 (record), M3 (ingest) |
| 11  | GET    | `/api/repositories/{repository_id}/snapshots`              | List snapshots                             | M1                       |
| 12  | GET    | `/api/snapshots/{snapshot_id}`                             | Snapshot details                           | M1                       |
| 13  | GET    | `/api/snapshots/{snapshot_id}/status`                      | Pipeline progress                          | M3                       |
| 14  | DELETE | `/api/snapshots/{snapshot_id}`                             | Delete snapshot and its indexes            | M3                       |
| 15  | POST   | `/api/snapshots/{snapshot_id}/reindex`                     | Rebuild indexes (e.g. new embed model)     | M6                       |
| 16  | GET    | `/api/jobs/{job_id}`                                       | Job status                                 | M3                       |
| 17  | GET    | `/api/snapshots/{snapshot_id}/jobs`                        | Jobs for a snapshot                        | M3                       |
| 18  | GET    | `/api/snapshots/{snapshot_id}/files`                       | File tree and metadata                     | M3                       |
| 19  | GET    | `/api/snapshots/{snapshot_id}/files/content`               | Source text (by path, optional line range) | M3                       |
| 20  | GET    | `/api/snapshots/{snapshot_id}/symbols`                     | List and filter symbols                    | M4                       |
| 21  | GET    | `/api/symbols/{symbol_id}`                                 | Symbol details                             | M4                       |
| 22  | GET    | `/api/symbols/{symbol_id}/relations`                       | Callers, callees, imports, tests           | M4                       |
| 23  | GET    | `/api/snapshots/{snapshot_id}/graph`                       | Dependency graph (filtered)                | M5                       |
| 24  | GET    | `/api/snapshots/{snapshot_id}/graph/neighbors`             | k-hop neighborhood of a symbol             | M5                       |
| 25  | GET    | `/api/snapshots/{snapshot_id}/architecture`                | Reconstructed architecture                 | M7                       |
| 26  | POST   | `/api/snapshots/{snapshot_id}/search`                      | Raw retrieval (no LLM)                     | M6                       |
| 27  | POST   | `/api/snapshots/{snapshot_id}/investigations`              | Ask an investigation question              | M7                       |
| 28  | GET    | `/api/investigations/{investigation_id}`                   | Investigation report and status            | M7                       |
| 29  | GET    | `/api/snapshots/{snapshot_id}/investigations`              | List past investigations                   | M7                       |
| 30  | POST   | `/api/snapshots/{snapshot_id}/analyze/root-cause`          | Root-cause analysis                        | v2                       |
| 31  | POST   | `/api/snapshots/{snapshot_id}/analyze/impact`              | Change-impact analysis                     | v2                       |
| 32  | POST   | `/api/snapshots/{snapshot_id}/analyze/execution-flow`      | Execution path reconstruction              | v2                       |
| 33  | GET    | `/api/github/installations`                                | GitHub App installations for user          | M3                       |
| 34  | GET    | `/api/github/installations/{installation_id}/repositories` | Repos available to import                  | M3                       |
| 35  | POST   | `/api/webhooks/github`                                     | Push events (signature-verified)           | later                    |

Relation to the original blueprint: `/api/repositories/{id}/ingest` becomes snapshot creation (#10), `/api/investigate` becomes #27, and `/api/analyze/*` are snapshot-scoped (#30-32).

---

## 2. Conventions

### Identifiers

UUIDs. Symbols are also addressable by `symbol_key` (e.g. `py:services/auth.py::AuthService.authenticate`) through query parameters, since keys are stable across commits.

### Pagination

`?limit=50&cursor=<opaque>`; default 50, max 200. Response:

```json
{ "items": [], "next_cursor": null }
```

### Error format

```json
{
  "error": {
    "code": "snapshot_not_ready",
    "message": "Snapshot is still indexing.",
    "details": { "status": "embedding" }
  }
}
```

| HTTP | Typical `code`                                                |
| ---- | ------------------------------------------------------------- |
| 400  | `invalid_request`, `invalid_ref`, `unsupported_language`      |
| 401  | `unauthenticated`                                             |
| 403  | `forbidden`, `external_processing_not_allowed`                |
| 404  | `not_found`                                                   |
| 409  | `snapshot_not_ready`, `duplicate_snapshot`, `job_in_progress` |
| 413  | `archive_too_large`                                           |
| 422  | Pydantic validation errors                                    |
| 429  | `rate_limited`                                                |
| 502  | `upstream_error` (GitHub, embedding or LLM provider)          |

### Status enums

```
snapshot.status : created | cloning | parsing | chunking | embedding | graph_building
                  | indexed | failed
job.status      : queued | running | succeeded | failed
job.type        : clone | parse | chunk | embed | build_graph | index_bm25
investigation.status : queued | running | completed | abstained | failed
```

### Evidence labels (used in reports)

`confirmed` (directly in source), `inferred` (static analysis), `hypothesis` (not directly supported).

---

## 3. Health

### GET `/health` (public)

```json
{ "status": "ok" }
```

### GET `/health/ready` (public)

```json
{ "status": "ok", "database": "ok", "qdrant": "ok", "version": "0.1.0" }
```

Returns `503` if a dependency is down.

---

## 4. Users and GitHub

### GET `/api/me`

```json
{ "id": "uuid", "email": "user@example.com" }
```

### GET `/api/github/installations`

Lists GitHub App installations linked to the user. Installation tokens are used only server-side.

### GET `/api/github/installations/{installation_id}/repositories`

```json
{
  "items": [
    { "full_name": "org/repo", "default_branch": "main", "private": true }
  ],
  "next_cursor": null
}
```

---

## 5. Repositories

### POST `/api/repositories`

Register a repository from GitHub.

Request:

```json
{
  "source": "github",
  "url": "https://github.com/org/repo",
  "installation_id": 12345678,
  "default_branch": "main",
  "allow_external_embeddings": false,
  "allow_external_llm": false
}
```

`installation_id` is required for private repositories. Privacy flags default to `false`.

Response `201`:

```json
{
  "id": "uuid",
  "source": "github",
  "url": "https://github.com/org/repo",
  "default_branch": "main",
  "allow_external_embeddings": false,
  "allow_external_llm": false,
  "created_at": "2026-11-09T10:00:00Z"
}
```

### POST `/api/repositories/upload`

`multipart/form-data`: `file` (ZIP), `name`, optional privacy flags. Archive paths are validated against traversal; size and file-count limits apply (`413 archive_too_large`). Response `201` as above with `"source": "zip"`.

### GET `/api/repositories`

Query: `limit`, `cursor`. Lists the caller's repositories with their latest snapshot status.

### GET `/api/repositories/{repository_id}`

Repository fields plus `latest_snapshot` summary.

### PATCH `/api/repositories/{repository_id}`

```json
{
  "default_branch": "develop",
  "allow_external_embeddings": true,
  "allow_external_llm": false
}
```

Changing an `allow_*` flag does not alter existing indexes; it controls future embedding and LLM calls. Re-embedding with a different provider requires `reindex` (#15).

### DELETE `/api/repositories/{repository_id}`

Deletes the repository, all snapshots, Postgres rows, Qdrant points and cached graphs. Response `202` with a cleanup job.

---

## 6. Snapshots and Ingestion

### POST `/api/repositories/{repository_id}/snapshots`

Creates a snapshot for a commit and enqueues ingestion.

Request:

```json
{
  "ref": "main",
  "embedding": { "provider": "voyage", "model": "voyage-code-4" }
}
```

`ref` may be a branch, tag or commit SHA and is resolved to a commit SHA. `embedding` is optional (defaults from server settings). If `provider` is external and the repository's `allow_external_embeddings` is false, returns `403 external_processing_not_allowed`. If a snapshot for the same commit and embedding model already exists and is indexed, returns `409 duplicate_snapshot` with its ID.

Response `202`:

```json
{
  "snapshot_id": "uuid",
  "commit_sha": "abc123...",
  "status": "created",
  "job_id": "uuid"
}
```

### GET `/api/repositories/{repository_id}/snapshots`

Paginated list ordered by creation time.

### GET `/api/snapshots/{snapshot_id}`

```json
{
  "id": "uuid",
  "repository_id": "uuid",
  "commit_sha": "abc123...",
  "status": "indexed",
  "embed_model": "voyage-code-4",
  "embed_dim": 1024,
  "indexed_at": "2026-11-09T10:12:00Z",
  "stats": {
    "files": 214,
    "symbols": 1830,
    "chunks": 1902,
    "edges": 5120,
    "unresolved_edge_ratio": 0.18
  }
}
```

### GET `/api/snapshots/{snapshot_id}/status`

```json
{
  "status": "embedding",
  "progress": { "stage": "embedding", "done": 640, "total": 1902 },
  "jobs": [
    { "id": "uuid", "type": "parse", "status": "succeeded" },
    { "id": "uuid", "type": "embed", "status": "running" }
  ],
  "error": null
}
```

### POST `/api/snapshots/{snapshot_id}/reindex`

Request (all optional): `{ "embedding": {...}, "rebuild": ["embed", "bm25", "graph"] }`. Response `202` with job IDs. Does not re-parse unless `"parse"` is included.

### DELETE `/api/snapshots/{snapshot_id}`

Removes the snapshot and its Qdrant points, BM25 data and graph cache. Response `202`.

---

## 7. Jobs

### GET `/api/jobs/{job_id}`

```json
{
  "id": "uuid",
  "snapshot_id": "uuid",
  "type": "embed",
  "status": "running",
  "attempts": 1,
  "error": null,
  "created_at": "2026-11-09T10:05:00Z"
}
```

### GET `/api/snapshots/{snapshot_id}/jobs`

All jobs for a snapshot.

---

## 8. Code Browsing

Available once the snapshot has reached at least `chunking`; otherwise `409 snapshot_not_ready`.

### GET `/api/snapshots/{snapshot_id}/files`

Query: `language`, `is_test`, `path_prefix`, `limit`, `cursor`.

```json
{
  "items": [
    {
      "id": "uuid",
      "rel_path": "services/auth.py",
      "language": "python",
      "loc": 120,
      "is_test": false,
      "parse_status": "ok"
    }
  ],
  "next_cursor": null
}
```

### GET `/api/snapshots/{snapshot_id}/files/content`

Query: `path` (required), `start_line`, `end_line`.

```json
{
  "rel_path": "services/auth.py",
  "language": "python",
  "start_line": 1,
  "end_line": 40,
  "content": "..."
}
```

Used by the Monaco viewer and to jump to cited lines.

### GET `/api/snapshots/{snapshot_id}/symbols`

Query: `kind` (function|method|class|module|endpoint|test), `name`, `qualname`, `file_path`, `symbol_key`, `limit`, `cursor`.

```json
{
  "items": [
    {
      "id": "uuid",
      "symbol_key": "py:services/auth.py::AuthService.authenticate",
      "kind": "method",
      "name": "authenticate",
      "qualname": "AuthService.authenticate",
      "file_path": "services/auth.py",
      "start_line": 15,
      "end_line": 32
    }
  ],
  "next_cursor": null
}
```

### GET `/api/symbols/{symbol_id}`

Symbol fields plus `signature`, `docstring`, `decorators`, `parent`, and its chunk IDs.

### GET `/api/symbols/{symbol_id}/relations`

Query: `types` (comma list of CALLS, IMPORTS, INHERITS, TESTS, ...), `direction` (in|out|both), `min_confidence`.

```json
{
  "symbol_id": "uuid",
  "outgoing": [
    {
      "edge_type": "CALLS",
      "target": { "id": "uuid", "qualname": "verify_password" },
      "resolution": "import_resolved",
      "confidence": 0.9,
      "evidence_line": 18
    },
    {
      "edge_type": "CALLS",
      "target": null,
      "unresolved_name": "user.save",
      "resolution": "unresolved",
      "confidence": 0.0,
      "evidence_line": 24
    }
  ],
  "incoming": []
}
```

---

## 9. Graph and Architecture

### GET `/api/snapshots/{snapshot_id}/graph`

Query: `level` (module|class|function, default module), `edge_types`, `min_confidence`, `path_prefix`, `max_nodes` (default 500).

```json
{
  "nodes": [{ "id": "uuid", "label": "services.auth", "kind": "module" }],
  "edges": [
    { "source": "uuid", "target": "uuid", "type": "IMPORTS", "confidence": 1.0 }
  ],
  "truncated": false
}
```

Shape is designed for React Flow. If the graph exceeds `max_nodes`, it is truncated by degree and `truncated` is true.

### GET `/api/snapshots/{snapshot_id}/graph/neighbors`

Query: `symbol_id` or `symbol_key`, `hops` (1-4, default 2), `edge_types`, `min_confidence`, `direction`.
Same node and edge shape, rooted at the given symbol.

### GET `/api/snapshots/{snapshot_id}/architecture`

Reconstructed summary: layers and modules, API-to-service map, database interaction map, entry points. Generated asynchronously on first request: returns `202` with `Retry-After` while building, then `200`. Each item carries evidence references; inferred groupings are labelled `inferred`.

---

## 10. Retrieval

### POST `/api/snapshots/{snapshot_id}/search`

Raw hybrid retrieval with no LLM call. Used by the UI "evidence" view and by the evaluation harness (ablations E1-E5).

Request:

```json
{
  "query": "where are login credentials validated?",
  "top_k": 10,
  "channels": { "vector": true, "bm25": true, "graph": true },
  "rerank": true,
  "filters": {
    "language": "python",
    "kind": ["function", "method"],
    "is_test": false
  }
}
```

Response:

```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "symbol_id": "uuid",
      "symbol_key": "py:services/auth.py::AuthService.authenticate",
      "file_path": "services/auth.py",
      "start_line": 15,
      "end_line": 32,
      "score": 0.0312,
      "channels": { "vector_rank": 1, "bm25_rank": 3, "graph_rank": null },
      "snippet": "def authenticate(self, email, password): ..."
    }
  ],
  "timings_ms": {
    "vector": 42,
    "bm25": 6,
    "graph": 11,
    "fusion": 1,
    "rerank": 180
  }
}
```

---

## 11. Investigations

### POST `/api/snapshots/{snapshot_id}/investigations`

Request:

```json
{
  "question": "Why does the login API return 500 when the database connection fails?",
  "type": "auto",
  "options": {
    "top_k": 12,
    "channels": { "vector": true, "bm25": true, "graph": true },
    "rerank": true,
    "allow_llm": true
  }
}
```

`type`: `auto | explain | locate | execution_flow | root_cause | impact | architecture`. If `allow_llm` is true but the repository's `allow_external_llm` is false, the request uses the configured local LLM, or returns `403 external_processing_not_allowed` if none is available.

Response `202`:

```json
{ "investigation_id": "uuid", "status": "queued" }
```

### GET `/api/investigations/{investigation_id}`

```json
{
  "id": "uuid",
  "snapshot_id": "uuid",
  "status": "completed",
  "question": "Why does the login API return 500 when the database connection fails?",
  "query_type": "root_cause",
  "sub_queries": [
    "Locate the login API endpoint",
    "Identify the authentication function",
    "Trace database dependencies",
    "Locate database connection handling",
    "Identify exception propagation and HTTP response handling"
  ],
  "report": {
    "entry_point": {
      "symbol_key": "py:routes/auth.py::login",
      "file_path": "routes/auth.py",
      "start_line": 12,
      "end_line": 30
    },
    "execution_path": [
      { "symbol_key": "py:routes/auth.py::login", "label": "confirmed" },
      {
        "symbol_key": "py:services/auth.py::AuthService.authenticate",
        "label": "confirmed"
      },
      {
        "symbol_key": "py:database/connection.py::get_connection",
        "label": "inferred"
      }
    ],
    "findings": [
      {
        "statement": "A failed connection raises an exception that is not caught in login().",
        "label": "inferred",
        "citations": [
          {
            "file_path": "database/connection.py",
            "start_line": 8,
            "end_line": 20
          },
          { "file_path": "routes/auth.py", "start_line": 12, "end_line": 30 }
        ]
      }
    ],
    "suggested_investigation": [
      "Inspect exception handling around get_connection"
    ],
    "confidence": {
      "overall": "medium",
      "notes": "Call from authenticate to get_connection is heuristic."
    },
    "unsupported_claims_removed": 1
  },
  "verification": { "citations_checked": 5, "citations_valid": 5 },
  "error": null,
  "created_at": "2026-11-09T10:20:00Z"
}
```

When evidence is insufficient: `"status": "abstained"` with a `report.reason` field instead of fabricated findings.

### GET `/api/snapshots/{snapshot_id}/investigations`

Paginated list with question, type, status and time.

---

## 12. Specialized Analyses (v2)

All three return `202` with an `investigation_id` and are read through `GET /api/investigations/{id}`, using the same report envelope.

### POST `/api/snapshots/{snapshot_id}/analyze/root-cause`

```json
{
  "symptom": "POST /login returns HTTP 500 when the database is down",
  "stack_trace": "optional pasted trace",
  "logs": "optional pasted log excerpt",
  "entry_point": "py:routes/auth.py::login"
}
```

Output: ranked candidate causes with evidence, exception-handler discovery, propagation path.

### POST `/api/snapshots/{snapshot_id}/analyze/impact`

```json
{
  "target": { "symbol_key": "py:services/auth.py::verify_password" },
  "max_depth": 4,
  "min_confidence": 0.5
}
```

Output: direct and indirect dependents, affected endpoints, related tests, database operations. Includes a `coverage_note`, because impact analysis is a prediction rather than a guarantee.

### POST `/api/snapshots/{snapshot_id}/analyze/execution-flow`

```json
{
  "entry_point": { "symbol_key": "py:routes/auth.py::login" },
  "max_depth": 6,
  "min_confidence": 0.5
}
```

Output: possible call paths labelled `confirmed` or `inferred`, with unresolved branches listed explicitly.

---

## 13. Webhooks (later)

### POST `/api/webhooks/github` (public, signature-verified)

Verifies `X-Hub-Signature-256`. On `push` to a tracked branch, enqueues a new snapshot (optionally reusing unchanged-file results by `sha256`). Idempotent by delivery ID.

---

## 14. Security and Limits

- JWT validation on every `/api` route; resource ownership checked on every access.
- Privacy flags enforced server-side before any call to an external embedding or LLM provider.
- ZIP uploads: path traversal checks, size, file-count and compression-ratio limits.
- Repository content is never executed.
- Rate limits on ingestion, search and investigations per user.
- Secrets detected during ingestion are redacted from stored chunks and API responses.
- CORS restricted to the frontend origin.

---

## 15. M1 Subset

Implement first (no embeddings, no LLM): `GET /health`, `GET /health/ready`, `POST/GET /api/repositories`, `GET/PATCH /api/repositories/{id}`, `POST/GET /api/repositories/{id}/snapshots`, `GET /api/snapshots/{id}`. In M1, snapshot creation only writes the record (status `created`); ingestion is wired in at M3.

---

## 16. Python Schema Sketch (Pydantic v2)

```python
from pydantic import BaseModel, HttpUrl
from uuid import UUID
from datetime import datetime

class RepositoryCreate(BaseModel):
    source: str = "github"
    url: HttpUrl
    installation_id: int | None = None
    default_branch: str = "main"
    allow_external_embeddings: bool = False
    allow_external_llm: bool = False

class RepositoryOut(BaseModel):
    id: UUID
    source: str
    url: str
    default_branch: str
    allow_external_embeddings: bool
    allow_external_llm: bool
    created_at: datetime

class SnapshotCreate(BaseModel):
    ref: str = "main"
    embedding: dict | None = None

class SnapshotOut(BaseModel):
    id: UUID
    repository_id: UUID
    commit_sha: str
    status: str
    embed_model: str | None = None
    embed_dim: int | None = None
    indexed_at: datetime | None = None
```
