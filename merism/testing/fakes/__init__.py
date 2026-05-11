"""Protocol-level fakes for external dependencies used by Merism.

Unlike ``unittest.mock.Mock``, these fakes **implement the real protocol**
(e.g., OpenAI ``chat.completions.create``, Feishu ``send_message``, Redis
streams). Tests can pass them in place of real clients without patching.

Every fake records its interactions so tests can assert call structure
directly instead of ``assert_called_with`` chains.
"""

from __future__ import annotations

from merism.testing.fakes.embeddings import hash_embedding
from merism.testing.fakes.im_channel import InMemoryIMAdapter, InMemorySentMessage
from merism.testing.fakes.llm import DeterministicLLM, LLMCall
from merism.testing.fakes.sse import SSEEvent, SSETestClient

__all__ = [
    "DeterministicLLM",
    "LLMCall",
    "InMemoryIMAdapter",
    "InMemorySentMessage",
    "SSETestClient",
    "SSEEvent",
    "hash_embedding",
]
