# ADR 0003 — Voice activity detection + end-to-end voice pipeline

**Status:** Accepted (2026-05-10)
**Deciders:** Jia
**Supersedes:** nothing
**Superseded by:** nothing
**Related:** ADR 0002 (barge-in default off)

## Context

The Merism interview pipeline is bound together by Voice Activity
Detection. Every downstream decision — when to stream audio to STT, when
to finalize a user turn, whether to accept a barge-in (ADR 0002), how
much bandwidth to use — depends on whether we reliably know if the
participant is speaking right now.

The MVP shipped a naive energy + hysteresis VAD client-side. It works in
a quiet office and fails everywhere else (keyboard typing, aircon,
coffee-shop crosstalk all cross the threshold). Research interviews run
in varied acoustic environments. We cannot rely on it.

## Decision

### VAD selection

**Client-side Silero VAD via `@ricky0123/vad-web` (ONNX Runtime Web).**
Server-side falls back to Paraformer's built-in endpointing for STT
turn boundaries. No server-side VAD — round-trip latency defeats
barge-in.

| Candidate | Chosen? | Why |
|---|---|---|
| Silero VAD (client, ONNX) | ✅ | Best accuracy 2024-2025, <5ms/frame on CPU, handles speech/laughter/cough/music distinction. 2.5 MB model, lazy-loaded only on Interview Room mount. |
| WebRTC VAD (WASM)         | ❌ | 2012 algorithm; false positives on keyboard, HVAC, table tapping. Merism participants won't always be in a studio. |
| Energy + hysteresis       | ❌ | What we had. Failure mode above. |
| Server-side Silero        | ❌ | 150-300 ms round trip kills barge-in UX (need < 100 ms). |

### AudioWorklet, not ScriptProcessor

`ScriptProcessor` is deprecated (removed from spec) and runs on the
main thread — causing UI jank under load. `AudioWorklet` runs on a
dedicated audio thread. The `@ricky0123/vad-web` library uses
AudioWorklet under the hood; our audio capture piggy-backs on the
same context so we don't fork mic access between VAD and capture.

### Silence suppression (bandwidth + cost)

When VAD reports "not speaking", audio frames are **not** sent to the
server. Savings:

- Bandwidth: 32 KB/s continuous → ~8 KB/s average (75% reduction for
  typical turn-taking interviews).
- STT cost: Paraformer billed per streamed second. Suppressing silence
  ~halves cost in voice mode.

### Pre-speech padding

VAD detection lag is typically 2-3 frames (~60-90 ms). If we start
sending audio at detection, the first consonant of the utterance is
lost. Solution: **maintain a rolling 300 ms ring buffer of raw audio**;
on `onSpeechStart` flush the buffer to WS, then switch to live streaming.

### End-to-end latency budget

Target: < 1.2 s from user stops talking → AI speaks. Budget:

| Stage | Budget | Notes |
|---|---|---|
| Client VAD `onSpeechEnd`        | 30-90 ms | Silero needs ~80 ms of silence |
| WS to server                    | 20-80 ms | Same region |
| Paraformer `is_final` flag      | 50-200 ms | Post last frame |
| Moderator LLM first token       | 400-800 ms | DeepSeek-Chat streaming |
| CosyVoice first audio chunk     | 200-400 ms | Streams on first text delta |
| WS back to client               | 20-80 ms |  |
| Web Audio decode + play         | 5-20 ms | Shared AudioContext |
| **Typical total**               | **~1.0 s** | Within budget |

### Shared AudioContext

One `AudioContext` for both capture and playback, re-used across the
session. Avoids the 100+ ms `AudioContext` initialization delay on
every message, and keeps `currentTime` reference stable for gapless TTS
playback.

## Consequences

### Positive

- VAD accurate enough for real participants in real rooms.
- Bandwidth and STT cost meaningfully lower.
- First consonant preserved via pre-speech padding.
- No ScriptProcessor deprecation risk.
- Barge-in responsive because detection is local.

### Negative

- +3 MB in the Interview Room bundle (ONNX runtime + Silero model).
  Lazy-loaded on entry to Interview Room only, so no impact on Ask / other
  surfaces. First-time participants wait ~300-500 ms at the mic-check
  screen for the model to fetch + warm up. Acceptable.
- Requires modern browser (AudioWorklet, SharedArrayBuffer — both widely
  supported 2025+). Documented in pre-flight mic check; falls back to
  text-mode on unsupported browsers.
- ONNX runtime occasionally ships security advisories. Monitor via
  Dependabot; pin to minor versions.

### Neutral

- VAD does not replace Paraformer's endpointing. Two signals, cross-checked.
  If VAD says "silent" but Paraformer keeps returning partial transcripts,
  Paraformer wins — it's hearing speech we misclassified.

## Mic-check UX (PRODUCT.md §2.2 step 4)

Before session starts, the Interview Room renders a :class:`MicCheck`
step that:

1. Requests mic permission.
2. Lazy-loads the Silero VAD model.
3. Shows a real-time level meter + "Say something like 'hello'" prompt.
4. On first successful `onSpeechEnd`, shows "We heard you — you're good
   to go."
5. Offers a "Mic not working?" link that drops the participant into
   text-only fallback mode (WS stays open for `text_input` messages).

This doubles as the load indicator for the ONNX model. No cold-start
surprise mid-session.

## Implementation contract

### Frontend modules

- `interview_room/voice/SileroVad.ts`  — wraps `@ricky0123/vad-web`
- `interview_room/voice/AudioCapture.ts` — AudioWorklet + ring buffer +
  silence suppression, uses SileroVad as its speech oracle
- `interview_room/voice/AudioPlayback.ts` — shared AudioContext player
- `interview_room/voice/MicCheck.tsx` — pre-session UI
- `interview_room/voiceStreamLogic.ts` — rewritten to compose the three

### Backend

- `merism/realtime/voice.py` — gains a `vad_signal_received` counter per
  session (logged to structlog) so we can monitor VAD accuracy against
  Paraformer's endpointing downstream. No business-logic change.

### Rollback plan

If Silero VAD causes field issues, the `voiceStreamLogic` is designed to
fall back to the energy-VAD implementation behind a feature flag
(`MERISM_VAD_BACKEND=energy`). The flag is client-side (query param) so
no deploy required.

## Revisit conditions

1. WebCodecs VAD native API ships in all major browsers — might obviate
   the ONNX runtime download. Currently experimental (2026-05).
2. Silero v5+ with quantized ≤ 500 KB ONNX available — swap drop-in.
3. Participant-reported mic issues > 5% in production telemetry —
   revisit mic-check UX and potentially add noise-suppression controls.
