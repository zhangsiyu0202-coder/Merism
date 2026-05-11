# Security

This is a proprietary, internal project. The process below applies to
employees, contractors, and authorized third-party licensees.

## Reporting a vulnerability

**Do not open a public issue or pull request for security matters.**

If you believe you have found a security vulnerability in Merism, email
[security@merism.ai](mailto:security@merism.ai) with:

1. A description of the issue and the potential impact.
2. Reproduction steps or a proof-of-concept (as minimal as possible).
3. The component affected (file path, endpoint, model name) and the
   commit SHA you tested against.
4. Your name and preferred contact channel.

You will receive an acknowledgment within **2 business days**. Please do
not disclose the issue externally or share details with people outside
the response chain until a fix has shipped and the affected customers
have been notified.

## Severity & SLA

We use a four-tier severity scale. Target fix SLAs are measured from the
time the report is triaged.

| Severity | Examples                                                                                     | Target fix SLA |
|----------|----------------------------------------------------------------------------------------------|----------------|
| P0       | Remote code execution, unauthenticated data exfiltration, bypass of tenant isolation.        | 24 hours       |
| P1       | Authenticated privilege escalation, stored XSS with session-cookie access, SSRF into internal services. | 3 business days |
| P2       | Reflected XSS, CSRF on non-destructive endpoints, information disclosure without secrets.    | 2 weeks        |
| P3       | Hardening recommendations, missing response headers, low-signal findings.                    | Next release   |

## Scope

In scope:

- All code under this repository (`merism/`, `frontend/`, `docker-compose.yml`,
  CI workflows, deployment manifests).
- Hosted services operated by the Company at `*.merism.ai` (production and
  staging).

Out of scope:

- Social engineering of employees.
- Physical attacks against Company offices or staff.
- Denial-of-service testing against production without prior written
  approval.
- Third-party services we integrate with (report to the respective
  vendor instead).

## Incident response SOP

When a confirmed security incident is declared:

1. **Triage (owner: on-call engineer).** Create a private incident channel,
   classify severity, assign an IC (Incident Commander).
2. **Contain (owner: IC).** Rotate exposed credentials, revoke compromised
   tokens, roll deployment back to a known-good commit if the fix is not
   immediately available. Disable the affected code path via a feature
   flag (`MERISM_*`) if possible.
3. **Eradicate (owner: responsible team).** Land a fix on `main`, cherry-
   pick to all active release branches, deploy.
4. **Recover (owner: IC).** Verify no residual persistence, re-enable the
   feature flag, monitor error rates and customer-reported signals for 24h.
5. **Learn (owner: IC).** Publish a blameless post-mortem within 5 business
   days covering timeline, root cause, impact (rows affected / users
   exposed / secrets rotated), and action items.

## Credential & secret policy

- Never commit real secrets. `.env` is gitignored; `.env.example` holds
  placeholders only.
- Channel credentials are encrypted with Fernet
  (`merism.recruitment.crypto`) before persistence. Raw values never
  leave `ChannelConfig.credentials_encrypted`.
- All LLM / STT / TTS API keys live in the deployment's secret manager
  (not committed). In CI, inject them via encrypted GitHub Actions
  secrets.
- Rotate `SECRET_KEY`, `MERISM_CHANNEL_ENCRYPTION_KEY`, and all
  third-party API keys **immediately** upon:
  - A suspected leak.
  - Departure of a person who had production access.
  - Every 180 days as a baseline.

## Data handling

- Participant PII (name, email hash, recipient identifiers) is
  restricted to `Invitation`, `DeliveryRecord`, `Participation`. Do
  not log raw PII — use `recipient_hash` (SHA-256) for trace
  correlation.
- Interview transcripts and session recordings are considered
  confidential research data. Encrypt at rest in object storage and
  apply a retention policy of 18 months by default; longer retention
  requires explicit customer consent.
- `trace_id` is safe to log; participant identifiers are not.

## Coordinated disclosure

For authorized security researchers under a written agreement with
the Company: once a fix has shipped and customers have been notified,
we will credit you in the internal post-mortem and, where applicable,
a public changelog entry. We do not currently run a public bug bounty.
