# ADR 0004 — DashScope Realtime API model names

**Status**: Accepted (2026-05-10)

**Context**

The `/api-ws/v1/realtime` endpoint and the older `/api-ws/v1/inference/`
endpoint accept different model identifiers. Live-testing confirmed that
some names valid on the old inference protocol (`fun-asr-realtime`,
`paraformer-realtime-v2`, `cosyvoice-v2`) are **not** accepted on the
newer Realtime API — the server silently acknowledges the WebSocket
handshake (`session.created`) but drops `session.update` without a
`session.updated` response, leading to 300-second idle timeouts.

**Decision**

For the Realtime API (`wss://dashscope.aliyuncs.com/api-ws/v1/realtime`):

| Function | Working model (verified live) |
|---|---|
| ASR | `qwen3-asr-flash-realtime` |
| TTS | `qwen3-tts-instruct-flash-realtime` |

Keep these as the defaults in `merism.settings.base`. Operators who want
a pinned snapshot can set `DASHSCOPE_STT_MODEL=qwen3-asr-flash-realtime-2026-02-10`
via env.

**Consequences**

* Developers setting `DASHSCOPE_STT_MODEL=fun-asr-realtime` on a fresh
  install will hit a silent 300-s hang. The clients in
  `merism/stt.py` + `merism/tts.py` include a 30-s idle watchdog so this
  can't bring down the whole moderator loop, but the transcription will
  still be absent.
* When DashScope publishes a newer snapshot, bump the default only after
  running `bin/smoke_voice.py` against it.

**Evidence**

Smoke proof:

    $ python bin/smoke_voice.py
      ✓ DeepSeek chat.completions
      ✓ ASR session.updated + speech_started + transcription.completed
      ✓ TTS 9 audio chunks / 130 560 bytes

Real loop proof (TTS → WAV → ASR):

    TTS text: "你好，我是 Merism 的研究主持人…"
    ASR partials (20): "你好，我是 Maryism 的研究主持人，今天我们要…"

`fun-asr-realtime` accepted the WS handshake but never emitted
`session.updated` or any transcription events.
