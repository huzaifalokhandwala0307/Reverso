# BlackBoxRAG: Project Details

AI-powered, structure-aware software reverse-engineering and repository intelligence platform.

> Status: pre-implementation. Architecture, v1 stack, schemas and migration plan are defined. Next step: Milestone 1 (backend foundation).

---

## 1. Overview

BlackBoxRAG analyzes unfamiliar software repositories, reconstructs their architecture, traces execution and dependency relationships, investigates likely root causes of failures, and predicts the impact of code changes. Answers are grounded in retrieved evidence with file and line-level citations.

It differs from conventional code RAG in three ways:

1. **Structure-aware chunking.** Chunks are functions, methods and classes from AST/Tree-sitter parsing, not fixed-size text windows.
2. **Multi-channel retrieval.** Vector, lexical (BM25) and graph retrieval are fused (RRF) and reranked.
3. **Evidence discipline.** Claims are verified against source, and the system separates confirmed behaviour, statically inferred behaviour and hypotheses. It can abstain when evidence is insufficient.

### Objectives

- Ingest repositories from GitHub, ZIP and local directories.
- Extract functions, classes, methods, imports, endpoints and call relationships.
- Build semantic, lexical and graph indexes under shared identifiers.
- Decompose investigation questions and retrieve evidence across all channels.
- Produce cited investigation reports (architecture, execution flow, root cause, impact).
- Later: compare static inference with runtime traces.
- Evaluate retrieval quality, dependency accuracy, citation accuracy and efficiency.

---

## 2. Architecture

| Layer | Component              | Responsibility                                                   |
| ----- | ---------------------- | ---------------------------------------------------------------- |
| L1    | Repository interface   | Accept GitHub URLs, ZIPs, local repos                            |
| L2    | Repository ingestion   | Discover, classify, filter files; create snapshots               |
| L3    | Code intelligence      | Parsing, symbol and relationship extraction, structural chunking |
| L4    | Knowledge construction | Vector, lexical and graph indexes                                |
| L5    | Hybrid retrieval       | Query routing, multi-channel retrieval, fusion, reranking        |
| L6    | Investigation engine   | Decomposition, dependency tracing, verification                  |
| L7    | Response generation    | Grounded explanations and reports with citations                 |
| L8    | Visualization          | Dashboard, architecture explorer, code viewer                    |

### Pipeline

```
GitHub / ZIP -> Ingestion -> File classification -> Language detection
  -> AST / Tree-sitter parsing -> Symbols + relationships (IR)
  -> Structural chunking -> Multi-index (Qdrant + BM25 + graph)
  -> Hybrid + graph retrieval -> Investigation engine
  -> Evidence verification -> Cited report
```

### Core modules

| Module                | Purpose                                                 |
| --------------------- | ------------------------------------------------------- |
| Architecture analyzer | Modules, layers, API-to-service and DB interaction maps |
| Execution analyzer    | Possible call paths (static first, runtime later)       |
| Root-cause analyzer   | Logs, stack traces, exception paths, ranked causes      |
| Impact analyzer       | Direct and indirect dependents, endpoints, tests        |
| Dependency analyzer   | Imports and dependency mapping                          |
| Evidence verifier     | Validates symbols, locations and claims                 |
| Confidence manager    | Tracks uncertainty in graph edges and conclusions       |

Impact analysis is a prediction, not a guarantee of completeness.

---

## 3. v1 Technology Stack

### Backend

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Uvicorn, HTTPX, Pytest, GitPython, PyGithub.

### Auth and GitHub

Supabase Auth (JWT validated in FastAPI), GitHub App (installation tokens handled only by the backend), GitHub REST API, Git CLI. Webhooks later.

### Data stores

| Store                 | Role                                                                                                 |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| PostgreSQL (Supabase) | Source of truth: users, repositories, snapshots, files, symbols, edges, chunks, jobs, investigations |
| Qdrant                | Embeddings and filterable payloads (chunk text is fetched from Postgres)                             |
| NetworkX              | In-memory, snapshot-specific graph built from Postgres and cached                                    |
| rank-bm25             | In-memory lexical index (code-aware tokenization)                                                    |

### Code intelligence

Python `ast` for Python, Tree-sitter (+ `tree-sitter-language-pack`) for additional languages, `pathspec` for gitignore-style filtering, `charset-normalizer` for encoding detection, a custom structural chunker.

### Retrieval and generation

- Query router: custom Python. Query decomposition: LLM.
- Fusion: Reciprocal Rank Fusion, keyed by `chunk_id`.
- Reranker: cross-encoder (candidate: `BAAI/bge-reranker-v2-m3`, benchmark first).
- Embeddings: Voyage Code 4 (primary candidate) vs Jina Code (benchmark); local Sentence Transformers/Ollama for private repos.
- LLM: OpenAI primary, Gemini alternative, behind a provider abstraction (LiteLLM or the base repo's `BaseLLM`).
- Structured outputs via Pydantic. The LLM reasons over retrieved evidence only; it must not invent architecture or execution paths.

### Frontend

React, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Router, TanStack Query, Zustand, React Flow, Monaco Editor, Recharts, Axios.

### Infrastructure

Docker, Docker Compose, GitHub Actions, Vercel (frontend), Render (backend initially), Supabase Cloud, Qdrant Cloud, Sentry, pytest-cov.

### Provisional choices (decide with evaluation results)

Embedding model, reranker, LLM provider.

### Explicitly postponed

Neo4j (if NetworkX becomes insufficient), Elasticsearch/OpenSearch, Redis + Celery, Kubernetes, Kafka, multiple vector databases, custom embedding training.

---

## 4. Identifiers and Schemas

### 4.1 Identifier convention

```
snapshot_id = uuid                               # one per (repository, commit_sha)
symbol_key  = "{lang}:{rel_path}::{qualname}"    # e.g. py:services/auth.py::AuthService.authenticate
              + "#2", "#3" for duplicate qualnames in a file
symbol_id   = uuid5(NAMESPACE, snapshot_id + symbol_key)
chunk_id    = uuid5(NAMESPACE, symbol_id + ":" + part_index)   # part_index = 0 unless sub-chunked
```

`symbol_key` is stable across commits (enables diffing). `symbol_id` and `chunk_id` are snapshot-scoped so stale and current results never mix.

### 4.2 PostgreSQL tables

```
repositories(id, owner_id NULL, source, url, default_branch,
             allow_external_embeddings, allow_external_llm, created_at)
snapshots(id, repository_id, commit_sha, status, indexed_at, embed_model, embed_dim)
files(id, snapshot_id, rel_path, language, sha256, loc, is_test, parse_status)
symbols(id, snapshot_id, file_id, symbol_key, kind, name, qualname, parent_id,
        start_line, end_line, signature, docstring, decorators jsonb)
edges(id, snapshot_id, src_symbol_id, dst_symbol_id NULL, dst_unresolved_name NULL,
      edge_type, resolution, confidence, evidence_line, evidence_file_id)
chunks(id, snapshot_id, symbol_id, part_index, text, token_count, start_line, end_line)
jobs(id, snapshot_id, type, status, attempts, error, locked_at, created_at)
investigations(id, snapshot_id, user_id, query, query_type, report jsonb, created_at)
```

`dst_symbol_id` may be NULL with `dst_unresolved_name` set, so unresolved calls are kept and the resolution rate can be measured.

### 4.3 Graph schema (NetworkX, built per snapshot)

```
node attrs: symbol_id, kind (module|class|function|method|endpoint|test),
            qualname, file, start_line, end_line
edge attrs: type (CONTAINS|IMPORTS|CALLS|INHERITS|DEFINES|TESTS|DECORATES),
            resolution (exact|import_resolved|heuristic|unresolved),
            confidence (0-1), evidence_line
```

Graph expansion multiplies path scores by edge confidence with hop decay, to avoid low-confidence edges and hub utilities flooding fusion.

### 4.4 Qdrant payload

One collection per embedding model and dimension (e.g. `chunks_voyage_code_4_1024`); point ID = `chunk_id`.

```json
{
  "repository_id": "...",
  "snapshot_id": "...",
  "symbol_id": "...",
  "symbol_key": "...",
  "file_path": "services/auth.py",
  "language": "python",
  "kind": "method",
  "qualname": "AuthService.authenticate",
  "parent_symbol_id": "...",
  "start_line": 3,
  "end_line": 9,
  "is_test": false
}
```

Payload holds filter fields only. Create payload indexes on `snapshot_id` and `kind`.

### 4.5 Intermediate representation (all parsers)

```json
{
  "language": "python",
  "kind": "method",
  "name": "authenticate",
  "qualname": "AuthService.authenticate",
  "file_path": "services/auth.py",
  "start_line": 15,
  "end_line": 32
}
```

The call extractor must record resolution status and confidence rather than assuming every call has a known destination.

---

## 5. Retrieval Design

1. **Query understanding:** classify intent (e.g. root-cause, architecture, impact, locate).
2. **Decomposition:** split into sub-queries (locate endpoint, find service function, trace DB dependencies, find error handling).
3. **Channels:** dense (Qdrant), sparse (BM25 with identifier splitting: `getUserById` -> `get user by id`, plus original token), graph expansion.
4. **Graph seeding:** top vector and BM25 hits are seeds; expand k hops along typed edges with decay and confidence weighting.
5. **Fusion:** RRF over ranked `chunk_id` lists (`RRF(d) = sum 1 / (k + rank_r(d))`, k = 60). State clearly whether plain or weighted RRF is used in each ablation.
6. **Reranking:** cross-encoder over the fused candidate set.
7. **Context assembly and generation:** evidence package -> LLM -> cited report -> verifier -> final report with explicit confidence and abstention.

### Report structure

Question, entry point, execution path, potential failure point, error propagation, supporting evidence (file + lines), suggested investigation, confidence. Findings are labelled confirmed, statically inferred or hypothesis.

---

## 6. Releases

| Release                         | Scope                                                                                                                                                                 |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v1.0 Core intelligence          | Repository ingestion, AST parsing, structural chunking, vector + BM25 + graph (NetworkX), hybrid retrieval, evidence-backed answers, basic architecture visualization |
| v2.0 Investigation intelligence | Multi-step decomposition, execution-flow reconstruction, root-cause analysis, change-impact analysis, evidence verification, advanced dashboard                       |
| v3.0 Runtime intelligence       | Sandboxed execution, instrumentation, dynamic call tracing, static vs dynamic comparison, more languages                                                              |

**Open scope decision:** the migration plan lists Python, Java, C++ and JavaScript parsers in v1. The recommendation is to implement Python only through retrieval and evaluation (baseline E1-E4), keep the IR language-agnostic, then add JS/TS, then Java. C++ call resolution is substantially harder.

---

## 7. Security and Reliability

| Risk                               | Mitigation                                                                                           |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Malicious repository code          | Never execute during ingestion                                                                       |
| Secret exposure                    | Detection and redaction; exclude sensitive files                                                     |
| Path traversal in archives         | Validate extraction paths                                                                            |
| Dependency attacks                 | Never auto-install dependencies                                                                      |
| Runtime exploitation               | Isolated, restricted Docker sandboxes; runtime off by default                                        |
| Resource exhaustion                | CPU, memory and time limits                                                                          |
| Prompt injection via source        | Treat repository content as untrusted data                                                           |
| Hallucinated dependencies          | Validate relationships against source evidence                                                       |
| Stale retrieval                    | Commit-based snapshot versioning                                                                     |
| Private code sent to third parties | Per-repo `allow_external_embeddings` / `allow_external_llm` (default False); local embedder/LLM path |

---

## 8. Research and Evaluation

### Hypothesis

Combining semantic retrieval, lexical retrieval and graph-based structural traversal improves relevance, completeness and reliability of retrieved evidence for software investigation tasks compared with conventional vector-only RAG.

### Ablations (same LLM, corpus, questions and settings)

| Experiment | Configuration                                  |
| ---------- | ---------------------------------------------- |
| E1         | Vector RAG                                     |
| E2         | Vector + BM25                                  |
| E3         | Vector + graph                                 |
| E4         | Vector + BM25 + graph                          |
| E5         | Full system: reranking + evidence verification |

### Metrics

Recall@K, Precision@K, MRR, NDCG@K, dependency precision/recall, root-cause accuracy, citation accuracy, answer faithfulness, abstention quality, latency, indexing time.

### Datasets

Repositories with many interconnected files, tests, documented issues and commit history. SWE-bench (issue localization), CodeSearchNet (retrieval) and CodeQL (static analysis) are complementary resources, not interchangeable benchmarks. A separate ground-truth set is needed for dependency reconstruction and execution flow (questions, relevant symbols, expected call edges, test links). **Start building it alongside parsing, not at the end.** Baseline the call-graph extractor against existing tools (e.g. Jedi, PyCG).

### Positioning

Graph-augmented code retrieval is an active area (e.g. RepoGraph, CodexGraph, GitNexus-style tools, SWE-agent localization work, Aider repo map). Do a literature pass; the distinctive contribution is likely evidence verification and the static-vs-dynamic comparison.

---

## 9. Base Repository and Migration Plan

**Base:** RAG-From-Scratch (`Abhilasha-Mangal/RAG-From-Scratch`), about 5,100 lines of Python. **License: Apache 2.0** (keep `LICENSE`, retain notices in reused files, mark modified files, add attribution in the README).

Keep the original in an archive branch or reference copy until replacements pass tests.

### What exists

Docling loader, four chunking strategies, embedders (local, OpenAI, Ollama), Chroma and Redis stores, retrievers (similarity, MMR, hybrid, rerank), prompt builder, LLM clients (Ollama, Groq, OpenAI), RAGAS evaluator, HyDE/query expansion/compression, ReAct and corrective agentic RAG, Gradio app, YAML config.

### File actions

| Existing                              | Action                          | Destination                                             |
| ------------------------------------- | ------------------------------- | ------------------------------------------------------- |
| `01_document_loading/loader.py`       | Replace                         | `app/ingestion/`                                        |
| `02_chunking/chunker.py`              | Replace                         | `app/chunking/structural_chunker.py`                    |
| `03_embeddings/embedder.py`           | Keep, extend (add Voyage, Jina) | `app/indexing/embedders/`                               |
| `04_vector_db/chroma/`                | Replace                         | `app/indexing/qdrant_store.py`                          |
| `04_vector_db/redis/`                 | Remove from v1                  | none                                                    |
| `04_vector_db/compare_dbs.py`         | Archive                         | `evaluation/`                                           |
| `05_retrieval/retriever.py`           | Refactor                        | `app/retrieval/` (new `fusion.py`)                      |
| `06_prompting/prompt_builder.py`      | Modify                          | `app/generation/prompt_manager.py`                      |
| `07_llm_integration/llm_client.py`    | Keep                            | `app/generation/llm_client.py`                          |
| `08_full_pipeline/pipeline.py`        | Rewrite                         | `app/services/`                                         |
| `08_full_pipeline/app.py` (Gradio)    | Replace                         | FastAPI                                                 |
| `09_evaluation/evaluator.py`          | Extend                          | `evaluation/` (retrieval-level metrics over symbol IDs) |
| `10_advanced/`, `11_agentic_rag/`     | Defer to v2                     | `app/investigation/`                                    |
| `src/models.py`                       | Replace                         | `app/models/`, `app/schemas/`                           |
| `src/config_loader.py`, `config.yaml` | Adapt                           | `app/config.py` (pydantic-settings, env-based)          |

### Findings from reading the code

- `BaseEmbedder` and `BaseLLM` are clean interfaces and worth keeping. Local and Ollama embedders double as the private-repo path.
- `HybridRetriever` uses alpha-weighted RRF, keys results by `text[:50]` (collides on repetitive code) and tokenizes BM25 with `.lower().split()`. Rewrite fusion to key by `chunk_id` and add code-aware tokenization.
- Numbered folders (`01_...`) are loaded through an `_import()` helper using `importlib`; this does not suit a FastAPI package, so port logic into proper `app/` modules.
- `Chunk(text, source, chunk_index, metadata)` lacks symbol ID, snapshot ID and line ranges; replacing it is the first priority.
- The RAGAS evaluator targets document QA; code retrieval needs custom metrics.

---

## 10. Target Directory Structure

```
BlackBoxRAG/
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  database.py
│   │   ├── api/            repositories.py  ingestion.py  analysis.py  investigation.py
│   │   ├── models/  schemas/
│   │   ├── ingestion/      github_loader, zip_loader, repository_manager, file_discovery,
│   │   │                   file_filter, language_detector, metadata_extractor, snapshot_manager
│   │   ├── parsers/        base, factory, python_parser, (java/cpp/javascript later),
│   │   │                   symbol_extractor, import_extractor, call_extractor
│   │   ├── chunking/       structural_chunker, function/class/module chunkers,
│   │   │                   context_builder, metadata_builder
│   │   ├── indexing/       embedders/, qdrant_store, lexical_index, index_manager
│   │   ├── graph/          graph_builder, graph_cache, graph_schema, graph_traversal,
│   │   │                   relationship_scorer
│   │   ├── retrieval/      query_analyzer, vector/lexical/graph retrievers, fusion, reranker,
│   │   │                   context_assembler
│   │   ├── investigation/  query_router, query_decomposer, architecture/execution/
│   │   │                   root_cause/impact/dependency analyzers, evidence_verifier
│   │   ├── generation/     llm_client, prompt_manager, answer_generator, citation_generator
│   │   ├── services/  workers/  runtime/ (v3)
│   ├── migrations/  tests/  requirements.txt  Dockerfile
├── frontend/
├── evaluation/   datasets/  benchmarks/  metrics/  experiments/
├── docs/
├── docker-compose.yml  .env.example  README.md  LICENSE  NOTICE
```

This is the target, not a requirement to create every file immediately.

---

## 11. API Surface (planned)

| Method | Endpoint                              | Purpose                    |
| ------ | ------------------------------------- | -------------------------- |
| POST   | `/api/repositories`                   | Register repository        |
| POST   | `/api/repositories/upload`            | Upload ZIP                 |
| GET    | `/api/repositories/{id}`              | Repository info            |
| POST   | `/api/repositories/{id}/ingest`       | Start ingestion            |
| GET    | `/api/repositories/{id}/status`       | Analysis progress          |
| GET    | `/api/repositories/{id}/architecture` | Architecture               |
| GET    | `/api/repositories/{id}/dependencies` | Dependency graph           |
| POST   | `/api/investigate`                    | Submit investigation query |
| POST   | `/api/analyze/root-cause`             | Root-cause analysis        |
| POST   | `/api/analyze/impact`                 | Change-impact analysis     |
| GET    | `/api/investigations/{id}`            | Retrieve report            |

Ingestion and analysis run asynchronously through a PostgreSQL-backed job worker (`jobs` table, `SELECT ... FOR UPDATE SKIP LOCKED`), not inside request handlers.

---

## 12. Frontend Sections

Dashboard (repo overview, stats), Architecture Explorer (React Flow), Investigation Workspace (questions, evidence, Monaco source viewer, reports), Execution Flow Explorer, Impact Analysis. The UI is a software-intelligence dashboard, not a plain chatbot.

---

## 13. Roadmap

| Milestone | Deliverable                              |
| --------- | ---------------------------------------- |
| M1        | Backend foundation + PostgreSQL          |
| M2        | Database schemas + migrations            |
| M3        | Repository ingestion + snapshots         |
| M4        | Parsers + IR (Python first)              |
| M5        | Structural chunking + evaluation dataset |
| M6        | Qdrant + BM25 + graph retrieval          |
| M7        | Investigation + LLM + verification       |
| M8        | API integration, frontend, deployment    |

Evaluation dataset work runs in parallel from M4 onward; ablation experiments run once M6 retrieval works.

### M1 definition of done

1. FastAPI server starts. 2. Connects to PostgreSQL. 3. Create a repository record. 4. Create a snapshot record. 5. Alembic migrations run. 6. Records retrievable through API. 7. Tests pass. No embeddings or LLM calls.

### M1 checklist

- [ ] Working branch / new repository (original preserved as archive)
- [ ] Backend directory structure
- [ ] Virtual environment
- [ ] FastAPI + Pydantic settings
- [ ] PostgreSQL connection
- [ ] SQLAlchemy base and session management
- [ ] Repository and snapshot models
- [ ] Alembic setup
- [ ] `/health` endpoint
- [ ] Test DB connection and migrations

### M1 implementation notes

- Run Alembic and the worker over a direct or session-pooler connection, not Supabase's transaction pooler (port 6543).
- Use local Postgres in `docker-compose.yml` for development and tests; Supabase for deployment. Test migrations by running `alembic upgrade head` against a throwaway DB in `conftest.py`.
- Start with synchronous SQLAlchemy 2.0 + psycopg 3; move to async only with a measured reason.
- Add nullable `owner_id` (no cross-schema FK to `auth.users`) to `repositories` now.
- Keep status values as a Postgres enum or check constraint.

---

## 14. Open Decisions

1. **Language scope for v1:** Python only (recommended) vs four languages.
2. **Embedding model:** Voyage Code 4 vs Jina Code vs local models (benchmark).
3. **Reranker:** `bge-reranker-v2-m3` vs alternatives on code retrieval.
4. **LLM provider and abstraction:** OpenAI/Gemini via LiteLLM vs the base repo's `BaseLLM`.
5. **Plain vs weighted RRF** per ablation, and graph-expansion parameters (hops, decay, edge-confidence weighting).
6. **Hub-node handling** in graph expansion.
7. **Graph persistence/caching strategy** on Render (ephemeral disk): Postgres as source of truth, LRU cache of built graphs.
8. **Neo4j trigger:** the measurable point at which NetworkX is no longer enough.

---

## 15. Additional Gaps to Cover

- Incremental re-indexing by commit diff (beyond snapshot versioning).
- Test-file linkage (`TESTS` edges) extracted in v1, since impact analysis depends on it.
- An explicit "insufficient evidence / abstain" outcome, evaluated like any other output.
- Per-repo UI notice when code is sent to external providers.
