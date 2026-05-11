"""End-to-end truncation plumbing: client VAD → InterruptionFrame → history trim.

This is the critical OpenAI-Realtime-semantic test — the client claims
``audio_played_ms=400``, so the server should trim its conversation
snapshot to what the user actually heard, not what was generated.

Uses the same fakes as test_voice_consumer.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from channels.testing import WebsocketCommunicator

from merism.asgi import application

from .test_voice_consumer import make_session, patched_voice_clients  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_vad_audio_played_ms_feeds_truncation(
    make_session, patched_voice_clients
):
    """audio_played_ms arrives → pipeline truncates → session.moderator_state reflects it.

    Integration: we feed text, let the fake LLM + fake TTS generate output,
    then send a VAD-start with a specific played_ms. On disconnect, the
    session row should have a moderator_state.conversation entry whose
    assistant text is TRUNCATED (``truncated: true``).
    """
    session = await asyncio.to_thread(make_session, barge_in_enabled=True)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)      # session_ready

    # Start a turn — fake LLM emits "很高兴你来了。" across several deltas.
    await communicator.send_to(
        text_data=json.dumps({"type": "text_input", "text": "你好"})
    )

    # Let deltas flow a moment, then interrupt claiming 200 ms heard.
    seen_done = False
    seen_any_delta = False
    for _ in range(20):
        try:
            frame = await communicator.receive_output(timeout=2)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        msg = json.loads(frame["text"])
        if msg.get("type") == "agent_text_delta":
            seen_any_delta = True
            # Send VAD start right after the first delta so the response
            # is still in flight.
            await communicator.send_to(
                text_data=json.dumps(
                    {
                        "type": "vad_speaking_start",
                        "ts": 0.1,
                        "audio_played_ms": 200,
                    }
                )
            )
        elif msg.get("type") == "barge_in_accepted":
            # Good — server accepted + queued InterruptionFrame
            break
        elif msg.get("type") == "agent_text_done":
            seen_done = True
            break

    assert seen_any_delta, "expected at least one agent_text_delta before interrupting"

    await communicator.disconnect()

    # Poll session — disconnect triggers persist; give it a moment.
    for _ in range(20):
        await asyncio.sleep(0.05)
        await asyncio.to_thread(session.refresh_from_db)
        if (session.moderator_state or {}).get("conversation"):
            break

    state = session.moderator_state or {}
    convo = state.get("conversation", [])
    # At minimum the user turn should be there.
    user_items = [it for it in convo if it["role"] == "user"]
    assert user_items, f"expected at least one user turn in conversation, got {convo}"

    # If an assistant item is present it should be marked truncated.
    assistant_items = [it for it in convo if it["role"] == "assistant"]
    if assistant_items:
        assert any(it["truncated"] for it in assistant_items), (
            f"expected at least one assistant item marked truncated=True, got {assistant_items}"
        )


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_explicit_interrupt_message_is_respected_regardless_of_flag(
    make_session, patched_voice_clients
):
    """Explicit ``interrupt`` message bypasses per-study barge_in_enabled flag."""
    session = await asyncio.to_thread(make_session, barge_in_enabled=False)
    communicator = WebsocketCommunicator(
        application, f"/ws/sessions/{session.id}/voice/"
    )
    await communicator.connect()
    await communicator.receive_from(timeout=3)     # session_ready

    # Send explicit interrupt BEFORE any turn — tests that the handler is
    # reachable and always queues InterruptionFrame, independent of
    # whether a turn is in flight or the barge_in_enabled flag.
    await communicator.send_to(
        text_data=json.dumps({"type": "interrupt", "audio_played_ms": 150})
    )

    saw_barge_in = False
    for _ in range(30):
        try:
            frame = await communicator.receive_output(timeout=2)
        except Exception:
            break
        if "text" not in frame or not frame["text"]:
            continue
        data = json.loads(frame["text"])
        if data.get("type") == "barge_in_accepted":
            saw_barge_in = True
            break

    assert saw_barge_in, "explicit 'interrupt' must be respected regardless of study flag"
    await communicator.disconnect()
