"""Theme analysis — cross-session pattern detection.

Pipeline:
    embedder  →  clusterer  →  theme_summarizer  →  theme_matcher

- ``embedder`` — batch-embed SessionQuote texts via LLM Gateway.
  Writes embeddings into ``KnowledgeChunk.embedding`` (existing table)
  keyed by ``metadata["quote_id"]``. Reuses the indexer path.
- ``clusterer`` — HDBSCAN over quote embeddings → cluster labels +
  centroid per cluster.
- ``theme_summarizer`` — for each cluster, ask the LLM to produce a
  short name + description + pick 3 representative quotes.
- ``theme_matcher`` — given an existing Theme and a new quote, decide
  if the quote belongs (cosine sim >= threshold) and assign.
"""
