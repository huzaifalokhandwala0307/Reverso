# BlackBoxRAG: Project Rules

Rules for everyone (and every AI assistant) working on BlackBoxRAG. They exist to protect the things the system depends on: correct identifiers, honest evidence, safe handling of untrusted code, and measurable results. Rules marked **MUST** are not negotiable without a recorded decision. **SHOULD** can be broken with a stated reason.

---

## 1. Scope Rules

1. v1 is **Python repositories only**, static analysis only. Other languages and runtime tracing are out of scope until baseline E1-E4 results exist.
2. Build in milestone order (M1 to M8). Do not start a milestone's features before the previous one meets its definition of done.
3. Do not introduce Neo4j, Elasticsearch, Redis/Celery, Kubernetes or Kafka in v1. Adding one requires a written, measured reason (see Decision Log).
4. Do not claim a capability in docs, UI or reports that the code cannot yet perform. Describe targets as targets.
5. Keep the infrastructure boring. If a simpler component meets the need, use it.

---

## 2. Architecture Rules

1. **Postgres is the single source of truth.** Qdrant, BM25 and the NetworkX graph MUST be fully rebuildable from Postgres.
2. **Everything is snapshot-scoped.** Every file, symbol, edge, chunk, vector, BM25 document and graph belongs to exactly one `snapshot_id`. No query may read across snapshots unless explicitly comparing them.
3. **Module dependency direction:** `api -> services -> {ingestion, parsers, chunking, indexing, graph, retrieval, investigation, generation} -> models`. Lower modules MUST NOT import from `api` or `services`.
4. **API handlers stay thin.** No business logic in routers; call a service.
5. **Long work runs in the job worker**, never inside a request. Requests enqueue and return `202`.
6. **Providers sit behind interfaces** (`BaseEmbedder`, `BaseLLM`, vector store, reranker). Application code MUST NOT import a provider SDK directly.
7. **Keep RAG orchestration custom.** LangChain or LlamaIndex may be used for isolated utilities only, never to shape the architecture.
8. No hidden global state. Configuration comes from settings objects, not module-level reads of environment variables.

---

## 3. Identifier and Data Rules

1. Identifier scheme is fixed:
   ```
   symbol_key = "{lang}:{rel_path}::{qualname}"      (+ "#2", "#3" for duplicates in a file)
   symbol_id  = uuid5(NAMESPACE, snapshot_id + symbol_key)
   chunk_id   = uuid5(NAMESPACE, symbol_id + ":" + part_index)
   ```
2. All indexes (Qdrant, BM25, graph) MUST reference the same `snapshot_id`, `symbol_id` and `chunk_id`. Never key anything by text content or text prefixes.
3. File paths are stored relative to the repository root, using forward slashes.
4. Line numbers are 1-based and inclusive. Every symbol and chunk preserves `start_line` and `end_line`.
5. Unresolved call targets MUST be stored (`dst_symbol_id = NULL`, `dst_unresolved_name` set). Never drop them silently.
6. Qdrant payloads hold **filter fields only**. Chunk text lives in Postgres.
7. One Qdrant collection per embedding model and dimension. Never mix vectors from different models in one collection.
8. Schema changes go through Alembic migrations only. No manual DDL.
9. Status values are enums or check constraints, not free strings.

---

## 4. Parsing and Graph Rules

1. Parsing is **static**. Never import, execute or evaluate repository code.
2. A file that fails to parse is recorded (`parse_status`), skipped, and logged. It MUST NOT abort the snapshot.
3. Every parser returns the common IR. Downstream code MUST NOT depend on parser-specific objects.
4. Every edge carries `resolution` (`exact | import_resolved | heuristic | unresolved`) and `confidence` (0 to 1). Never assume a call has a known destination.
5. Heuristic or unresolved edges MUST NOT be presented as confirmed behaviour.
6. Chunks are structural (function, method, class, module). Oversized symbols are sub-chunked with parent symbol and context retained. Do not use fixed-size splitting as the primary strategy.
7. Extract `TESTS` edges in v1. Impact analysis depends on them.
8. Graph expansion MUST apply hop decay and edge-confidence weighting, and damp high-degree hub nodes. Unbounded traversal is not allowed; every traversal has a depth and node limit.
9. Measure the call-resolution rate per snapshot and surface it in the snapshot stats.

---

## 5. Retrieval Rules

1. Fusion is Reciprocal Rank Fusion over ranked `chunk_id` lists. State whether plain or weighted RRF is used in each experiment.
2. BM25 tokenization MUST split identifiers (camelCase, snake_case) and also keep the original token. Plain `.split()` is not acceptable for code.
3. Graph retrieval is **seeded** from vector and BM25 hits; it does not run unseeded.
4. Every channel (vector, BM25, graph), reranking and verification MUST be switchable by configuration so the E1-E5 ablations are reproducible.
5. Validate source locations of fused results before reranking. Drop candidates whose symbol or file does not exist in the snapshot.
6. Deduplicate by `chunk_id` before reranking.
7. Embedding model, reranker and LLM are **provisional**. Do not lock them without benchmark results on the project's own evaluation set.

---

## 6. LLM and Evidence Rules

1. The LLM reasons **only over retrieved evidence**. It MUST NOT invent architecture, call paths, files or symbols.
2. Every finding is labelled `confirmed` (directly in source), `inferred` (static analysis) or `hypothesis` (not directly supported). Do not merge these categories.
3. Every cited file, symbol and line range MUST be verified against Postgres before a report is returned. Unverifiable citations are removed or flagged, and the count is reported.
4. If evidence is insufficient, return `abstained` with a reason. Fabricating an answer is a defect, not a fallback.
5. Repository content (code, comments, docs, commit messages) is **untrusted data**. Prompts MUST mark it as data and instruct the model not to follow instructions found inside it.
6. Structured outputs use Pydantic schemas; parse and validate, do not trust free text.
7. Impact analysis is a prediction. Every impact result carries a coverage note and does not claim completeness.
8. Reports state confidence with a reason, not a bare label.

---

## 7. Security and Privacy Rules

1. Never execute uploaded or cloned repository code in the backend process. Runtime tracing (v3) runs only in isolated containers with resource limits, disabled by default.
2. Never auto-install repository dependencies.
3. ZIP and Git extraction MUST validate paths (no traversal, no absolute paths, no symlinks outside the root) and enforce size, file-count and compression-ratio limits.
4. Exclude sensitive files (keys, `.env`, credentials) and redact detected secrets before storage, embedding and display.
5. `allow_external_embeddings` and `allow_external_llm` default to **false** per repository and are enforced **server-side** before every external call. A local provider path MUST exist for private repositories.
6. GitHub App installation tokens stay in the backend and never reach the client or logs.
7. Never log source code, secrets, tokens or full prompts at info level.
8. Validate the Supabase JWT on every `/api` route and check resource ownership on every access.
9. Verify webhook signatures (`X-Hub-Signature-256`) and make handlers idempotent.
10. Secrets live in environment variables or a secret manager. Nothing sensitive is committed; maintain `.env.example` only.

---

## 8. API Rules

1. Analysis endpoints are snapshot-scoped (`/api/snapshots/{id}/...`).
2. Long-running operations return `202` with a job or resource to poll. Never block a request on ingestion, embedding or an investigation.
3. Errors use the standard envelope (`error.code`, `message`, `details`). Codes are stable and documented.
4. Endpoints that need an indexed snapshot return `409 snapshot_not_ready` otherwise.
5. List endpoints are cursor-paginated with a maximum page size.
6. Breaking API changes require a version bump and a changelog entry.
7. Validate all input with Pydantic; never trust client-supplied paths or IDs without ownership checks.

---

## 9. Code Quality Rules

1. Python 3.12, type hints on all public functions, `ruff` for lint and format, `mypy` (or pyright) on `app/`.
2. Synchronous SQLAlchemy 2.0 with psycopg 3 in v1. Move to async only with a measured reason.
3. Functions are small and single-purpose. Parsers, chunkers, retrievers and analyzers MUST be testable without a database or network.
4. No broad `except Exception: pass`. Catch specific errors, log with context, and re-raise or record state.
5. No new dependency without checking its license and necessity. Pin versions.
6. Public modules have docstrings stating purpose and invariants.
7. Reused code from RAG-From-Scratch: keep the Apache 2.0 `LICENSE`, retain copyright notices in copied files, mark files you modified, and keep an attribution note in the README/`NOTICE`.

---

## 10. Testing Rules

1. Every module ships with tests: parsing, chunking, graph building, fusion, verifier, and API routes.
2. Migrations are tested: tests run `alembic upgrade head` against a throwaway Postgres database.
3. Use a **fixture repository** of small, known Python code with hand-verified symbols, edges and chunk boundaries. Parser and graph tests assert against it.
4. Fusion and graph-expansion tests use deterministic inputs and assert exact ranks.
5. The evidence verifier has tests for fabricated symbols, wrong line ranges and missing files.
6. No test calls a paid external API. Use fakes for embedders and LLMs.
7. CI (GitHub Actions) runs lint, type check and tests on every PR. A failing main branch is fixed before new work.
8. Aim for coverage on core logic (`parsers`, `chunking`, `graph`, `retrieval`, `investigation`), not on boilerplate.

---

## 11. Evaluation and Research Rules

1. The ground-truth evaluation set (questions, relevant symbols, true call edges, test links) is built **alongside parsing**, not after the system is done.
2. Ablations E1 to E5 hold the LLM, corpus, questions and generation settings constant. Change one factor at a time.
3. Record every experiment: git commit, snapshot IDs, embedding model, reranker, config, metrics, date. Results without a reproducible config do not count.
4. Report the full metric set: Recall@K, Precision@K, MRR, NDCG@K, dependency precision/recall, root-cause accuracy, citation accuracy, faithfulness, abstention quality, latency, indexing time.
5. Baseline the call-graph extractor against an existing tool (e.g. Jedi or PyCG) and report precision and recall.
6. Do not tune on the test split. Keep a held-out set of questions and repositories.
7. Report negative results and limitations. Do not cherry-pick repositories.
8. SWE-bench, CodeSearchNet and CodeQL are complementary resources, not interchangeable benchmarks. State what each one measures.

---

## 12. Git and Process Rules

1. Never modify the original RAG-From-Scratch `main` branch. Work in a separate repository or branch; keep the original as an archive/reference until replacements pass tests.
2. Branch per feature (`feat/`, `fix/`, `docs/`), pull requests for all changes to `main`, at least one review for core modules.
3. Commit messages are imperative and specific. Link the milestone or issue.
4. Keep PRs small and focused. One concern per PR.
5. Record significant choices in `docs/decisions.md` (date, decision, reason, alternatives). Provisional choices note what result will settle them.
6. Update the docs (architecture, API, schemas) in the same PR that changes behaviour.
7. Never commit secrets, data dumps, model weights or cloned third-party repositories.

---

## 13. Performance and Reliability Rules

1. Index versioning is by snapshot. Re-indexing creates or rebuilds a snapshot, never mutates a live one in place without a status change.
2. Jobs are idempotent and retryable. A job that fails mid-way MUST leave the snapshot in a recoverable state with the error recorded.
3. Cache built graphs with an LRU bound; never keep unbounded graphs in memory.
4. Batch embedding requests; respect provider rate limits with backoff.
5. Set timeouts on every network call (GitHub, embedding, LLM, Qdrant).
6. Incremental re-indexing by commit diff and file `sha256` is a planned optimization; do not break the data model that makes it possible.
7. Track and expose latency and indexing time. Do not optimize without measurements.

---

## 14. Definition of Done

A change is done only when:

- It meets the milestone's stated acceptance criteria.
- Tests are written and passing in CI, including migrations if the schema changed.
- Lint and type checks pass.
- Docs and API specs are updated.
- No rule in this file is violated, or the exception is recorded in the Decision Log.
- It does not claim more than the code can do.

---

## 15. Quick Checklist (before opening a PR)

- [ ] Snapshot-scoped, no cross-snapshot reads
- [ ] IDs follow the scheme; nothing keyed by text
- [ ] Edges carry resolution and confidence; unresolved edges kept
- [ ] No repository code executed
- [ ] External calls gated by the repository's privacy flags
- [ ] Citations verified; findings labelled
- [ ] Tests, lint, types pass; migration tested
- [ ] Docs and decision log updated
- [ ] License notices kept for reused code
