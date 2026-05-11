#!/usr/bin/env python
"""End-to-end voice loop — DeepSeek → TTS → WAV → ASR.

Proves the three real services interoperate. Each run burns a few cents
of DashScope credit + one DeepSeek completion.
"""
from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")
django.setup()

from django.conf import settings

from merism.memai.llm import get_llm
from merism.tts import CosyVoiceClient

GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"


async def main() -> int:
    # ── 1. LLM ──
    print(f"{DIM}1. DeepSeek → Chinese reply{RESET}")
    client = get_llm()
    stream = client.chat.completions.create(
        model=settings.MERISM_LLM_MODEL,
        messages=[
            {"role": "system", "content": "你是 Merism 研究平台的 AI 主持人。用一句简短的中文欢迎用户。"},
            {"role": "user", "content": "开始面试。"},
        ],
        stream=True,
        max_tokens=60,
    )
    reply_text = ""

    async def text_iter():
        nonlocal reply_text
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                reply_text += delta
                yield delta

    # ── 2. TTS → WAV ──
    print(f"{DIM}2. Qwen-TTS → PCM audio{RESET}")
    tts = CosyVoiceClient()
    audio_buf = bytearray()
    async for blob in tts.stream_tts(text_iter()):
        audio_buf.extend(blob)

    wav_path = ROOT / "bin" / "smoke_voice_loop.wav"
    with wave.open(str(wav_path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(bytes(audio_buf))
    print(f"   LLM reply: {reply_text!r}")
    print(f"   WAV: {len(audio_buf)} bytes ({len(audio_buf)/48000:.1f}s @ 24 kHz) → {wav_path.name}")

    # ── 3. ASR on the WAV ──
    print(f"{DIM}3. Qwen-ASR → transcript{RESET}")
    samples = list(struct.unpack(f"<{len(audio_buf)//2}h", bytes(audio_buf)))
    pcm16 = bytearray()
    for i in range(0, len(samples) - 2, 3):
        pcm16 += struct.pack("<hh", samples[i], samples[i + 1])
    pcm16_bytes = bytes(pcm16)

    from websockets.asyncio.client import connect
    import base64

    api_key = settings.DASHSCOPE_ASR_API_KEY or settings.DASHSCOPE_API_KEY
    url = f"{settings.DASHSCOPE_REALTIME_URL}?model={settings.DASHSCOPE_STT_MODEL}"

    async with connect(url, additional_headers={
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }) as ws:
        await ws.send(json.dumps({
            "event_id": uuid.uuid4().hex[:12],
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "input_audio_format": "pcm",
                "sample_rate": 16000,
                "input_audio_transcription": {"language": "zh"},
                "turn_detection": {"type": "server_vad", "threshold": 0.0, "silence_duration_ms": 600},
            },
        }))

        async def pump():
            CHUNK = 3200
            for i in range(0, len(pcm16_bytes), CHUNK):
                await ws.send(json.dumps({
                    "event_id": uuid.uuid4().hex[:12],
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(pcm16_bytes[i:i+CHUNK]).decode(),
                }))
                await asyncio.sleep(0.08)
            # trailing silence to trigger VAD stop
            tail_silence = b"\x00\x00" * 16000
            for i in range(0, len(tail_silence), CHUNK):
                await ws.send(json.dumps({
                    "event_id": uuid.uuid4().hex[:12],
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(tail_silence[i:i+CHUNK]).decode(),
                }))
                await asyncio.sleep(0.08)

        pump_task = asyncio.create_task(pump())
        final_transcript = ""
        try:
            async with asyncio.timeout(25):
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    ev = json.loads(raw)
                    etype = ev.get("type", "")
                    if etype == "conversation.item.input_audio_transcription.completed":
                        final_transcript = ev.get("transcript", "")
                        await ws.send(json.dumps({
                            "event_id": uuid.uuid4().hex[:12],
                            "type": "session.finish",
                        }))
                    elif etype == "session.finished":
                        break
        except asyncio.TimeoutError:
            pass
        finally:
            pump_task.cancel()

    print(f"   ASR final: {final_transcript!r}")

    # ── summary ──
    print()
    if reply_text and len(audio_buf) > 0 and final_transcript:
        print(f"{GREEN}✓ voice loop OK:{RESET}")
        print(f"    LLM → TTS → ASR round-trip proven against real endpoints.")
        print(f"    {len(reply_text)} chars text → {len(audio_buf)} bytes audio → {len(final_transcript)} chars transcript.")
        return 0
    print("✗ voice loop incomplete — check each stage's output above.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
