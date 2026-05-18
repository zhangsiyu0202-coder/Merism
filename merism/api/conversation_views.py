"""Conversation persistence API for AI assistant."""
from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from merism.models import Conversation, OrganizationMembership, Team


def _get_team(user):
    m = OrganizationMembership.objects.filter(user=user).select_related("organization").first()
    if not m:
        return None
    return Team.objects.filter(organization=m.organization).first()


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def list_conversations(request: HttpRequest) -> JsonResponse:
    team = _get_team(request.user)
    if not team:
        return JsonResponse({"conversations": []})
    convos = Conversation.objects.filter(team=team, user=request.user).order_by("-updated_at")[:30]
    return JsonResponse({
        "conversations": [
            {"id": str(c.id), "title": c.title or "新对话", "updated_at": c.updated_at.isoformat(), "study_id": str(c.study_id) if c.study_id else None}
            for c in convos
        ]
    })


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def get_conversation(request: HttpRequest, conversation_id: str) -> JsonResponse:
    team = _get_team(request.user)
    if not team:
        return JsonResponse({"error": "no team"}, status=404)
    try:
        c = Conversation.objects.get(id=conversation_id, team=team, user=request.user)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    return JsonResponse({
        "id": str(c.id),
        "title": c.title,
        "messages": c.messages,
        "study_id": str(c.study_id) if c.study_id else None,
        "updated_at": c.updated_at.isoformat(),
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def save_conversation(request: HttpRequest) -> JsonResponse:
    team = _get_team(request.user)
    if not team:
        return JsonResponse({"error": "no team"}, status=400)
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        body = {}

    conv_id = body.get("id")
    messages = body.get("messages", [])
    title = body.get("title", "")
    study_id = body.get("study_id")

    if conv_id:
        try:
            c = Conversation.objects.get(id=conv_id, team=team, user=request.user)
            c.messages = messages
            if title:
                c.title = title
            c.save()
        except Conversation.DoesNotExist:
            c = Conversation.objects.create(id=conv_id, team=team, user=request.user, title=title, messages=messages, study_id=study_id)
    else:
        c = Conversation.objects.create(team=team, user=request.user, title=title, messages=messages, study_id=study_id)

    return JsonResponse({"id": str(c.id), "title": c.title})


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def delete_conversation(request: HttpRequest, conversation_id: str) -> JsonResponse:
    team = _get_team(request.user)
    if not team:
        return JsonResponse({"error": "no team"}, status=400)
    Conversation.objects.filter(id=conversation_id, team=team, user=request.user).delete()
    return JsonResponse({"ok": True})
