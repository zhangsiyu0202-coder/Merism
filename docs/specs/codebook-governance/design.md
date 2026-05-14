# Codebook Governance Subsystem — Design Document

> Status: Draft
> Author: AI-assisted
> Date: 2026-05-12

## 1. Overview

The Codebook Governance subsystem manages the lifecycle of qualitative codes
across a study. It automates code discovery, review, versioning, retagging,
and theme synthesis — turning the codebook from a static seed into a living,
versioned analytical instrument.

## 2. Components

```
CodebookSeeder (existing)
  → generates initial deductive codes from research_goal

QuoteTagger (existing)
  → matches quotes to existing codes (deductive) + per-quote inductive hints

InductiveCodeSuggester (NEW)
  → batch discovers emergent codes from a session's quotes
  → RAG-checks against existing codebook before proposing

CodebookReviewer (NEW)
  → generates change proposals (merge/split/rename/deprecate/add)
  → uses overlap/coverage/novelty heuristics

CodebookVersionManager (NEW)
  → applies approved proposals → creates immutable CodebookVersion snapshots
  → records CodeChange + CodeMapping for audit trail

RetaggingJob (NEW)
  → finds quotes affected by code changes
  → re-runs QuoteTagger with updated codebook

ThemeSynthesizer (existing analysis/themes/, NEW auto-trigger)
  → triggered when codebook saturates OR study reaches target_completed_count
```

## 3. Data Models

### 3.1 CodebookVersion

```python
class CodebookVersion(TimestampedModel):
    id: UUIDField(primary_key)
    team: FK(Team)
    study: FK(Study)
    version: PositiveIntegerField  # monotonically increasing per study
    codes: JSONField  # immutable snapshot: [{code_id, name, description, parent_id, status, ...}]
    source: CharField  # "seed" | "review" | "manual"
    created_by_change: FK(CodeChange, null=True)  # what triggered this version

    class Meta:
        db_table = "merism_codebook_version"
        unique_together = [("study", "version")]
```

### 3.2 CodeChange

```python
class CodeChange(TimestampedModel):
    id: UUIDField(primary_key)
    team: FK(Team)
    study: FK(Study)
    from_version: FK(CodebookVersion, related_name="changes_from")
    to_version: FK(CodebookVersion, null=True, related_name="changes_to")
    change_type: CharField  # "add" | "merge" | "split" | "rename" | "deprecate"
    payload: JSONField
    # Shape per change_type:
    #   add:       {"code": {code_id, name, description}}
    #   merge:     {"source_ids": [...], "target_id": "..."}
    #   split:     {"source_id": "...", "target_ids": [...]}
    #   rename:    {"code_id": "...", "old_name": "...", "new_name": "..."}
    #   deprecate: {"code_id": "...", "replaced_by": "..." | null}
    rationale: TextField(blank=True)
    status: CharField  # "proposed" | "approved" | "rejected" | "applied"

    class Meta:
        db_table = "merism_code_change"
```

### 3.3 CodeMapping

```python
class CodeMapping(TimestampedModel):
    id: UUIDField(primary_key)
    team: FK(Team)
    study: FK(Study)
    change: FK(CodeChange)
    old_code_id: CharField(max_length=64)
    new_code_id: CharField(max_length=64, blank=True)  # empty = deprecated with no replacement
    version: FK(CodebookVersion)  # the version this mapping belongs to

    class Meta:
        db_table = "merism_code_mapping"
        indexes = [("study", "old_code_id")]
```

## 4. Agent Contracts

### 4.1 InductiveCodeSuggester

- **Input**: session quotes (text[]), current codebook (codes[])
- **Algorithm** (inspired by GATOS workflow):
  1. Receive all quotes from the just-completed session
  2. LLM identifies patterns NOT covered by existing codebook
  3. For each candidate, checks semantic similarity to existing codes
  4. Only proposes codes that are genuinely novel (not near-duplicates)
- **Output**: `[{code_id, name, description, evidence_quotes[], rationale}]`
- **Constraint**: single LLM call, structured JSON output

### 4.2 CodebookReviewer

- **Input**: current codebook, accumulated inductive suggestions, code usage stats
- **Algorithm** (inspired by Chen et al. 2024 merge metrics):
  - High overlap between two codes → propose merge
  - Code with zero/very low usage → propose deprecate
  - Inductive suggestion recurring 3+ times → propose add
  - Code name ambiguous or inconsistent → propose rename
  - Code covering too many disparate quotes → propose split
- **Output**: `[{change_type, payload, rationale, confidence}]`
- **Constraint**: single LLM call, structured JSON output

## 5. Pipeline Flow

```
post_session_pipeline (existing, extended):
  1. transcript_polish
  2. codebook_seed (idempotent, once)
  3. quote_extraction
  4. quote_tagging (deductive + per-quote inductive hints)
  5. rag_indexing
  6. session_insight_generation
  7. [NEW] inductive_code_suggest (batch, session-level)
  8. [NEW] codebook_review (study-level, proposes changes)
  9. [NEW] version_manager.apply (if auto_approve or researcher approves)
  10. [NEW] retagging_job (affected quotes only)
  11. [NEW] theme_synthesizer_trigger (conditional)
  12. cross-session analysis (existing rebuild_study_analysis)
```

Steps 7-11 are the new codebook governance additions.

## 6. ThemeSynthesizer Trigger Conditions

Auto-trigger when EITHER:
- `study.actual_completed_count >= study.target_completed_count`
- Codebook saturation detected: last 3 sessions produced 0 new approved codes

The existing `merism/analysis/themes/` pipeline (clusterer → embedder →
summarizer) serves as the ThemeSynthesizer. We add a gating check, not a
new agent.

## 7. Saturation Detection

Inspired by GATOS paper's code-creation-rate curve and De Paoli 2024's
Inductive Thematic Saturation (ITS) metric:

```python
def is_codebook_saturated(study: Study, lookback: int = 3) -> bool:
    """True if last N sessions produced no new approved codes."""
    recent_sessions = (
        InterviewSession.objects
        .filter(study=study, status="completed")
        .order_by("-completed_at")[:lookback]
    )
    new_codes = CodeChange.objects.filter(
        study=study,
        change_type="add",
        status="applied",
        created_at__gte=recent_sessions.last().completed_at,
    )
    return new_codes.count() == 0
```

## 8. Version Manager Logic

Pure Python, no LLM:

```python
def apply_proposal(study, change: CodeChange) -> CodebookVersion:
    current = get_latest_version(study)
    new_codes = deep_copy(current.codes)

    match change.change_type:
        case "add":
            new_codes.append(change.payload["code"])
        case "merge":
            # Remove source codes, keep target
            source_ids = change.payload["source_ids"]
            new_codes = [c for c in new_codes if c["code_id"] not in source_ids]
            # Create mappings: source → target
            for sid in source_ids:
                CodeMapping.create(old_code_id=sid, new_code_id=change.payload["target_id"])
        case "deprecate":
            for c in new_codes:
                if c["code_id"] == change.payload["code_id"]:
                    c["status"] = "deprecated"
            CodeMapping.create(old_code_id=..., new_code_id=change.payload.get("replaced_by", ""))
        case "rename":
            for c in new_codes:
                if c["code_id"] == change.payload["code_id"]:
                    c["name"] = change.payload["new_name"]
        case "split":
            # Remove source, add targets
            ...

    new_version = CodebookVersion.create(
        study=study, version=current.version + 1, codes=new_codes
    )
    change.to_version = new_version
    change.status = "applied"
    change.save()

    # Also update Study.codebook (the live field used by QuoteTagger)
    study.codebook = new_codes
    study.save()

    return new_version
```

## 9. Retagging Strategy

Only retag quotes affected by code changes:

```python
def retag_affected_quotes(study, change: CodeChange):
    mappings = CodeMapping.objects.filter(change=change)
    old_code_ids = [m.old_code_id for m in mappings]

    affected_quotes = SessionQuote.objects.filter(
        study=study,
        tags__deductive__contains=[{"code_id": oid} for oid in old_code_ids]
    )
    # Clear deductive tags and re-run tagger
    for quote in affected_quotes:
        quote.tags.pop("deductive", None)
        quote.save()

    # Re-tag with updated codebook
    tag_quotes_for_session(list(affected_quotes), study)
```

## 10. File Layout

```
merism/codebook/
├── __init__.py
├── models.py              # CodebookVersion, CodeChange, CodeMapping
├── version_manager.py     # apply_proposal(), get_latest_version()
├── retagging.py           # retag_affected_quotes()
├── saturation.py          # is_codebook_saturated()
├── tasks.py               # Celery tasks wrapping the pipeline steps
└── tests/
    ├── __init__.py
    ├── test_version_manager.py
    └── test_retagging.py

merism/memai/agents/
├── inductive_code_suggester.py  # NEW
├── codebook_reviewer.py         # NEW
└── tests/
    ├── test_inductive_code_suggester.py
    └── test_codebook_reviewer.py
```

## 11. Migration Plan

Single migration `0018_codebook_governance.py`:
- CodebookVersion
- CodeChange
- CodeMapping

On deploy, create version 1 for each study that already has a non-empty
`Study.codebook` (data migration).

## 12. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Immutable version snapshots | Audit trail; can always reconstruct state at any point |
| Study.codebook remains the "live" field | Backward compat with existing QuoteTagger/Seeder |
| Single LLM call per agent | AGENTS.md Rule 4; no multi-turn loops |
| RAG check in InductiveCodeSuggester | GATOS paper shows this prevents redundant code creation |
| Saturation = 3 sessions with 0 new codes | De Paoli 2024 ITS metric; configurable via study settings |
| Auto-approve default OFF | Researcher control; can enable per-study |
| Retagging is selective, not full-study | Performance; only quotes with affected codes |

## 13. References

- GATOS workflow (Katz et al., Nature HSS Comms 2026) — RAG-based codebook generation
- Chen et al. (ACL 2026, arXiv:2411.12142) — LLM-enriched codebook merging + 4 metrics
- De Paoli (arXiv:2503.04859) — Inductive Thematic Saturation for LLMs
- PerttuHamalainen/LLMCode — codes-to-themes pipeline
- cproctor/qualitative-coding — tree-based codebook in YAML, versioning
