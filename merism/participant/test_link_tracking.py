"""Tests for link click and share tracking."""

from __future__ import annotations

from django.test import RequestFactory, TestCase

from merism.models import LinkClick, LinkShareEvent, Participation, Study, StudyLink, Team
from merism.models.team import Organization
from merism.models.link_tracking import _identity_hash
from merism.participant.link_tracking import (
    _is_bot,
    _parse_device,
    record_click,
    record_share,
)


def _make_study_and_link():
    org = Organization.objects.create(name="Test Org")
    team = Team.objects.create(name="Test Team", organization=org)
    study = Study.objects.create(
        team=team,
        research_goal="Test goal",
        name="Test Study",
    )
    link = StudyLink.objects.create(study=study, team=team)
    return team, study, link


def _make_participation(team, study):
    return Participation.objects.create(
        team=team, study=study, status="invited"
    )


class TestIdentityHash:
    def test_deterministic(self):
        assert _identity_hash("1.2.3.4", "Mozilla/5.0") == _identity_hash("1.2.3.4", "Mozilla/5.0")

    def test_different_ip_different_hash(self):
        assert _identity_hash("1.2.3.4", "ua") != _identity_hash("5.6.7.8", "ua")


class TestBotDetection:
    def test_googlebot_detected(self):
        assert _is_bot("Mozilla/5.0 (compatible; Googlebot/2.1)")

    def test_normal_browser_not_bot(self):
        assert not _is_bot("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0")

    def test_whatsapp_preview_detected(self):
        assert _is_bot("WhatsApp/2.23.20.0")


class TestParseDevice:
    def test_desktop_chrome(self):
        device, browser, os = _parse_device(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        )
        assert device == "desktop"
        assert browser == "Chrome"
        assert os == "Windows"

    def test_mobile_android(self):
        device, browser, os = _parse_device(
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) Mobile Safari/537.36 Chrome/120.0"
        )
        assert device == "mobile"
        assert browser == "Chrome"
        assert os == "Android"

    def test_iphone_safari(self):
        device, browser, os = _parse_device(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/605.1"
        )
        assert device == "mobile"
        assert browser == "Safari"
        assert os == "iOS"


class TestRecordClick(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team, cls.study, cls.link = _make_study_and_link()
        cls.factory = RequestFactory()

    def _request(self, ip="1.2.3.4", ua="Mozilla/5.0 Chrome/120.0", **params):
        request = self.factory.get("/i/test/", data=params)
        request.META["REMOTE_ADDR"] = ip
        request.META["HTTP_USER_AGENT"] = ua
        return request

    def test_records_click_on_first_visit(self):
        req = self._request()
        click = record_click(req, self.link)
        assert click is not None
        assert click.study_link == self.link
        assert click.is_unique is True
        assert click.trigger == LinkClick.Trigger.LINK

    def test_deduplicates_within_one_hour(self):
        req = self._request(ip="10.0.0.1")
        first = record_click(req, self.link)
        assert first is not None
        second = record_click(req, self.link)
        assert second is None

    def test_different_ip_not_deduplicated(self):
        req1 = self._request(ip="10.0.1.1")
        req2 = self._request(ip="10.0.1.2")
        assert record_click(req1, self.link) is not None
        assert record_click(req2, self.link) is not None

    def test_bot_filtered(self):
        req = self._request(ua="Googlebot/2.1")
        assert record_click(req, self.link) is None

    def test_utm_params_captured(self):
        req = self._request(
            ip="10.0.2.1",
            utm_source="feishu",
            utm_medium="im",
            utm_campaign="spring2026",
        )
        click = record_click(req, self.link)
        assert click is not None
        assert click.utm_source == "feishu"
        assert click.utm_medium == "im"
        assert click.utm_campaign == "spring2026"

    def test_qr_trigger_detected(self):
        req = self._request(ip="10.0.3.1", qr="1")
        click = record_click(req, self.link)
        assert click is not None
        assert click.trigger == LinkClick.Trigger.QR

    def test_increments_link_click_counter(self):
        req = self._request(ip="10.0.4.1")
        record_click(req, self.link)
        self.link.refresh_from_db()
        assert self.link.clicks >= 1
        assert self.link.last_clicked_at is not None

    def test_referrer_participation_tracked(self):
        participation = _make_participation(self.team, self.study)
        req = self._request(ip="10.0.5.1")
        click = record_click(
            req, self.link, referrer_participation=participation
        )
        assert click is not None
        assert click.referrer_participation == participation

    def test_participation_bound_to_click(self):
        participation = _make_participation(self.team, self.study)
        req = self._request(ip="10.0.6.1")
        click = record_click(req, self.link, participation=participation)
        assert click is not None
        assert click.participation == participation
        assert click.trace_id == participation.trace_id


class TestRecordShare(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team, cls.study, cls.link = _make_study_and_link()
        cls.factory = RequestFactory()

    def test_records_copy_event(self):
        participation = _make_participation(self.team, self.study)
        req = self.factory.post("/i/test/share/")
        event = record_share(req, self.link, action="copy", participation=participation)
        assert event.action == "copy"
        assert event.sharer_participation == participation
        assert event.study_link == self.link

    def test_records_share_api_event(self):
        req = self.factory.post("/i/test/share/")
        event = record_share(req, self.link, action="share_api")
        assert event.action == "share_api"
        assert event.sharer_participation is None


class TestUpstreamDownstreamChain(TestCase):
    """Test the full upstream/downstream referral chain."""

    @classmethod
    def setUpTestData(cls):
        cls.team, cls.study, cls.link = _make_study_and_link()
        cls.factory = RequestFactory()

    def test_full_chain_a_shares_to_b(self):
        participation_a = _make_participation(self.team, self.study)
        participation_b = _make_participation(self.team, self.study)

        # A clicks the link (original recipient)
        req_a = self.factory.get("/i/test/")
        req_a.META["REMOTE_ADDR"] = "11.1.1.1"
        req_a.META["HTTP_USER_AGENT"] = "Chrome/120"
        click_a = record_click(req_a, self.link, participation=participation_a)
        assert click_a is not None
        assert click_a.referrer_participation is None

        # A shares the link
        record_share(
            self.factory.post("/"), self.link,
            action="copy", participation=participation_a,
        )

        # B clicks the link with A as referrer
        req_b = self.factory.get("/i/test/")
        req_b.META["REMOTE_ADDR"] = "11.2.2.2"
        req_b.META["HTTP_USER_AGENT"] = "Chrome/120"
        click_b = record_click(
            req_b, self.link,
            participation=participation_b,
            referrer_participation=participation_a,
        )
        assert click_b is not None
        assert click_b.referrer_participation == participation_a

        # Verify chain: A's downstream clicks include B's click
        downstream = LinkClick.objects.filter(referrer_participation=participation_a)
        assert downstream.count() == 1
        assert downstream.first() == click_b
