# Participant entry flow — design

## What this is

The participant-facing flow that turns a public invite link
(`/i/<slug>`) into a completed interview. Researchers never use this
flow — they paste the URL into email / WeCom / QQ, and recipients
follow it.

## Reference designs we drew from

| Product        | Pattern we kept                                          |
|----------------|----------------------------------------------------------|
| Typeform       | One thing per screen, browser-session resumable          |
| Calendly       | Short slug URL, no account required                      |
| Userinterviews | Consent → screener → schedule → session, clear gating    |
| Dovetail       | PIPL-style consent language, evidence-linked recordings  |
| Zoom meeting   | Anonymous join by link, device check before the room     |

## URL + state machine

```
  /i/:slug                    ← public entry (GET)
      │
      ▼
   resolve link + quota
      │
      ├── inactive / expired / closed → hero "Study closed"
      ├── preview=1 & researcher     → skip quota, mark is_preview=True
      └── valid
              │
              ▼
   recover or create Participation
   (via browser_token cookie; 30-day sliding window)
              │
              ▼
   ┌─ Participation.status decides the next step ──────┐
   │                                                    │
   │  INVITED     → /consent  (PIPL language)           │
   │  CONSENTED   → /screener (if Study has one) or     │
   │                  skip to → /session                │
   │  SCREENED    → /session  (create InterviewSession) │
   │  INTERVIEWING→ resume same session                 │
   │  COMPLETED   → "Thanks" screen                     │
   │  DROPPED     → same as COMPLETED, different copy   │
   └────────────────────────────────────────────────────┘
```

## Endpoints (all anonymous, CSRF-exempt, rate-limited)

| Method | Path                               | Purpose                                              |
|--------|------------------------------------|------------------------------------------------------|
| GET    | `/i/<slug>/`                       | Resolve link + current Participation state           |
| POST   | `/i/<slug>/consent/`               | Record `consented_at`, advance status to CONSENTED   |
| GET    | `/i/<slug>/screener/`              | Fetch screener questions                             |
| POST   | `/i/<slug>/screener/`              | Submit answers → grade → advance or DROPPED          |
| POST   | `/i/<slug>/start/`                 | Create `InterviewSession` with proper FKs            |

All return JSON; all anonymous; all rely on the `merism_browser_token`
cookie (HttpOnly, SameSite=Lax, 30-day) to identify the Participation.

## Security posture

- **Slug entropy**: 10 char lowercase-alphanumeric = 36¹⁰ ≈ 3.6×10¹⁵
  space. Enumeration-resistant for practical recruitment scale.
- **Rate limit**: 30 req/min per source IP on all /i/* endpoints
  (existing `rate_limit.check_and_increment_rate` reused).
- **No PII in URL**: slug is opaque. Participant attributes live in
  cookie + DB.
- **Consent logged**: `Participation.consented_at` timestamp.
- **Preview mode**: `?preview=1` sets `Participation.is_preview=True`
  — does NOT count toward quota, does NOT enqueue analysis pipeline.
- **Quota check**: before creating a new Participation (i.e. not
  recovering), count existing non-preview Participations for the
  study. If `study.target_completed_count` reached → show "Study full".
- **Session recovery**: a returning cookie that already has an
  InterviewSession gets sent to `/session` for the same session id —
  avoids losing in-progress interviews when the browser reloads.

## What we explicitly do NOT do yet (tracked as follow-ups)

- Email verification gate (would add friction; Phase-2 option)
- SMS-based OTP
- Scheduled slots (we do on-demand joins; Userinterviews-style
  scheduling lands later)
- Multi-round studies
