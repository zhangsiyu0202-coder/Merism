# `merism.testing` — Merism-native test harness

pytest-first scaffolding for Merism code. Domain-aware factories, protocol
fakes for external deps, Merism-specific assertions, and clean base classes.

## Quick links

- [Write a new test](#write-a-new-test)
- [Factories](#factories)
- [Fakes](#fakes)
- [Assertions](#assertions)
- [Fixtures](#fixtures)
- [Markers](#markers)
- [Migrate from `posthog.test.base`](#migrate-from-posthogtestbase)
- [Design principles](#design-principles)

## Write a new test

```python
from merism.testing import (
    MerismTestCase,
    make_study_with_goals,
    make_interview,
    DeterministicLLM,
    assert_conductor_phase,
)


class TestConductorWarmupExit(MerismTestCase):
    def test_advances_to_active_after_three_warmup_turns(self):
        study = make_study_with_goals(goals=["Why bounce at signup?"])
        interview = make_interview(study, state="warmup")
        llm = DeterministicLLM(prefix_to_response={"intro_done?": "yes"})

        # ... exercise your code ...
        new_state = advance_interview(interview, llm=llm, turn_count=3)

        assert_conductor_phase(new_state, expected="active")
        assert len(llm.calls) == 1
        assert llm.last_call.last_user_message.startswith("intro_done?")
```

Start with `MerismTestCase` for DB-backed unit tests. Use `MerismSmokeTest`
when you don't touch the ORM at all (fastest). Use `MerismTransactionTestCase`
when tests cross transaction boundaries (Redis streams, Celery eager).

## Factories

All factories live under `merism.testing.factories.*` and return a
`SimpleNamespace` (stub mode, default) until Phase C1 introduces a real
`merism.Team` model. The shape matches the corresponding Django model fields
and relations closely enough for most assertion use.

| Domain | Module | Common factories |
|---|---|---|
| Study | `factories.study` | `make_study`, `make_study_with_goals`, `make_study_goal`, `make_study_link`, `make_study_trigger`, `make_study_template` |
| Interview | `factories.interview` | `make_interview`, `make_interview_guide`, `make_participation`, `make_participant`, `make_turn` |
| Conductor | `factories.conductor` | `make_execution_state`, `make_policy_context` |
| Knowledge | `factories.knowledge` | `make_knowledge_chunk`, `make_knowledge_document`, `make_team_kb`, `make_study_kb` |
| Recruitment | `factories.recruitment` | `make_channel_config`, `make_message_template`, `make_broadcast`, `make_delivery` |
| Report | `factories.report` | `make_session_insight`, `make_aggregate_synthesis`, `make_study_report` |

## Fakes

| What | Import | Replaces |
|---|---|---|
| LLM (OpenAI protocol + LangChain) | `from merism.testing.fakes.llm import DeterministicLLM` | Any `openai.OpenAI` / `ChatOpenAI` / custom client |
| IM channels (Feishu/WeCom/QQ) | `from merism.testing.fakes.im_channel import InMemoryIMAdapter` | `products.studies.backend.recruitment.channels.*` |
| STT (Paraformer) | `from merism.testing.fakes.stt import FakeParaformer` | `products.studies.backend.stt.ParaformerClient` |
| TTS (CosyVoice) | `from merism.testing.fakes.tts import FakeCosyVoice` | `products.studies.backend.tts.CosyVoiceClient` |
| Vision | `from merism.testing.fakes.vision import FakeVisionClient` | `products.studies.backend.vision.describe_frame` |
| Redis | `from merism.testing.fakes.redis import fakeredis_monkeypatch, BrokenEvalRedis` | `django_redis.get_redis_connection` |
| SSE | `from merism.testing.fakes.sse import SSETestClient` | Any SSE byte stream consumer |
| Embeddings | `from merism.testing.fakes.embeddings import hash_embedding` | Real embedding API |
| RAG retrieval | `from merism.testing.fakes.rag import FakeRAGRetriever` | `products.studies.backend.knowledge_rag.*_search*` |

Every fake records its calls so tests can assert on call structure without
patching.

## Assertions

From `merism.testing.assertions` (or the top-level `merism.testing`):

- `assert_conductor_phase(state, expected="active")`
- `assert_next_action(state, expected="deepen")`
- `assert_goal_coverage_close_to(goal, expected=0.3, tolerance=0.05)`
- `assert_citation_chain(decision, expected_source_ids=[...])`
- `assert_sse_sequence(client_or_events, expected=["turn", "phase_change"])`
- `assert_broadcast_status(broadcast, expected="completed")`
- `assert_delivery_sent_to(adapter, recipient_id="user_a")`
- `assert_block_valid(block_dict)` — report block schema shape check
- `assert_policy_fired(result, expected_policy="off_topic")`
- `assert_no_posthog_modules_loaded()` — boundary guard
- `FuzzyInt(lowest, highest)` — query-count tolerance

## Fixtures

If you prefer pytest fixtures over explicit factory calls, import from
`merism.testing.fixtures`:

```python
# conftest.py
from merism.testing.fixtures import study, interview, fake_llm, feishu_adapter  # noqa

# test_something.py
def test_xyz(interview, fake_llm):
    ...
```

## Markers

- `@pytest.mark.merism_llm_live` — skipped unless `MERISM_LLM_API_KEY` is set
- `@pytest.mark.merism_im_live` — skipped unless `MERISM_IM_LIVE=1`
- `@pytest.mark.merism_slow` — opt out with `-m "not merism_slow"`

To enable the plugin, add to your `pytest.ini`:

```ini
addopts = -p merism.testing.pytest_plugin
```

## Migrate from `posthog.test.base`

Replacement table for the imports Merism tests used historically:

| Before (`posthog.test.base`) | After (`merism.testing`) | Notes |
|---|---|---|
| `BaseTest` | `MerismTestCase` | Drop-in after Phase C1 |
| `NonAtomicBaseTest` | `MerismTransactionTestCase` | Drop-in after Phase C1 |
| `APIBaseTest` | `MerismAPITestCase` | Drop-in after Phase C1; already logs in `self.user` |
| `ClickhouseTestMixin` | **delete** | Merism doesn't run ClickHouse; Phase C2 removes remaining ClickHouse imports |
| `_create_event` / `_create_person` / `flush_persons_and_events` | **delete or rewrite** | Merism has no events/persons. Tests that rely on these are for PostHog-era code that Phase C will rewrite |
| `snapshot_hogql_queries` / `snapshot_clickhouse_queries` / `snapshot_postgres_queries` | **delete** | HogQL/ClickHouse go away in Phase C2. For Postgres query snapshots, use Django's `assertNumQueries` + `FuzzyInt` |
| `FuzzyInt` | `FuzzyInt` from `merism.testing` | 1:1 port |
| `QueryMatchingTest` | **delete** | ClickHouse-specific, not needed |
| `also_test_with_materialized_columns` | **delete** | ClickHouse-specific |
| `also_test_with_different_timezones` | **inline** | One-off decorator; use `@pytest.mark.parametrize` if needed |
| `ErrorResponsesMixin` | Inline the 4 helpers you use | Tiny mixin, not worth a cross-cutting dependency |

Migration pattern (per file):

```diff
- from posthog.test.base import BaseTest, ClickhouseTestMixin, _create_event
+ from merism.testing import MerismTestCase
+ # Delete: ClickhouseTestMixin, _create_event — Merism has no ClickHouse/events
```

If your test genuinely needs events/persons data, the test belongs on the
ORM entry (`products/studies/pytest.orm.ini`) until Phase C3/C4 replaces the
PostHog-origin models — don't force it onto the Merism lightweight boundary.

## Design principles

1. **Protocol fakes, not `Mock`s.** Every fake implements the real interface
   (e.g., OpenAI `chat.completions`, IM adapter `send_message`). Tests pass
   them directly without `with patch(...)`.
2. **Fakes record calls.** Tests assert on structured call history
   (`fake.calls`, `adapter.sent_messages`) instead of `mock.assert_called_with`.
3. **Factories say Merism words.** `make_study_with_goals`, not
   `create_test_organization_team_and_user`. The test code reads like a
   description of a Merism scenario.
4. **Assertions are domain-aware.** `assert_conductor_phase` gives a better
   error than `assert state.phase == "active"`. Failure messages include what
   Merism thinks is wrong, not just the Python-level mismatch.
5. **No PostHog coupling.** The package imports zero `posthog.*` modules.
   This is enforced by `merism/tests/test_boundary.py`.
6. **Stub today, real after Phase C1.** Until `merism.Team` exists, factories
   return `SimpleNamespace` so tests work on the lightweight boundary. After
   Phase C1, add `stub=False` callers one at a time.
