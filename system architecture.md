# BlackBoxRAG: System Architecture

Scope: v1 architecture (Python-first, NetworkX graph, Postgres + Qdrant). Items marked _later_ belong to v2/v3.

---

## 1. High-Level System Overview

```mermaid
flowchart TB
    subgraph Client["Client"]
        UI["React + TypeScript UI<br/>Dashboard, Architecture Explorer,<br/>Investigation Workspace, Monaco viewer"]
    end

    subgraph Edge["Auth"]
        SA["Supabase Auth<br/>JWT"]
        GH["GitHub App<br/>installation tokens, backend only"]
    end

    subgraph API["FastAPI Backend"]
        R["REST API layer"]
        SVC["Services layer"]
        ING["Ingestion"]
        PAR["Parsers + IR"]
        CHK["Structural chunker"]
        IDX["Index manager"]
        GRA["Graph builder + cache"]
        RET["Retrieval engine"]
        INV["Investigation engine"]
        GEN["Generation + verifier"]
    end

    subgraph Worker["Job Worker"]
        W["Postgres-backed worker<br/>SKIP LOCKED polling"]
    end

    subgraph Stores["Data Stores"]
        PG[("PostgreSQL / Supabase<br/>source of truth")]
        QD[("Qdrant<br/>vectors + filter payloads")]
        MEM["In-memory<br/>BM25 + NetworkX graph cache"]
    end

    subgraph External["External Services"]
        GHA["GitHub REST + Git"]
        EMB["Embedding providers<br/>Voyage, Jina, local"]
        LLM["LLM providers<br/>OpenAI, Gemini, Ollama"]
    end

    UI --> SA
    UI --> R
    R --> SVC
    SVC --> PG
    SVC --> W
    W --> ING --> PAR --> CHK --> IDX
    PAR --> GRA
    ING --> GHA
    GH --> GHA
    IDX --> EMB
    IDX --> QD
    IDX --> MEM
    GRA --> PG
    SVC --> RET --> INV --> GEN
    RET --> QD
    RET --> MEM
    RET --> PG
    GEN --> LLM
    GEN --> PG
```

---

## 2. Layered View

| Layer                     | Components                                                                                                                         | Backing tech                             |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| L8 Visualization          | Repository dashboard, architecture explorer, investigation workspace, execution-flow and impact views                              | React, React Flow, Monaco, Recharts      |
| L7 Response generation    | Prompt manager, answer generator, citation generator                                                                               | LiteLLM / provider abstraction, Pydantic |
| L6 Investigation engine   | Query router, decomposer, architecture, execution, root-cause, impact, dependency analyzers, evidence verifier, confidence manager | Custom Python                            |
| L5 Hybrid retrieval       | Vector, lexical and graph retrievers, RRF fusion, cross-encoder reranker, context assembler                                        | Qdrant, rank-bm25, NetworkX              |
| L4 Knowledge construction | Embedding service, Qdrant store, BM25 index, graph builder                                                                         | Voyage / Jina / local embedders          |
| L3 Code intelligence      | Parsers, symbol / import / call extractors, structural chunker                                                                     | Python `ast`, Tree-sitter (later)        |
| L2 Ingestion              | GitHub / ZIP loaders, file discovery, filtering, language detection, snapshot manager                                              | GitPython, PyGithub, pathspec            |
| L1 Interface              | REST API, auth, job submission                                                                                                     | FastAPI, Supabase Auth                   |

---

## 3. Ingestion and Indexing Pipeline

```mermaid
flowchart LR
    A["Repository source<br/>GitHub URL or ZIP"] --> B["Clone / extract<br/>validate paths"]
    B --> C["Create snapshot<br/>commit SHA"]
    C --> D["File discovery<br/>pathspec filters"]
    D --> E["Classify + detect language<br/>drop binary, secrets"]
    E --> F["Parse<br/>AST to common IR"]
    F --> G["Extract symbols,<br/>imports, calls, tests"]
    G --> H[("symbols + edges<br/>in Postgres")]
    G --> I["Structural chunking<br/>function / class / module"]
    I --> J[("chunks in Postgres")]
    J --> K["Embed chunks"]
    K --> L[("Qdrant<br/>collection per model")]
    J --> M["Tokenize identifiers<br/>build BM25"]
    H --> N["Build NetworkX graph<br/>per snapshot"]
    L --> O["Snapshot status:<br/>indexed"]
    M --> O
    N --> O
```

Notes:

- Nothing from the repository is executed during ingestion.
- Every artifact carries `snapshot_id`, so indexes from different commits never mix.
- Call edges are stored with `resolution` and `confidence`; unresolved calls are kept with `dst_unresolved_name`.
- Embedding runs through the external provider only if `allow_external_embeddings` is true for that repository; otherwise a local embedder is used.

---

## 4. Investigation (Query) Flow

```mermaid
sequenceDiagram
    actor U as User
    participant API as FastAPI
    participant QR as Query router
    participant QD as Decomposer
    participant VR as Vector retriever
    participant LR as BM25 retriever
    participant GR as Graph expander
    participant FU as RRF fusion
    participant RR as Reranker
    participant CA as Context assembler
    participant LLM as LLM
    participant EV as Evidence verifier
    participant PG as Postgres

    U->>API: POST /api/investigate
    API->>QR: classify intent and entities
    QR->>QD: decompose into sub-queries
    loop each sub-query
        QD->>VR: semantic search, snapshot filter
        QD->>LR: identifier / keyword search
        VR-->>GR: top hits as seeds
        LR-->>GR: top hits as seeds
        GR-->>FU: expanded candidates with edge confidence
        VR-->>FU: ranked chunk_ids
        LR-->>FU: ranked chunk_ids
    end
    FU->>RR: fused candidates
    RR->>CA: top-ranked evidence
    CA->>PG: fetch chunk text, locations, paths
    CA->>LLM: question plus evidence package
    LLM-->>EV: draft report with citations
    EV->>PG: verify symbols, files, line ranges
    EV-->>API: report with confirmed / inferred / hypothesis labels, or abstain
    API-->>U: investigation report
```

Rules enforced at this stage:

- The LLM reasons only over the assembled evidence.
- Citations that do not resolve to a real symbol and line range are removed or flagged.
- If evidence is insufficient, the report abstains instead of guessing.

---

## 5. Retrieval Engine Detail

```mermaid
flowchart TB
    Q["Sub-query"] --> V["Dense search<br/>Qdrant"]
    Q --> L["Sparse search<br/>BM25, identifier-split tokens"]
    V --> S["Seed set"]
    L --> S
    S --> G["Graph expansion<br/>k hops, hop decay,<br/>edge confidence weighting,<br/>hub-node damping"]
    V --> F["RRF fusion<br/>keyed by chunk_id"]
    L --> F
    G --> F
    F --> D["Dedupe + location validation"]
    D --> R["Cross-encoder rerank"]
    R --> C["Context assembly<br/>chunks, paths, relationships,<br/>retrieval confidence"]
```

Ablation switches (for E1-E5): each channel (BM25, graph), reranking and verification can be enabled or disabled by configuration.

---

## 6. Data Model

```mermaid
erDiagram
    REPOSITORIES ||--o{ SNAPSHOTS : has
    SNAPSHOTS ||--o{ FILES : contains
    FILES ||--o{ SYMBOLS : defines
    SNAPSHOTS ||--o{ SYMBOLS : scopes
    SYMBOLS ||--o{ EDGES : source
    SYMBOLS ||--o{ CHUNKS : chunked_into
    SNAPSHOTS ||--o{ JOBS : runs
    SNAPSHOTS ||--o{ INVESTIGATIONS : answers

    REPOSITORIES {
        uuid id
        uuid owner_id
        string source
        string url
        bool allow_external_embeddings
        bool allow_external_llm
    }
    SNAPSHOTS {
        uuid id
        uuid repository_id
        string commit_sha
        string status
        string embed_model
        int embed_dim
    }
    FILES {
        uuid id
        uuid snapshot_id
        string rel_path
        string language
        string sha256
        bool is_test
    }
    SYMBOLS {
        uuid id
        uuid snapshot_id
        uuid file_id
        string symbol_key
        string kind
        string qualname
        int start_line
        int end_line
    }
    EDGES {
        uuid id
        uuid src_symbol_id
        uuid dst_symbol_id
        string dst_unresolved_name
        string edge_type
        string resolution
        float confidence
    }
    CHUNKS {
        uuid id
        uuid symbol_id
        int part_index
        text text
        int token_count
    }
    JOBS {
        uuid id
        string type
        string status
        int attempts
    }
    INVESTIGATIONS {
        uuid id
        string query
        string query_type
        json report
    }
```

Identifier scheme:

```
symbol_key = "{lang}:{rel_path}::{qualname}"   (stable across commits)
symbol_id  = uuid5(NAMESPACE, snapshot_id + symbol_key)
chunk_id   = uuid5(NAMESPACE, symbol_id + ":" + part_index)
```

---

## 7. Store Responsibilities

| Store             | Holds                                                                                           | Does not hold                           |
| ----------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------- |
| PostgreSQL        | Users, repositories, snapshots, files, symbols, edges, chunks (with text), jobs, investigations | Vectors                                 |
| Qdrant            | Vectors plus filter-only payload (snapshot, file path, kind, language, is_test, symbol IDs)     | Chunk text                              |
| NetworkX (memory) | Snapshot graph built from `symbols` + `edges`, LRU cached                                       | Anything not reproducible from Postgres |
| BM25 (memory)     | Tokenized chunk corpus per snapshot                                                             | Anything not reproducible from Postgres |

Postgres is the single source of truth. Qdrant, BM25 and the graph can all be rebuilt from it.

---

## 8. Job Processing

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running: worker claims row (SKIP LOCKED)
    running --> succeeded
    running --> failed: error, attempts exhausted
    running --> queued: error, retry
    succeeded --> [*]
    failed --> [*]
```

Job types: `clone`, `parse`, `chunk`, `embed`, `build_graph`, `index_bm25`. Snapshot status advances only when its required jobs succeed. A separate worker process polls the `jobs` table, so a backend restart does not lose work. Celery and Redis are deferred.

---

## 9. Security Boundaries

```mermaid
flowchart LR
    subgraph Untrusted["Untrusted"]
        REPO["Repository content<br/>code, comments, docs"]
        USERIN["User queries"]
    end
    subgraph Trusted["Backend process"]
        SAN["Sanitize + validate<br/>path checks, secret redaction"]
        PARSE["Static parsing only"]
        PROMPT["Prompt assembly<br/>repo text marked as data"]
    end
    subgraph Isolated["Later: isolated sandbox"]
        SBX["Docker sandbox<br/>resource limits, no network"]
    end
    REPO --> SAN --> PARSE --> PROMPT
    USERIN --> PROMPT
    REPO -.-> SBX
```

- v1 never executes repository code.
- Repository text is treated as untrusted data in prompts (prompt-injection defense).
- Runtime tracing (v3) runs only in isolated containers, disabled by default.
- Private repositories default to `allow_external_embeddings = false` and `allow_external_llm = false`.
- GitHub App installation tokens never reach the frontend.

---

## 10. Deployment Topology

```mermaid
flowchart LR
    U["Users"] --> V["Vercel<br/>React frontend"]
    V --> SB["Supabase<br/>Auth + PostgreSQL"]
    V --> RN["Render<br/>FastAPI API"]
    RN --> SB
    RN --> QC["Qdrant Cloud"]
    RN --> W["Render<br/>job worker"]
    W --> SB
    W --> QC
    RN --> EXT["Embedding + LLM providers"]
    W --> EXT
    RN --> SN["Sentry"]
    W --> SN
    GA["GitHub Actions<br/>CI: tests, lint, build"] --> V
    GA --> RN
```

Local development: `docker-compose.yml` runs Postgres and Qdrant (optionally Ollama), with the API and worker running against them. Tests run migrations against a throwaway Postgres database.

---

## 11. Backend Module Map

```
app/
├── api/            REST routers
├── services/       orchestration, one service per use case
├── workers/        job runner
├── ingestion/      loaders, discovery, filtering, snapshot manager
├── parsers/        language parsers, IR, symbol / import / call extractors
├── chunking/       structural chunker and context builder
├── indexing/       embedders, qdrant_store, lexical_index, index_manager
├── graph/          builder, cache, schema, traversal, relationship scorer
├── retrieval/      query analysis, retrievers, fusion, reranker, context assembler
├── investigation/  router, decomposer, analyzers, evidence verifier
├── generation/     llm_client, prompt_manager, answer + citation generators
├── models/         SQLAlchemy models
└── schemas/        Pydantic request / response and IR schemas
```

Dependency direction: `api -> services -> {ingestion, parsers, chunking, indexing, graph, retrieval, investigation, generation} -> models`. Lower modules do not import from `api` or `services`.

---

## 12. Release Evolution

| Release   | Architecture additions                                                                                                                 |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| v1.0      | Everything above except runtime and multi-language parsers                                                                             |
| v2.0      | Multi-step decomposition loop, execution-flow reconstruction, root-cause and impact engines, stronger verification, advanced dashboard |
| v3.0      | Sandbox manager, trace collector and analyzer, static-vs-dynamic comparison, additional Tree-sitter languages                          |
| If needed | Neo4j replaces NetworkX; Elasticsearch replaces in-memory BM25; Redis + Celery replace the Postgres job worker                         |
