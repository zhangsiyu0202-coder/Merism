# `merism.knowledge`

RAG layer. Postgres + pgvector; no ClickHouse, no HogQL.

## What's done

- `citations.py` — `format_chunk_citations(chunks)` pure function.
  Shape compatible with `merism.testing.factories.knowledge.make_knowledge_chunk`.

## Task list (R8 follow-up)

1. **`indexer.py`** — `index_session(session)` chunks `session.transcript`
   into 300-500 token windows, computes embeddings via DeepSeek
   `text-embedding-v3` (or OpenAI if DEEPSEEK_EMBED=0), and writes
   `KnowledgeChunk` rows. Run as a Celery task after session completes.
2. **`indexer.py`** — `index_study_report(report)` same flow for generated
   reports so they're searchable in cross-study Knowledge Explore.
3. **`search.py`** — two callable tables:
   - `chunk_search_team(team_id, query, limit=7)` — L1 retrieval across
     the whole team. Hybrid BM25 + cosine, Reciprocal Rank Fusion (RRF).
   - `chunk_search_study(study_id, query, limit=5)` — L2 retrieval
     scoped to one study.
4. **`search.py`** — `_lexical_bm25(team_id, query, limit)` using
   Postgres `to_tsvector` + `ts_rank_cd`. Migration enables the GIN
   index on `merism_knowledge_chunk.content`.
5. **`search.py`** — `_vector_cosine(team_id, query_embedding, limit)`
   using `pgvector`'s `<=>` operator. Migration creates IVFFLAT index.
6. **`search.py`** — `_rrf_merge(lexical, vector, k=60)` Reciprocal Rank
   Fusion merging. Fixed k=60 per Cormack et al. 2009.
7. **Tests** at `tests/test_citations.py`, `tests/test_indexer.py`,
   `tests/test_search.py`. Use `merism.testing.fakes.FakeRAGRetriever` as
   a drop-in for agent-level tests.

## Migrations required

1. Enable pgvector extension — already in `bin/postgres-init.sql`.
2. IVFFLAT index on `merism_knowledge_chunk.embedding` for cosine.
3. GIN index on `merism_knowledge_chunk.content` (to_tsvector('simple'))
   for BM25.
4. Both ship as a dedicated `merism/migrations/0002_knowledge_indexes.py`
   — hand-written RunSQL because Django doesn't know about pgvector
   index types.
