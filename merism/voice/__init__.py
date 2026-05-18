"""Merism voice pipeline — powered by pipecat-ai 1.2.

Architecture:
  WebSocket Transport → STT (Qwen Paraformer) → Moderator → TTS (Qwen CosyVoice) → WebSocket Transport

The moderator processor calls merism.conductor.moderator.stream_turn()
which handles all interview logic (dynamic probing, coverage steering, etc).
"""
