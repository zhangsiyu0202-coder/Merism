# ADR 0014 — genai-processors evaluation + selective pattern adoption

**Status**: accepted
**Date**: 2026-05-23
**Deciders**: jia
**Supersedes**: —
**Related**: ADR 0005 (voice pipeline frame architecture)

## Context

`google-gemini/genai-processors` (Apache 2.0, v2.0 released 2026-03-10,
2.1k stars) is a Python library for building modular asynchronous AI
content pipelines. The `Processor` class consumes/yields async streams
of `ProcessorPart` (multimodal content). It composes via `+` (chain) and
`//` (parallel) operators, ships built-in `GenaiModel` (turn-based
Gemini calls) and `LiveProcessor` (Gemini Live API real-time streaming),
and bills itself as the canonical Python framework for Gemini-based
agents.

Question raised 2026-05-23: *can we use this in Merism?*

This ADR records the evaluation, the decision (no), and which of its
ideas we will selectively adopt into our existing pipecat-inspired
voice pipeline (`merism/voice/frames.py`).

## Comparison

| Dimension | genai-processors | Merism (current) |
|---|---|---|
| **LLM binding** | Hard-coupled to Gemini API (`GenaiModel`/`LiveProcessor` wrap `genai.types.Part`) | DeepSeek + Qwen via OpenAI-compat client (AGENTS.md Rule 5) |
| **Voice runtime** | Gemini Live API: STT/LLM/TTS fused server-side | Three independent client-side stages: Qwen Paraformer (STT) → DeepSeek (LLM) → Qwen CosyVoice (TTS) |
| **Stream unit** | `ProcessorPart` (wraps `genai.types.Part` with mime metadata) | `Frame` subclasses (`InputAudioRawFrame` / `TranscriptionFrame` / `LLMTextFrame` / `TTSAudioRawFrame` / etc.) |
| **Composition** | `+` (chain), `//` (parallel) operators | `Pipeline([...])` ordered list |
| **Async model** | Native `asyncio` | Native `asyncio` (pipecat-style) |
| **Dependencies** | `pip install genai-processors` + Google `genai` SDK | Self-contained, zero third-party deps |
| **License** | Apache 2.0 | Proprietary |

## Decision

**Do not adopt `genai-processors` as a dependency.** Selectively borrow
the `|`-chain composition pattern (Idea 1 below). Defer or skip the rest.

## Rationale (why not adopt)

Three blockers:

### 1. Stack conflict with AGENTS.md Rule 5

> "DeepSeek + Qwen stack only. Do not add new LLM providers without an ADR."

`genai-processors`' core value is its built-in Gemini integration. To
consume it without violating Rule 5 we would either:
- (a) Switch the LLM stack to Gemini — major business decision, requires
  separate ADR, breaks every prompt + cost model assumption.
- (b) Strip out `GenaiModel` / `LiveProcessor` and only use the async
  stream skeleton — defeats the purpose; what's left is a generic
  `asyncio` stream library.

Both paths fail.

### 2. Voice runtime topology mismatch

Gemini Live API is **server-side end-to-end**: browser sends audio →
Google server runs STT + LLM + TTS in one streaming session → returns
audio. `LiveProcessor` is built around this flow.

Merism's voice runtime is **client-side three-stage**: browser →
Paraformer (STT) → DeepSeek (LLM) → CosyVoice (TTS) → browser. Each
stage is a separate processor with independent lifecycle and timeouts.

`LiveProcessor`'s abstraction does not fit a separated three-stage
pipeline; we'd be using the library against the grain.

### 3. Replacement cost vs marginal gain

We have a working pipecat-inspired pipeline (`merism/voice/frames.py`,
`merism/voice/processors/`, ~600 LOC). We just finished decoupling
voice mode from text mode (2026-05-23 refactor). Migrating to
`genai-processors` would require:

- Rewriting all `Frame` subclasses to `ProcessorPart` (loses dataclass
  type safety — see Idea 3 below).
- Rewriting all `FrameProcessor` subclasses to the genai-processors
  `Processor` interface.
- Rewiring `merism/voice/setup.py` and `merism/realtime/voice.py`.

Estimated several thousand LOC of refactor. Marginal gain: cleaner
operator syntax (`|` instead of `Pipeline([...])`).

ROI is negative.

## Ideas to selectively adopt (or skip)

These are the four notable patterns in `genai-processors`. We evaluate
each independently — adoption is per-idea, not all-or-nothing.

### Idea 1: `|` chain operator overload — **MAYBE ADOPT**

**What**:
```python
# Current
pipeline = Pipeline([STTProcessor(client), moderator, TTSProcessor(), state])

# After
pipeline = STTProcessor(client) | moderator | TTSProcessor() | state
```

**Implementation**: add `__or__` to `FrameProcessor`:
```python
class FrameProcessor:
    def __or__(self, other: FrameProcessor) -> Pipeline:
        return Pipeline([self, other])
```

`Pipeline` keeps the same `__or__` so chains extend cleanly. Backward
compatible — existing `Pipeline([...])` call sites keep working.

**Cost**: ~30 LOC (operator method + tests).

**Benefit**:
- Reads more naturally for sequential pipelines.
- IDE type inference becomes friendlier (each `|` has clear lhs/rhs
  types).
- No runtime difference.

**Verdict**: Low cost, modest readability gain. **Eligible** — pull the
trigger when we touch pipeline construction next.

### Idea 2: `//` parallel fan-out — **SKIP**

**What**:
```python
# Same input flows to two analyzers, results merge downstream
pipeline = stt | (sentiment_analyzer // topic_extractor) | merge
```

Useful when the same data needs multiple independent transformations.

**Verdict**: We have **zero parallel-fanout cases**. Interview is strictly
sequential: STT → moderator → TTS → state. Adding the primitive without
a use case is dead code. **Skip until we have a real need.**

### Idea 3: Dual interface (gather / text / stream) — **MAYBE ADOPT (test ergonomics)**

**What**: a single processor invocation returns a `Result` object that
supports three consumption modes:
```python
result = await stt(audio).gather()  # collect all frames into a list
text = await stt(audio).text()       # collapse to plain text string
async for frame in stt(audio):       # iterate as frames arrive
    ...
```

**Current**: tests manually wire downstream subscriber:
```python
out = []
processor.set_downstream(lambda f: out.append(f))
await processor.process_frame(audio_frame)
assert any(isinstance(f, TranscriptionFrame) for f in out)
```

**After**:
```python
text = await stt(audio_frame).text()
assert text == "你好"
```

**Cost**: ~150 LOC (Result class + futures wiring) + update ~10 existing
voice tests.

**Benefit**:
- Test code roughly 50% shorter for subscriber-style assertions.
- Clearer call-site semantics ("I want all of it" vs "I want the text"
  vs "I want to stream").
- No runtime perf change.

**Verdict**: **Eligible** if test ergonomics start hurting. Currently
manageable — defer.

### Idea 4: Unified `Part` metadata model — **REJECT**

**What**: replace per-content-type dataclass subclasses with one generic
container:
```python
class Frame:
    role: str          # "user" | "assistant" | "system"
    mime: str          # "text/plain" | "audio/pcm" | "image/png"
    data: bytes | str
    meta: dict
```

vs current:
```python
@dataclass
class TranscriptionFrame(DataFrame):
    text: str
    is_final: bool = True

@dataclass
class TTSAudioRawFrame(DataFrame):
    audio: bytes
    sample_rate: int = 16000
```

**Pros**: multimodal extension is mime-string-driven; no new class for
each content variant.

**Cons**:
- Loses type safety. `frame.text` is statically known to be `str` in our
  model; `frame.data` could be `str | bytes` and requires runtime check
  on `frame.mime`.
- We don't need multimodal extension. Current scope: voice + text. No
  video / image streaming on the roadmap.
- IDE autocomplete + pyright catch shape errors today; switching to a
  bag-of-bytes model trades that for runtime errors.

**Verdict**: **Reject.** Type-safe per-class frames are a net win for
our scope. Revisit if/when we add video or screen-share modalities.

## Adoption summary

| Idea | Decision | Trigger |
|---|---|---|
| `\|` chain operator | Adopt when convenient | Next time we touch `voice/setup.py` or `Pipeline` |
| `//` parallel | Skip indefinitely | New ADR if a parallel use case appears |
| Dual interface (gather/text/stream) | Adopt if test pain grows | When voice tests double in count or get noticeably noisy |
| Unified `Part` metadata | Reject | Reopen if we add image/video modality |

## Consequences

**Positive**:
- Voice pipeline architecture stays self-contained; no third-party stack
  dependency that could constrain LLM or runtime choice.
- AGENTS.md Rule 5 (DeepSeek + Qwen only) remains intact without
  exception.
- Selective borrowing keeps cognitive overhead low — readers don't need
  to learn a new framework, just one operator.

**Negative**:
- We forgo the `LiveProcessor` shortcut for Gemini-based agents (we
  don't use Gemini, so this is moot for now).
- If a future modality (video, screen share) is added, we'll re-evaluate
  whether typed-frame model still scales — this ADR may need revisiting.

## References

- `google-gemini/genai-processors` README — https://github.com/google-gemini/genai-processors
- ADR 0005 — voice pipeline frame architecture (current `Frame` /
  `FrameProcessor` design)
- AGENTS.md Rule 5 — DeepSeek + Qwen stack only
- `merism/voice/frames.py`, `merism/voice/setup.py`,
  `merism/voice/processors/` — current voice runtime
