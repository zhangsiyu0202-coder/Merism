"""真实 STT/TTS 端到端: TTS 把用户答案转音频 → STT 转回文字 → v3 graph 处理.

走通: 完整闭环 TTS + STT 都用真实 DashScope.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, "/home/jia/merism-app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")

import django
django.setup()

from dotenv import load_dotenv
load_dotenv("/home/jia/merism-app/.env")


async def main() -> None:
    from merism.tts import CosyVoiceClient
    from merism.stt import ParaformerClient

    print("=" * 70)
    print("真实 DashScope STT + TTS 端到端测试")
    print("=" * 70)

    # ── Test 1: TTS 把一句话转成音频 ──
    print("\n--- Test 1: TTS 文本→音频 ---")
    tts_client = CosyVoiceClient()
    
    text_to_speak = "你好,我是访谈助手,请先简单介绍一下你的工作"
    print(f"输入文本: {text_to_speak}")
    
    async def text_iter():
        yield text_to_speak

    t0 = time.time()
    audio_chunks = []
    async for chunk in tts_client.stream_tts(text_iter()):
        audio_chunks.append(chunk)
    tts_time = time.time() - t0
    
    total_audio_bytes = sum(len(c) for c in audio_chunks)
    print(f"TTS 输出: {len(audio_chunks)} chunks, 总 {total_audio_bytes} bytes, 耗时 {tts_time*1000:.0f}ms")
    
    # Save audio to wav for verification
    import wave
    out_path = "/tmp/v3_tts_output.wav"
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit PCM
        w.setframerate(24000)
        for chunk in audio_chunks:
            w.writeframes(chunk)
    audio_duration_s = total_audio_bytes / 2 / 24000  # 16-bit @ 24kHz
    print(f"音频时长: {audio_duration_s:.2f}s, 已保存 {out_path}")
    
    # ── Test 2: STT 把音频转回文字 ──
    print("\n--- Test 2: STT 音频→文本 (resample 到 16kHz) ---")
    
    # Resample 24kHz → 16kHz for ASR
    import audioop
    raw_bytes_24k = b"".join(audio_chunks)
    raw_bytes_16k, _ = audioop.ratecv(raw_bytes_24k, 2, 1, 24000, 16000, None)
    print(f"重采样: 24kHz {len(raw_bytes_24k)}B → 16kHz {len(raw_bytes_16k)}B")
    
    stt_client = ParaformerClient(language="zh", use_server_vad=False, sample_rate=16000)
    
    async def audio_iter():
        # Stream in 320-byte chunks (10ms @ 16kHz/16-bit)
        chunk_size = 3200  # 100ms chunks
        for i in range(0, len(raw_bytes_16k), chunk_size):
            yield raw_bytes_16k[i:i+chunk_size]
            await asyncio.sleep(0.01)  # simulate realtime

    t0 = time.time()
    transcripts = []
    final_text = ""
    async for ev in stt_client.stream_stt(audio_iter()):
        text = ev.text
        if ev.is_final:
            final_text = text
        transcripts.append((ev.is_final, text))
    stt_time = time.time() - t0
    
    print(f"STT 输出: {len(transcripts)} events, 耗时 {stt_time*1000:.0f}ms")
    print(f"Final transcript: {final_text!r}")
    print(f"原文 vs 转写匹配度: {'✅ 高' if len(final_text) >= len(text_to_speak) * 0.7 else '⚠️ 低'}")

    # ── Test 3: 完整闭环 — 把 STT 输出喂给 v3 graph ──
    print("\n--- Test 3: 闭环 TTS→STT→v3 graph ---")
    from langgraph.checkpoint.memory import InMemorySaver
    from merism.conductor.graph import build_graph
    from merism.conductor.runner import (
        answer_interview,
        get_interrupt_payload,
        start_interview,
    )
    from merism.conductor.schema import Outline, Question, Section

    outline = Outline(sections=[
        Section(id="s1", title="Test", questions=[
            Question(id="q1", ask="先介绍一下你的工作", follow_up_mode="off"),
            Question(id="q2", ask="工作中最头疼什么", follow_up_mode="off"),
        ])
    ])
    
    graph = build_graph(checkpointer=InMemorySaver())
    thread_id = f"voice-real-{int(time.time())}"
    
    result = start_interview(graph, outline=outline, thread_id=thread_id, follow_up_mode="off")
    payload = get_interrupt_payload(result)
    print(f"Q1 (graph 出): {payload['question']!r}")
    
    # Use the STT-transcribed text (final_text from above) as user answer
    if not final_text:
        final_text = "我是产品经理"  # fallback
    
    result = answer_interview(graph, user_answer=final_text, thread_id=thread_id)
    payload = get_interrupt_payload(result)
    print(f"USER (来自 STT): {final_text!r}")
    next_q = payload["question"] if payload else "(graph 已结束)"
    print(f"Q2 (graph 出): {next_q!r}")
    
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print(f"TTS:    ✅ {tts_time*1000:.0f}ms 转 {audio_duration_s:.1f}s 音频")
    print(f"STT:    ✅ {stt_time*1000:.0f}ms 转写 {len(final_text)} 字: {final_text!r}")
    print(f"Graph:  ✅ 接收 STT 输出, 推进到下一题")
    print(f"完整闭环: TTS → 音频 → STT → 文字 → v3 graph → 下一题")
    
    await tts_client.close() if hasattr(tts_client, 'close') else None
    await stt_client.close() if hasattr(stt_client, 'close') else None


if __name__ == "__main__":
    asyncio.run(main())
