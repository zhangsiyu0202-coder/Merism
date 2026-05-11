# `merism.recruitment`

IM recruitment subsystem. Implements the spec at
[`docs/specs/cowagent-im-recruitment/`](../../docs/specs/cowagent-im-recruitment/).

## Ported

- `adapters/base.py`               — `IMChannelBase`, `IMMessage`, `SendResult`
- `adapters/feishu_adapter.py`     — Feishu (Lark) open API adapter
- `adapters/wecom_bot_adapter.py`  — WeCom webhook bot adapter
- `adapters/qq_group_adapter.py`   — QQ Group bot (OAuth2 client_credentials)
- `adapters/qq_guild_adapter.py`   — QQ Guild (频道) bot adapter
- `adapters/factory.py`            — `get_adapter(channel_type, config)`
- `crypto.py`                      — Fernet encrypt/decrypt for credentials
                                     (prefers `MERISM_CHANNEL_ENCRYPTION_KEY`
                                     env, falls back to PBKDF2 on `SECRET_KEY`
                                     for dev)
- `renderer.py`                    — `{{placeholder}}` rendering + per-channel
                                     payload adaptation (text / markdown / card)
- `rate_limit.py`                  — 100 msg/channel/hour sliding-window cap
- `builtin_templates.py`           — system-owned `MessageTemplate` seeds

## TODO (not ported — owner rewriting against Merism models)

- `tasks.py`    — Celery tasks (`dispatch_recruitment_delivery`,
                 `retry_failed_deliveries`, `sync_channel_mirror`). The old
                 versions reference `posthog.models.Team` + `products.studies.*`;
                 rewrite against `merism.models.recruitment.*`.
- `api.py`      — DRF viewsets (`ChannelConfigViewSet`,
                 `MessageTemplateViewSet`, `RecruitmentBroadcastViewSet`).
                 Blocked on `merism.api` scaffolding.
- `urls.py`     — router wiring. Blocked on api.py.
- `cohort.py`   — email-based cohort recruitment helper. Phase 2: might port,
                 might delete if we go channel-first.

## Task list

1. **Migrations**: generate initial migration from
   `merism.models.recruitment.*` and apply.
2. **Port `tasks.py`**: write `dispatch_recruitment_delivery` against the
   new `ChannelConfig` / `RecruitmentBroadcast` / `DeliveryRecord` models.
   Must use `ph_scoped_capture` equivalent (see AGENTS.md AI conventions).
3. **Port `api.py`**: DRF viewsets. Wire `ChannelConfig.credentials` through
   `encrypt_credentials` on write and `decrypt_credentials` on read.
   `_mask_credentials` when non-admin users read.
4. **Onboarding wizard**: frontend-side; deliver as part of R9 design-system
   work. Backend only needs to expose channel type metadata + tooltips.
5. **Health checks**: Celery beat periodic task (every 30 min per spec Req
   5.1) that calls `adapter.health_check()` and updates
   `ChannelHealthCheck` + `ChannelConfig.status` + `consecutive_failures`.
6. **Tests**: port the relevant subset of
   `products/studies/backend/tests/recruitment/` — adapter unit tests
   (factory, each adapter), renderer, crypto, rate_limit. These mostly
   already use `merism.testing`-compatible patterns (`InMemoryIMAdapter`
   would replace the custom mocks once the real adapters ship).

## Usage (after tasks.py is ported)

```python
from merism.recruitment import get_adapter, decrypt_credentials
from merism.models import ChannelConfig

config = ChannelConfig.objects.get(id=...)
creds = decrypt_credentials(config.credentials_encrypted)
adapter = get_adapter(config.channel_type, creds)
ok, err = adapter.health_check()
```
