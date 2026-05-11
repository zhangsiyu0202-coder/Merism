"""LLM Gateway unit tests — models, presets loader, get_client factory, budget."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from django.test import TestCase

from merism.llm_gateway.exceptions import BudgetExceededError, RouteNotFoundError
from merism.llm_gateway.presets import load_presets, presets_for_protocol
from merism.models.llm_gateway import LLMBudget, LLMProvider, LLMRoute
from merism.models.team import Organization, Team
from merism.recruitment.crypto import encrypt_credentials


pytestmark = pytest.mark.django_db


def _make_team() -> Team:
    org = Organization.objects.create(name="Test Org", slug=f"test-{uuid4().hex[:8]}")
    return Team.objects.create(name="Test Team", organization=org)


def _make_provider(team=None, protocol="http", model="deepseek-chat", active=True) -> LLMProvider:
    return LLMProvider.objects.create(
        team=team,
        display_name=f"Test {model}",
        protocol=protocol,
        base_url="https://api.example.com",
        model=model,
        credentials_encrypted=encrypt_credentials({"api_key": "sk-test-key"}),
        is_active=active,
    )


class TestLLMProviderModel:
    def test_create_http_provider(self) -> None:
        team = _make_team()
        p = _make_provider(team=team)
        assert p.protocol == "http"
        assert p.is_active is True
        assert str(p.team_id) == str(team.id)

    def test_create_ws_provider(self) -> None:
        p = _make_provider(protocol="ws", model="qwen3-asr-flash-realtime")
        assert p.protocol == "ws"
        assert p.team is None  # global

    def test_str_repr(self) -> None:
        team = _make_team()
        p = _make_provider(team=team)
        assert "Test deepseek-chat" in str(p)
        assert "http" in str(p)


class TestLLMRouteModel:
    def test_create_route(self) -> None:
        team = _make_team()
        primary = _make_provider(team=team)
        route = LLMRoute.objects.create(
            team=team,
            logical_name="chat",
            primary=primary,
            temperature=0.5,
        )
        assert route.logical_name == "chat"
        assert route.fallback is None
        assert route.max_retries == 2

    def test_unique_together_enforced(self) -> None:
        team = _make_team()
        primary = _make_provider(team=team)
        LLMRoute.objects.create(team=team, logical_name="chat", primary=primary)
        with pytest.raises(Exception):  # IntegrityError
            LLMRoute.objects.create(team=team, logical_name="chat", primary=primary)


class TestLLMBudgetModel:
    def test_soft_limit_property(self) -> None:
        team = _make_team()
        budget = LLMBudget.objects.create(
            team=team,
            period="2026-05",
            monthly_cap_usd=Decimal("100.00"),
            current_spent_usd=Decimal("79.99"),
        )
        assert budget.is_over_soft_limit is False  # 79.99% < 80%

        budget.current_spent_usd = Decimal("80.01")
        assert budget.is_over_soft_limit is True

    def test_hard_limit_property(self) -> None:
        team = _make_team()
        budget = LLMBudget.objects.create(
            team=team,
            period="2026-05",
            monthly_cap_usd=Decimal("50.00"),
            current_spent_usd=Decimal("50.00"),
        )
        assert budget.is_over_hard_limit is True

    def test_default_action_is_alert_only(self) -> None:
        team = _make_team()
        budget = LLMBudget.objects.create(
            team=team, period="2026-05", monthly_cap_usd=Decimal("100")
        )
        assert budget.hard_limit_action == "alert_only"


class TestPresetsLoader:
    def test_loads_all_presets(self) -> None:
        presets = load_presets()
        assert len(presets) >= 15

    def test_every_preset_has_required_keys(self) -> None:
        for p in load_presets():
            assert "label" in p
            assert "protocol" in p
            assert "base_url" in p
            assert "model" in p
            assert "serves" in p

    def test_filter_by_protocol(self) -> None:
        http = presets_for_protocol("http")
        ws = presets_for_protocol("ws")
        assert all(p["protocol"] == "http" for p in http)
        assert all(p["protocol"] == "ws" for p in ws)
        assert len(http) + len(ws) == len(load_presets())


class TestGetClient:
    @pytest.mark.asyncio
    async def test_route_not_found_raises(self) -> None:
        from asgiref.sync import sync_to_async

        from merism.llm_gateway.client import get_client

        team = await sync_to_async(_make_team)()
        with pytest.raises(RouteNotFoundError):
            await get_client("chat", team=team, trace_id=uuid4())

    @pytest.mark.asyncio
    async def test_inactive_provider_raises(self) -> None:
        from asgiref.sync import sync_to_async

        from merism.llm_gateway.client import get_client
        from merism.llm_gateway.exceptions import ProviderUnavailableError

        team = await sync_to_async(_make_team)()
        provider = await sync_to_async(_make_provider)(team=team, active=False)
        await sync_to_async(LLMRoute.objects.create)(team=team, logical_name="chat", primary=provider)

        with pytest.raises(ProviderUnavailableError):
            await get_client("chat", team=team, trace_id=uuid4())

    @pytest.mark.asyncio
    async def test_http_returns_litellm_client(self) -> None:
        from asgiref.sync import sync_to_async

        from merism.llm_gateway.client import get_client
        from merism.llm_gateway.litellm_client import LiteLLMClient

        team = await sync_to_async(_make_team)()
        provider = await sync_to_async(_make_provider)(team=team)
        await sync_to_async(LLMRoute.objects.create)(team=team, logical_name="chat", primary=provider)

        client = await get_client("chat", team=team, trace_id=uuid4())
        assert isinstance(client, LiteLLMClient)

    @pytest.mark.asyncio
    async def test_ws_returns_paraformer_client(self) -> None:
        from asgiref.sync import sync_to_async

        from merism.llm_gateway.client import get_client
        from merism.stt import ParaformerClient

        team = await sync_to_async(_make_team)()
        provider = await sync_to_async(_make_provider)(team=team, protocol="ws", model="qwen3-asr-flash-realtime")
        await sync_to_async(LLMRoute.objects.create)(team=team, logical_name="asr_realtime", primary=provider)

        client = await get_client("asr_realtime", team=team, trace_id=uuid4())
        assert isinstance(client, ParaformerClient)

    @pytest.mark.asyncio
    async def test_budget_block_raises(self) -> None:
        import datetime

        from asgiref.sync import sync_to_async

        from merism.llm_gateway.client import get_client

        team = await sync_to_async(_make_team)()
        provider = await sync_to_async(_make_provider)(team=team)
        await sync_to_async(LLMRoute.objects.create)(team=team, logical_name="chat", primary=provider)

        period = datetime.date.today().strftime("%Y-%m")
        await sync_to_async(LLMBudget.objects.create)(
            team=team,
            period=period,
            monthly_cap_usd=Decimal("10.00"),
            current_spent_usd=Decimal("10.01"),
            hard_limit_action="block",
        )

        with pytest.raises(BudgetExceededError):
            await get_client("chat", team=team, trace_id=uuid4())

    @pytest.mark.asyncio
    async def test_budget_alert_only_does_not_block(self) -> None:
        import datetime

        from asgiref.sync import sync_to_async

        from merism.llm_gateway.client import get_client
        from merism.llm_gateway.litellm_client import LiteLLMClient

        team = await sync_to_async(_make_team)()
        provider = await sync_to_async(_make_provider)(team=team)
        await sync_to_async(LLMRoute.objects.create)(team=team, logical_name="chat", primary=provider)

        period = datetime.date.today().strftime("%Y-%m")
        await sync_to_async(LLMBudget.objects.create)(
            team=team,
            period=period,
            monthly_cap_usd=Decimal("10.00"),
            current_spent_usd=Decimal("99.00"),
            hard_limit_action="alert_only",
        )

        client = await get_client("chat", team=team, trace_id=uuid4())
        assert isinstance(client, LiteLLMClient)
