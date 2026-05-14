"""Link click recording service.

Handles:
- Click deduplication (same identity_hash + link within 1 hour)
- Bot filtering (basic UA check)
- UTM parameter extraction
- Device/browser parsing from UA
- Atomic counter increment on StudyLink
- Upstream referrer resolution
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.db.models import F
from django.http import HttpRequest
from django.utils import timezone

from merism.models.link_tracking import LinkClick, LinkShareEvent, _identity_hash
from merism.models.study import StudyLink

if TYPE_CHECKING:
    from merism.models import Participation

# Simple bot detection patterns (subset of Dub.co's approach)
_BOT_RE = re.compile(
    r"(bot|crawl|spider|slurp|facebookexternalhit|Twitterbot|"
    r"LinkedInBot|WhatsApp|TelegramBot|Googlebot|bingbot|YandexBot)",
    re.IGNORECASE,
)


def _is_bot(user_agent: str) -> bool:
    return bool(_BOT_RE.search(user_agent))


def _parse_device(user_agent: str) -> tuple[str, str, str]:
    """Return (device_type, browser, os) from UA string. Basic heuristic."""
    ua = user_agent.lower()
    # Device type
    if "ipad" in ua:
        device = "tablet"
    elif "iphone" in ua or ("mobile" in ua and "tablet" not in ua):
        device = "mobile"
    elif "android" in ua and "mobile" not in ua:
        device = "tablet"
    elif "android" in ua:
        device = "mobile"
    else:
        device = "desktop"
    # Browser
    if "chrome" in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "edg" in ua:
        browser = "Edge"
    else:
        browser = ""
    # OS
    if "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "windows" in ua:
        os_name = "Windows"
    elif "android" in ua:
        os_name = "Android"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = ""
    return device, browser, os_name


def _extract_referer_domain(referer: str) -> str:
    """Extract domain from referer URL, stripping www."""
    if not referer:
        return ""
    try:
        parsed = urlparse(referer)
        domain = parsed.hostname or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain[:512]
    except Exception:
        return ""


def record_click(
    request: HttpRequest,
    link: StudyLink,
    *,
    participation: Participation | None = None,
    referrer_participation: Participation | None = None,
) -> LinkClick | None:
    """Record a link click event. Returns None if deduplicated or bot.

    Called from the resolve_link view after successful link resolution.
    """
    ua_string = request.META.get("HTTP_USER_AGENT", "")

    # Bot filter
    if _is_bot(ua_string):
        return None

    # Build identity hash for dedup
    ip = _get_client_ip(request)
    ident = _identity_hash(ip, ua_string)

    # Dedup: same identity + link within 1 hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    is_unique = not LinkClick.objects.filter(
        study_link=link,
        identity_hash=ident,
        created_at__gte=one_hour_ago,
    ).exists()

    if not is_unique:
        return None

    # Extract UTM params
    utm_source = request.GET.get("utm_source", "")[:200]
    utm_medium = request.GET.get("utm_medium", "")[:200]
    utm_campaign = request.GET.get("utm_campaign", "")[:200]
    utm_term = request.GET.get("utm_term", "")[:200]
    utm_content = request.GET.get("utm_content", "")[:200]

    # Parse device info
    device_type, browser, os_name = _parse_device(ua_string)

    # Referer
    referer_url = request.META.get("HTTP_REFERER", "")
    referer_domain = _extract_referer_domain(referer_url)

    # Trigger detection
    trigger = LinkClick.Trigger.LINK
    if request.GET.get("qr") == "1":
        trigger = LinkClick.Trigger.QR

    # Determine trace_id
    trace_id = participation.trace_id if participation else None

    click = LinkClick.objects.create(
        team=link.team,
        study_link=link,
        identity_hash=ident,
        participation=participation,
        trace_id=trace_id or LinkClick._meta.get_field("trace_id").default(),
        ip_hash=_identity_hash(ip, ""),  # hash IP alone for geo lookup later
        user_agent=ua_string[:1024],
        referer=referer_domain,
        referer_url=referer_url[:1024],
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_term=utm_term,
        utm_content=utm_content,
        device_type=device_type,
        browser=browser,
        os=os_name,
        trigger=trigger,
        is_unique=True,
        referrer_participation=referrer_participation,
    )

    # Atomic counter increment on StudyLink
    StudyLink.objects.filter(id=link.id).update(
        clicks=F("clicks") + 1,
        last_clicked_at=timezone.now(),
    )

    return click


def record_share(
    request: HttpRequest,
    link: StudyLink,
    *,
    action: str = "copy",
    participation: Participation | None = None,
) -> LinkShareEvent:
    """Record a link share/copy event."""
    return LinkShareEvent.objects.create(
        team=link.team,
        study_link=link,
        action=action,
        sharer_participation=participation,
        trace_id=participation.trace_id if participation else LinkShareEvent._meta.get_field("trace_id").default(),
    )


def _get_client_ip(request: HttpRequest) -> str:
    """Extract client IP, respecting X-Forwarded-For."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
