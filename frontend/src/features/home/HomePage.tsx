import { useActions, useMountedLogic, useValues } from "kea";
import { router } from "kea-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Clock, FlaskConical, Lightbulb, Plus, Users } from "lucide-react";

import { urls } from "~/app/routes";
import {
  Button,
  Illustration,
  KpiCard,
  KpiGrid,
  PageTopBar,
  SectionLabel,
  Select,
  Tag,
} from "~/lib/merism";
import { studiesLogic } from "~/features/studies/studiesLogic";
import type { Study } from "~/types";

import { homeLogic } from "./homeLogic";

type StudiesFilterTab = "all" | "active" | "drafts" | "archived";

export default function HomePage(): JSX.Element {
  const { t } = useTranslation();
  useMountedLogic(homeLogic);
  const { stats } = useValues(homeLogic);
  const {
    studies,
    studiesLoading,
    hasLoaded,
    draftStudies,
    liveStudies,
    archivedStudies,
    newStudyLoading,
    page,
    pageSize,
  } = useValues(studiesLogic);
  const { createStudy, setPage, setPageSize } = useActions(studiesLogic);

  const [filterTab, setFilterTab] = useState<StudiesFilterTab>("all");

  useEffect(() => {
    setPage(0);
  }, [filterTab, setPage]);

  const visibleStudies =
    filterTab === "active"
      ? liveStudies
      : filterTab === "drafts"
        ? draftStudies
        : filterTab === "archived"
          ? archivedStudies
          : studies;

  const start = page * pageSize;
  const pagedStudies = visibleStudies.slice(start, start + pageSize);
  const effectivePageCount = Math.max(
    1,
    Math.ceil(visibleStudies.length / pageSize),
  );

  const TABS = [
    { value: "all", label: t("studies.tabs.all") },
    { value: "active", label: t("studies.tabs.active") },
    { value: "drafts", label: t("studies.tabs.drafts") },
    { value: "archived", label: t("studies.tabs.archived") },
  ];

  return (
    <div className="flex flex-col gap-8">
      <PageTopBar
        title={t("home.title")}
        actions={
          <Button
            iconLeft={<Plus className="h-4 w-4" />}
            size="sm"
            onClick={createStudy}
            isLoading={newStudyLoading}
          >
            {t("studies.new_study")}
          </Button>
        }
        tabs={TABS}
        activeTab={filterTab}
        onTabChange={(v) => setFilterTab(v as StudiesFilterTab)}
      />

      {/* KPI row */}
      <KpiGrid columns={5}>
        <KpiCard
          label={t("home.kpi.sessions_week")}
          value={stats?.sessions_week ?? "—"}
          subtitle={t("home_kpi.sessions_subtitle")}
          icon={<Clock className="h-3 w-3" />}
          size="title"
        />
        <KpiCard
          label={t("home.kpi.active_studies")}
          value={stats?.studies_total ?? "—"}
          subtitle={
            stats
              ? `${stats.studies_active} ${t("studies.tabs.active").toLowerCase()}`
              : "total"
          }
          icon={<FlaskConical className="h-3 w-3" />}
          size="title"
        />
        <KpiCard
          label={t("home_kpi.talk_time")}
          value={stats ? `${stats.talk_time_hours.toFixed(1)}h` : "—"}
          subtitle={t("home_kpi.talk_time_subtitle")}
          size="title"
        />
        <KpiCard
          label={t("home.kpi.participants")}
          value={stats?.participants_total ?? "—"}
          subtitle={t("home_kpi.participants_subtitle")}
          icon={<Users className="h-3 w-3" />}
          size="title"
        />
        <KpiCard
          label={t("home.kpi.insights")}
          value={stats?.insights_total ?? "—"}
          subtitle={t("home_kpi.insights_subtitle")}
          icon={<Lightbulb className="h-3 w-3" />}
          size="title"
        />
      </KpiGrid>

      {/* Study list */}
      {(!hasLoaded || studiesLoading) && studies.length === 0 ? (
        <StudyListSkeleton />
      ) : studies.length === 0 ? (
        <FirstStudyHero onCreate={createStudy} isCreating={newStudyLoading} />
      ) : visibleStudies.length === 0 ? (
        <EmptyPlaceholder
          text={t("studies.empty_tab_body", {
            tab: t(`studies.tabs.${filterTab}`).toLowerCase(),
          })}
        />
      ) : (
        <>
          <StudyListSection items={pagedStudies} />
          {visibleStudies.length > pageSize && (
            <PaginationBar
              page={page}
              pageCount={effectivePageCount}
              pageSize={pageSize}
              total={visibleStudies.length}
              onPage={setPage}
              onPageSize={setPageSize}
            />
          )}
        </>
      )}
    </div>
  );
}

// ── Study list ────────────────────────────────────────

function StudyListSection({ items }: { items: Study[] }): JSX.Element {
  const { t } = useTranslation();
  return (
    <section>
      <SectionLabel className="pb-3">
        {items.length} · {t("studies.title").toLowerCase()}
      </SectionLabel>
      <ul className="divide-y divide-[color:var(--merism-hairline)] border-t border-[color:var(--merism-hairline)]">
        {items.map((study) => (
          <StudyRow key={study.id} study={study} />
        ))}
      </ul>
    </section>
  );
}

function StudyRow({ study }: { study: Study }): JSX.Element {
  const { t } = useTranslation();
  const { push } = useActions(router);
  return (
    <li>
      <button
        type="button"
        onClick={() => push(urls.study(study.id))}
        className="group flex w-full items-center gap-6 py-4 text-left transition-colors hover:bg-merism-bg-subtle/60"
      >
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-merism-body font-[500] text-merism-text group-hover:text-merism-accent">
              {study.name || t("common.draft")}
            </span>
            <StatusTag status={study.status} />
            <Tag variant="outline" case="normal">
              {t(`study.mode.${study.interview_mode}`, {
                defaultValue: study.interview_mode,
              })}
            </Tag>
          </div>
          <p className="line-clamp-1 text-merism-label text-merism-text-muted">
            {study.research_goal || ""}
          </p>
        </div>
        <time className="shrink-0 font-mono text-merism-caption text-merism-text-subtle">
          {formatDate(study.updated_at)}
        </time>
      </button>
    </li>
  );
}

function StatusTag({ status }: { status: Study["status"] }): JSX.Element {
  const { t } = useTranslation();
  const label = t(`studies.status.${status}`, { defaultValue: status });
  if (status === "live") {
    return <Tag variant="accent">{label}</Tag>;
  }
  if (status === "draft") {
    return <Tag variant="neutral">{label}</Tag>;
  }
  return <Tag variant="outline">{label}</Tag>;
}

// ── Pagination ────────────────────────────────────────

function PaginationBar({
  page,
  pageCount,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}): JSX.Element {
  const { t } = useTranslation();
  const start = page * pageSize + 1;
  const end = Math.min(total, (page + 1) * pageSize);
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-t border-[color:var(--merism-hairline)] pt-4">
      <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
        {t("pagination.range", { start, end, total })}
      </span>
      <div className="flex items-center gap-2">
        <Select
          aria-label="Page size"
          value={String(pageSize)}
          onValueChange={(v) => onPageSize(parseInt(v, 10))}
          size="sm"
          className="min-w-[9.5rem]"
          options={[10, 20, 50].map((count) => ({
            value: String(count),
            label: t("pagination.per_page", { n: count }),
          }))}
        />
        <button
          type="button"
          onClick={() => onPage(Math.max(0, page - 1))}
          disabled={page === 0}
          className="rounded-merism-md bg-merism-surface px-3 py-1 text-merism-label ring-1 ring-[color:var(--merism-hairline-strong)] transition-colors hover:bg-merism-bg-subtle disabled:opacity-40"
        >
          {t("pagination.prev")}
        </button>
        <span className="font-mono text-merism-caption tabular-nums text-merism-text-muted">
          {t("pagination.page_of", { page: page + 1, count: pageCount })}
        </span>
        <button
          type="button"
          onClick={() => onPage(Math.min(pageCount - 1, page + 1))}
          disabled={page >= pageCount - 1}
          className="rounded-merism-md bg-merism-surface px-3 py-1 text-merism-label ring-1 ring-[color:var(--merism-hairline-strong)] transition-colors hover:bg-merism-bg-subtle disabled:opacity-40"
        >
          {t("pagination.next")}
        </button>
      </div>
    </div>
  );
}

// ── Empty states ──────────────────────────────────────

function FirstStudyHero({
  onCreate,
  isCreating,
}: {
  onCreate: () => void;
  isCreating: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-16 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <Illustration
        name="planning-a-trip"
        size="xl"
        className="text-merism-text"
      />
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
          {t("home.first_study_hero.title")}
        </h2>
        <p className="max-w-sm text-merism-body text-merism-text-muted">
          {t("home.first_study_hero.body")}
        </p>
      </div>
      <Button
        iconLeft={<Plus className="h-4 w-4" />}
        onClick={onCreate}
        isLoading={isCreating}
        size="lg"
      >
        {t("home.first_study_hero.cta")}
      </Button>
    </div>
  );
}

function EmptyPlaceholder({ text }: { text: string }): JSX.Element {
  return (
    <div className="flex min-h-32 items-center justify-center text-merism-label text-merism-text-muted">
      {text}
    </div>
  );
}

function StudyListSkeleton(): JSX.Element {
  return (
    <section className="animate-pulse">
      <div className="mb-3 h-4 w-24 rounded bg-merism-bg-subtle" />
      <ul className="divide-y divide-[color:var(--merism-hairline)] border-t border-[color:var(--merism-hairline)]">
        {Array.from({ length: 5 }).map((_, i) => (
          <li key={i} className="flex items-center gap-6 py-4">
            <div className="flex flex-1 flex-col gap-2">
              <div className="h-4 w-48 rounded bg-merism-bg-subtle" />
              <div className="h-3 w-72 rounded bg-merism-bg-subtle" />
            </div>
            <div className="h-3 w-16 rounded bg-merism-bg-subtle" />
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
