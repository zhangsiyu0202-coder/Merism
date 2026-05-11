"""Pytest fixtures wrapping Merism factories and fakes.

Import these a la carte — they are not auto-registered via a conftest. Example::

    # your conftest.py
    from merism.testing.fixtures import study, interview, fake_llm  # noqa

Then your test functions receive them as arguments::

    def test_something(study, interview, fake_llm):
        ...
"""

from __future__ import annotations

import pytest

from merism.testing.factories.interview import make_interview, make_turn
from merism.testing.factories.knowledge import make_knowledge_chunk
from merism.testing.factories.recruitment import make_broadcast, make_channel_config
from merism.testing.factories.study import make_study, make_study_with_goals
from merism.testing.fakes.im_channel import InMemoryIMAdapter
from merism.testing.fakes.llm import DeterministicLLM
from merism.testing.fakes.rag import FakeRAGRetriever
from merism.testing.fakes.sse import SSETestClient


@pytest.fixture
def study():
    """A stub Study with no goals attached."""
    return make_study()


@pytest.fixture
def study_with_goals():
    """A stub Study with one P0 + one P1 goal."""
    return make_study_with_goals(
        goals=[("p0", "Why do users bounce at signup?"), ("p1", "Is pricing clear?")]
    )


@pytest.fixture
def interview(study_with_goals):
    """A stub active voice interview linked to ``study_with_goals``."""
    return make_interview(study_with_goals, state="active", mode="voice")


@pytest.fixture
def agent_turn(interview):
    """Append an agent turn to ``interview`` and yield it."""
    return make_turn(interview, role="agent", content="Hello! Can you tell me about your role?")


@pytest.fixture
def participant_turn(interview):
    return make_turn(interview, role="participant", content="I'm a product manager at a fintech.")


@pytest.fixture
def fake_llm():
    """A stateless ``DeterministicLLM`` — queue responses per test."""
    return DeterministicLLM()


@pytest.fixture
def feishu_adapter():
    """An :class:`InMemoryIMAdapter` configured for Feishu."""
    return InMemoryIMAdapter(channel_type="feishu")


@pytest.fixture
def feishu_channel(feishu_adapter):
    """A ChannelConfig with a Feishu adapter attached."""
    return make_channel_config(channel_type="feishu", adapter=feishu_adapter)


@pytest.fixture
def broadcast(study, feishu_channel):
    """A draft broadcast for ``study`` over ``feishu_channel``. No recipients yet."""
    return make_broadcast(study=study, channel=feishu_channel, status="draft")


@pytest.fixture
def fake_retriever():
    """Empty :class:`FakeRAGRetriever` — seed chunks per test."""
    return FakeRAGRetriever()


@pytest.fixture
def sse_client():
    """Fresh :class:`SSETestClient` collecting events."""
    return SSETestClient()
