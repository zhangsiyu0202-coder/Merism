import { useActions, useMountedLogic, useValues } from "kea";
import { router } from "kea-router";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { urls } from "~/app/routes";
import {
  Button,
  Illustration,
  PageTopBar,
  Select,
  SectionLabel,
  Tag,
} from "~/lib/merism";
import type { Study } from "~/types";

import { studiesLogic } from "./studiesLogic";

type StudiesFilterTab = "all" | "active" | "drafts" | "archived";

/**
 * StudiesPage — workspace > Studies list.
 *
 * Shares the ``PageTopBar`` masthead with every other top-level scene,
 * and adds four sub-tabs as local sub-navigation:
 *   - All (default) — everything
 *   - Active       — recruiting / live / ready
 *   - Drafts       — draft status
 *   - Archived     — closed / archived
 */
export default function StudiesPage(): JSX.Element {
  const { t } = useTranslation();
  useMountedLogic(studiesLogic);
  const {
    studies,
    studiesLoading,
    draftStudies,
    liveStudies,
    archivedStudies,
    newStudyLoading,
    page,
    pageSize,
  } = useValues(studiesLogic);
  const { loadStudies, createStudy, setPage, setPageSize } =
    useActions(studiesLogic);

  const [activeTab, setActiveTab] = useState<StudiesFilterTab>("all");

  useEffect(() => {
    loadStudies();
  }, [loadStudies]);

  // Reset to page 0 when tab changes.
  useEffect(() => {
    setPage(0);
  }, [activeTab, setPage]);

  const visibleStudies =
    activeTab === "active"
      ? liveStudies
      : activeTab === "drafts"
        ? draftStudies
        : activeTab === "archived"
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
        title={t("studies.title")}
        lede={t("studies.lede")}
        actions={
          <Button
            iconLeft={<Plus className="h-4 w-4" />}
            onClick={createStudy}
            isLoading={newStudyLoading}
            size="sm"
          >
            {t("studies.new_study")}
          </Button>
        }
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={(v) => setActiveTab(v as StudiesFilterTab)}
      />

      {studiesLoading && studies.length === 0 ? (
        <EmptyPlaceholder text={t("common.loading")} />
      ) : studies.length === 0 ? (
        <FirstStudyHero onCreate={createStudy} isCreating={newStudyLoading} />
      ) : visibleStudies.length === 0 ? (
        <EmptyPlaceholder
          text={t("studies.empty_tab_body", {
            tab: t(`studies.tabs.${activeTab}`).toLowerCase(),
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

// ── Pagination control ────────────────────────────────

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
  const { t: tPag } = useTranslation();
  const start = page * pageSize + 1;
  const end = Math.min(total, (page + 1) * pageSize);
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-t border-[color:var(--merism-hairline)] pt-4">
      <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
        {tPag("pagination.range", { start, end, total })}
      </span>
      <div className="flex items-center gap-2">
        <Select
          aria-label="Page size"
          value={String(pageSize)}
          onValueChange={(nextValue) => onPageSize(parseInt(nextValue, 10))}
          size="sm"
          className="min-w-[9.5rem]"
          options={[10, 20, 50].map((count) => ({
            value: String(count),
            label: tPag("pagination.per_page", { n: count }),
          }))}
        />
        <button
          type="button"
          onClick={() => onPage(Math.max(0, page - 1))}
          disabled={page === 0}
          className="rounded-merism-md bg-merism-surface px-3 py-1 text-merism-label ring-1 ring-[color:var(--merism-hairline-strong)] transition-colors hover:bg-merism-bg-subtle disabled:opacity-40"
        >
          {tPag("pagination.prev")}
        </button>
        <span className="font-mono text-merism-caption tabular-nums text-merism-text-muted">
          {tPag("pagination.page_of", { page: page + 1, count: pageCount })}
        </span>
        <button
          type="button"
          onClick={() => onPage(Math.min(pageCount - 1, page + 1))}
          disabled={page >= pageCount - 1}
          className="rounded-merism-md bg-merism-surface px-3 py-1 text-merism-label ring-1 ring-[color:var(--merism-hairline-strong)] transition-colors hover:bg-merism-bg-subtle disabled:opacity-40"
        >
          {tPag("pagination.next")}
        </button>
      </div>
    </div>
  );
}

/**
 * First-study hero — rendered when the team has no studies at all
 * (not just an empty filter tab).
 *
 * Uses the ``jumping`` illustration (vs Home's ``planning-a-trip``)
 * so the two surfaces have distinct visual identities despite
 * sharing the same CTA — Home is about overview / planning, while
 * the Studies list is about *launching* the first one.
 */
function FirstStudyHero({
  onCreate,
  isCreating,
}: {
  onCreate: () => void;
  isCreating: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-12 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <Illustration name="jumping" size="xl" className="text-merism-text" />
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
          {t("studies.empty_hero_title")}
        </h2>
        <p className="text-merism-body text-merism-text-muted">
          {t("studies.empty_hero_body")}
        </p>
      </div>
      <Button
        iconLeft={<Plus className="h-4 w-4" />}
        onClick={onCreate}
        isLoading={isCreating}
        size="lg"
      >
        {t("studies.new_study")}
      </Button>
    </div>
  );
}

function StudyListSection({ items }: { items: Study[] }): JSX.Element {
  const { t: tSL } = useTranslation();
  return (
    <section>
      <SectionLabel className="pb-3">
        {items.length} · {tSL("studies.title").toLowerCase()}
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
  const { t: tSR } = useTranslation();
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
              {study.name || tSR("common.draft")}
            </span>
            <StatusTag status={study.status} />
            <Tag variant="outline" case="normal">
              {tSR(`study.mode.${study.interview_mode}`, {
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
  if (status === "recruiting" || status === "active") {
    return <Tag variant="accent">{label}</Tag>;
  }
  if (status === "draft" || status === "ready") {
    return <Tag variant="neutral">{label}</Tag>;
  }
  return <Tag variant="outline">{label}</Tag>;
}

function EmptyPlaceholder({ text }: { text: string }): JSX.Element {
  return (
    <div className="flex min-h-32 items-center justify-center text-merism-label text-merism-text-muted">
      {text}
    </div>
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
