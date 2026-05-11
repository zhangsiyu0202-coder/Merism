# `merism.memai`

Merism's AI agent layer. Follows PRODUCT.md §5 — **three agents**:

| Agent | Where | Trigger |
|---|---|---|
| Outline Review Agent    | `merism.memai.agents.outline_review` (R8 TODO) | Researcher clicks "让 AI 审查" on Outline tab |
| Interview Moderator     | **`merism.conductor`**                         | Every user turn in an active interview |
| Analysis Agent          | `merism.memai.agents.analysis` (R8 TODO)       | `(A)` Celery task after session ends; `(B)` user asks a Custom Report question |

> Note the Interview Moderator lives under `merism.conductor/` not here,
> because per PRODUCT.md §5.2 it's a single-call text+function-call
> streaming loop, not a multi-tool agent.

## What's done

| File | Role |
|---|---|
| `tool.py`  | `MemTool` abstract base — name / description / args_schema / `_arun_impl`. Provides `openai_function_spec()` for LLM function calling. |
| `llm.py`   | `get_llm(async_=False)` returns an OpenAI-compatible client pointed at DeepSeek by default (per PRODUCT.md §6). `LLMUnavailableError` if `MERISM_LLM_API_KEY` not set. |

## Task list (R8 follow-up)

### Tools (`merism/memai/tools/*.py`)

Each tool is a single file. Each file contains: args schema (Pydantic), tool class subclassing `MemTool`, and colocated tests.

1. **`search_research.py`** — semantic search over the team's studies.
   Wraps `merism.knowledge.search.hybrid_search_team(team_id, query)`.
2. **`compare_personas.py`** — cross-persona or cross-study comparison.
   Takes two filter sets, returns a structured comparison block.
3. **`analyze_interviews.py`** — ad-hoc multi-session deep analysis.
   Runs the Analysis Agent (B path) against arbitrary session filters.
4. **`recruitment_plan.py`** — draft a recruitment plan given a study.
5. **`recruitment_draft_copy.py`** — draft invite message copy for a
   channel (Feishu / WeCom / QQ Group / QQ Guild / WeCom Bot).
6. **`recruitment_preview.py`** — render a preview of an about-to-send
   broadcast.
7. **`recruitment_send.py`** — wrapper that creates a
   `RecruitmentBroadcast(status="approved")` and kicks off dispatch.
8. **`recruitment_status.py`** — read-only: return counters for a broadcast.
9. **`manage_memories.py`** — CRUD + semantic search over `AgentMemory`.

### Agents (`merism/memai/agents/*.py`)

1. **`outline_review.py`** — conversational, function-calling.
   Uses `build_proposed_changes_fn` → returns `{reply_markdown,
   proposed_changes, awaiting_user_decision}` per PRODUCT.md §5.1.
   No independent LLM module — uses `merism.memai.llm`.
2. **`analysis.py`** — two entry points:
   - `generate_session_insight(session)` — runs on Celery task after
     session completes. One LLM call, produces `SessionInsight`.
   - `answer_custom_report_question(study_id, user, question)` —
     invokes retriever over `SessionInsight + KnowledgeChunk`, then LLM
     with three callable functions: `aggregate_tag` / `filter_sessions`
     / `cite_quote`. Returns a `CustomReportAnswer` (see
     `merism.reports.schema`).
3. **`ask_merism.py`** — top-level Ask Merism router. Single conversation
   agent with access to all tools in `tools/`. No "mode switching" like
   the old repo had — tools are available by default; skills are just
   the tools themselves.

### LLM trace / cost tracking

Optional. If we decide to add it, wrap `get_llm()` with a thin decorator
that pipes events to `posthoganalytics` (the PyPI SDK, not `posthog.*`).
Document the decision as an ADR.

### Tests

Use the existing `merism.testing` harness:

- `merism.testing.fakes.DeterministicLLM` — replace `get_llm()` in tests
- `merism.testing.factories.*` — build Study / Interview fixtures
- `merism.testing.fakes.FakeRAGRetriever` — seed retrieval results for
  analysis agent tests

Pattern:
```python
from merism.testing import MerismTestCase
from merism.testing.fakes import DeterministicLLM, FakeRAGRetriever
from merism.memai.agents.outline_review import review_outline

class TestOutlineReview(MerismTestCase):
    def test_privacy_concern_surfaced(self):
        llm = DeterministicLLM(prefix_to_response={
            "review the outline": '{"reply_markdown": "Q3 is sensitive PII...", ...}'
        })
        result = review_outline(study=..., llm=llm)
        assert result.proposed_changes[0].op == "modify_question"
```

### What's NOT in this package

Per `docs/MIGRATION.md`:

- No `execute_sql` / `create_insight` / `upsert_dashboard` / `create_form`
  / `create_notebook` / `call_mcp_server` / `list_data` / `read_data` /
  `read_taxonomy` / `read_data_warehouse_schema` / `search` tools — all
  PostHog-product-specific, none are Merism features.
- No `agent_modes` / presets for ProductAnalytics / SessionReplay /
  ErrorTracking / Flags / Survey / LLMAnalytics. Merism has one default
  mode; tools are scoped by availability, not by mode switching.
- No `chat_agent/rag/nodes.py` style HogQL-based retrieval — use
  `merism.knowledge.search` instead.
- No memory onboarding flow asking "what events do you track?" — the
  Merism equivalent is handled in the Study creation wizard.
