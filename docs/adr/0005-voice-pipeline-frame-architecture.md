# ADR 0005 — Voice pipeline: pipecat-inspired frame/processor architecture

**Status**: Accepted (2026-05-10)

**Context**

The first iteration of Merism's voice path (`merism/stt.py` + `merism/tts.py`
+ `merism/realtime/voice.py`) was a direct hand-wired orchestration: three
coroutines pushing bytes / strings between each other via `asyncio.Queue`s
inside `VoiceConsumer`. Functional but hard to evolve:

- No typed event vocabulary — every cross-processor contract was ad-hoc
  bytes / str.
- Barge-in was a single `bool` check + `task.cancel()`. TTS's in-flight
  audio buffer still played out, producing stuttered overruns.
- Zero observability — latency and TTFB had to be instrumented by hand
  at every call site.
- No idle-user detection, no recorder, no metrics breakout.
- Adding a middleware (moderation filter, recording, a Whisker-style
  debugger) required editing the consumer.

[Pipecat](https://github.com/pipecat-ai/pipecat) (v1.1, BSD-2, 12 k ★)
solved these problems with a frame-and-processor architecture that is now
the de-facto pattern for real-time voice AI agents (also seen in LiveKit
Agents and OpenAI's realtime-agents reference).

**Decision**

Surgically port the smallest subset of pipecat's abstractions that earns
its keep in a focused product like Merism. Specifically:

| Ported | File | Reason |
|---|---|---|
| `Frame` taxonomy (`SystemFrame` / `DataFrame` / `ControlFrame`) | `merism/voice/frames.py` | Typed event vocabulary |
| `FrameProcessor` base (two-queue priority lanes) | `merism/voice/pipeline.py` | Composable middleware |
| `Pipeline`, `PipelineTask`, `PipelineRunner` | `merism/voice/pipeline.py` | Lifecycle, SIGINT, cleanup |
| `Observer` pattern | `merism/voice/observer.py` | Metrics / recording / tracing without touching the pipeline |
| `InterruptionFrame` as `SystemFrame` that clears each processor's data queue | `merism/voice/pipeline.py` | Correct barge-in semantics |
| Pipecat-style `MetricsObserver` (TTFB + STT / LLM / TTS latency) | `merism/voice/observer.py` | Observability baseline |
| `UserIdleDetector` | `merism/voice/processors/user_idle.py` | UX — re-engage silent participants |

| NOT ported | Reason |
|---|---|
| WebRTC transport (Daily / LiveKit / SmallWebRTCTransport) | We use Django Channels WebSocket; transport is Merism-shaped |
| Twilio / Plivo / Telnyx / Exotel serializers | No telephony scope |
| Video frame types (`OutputImageRawFrame`, HeyGen / Tavus integrations) | No avatar scope this phase |
| `ParallelPipeline` | Premature — only needed for multi-language TTS or multi-LLM fallback, neither are on the roadmap |
| `PipelineParams.enable_metrics` feature-flag machinery | Observer pattern subsumes this — flip on/off by (un)attaching an observer |
| Speech-to-Speech integration (OpenAI Realtime S2S, Gemini Live) | We do discrete STT + LLM + TTS by design for cost, quality control and tenancy |

**Consequences**

- The new `merism/voice/` module is parallel to existing `merism/stt.py` /
  `merism/tts.py` / `merism/realtime/voice.py`. None of those are
  removed or modified in this ADR's scope.
- `STTProcessor` / `LLMProcessor` / `TTSProcessor` wrap the existing
  clients so we can flip `VoiceConsumer` internals over in a subsequent
  PR without touching the client protocol code (which is the riskiest
  layer — it talks to DashScope).
- Frame IDs (auto-incrementing) + processor names appear in every log
  line — tracing a single turn through the pipe becomes grep-able.
- `InterruptionFrame` semantics are now correct: every processor drops
  its data-queue backlog while keeping system-frame order intact. The
  TTS processor's `_abort_session` also kills the in-flight DashScope
  WebSocket so no stale audio leaks out.
- Tests at `merism/voice/tests/test_pipeline.py` (5 tests, all passing)
  fence the abstraction contracts — interruption-drops-queue, observer
  sees every push, metrics compute correctly, runner lifecycle clean.

**Rollout plan**

- Phase 1 (this ADR): abstraction + processors + tests. `VoiceConsumer`
  unchanged.
- Phase 2 (next): swap `VoiceConsumer` internals to construct a
  `Pipeline([STTProcessor, LLMProcessor, TTSProcessor, UserIdleDetector])`
  + attach `MetricsObserver` + `TranscriptRecorder`. Delete the hand-wired
  `asyncio.Queue` / `_audio_queue` / `_turn_task` plumbing.
- Phase 3: add recording observer that streams mic + TTS audio to S3 via
  `django-storages`; align with spec's session recording requirement.

**Attribution**

Design language (Frame / FrameProcessor / FrameDirection / SystemFrame /
DataFrame / ControlFrame / InterruptionFrame / ParallelPipeline / Observer)
is borrowed directly from pipecat (BSD-2). Their documentation at
https://docs.pipecat.ai/pipecat/learn/pipeline is what made the port
viable in a single evening.

## Addendum — OpenAI Realtime API truncation semantics

Pipecat's frame model solves **composition**. But OpenAI's Realtime
API and accompanying community posts crystallised a second critical
correctness property that pipecat does NOT model as a first-class
concept:

> "Transcript deltas emit even if audio never plays... the transcript
> history becomes incorrect and no longer reflects what the caller
> actually experienced."
> — OpenAI community forum, Jan 2026

Concretely: when a user barges in after hearing only a fraction of the
bot's generated reply, the LLM's multi-turn context must reflect **what
the user heard**, not **what the model generated** — otherwise every
follow-up silently drifts.

OpenAI's answer is the ``conversation.item.truncate`` event:

```
{ "type": "conversation.item.truncate",
  "item_id": "resp_abc",
  "content_index": 0,
  "audio_end_ms": 420 }
```

We port this semantic into two additional frame types + one processor:

| Added | File | Role |
|---|---|---|
| ``response_id`` field on every LLM / TTS / Interruption / Truncated frame | `frames.py` | Thread a stable ID from LLM through TTS |
| ``TruncatedFrame(response_id, audio_played_ms)`` (SystemFrame) | `frames.py` | Emitted by TTS after InterruptionFrame |
| ``ConversationState`` processor — maintains a ``list[ConversationItem]`` + trims the matching assistant item on TruncatedFrame (using a ``chars_per_ms`` heuristic for the ZH TTS rate) | `processors/conversation_state.py` | Keeps history = what user HEARD |

Tests at ``merism/voice/tests/test_conversation_state.py`` (4 tests,
all passing) fence this contract:

1. Clean turn → text stored verbatim (assert ``truncated == False``)
2. Interruption → TruncatedFrame → text trimmed to ``played_ms × chars_per_ms``; original kept for diagnostics
3. Unknown response_id in TruncatedFrame → noop + WARN log
4. InterruptionFrame WITHOUT matching TruncatedFrame → no mutation

### Deliberately not taken from OpenAI

| OpenAI feature | Reason we skipped |
|---|---|
| Function calling interleaved with audio responses | Phase 3 — nothing in the moderator needs it yet |
| ``session.update`` hot-reconfiguration of instructions/tools | Our instructions are study-bound (StudyPage sets them once) |
| Multi-response correlation + ``response.cancel`` wire event | Single response per turn — single in-flight is always the current ``response_id``. ``conversation.item.truncate`` covers the cancel case |
| WebRTC DataChannel transport | We stay on Channels WebSocket |
| ``rate_limits`` event | Our queues apply natural backpressure |
