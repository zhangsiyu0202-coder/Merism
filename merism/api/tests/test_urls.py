"""URL routing tests for the API module."""

from __future__ import annotations

from collections import Counter

import pytest
from django.urls import NoReverseMatch, resolve, reverse

from merism.api import urls as api_urls
from merism.api.conversation_views import (
    delete_conversation,
    get_conversation,
    list_conversations,
    save_conversation,
)


def test_conversation_routes_resolve_to_function_views() -> None:
    assert resolve("/api/conversations/").func == list_conversations
    assert resolve("/api/conversations/save/").func == save_conversation
    assert resolve("/api/conversations/abc123/").func == get_conversation
    assert resolve("/api/conversations/abc123/delete/").func == delete_conversation


def test_conversation_routes_reverse_cleanly() -> None:
    assert reverse("conversations-list") == "/api/conversations/"
    assert reverse("conversations-save") == "/api/conversations/save/"
    assert reverse("conversations-detail", kwargs={"conversation_id": "abc123"}) == (
        "/api/conversations/abc123/"
    )
    assert reverse("conversations-delete", kwargs={"conversation_id": "abc123"}) == (
        "/api/conversations/abc123/delete/"
    )

    with pytest.raises(NoReverseMatch):
        reverse("conversation-list")


def test_conversation_paths_registered_once() -> None:
    names = Counter(
        pattern.name for pattern in api_urls.urlpatterns if getattr(pattern, "name", None)
    )

    assert names["conversations-list"] == 1
    assert names["conversations-save"] == 1
    assert names["conversations-detail"] == 1
    assert names["conversations-delete"] == 1
