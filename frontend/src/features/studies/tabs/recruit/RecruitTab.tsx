import { useActions, useMountedLogic, useValues } from "kea";
import { Pencil, Plus, Save, Send, Users } from "lucide-react";
import { useEffect } from "react";

import {
  Button,
  Illustration,
  Input,
  KpiCard,
  KpiGrid,
  SectionLabel,
  Tag,
} from "~/lib/merism";
import { studyLogic } from "~/features/studies/studyLogic";

import { broadcastsLogic, type BroadcastRow } from "./broadcastsLogic";
import { launchRecruitmentLogic } from "./launchRecruitmentLogic";
import { QuotaDialog } from "./QuotaDialog";
import { recruitPlanLogic } from "./recruitPlanLogic";

/**
 * RecruitTab — sample description + quota constraints editor.
 *
 * Above the fold:
 *   1. "Who are we talking to?"  (target_audience free-text)
 *   2. "How many?"               (target_completed_count number)
 *   3. "Any constraints?"        (recruitment_quotas quota pills)
 *
 * Sample quotas build up through a modal (QuotaDialog). The KpiGrid
 * at top tracks quota target vs study target + quota dimension count
 * so researchers see at a glance whether their quotas add up.
 *
 * Channel composer (Feishu / WeCom / QQ) lives downstream of this
 * plan — once the plan is set, recruitment broadcast reads from these
 * fields.
 */

export default function RecruitTab(): JSX.Element {
  useMountedLogic(recruitPlanLogic);
  useMountedLogic(broadcastsLogic);
  useMountedLogic(launchRecruitmentLogic);
  const { study } = useValues(studyLogic);
  const {
    draftAudience,
    draftCount,
    draftQuotas,
    totalQuotaTargets,
    hasUnsavedChanges,
    savedAtLoading,
  } = useValues(recruitPlanLogic);
  const {
    hydrateFromStudy,
    setAudience,
    setCompletedCount,
    openQuotaDialog,
    removeQuota,
    saveRecruitmentPlan,
  } = useActions(recruitPlanLogic);

  useEffect(() => {
    if (study) hydrateFromStudy(study);
  }, [study, hydrateFromStudy]);

  if (!study) {
    return (
      <div className="text-merism-text-muted">Loading recruitment plan…</div>
    );
  }

  const quotaMismatch =
    draftQuotas.length > 0 && totalQuotaTargets !== draftCount;

  return (
    <div className="flex flex-col gap-[var(--spacing-merism-section-y)]">
      {/* ── KPI row ────────────────────────────────── */}
      <KpiGrid columns={3}>
        <KpiCard
          label="Target sessions"
          value={draftCount}
          subtitle="completed interviews wanted"
          icon={<Users className="h-3 w-3" />}
          size="title"
        />
        <KpiCard
          label="Quotas"
          value={draftQuotas.length}
          subtitle={
            draftQuotas.length === 0
              ? "no constraints set"
              : `${draftQuotas.length} dimensions`
          }
          size="title"
        />
        <KpiCard
          label="Quota sum"
          value={totalQuotaTargets}
          subtitle={
            draftQuotas.length === 0
              ? "N/A"
              : quotaMismatch
                ? "≠ target count"
                : "matches target"
          }
          trend={
            draftQuotas.length === 0
              ? undefined
              : quotaMismatch
                ? {
                    value: `${totalQuotaTargets} vs ${draftCount}`,
                    direction: "flat",
                    positive: false,
                  }
                : undefined
          }
          size="title"
        />
      </KpiGrid>

      {/* ── Section 1 · Audience ───────────────────── */}
      <section className="flex flex-col gap-4">
        <SectionLabel>Who are we talking to?</SectionLabel>
        <textarea
          value={draftAudience}
          onChange={(e) => setAudience(e.target.value)}
          rows={5}
          placeholder="e.g. Chinese working professionals aged 25-40 who use productivity apps daily and have used at least 2 competing tools in the past 6 months."
          className="w-full rounded-merism-lg bg-merism-surface p-4 text-merism-body leading-relaxed text-merism-text outline-none ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card placeholder:text-merism-text-subtle focus:ring-[color:var(--merism-hairline-strong)]"
        />
        <p className="text-merism-body-sm text-merism-text-muted">
          Describe the participant profile in plain language. This powers the
          screener question bank and recruitment-channel targeting.
        </p>
      </section>

      {/* ── Section 2 · Target count ─────────────── */}
      <section className="flex flex-col gap-4">
        <SectionLabel>How many participants?</SectionLabel>
        <div className="flex items-center gap-3">
          <Input
            type="number"
            min={1}
            max={500}
            value={draftCount}
            onChange={(e) => setCompletedCount(parseInt(e.target.value, 10))}
            className="w-28 text-right text-merism-subtitle font-display"
          />
          <span className="text-merism-body-sm text-merism-text-muted">
            completed interviews
          </span>
        </div>
      </section>

      {/* ── Section 3 · Quotas ─────────────────────── */}
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <SectionLabel>Quota constraints</SectionLabel>
          <Button
            size="sm"
            variant="secondary"
            iconLeft={<Plus className="h-4 w-4" />}
            onClick={() => openQuotaDialog(null)}
          >
            Add quota
          </Button>
        </div>

        {draftQuotas.length === 0 ? (
          <QuotaEmpty onAdd={() => openQuotaDialog(null)} />
        ) : (
          <div className="flex flex-col gap-3">
            {draftQuotas.map((quota, i) => (
              <QuotaRow
                key={`${quota.dimension}-${i}`}
                quota={quota}
                onEdit={() => openQuotaDialog(i)}
                onRemove={() => removeQuota(i)}
              />
            ))}
          </div>
        )}

        {quotaMismatch && (
          <p className="text-merism-body-sm text-[color:var(--merism-status-warning)]">
            Heads up: your quotas sum to {totalQuotaTargets} but you're
            targeting {draftCount} total participants. Adjust either side so
            they match.
          </p>
        )}
      </section>

      {/* ── Save bar ─────────────────────────────── */}
      {hasUnsavedChanges && (
        <div className="sticky bottom-6 flex items-center justify-between rounded-merism-lg bg-merism-bg-inverse px-5 py-3 text-merism-text-inverse shadow-merism-float">
          <span className="text-merism-body-sm">You have unsaved changes.</span>
          <Button
            size="sm"
            iconLeft={<Save className="h-4 w-4" />}
            isLoading={savedAtLoading}
            onClick={saveRecruitmentPlan}
          >
            Save plan
          </Button>
        </div>
      )}

      <QuotaDialog />
      <RecruitmentStatusPanel hasUnsavedChanges={hasUnsavedChanges} />
    </div>
  );
}

// ── Internal components ──

function QuotaEmpty({ onAdd }: { onAdd: () => void }): JSX.Element {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-merism-lg bg-merism-surface p-8 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <Illustration name="flag" size="md" className="text-merism-text-subtle" />
      <div className="flex flex-col gap-1">
        <h3 className="text-merism-body font-medium text-merism-text">
          No quotas yet
        </h3>
        <p className="text-merism-body-sm text-merism-text-muted">
          Add a quota to require a balanced sample across dimensions like age,
          location, or usage frequency.
        </p>
      </div>
      <Button
        size="sm"
        variant="secondary"
        iconLeft={<Plus className="h-4 w-4" />}
        onClick={onAdd}
      >
        Add your first quota
      </Button>
    </div>
  );
}

function QuotaRow({
  quota,
  onEdit,
  onRemove,
}: {
  quota: import("~/types").RecruitmentQuota;
  onEdit: () => void;
  onRemove: () => void;
}): JSX.Element {
  const total = quota.segments.reduce((s, seg) => s + seg.target, 0);

  return (
    <div className="flex items-start gap-4 rounded-merism-lg bg-merism-surface p-5 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex items-center gap-3">
          <h4 className="text-merism-body font-medium text-merism-text">
            {quota.label}
          </h4>
          <Tag variant="outline" size="sm">
            {total} targets
          </Tag>
        </div>
        <div className="flex flex-wrap gap-2">
          {quota.segments.map((seg, i) => (
            <Tag
              key={`${seg.label}-${i}`}
              variant="neutral"
              size="sm"
              case="normal"
            >
              {seg.label} · {seg.target}
            </Tag>
          ))}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onEdit}
          aria-label="Edit quota"
          className="flex h-8 w-8 items-center justify-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove quota"
          className="flex h-8 w-8 items-center justify-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-danger"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M2 4.5h10M5.5 2h3M5 6.5v4M9 6.5v4M3.5 4.5l.5 7a1 1 0 001 1h4a1 1 0 001-1l.5-7"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// RecruitmentStatusPanel — read-only broadcast status + participant URL.
// All CRUD for channels / templates / broadcasts lives in Django admin.
// This panel is just a mirror so researchers can see status in-app.
// ─────────────────────────────────────────────────────────────

function RecruitmentStatusPanel({
  hasUnsavedChanges,
}: {
  hasUnsavedChanges: boolean;
}): JSX.Element {
  const { broadcasts, broadcastsLoading } = useValues(broadcastsLogic);
  const { isLaunching, lastLaunchResult, launchError } = useValues(
    launchRecruitmentLogic,
  );
  const { launchRecruitment, clearLaunchFeedback } = useActions(
    launchRecruitmentLogic,
  );

  return (
    <section className="flex flex-col gap-6">
      <SectionLabel>Recruitment outreach</SectionLabel>
      <div className="flex flex-col gap-4 rounded-merism-lg bg-merism-surface p-6 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl">
            <p className="text-merism-body font-medium text-merism-text">
              Generate and send invites automatically
            </p>
            <p className="text-merism-body-sm text-merism-text-muted">
              Merism will turn your target audience and quotas into a
              group-ready invite, then send it to the default QQ / WeCom groups
              configured in admin.
            </p>
          </div>
          <Button
            iconLeft={<Send className="h-4 w-4" />}
            isLoading={isLaunching}
            disabled={hasUnsavedChanges}
            onClick={launchRecruitment}
          >
            Start recruitment
          </Button>
        </div>

        {hasUnsavedChanges && (
          <p className="text-merism-body-sm text-[color:var(--merism-status-warning)]">
            Save the recruitment plan before sending outreach.
          </p>
        )}

        {launchError && (
          <div className="flex items-start justify-between gap-3 rounded-merism-md bg-[color:var(--merism-status-danger-soft)] px-4 py-3">
            <p className="text-merism-body-sm text-merism-text">
              {launchError}
            </p>
            <button
              type="button"
              onClick={clearLaunchFeedback}
              className="text-merism-caption text-merism-text-subtle hover:text-merism-text"
            >
              Dismiss
            </button>
          </div>
        )}

        {lastLaunchResult && (
          <div className="flex flex-col gap-2 rounded-merism-md bg-[color:var(--merism-status-success-soft)] px-4 py-3">
            <p className="text-merism-body-sm text-merism-text">
              Queued {lastLaunchResult.created_count} deliveries across{" "}
              {lastLaunchResult.queued_broadcast_ids.length} broadcasts.
            </p>
            {lastLaunchResult.skipped_channels.length > 0 && (
              <p className="text-merism-caption text-merism-text-muted">
                Skipped:{" "}
                {lastLaunchResult.skipped_channels
                  .map((item: { channel_name: string }) => item.channel_name)
                  .join(", ")}
              </p>
            )}
            {lastLaunchResult.errors.length > 0 && (
              <p className="text-merism-caption text-merism-text-muted">
                Errors: {lastLaunchResult.errors.join(" · ")}
              </p>
            )}
          </div>
        )}
      </div>

      <SectionLabel className="mt-4">Broadcasts</SectionLabel>
      <BroadcastList rows={broadcasts} loading={broadcastsLoading} />
    </section>
  );
}

function BroadcastList({
  rows,
  loading,
}: {
  rows: BroadcastRow[];
  loading: boolean;
}): JSX.Element {
  if (loading && rows.length === 0) {
    return (
      <div className="rounded-merism-lg bg-merism-surface p-6 text-merism-body-sm text-merism-text-muted shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
        Loading broadcasts…
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <div className="flex items-center justify-between rounded-merism-lg bg-merism-surface p-6 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
        <div>
          <p className="text-merism-body font-medium text-merism-text">
            No broadcasts sent yet
          </p>
          <p className="text-merism-body-sm text-merism-text-muted">
            Configure active channels and default target groups in{" "}
            <a
              href="/admin/merism/channelconfig/"
              className="text-merism-accent hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              Django admin
            </a>
            .
          </p>
        </div>
        <Send className="h-5 w-5 text-merism-text-subtle" />
      </div>
    );
  }
  return (
    <ul className="divide-y divide-[color:var(--merism-hairline)] rounded-merism-lg bg-merism-surface shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      {rows.map((b) => (
        <li key={b.id} className="flex items-center gap-4 px-4 py-3">
          <Send className="h-4 w-4 shrink-0 text-merism-text-subtle" />
          <div className="flex-1 min-w-0">
            <p className="text-merism-body-sm text-merism-text">
              {b.channel_name ?? b.channel ?? "(channel)"}
            </p>
            <p className="font-mono text-merism-caption text-merism-text-subtle">
              sent: {b.counters.sent ?? 0} · failed: {b.counters.failed ?? 0} ·
              pending: {b.counters.pending ?? 0}
            </p>
          </div>
          <Tag
            variant={
              b.status === "completed"
                ? "success"
                : b.status === "failed"
                  ? "danger"
                  : b.status === "sending"
                    ? "accent"
                    : "neutral"
            }
            size="sm"
          >
            {b.status}
          </Tag>
        </li>
      ))}
    </ul>
  );
}
