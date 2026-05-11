import { useActions, useMountedLogic, useValues } from "kea"
import { router } from "kea-router"
import { useTranslation } from "react-i18next"
import {
    Clock,
    FlaskConical,
    Lightbulb,
    Plus,
    Users,
} from "lucide-react"

import { urls } from "~/app/routes"
import {
    Button,
    Illustration,
    KpiCard,
    KpiGrid,
    PageTopBar,
    SectionLabel,
    StudyCard,
} from "~/lib/merism"
import { studiesLogic } from "~/features/studies/studiesLogic"
import type { Study } from "~/types"

import { homeLogic, type HomeStats, type HomeTab } from "./homeLogic"

/**
 * HomePage — the landing scene.
 *
 * Overview tab (primary):
 *   - Page top bar with Overview / Activity / Drafts sub-tabs
 *   - 5-column KPI row (sessions · studies · talk time · participants · insights)
 *   - Horizontal strip of StudyCard (active + recent)
 *   - "+ Start a new study" CTA card at the end of the strip
 *
 * Activity + Drafts tabs are stubs for now — labelled + switchable,
 * with content panels that say "coming soon".
 */
export default function HomePage(): JSX.Element {
    const { t } = useTranslation()
    useMountedLogic(homeLogic)
    const { stats, studies, studiesLoading, activeTab } = useValues(homeLogic)
    const { setActiveTab } = useActions(homeLogic)
    const { createStudy } = useActions(studiesLogic)
    const { newStudyLoading } = useValues(studiesLogic)
    const { push } = useActions(router)

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
                tabs={[
                    { value: "overview", label: t("home.tabs.overview") },
                    { value: "activity", label: t("home.tabs.inbox") },
                    { value: "drafts", label: t("home.tabs.drafts") },
                ]}
                activeTab={activeTab}
                onTabChange={(tab) => setActiveTab(tab as HomeTab)}
            />

            {activeTab === "overview" && (
                <OverviewTab
                    stats={stats}
                    studies={studies}
                    studiesLoading={studiesLoading}
                    onOpenStudy={(id) => push(urls.study(id))}
                    onCreateStudy={createStudy}
                    isCreating={newStudyLoading}
                />
            )}

            {activeTab === "activity" && <ComingSoon label={t("common.coming_soon")} />}
            {activeTab === "drafts" && <ComingSoon label={t("common.coming_soon")} />}
        </div>
    )
}

interface OverviewProps {
    stats: HomeStats | null
    studies: Study[]
    studiesLoading: boolean
    onOpenStudy: (id: string) => void
    onCreateStudy: () => void
    isCreating: boolean
}

function OverviewTab({
    stats,
    studies,
    studiesLoading,
    onOpenStudy,
    onCreateStudy,
    isCreating,
}: OverviewProps): JSX.Element {
    const { t } = useTranslation()
    return (
        <div className="flex flex-col gap-[var(--spacing-merism-section-y)]">
            {/* ── THIS WEEK ────────────────────────────────────── */}
            <section className="flex flex-col gap-6">
                <SectionLabel>This week</SectionLabel>
                <KpiGrid columns={5}>
                    <KpiCard
                        label={t("home.kpi.sessions_week")}
                        value={stats?.sessions_week ?? "—"}
                        subtitle="completed in the last 7 days"
                        icon={<Clock className="h-3 w-3" />}
                        size="title"
                    />
                    <KpiCard
                        label={t("home.kpi.active_studies")}
                        value={stats?.studies_total ?? "—"}
                        subtitle={
                            stats
                                ? `${stats.studies_active} active`
                                : "total"
                        }
                        icon={<FlaskConical className="h-3 w-3" />}
                        size="title"
                    />
                    <KpiCard
                        label="TALK TIME"
                        value={
                            stats
                                ? `${stats.talk_time_hours.toFixed(1)}h`
                                : "—"
                        }
                        subtitle="cumulative interviewing"
                        size="title"
                    />
                    <KpiCard
                        label={t("home.kpi.participants")}
                        value={stats?.participants_total ?? "—"}
                        subtitle="across all studies"
                        icon={<Users className="h-3 w-3" />}
                        size="title"
                    />
                    <KpiCard
                        label={t("home.kpi.insights")}
                        value={stats?.insights_total ?? "—"}
                        subtitle="captured so far"
                        icon={<Lightbulb className="h-3 w-3" />}
                        size="title"
                    />
                </KpiGrid>
            </section>

            {/* ── YOUR STUDIES (horizontal strip) ────────────────── */}
            <section className="flex flex-col gap-6">
                <div className="flex items-baseline justify-between">
                    <SectionLabel>{t("home.section.active_studies")}</SectionLabel>
                    {studies.length > 0 && (
                        <button
                            type="button"
                            onClick={() => window.location.assign(urls.studies())}
                            className="text-merism-body-sm text-merism-text-muted transition-colors hover:text-merism-accent"
                        >
                            {t("home.section.see_all")} →
                        </button>
                    )}
                </div>

                {studiesLoading && studies.length === 0 ? (
                    <EmptyHorizontalStrip text={t("common.loading")} />
                ) : studies.length === 0 ? (
                    <FirstStudyHero
                        onCreate={onCreateStudy}
                        isCreating={isCreating}
                    />
                ) : (
                    <div className="flex gap-4 overflow-x-auto pb-2">
                        {studies.map((study) => (
                            <div key={study.id} className="w-72 shrink-0">
                                <StudyCard
                                    id={study.id}
                                    name={study.name || t("common.draft")}
                                    researchGoal={study.research_goal}
                                    status={
                                        study.status as
                                            | "draft"
                                            | "ready"
                                            | "recruiting"
                                            | "active"
                                            | "closed"
                                            | "archived"
                                    }
                                    onOpen={onOpenStudy}
                                />
                            </div>
                        ))}
                        {/* Tail card: + Start a new study */}
                        <NewStudyCard
                            onClick={onCreateStudy}
                            isLoading={isCreating}
                        />
                    </div>
                )}
            </section>
        </div>
    )
}

/**
 * First-study hero — large CTA when the team has no studies yet.
 */
function FirstStudyHero({
    onCreate,
    isCreating,
}: {
    onCreate: () => void
    isCreating: boolean
}): JSX.Element {
    const { t } = useTranslation()
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
    )
}

/**
 * Trailing "+ Start a new study" card — sits at the end of the
 * horizontal study strip.
 */
function NewStudyCard({
    onClick,
    isLoading,
}: {
    onClick: () => void
    isLoading: boolean
}): JSX.Element {
    const { t } = useTranslation()
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={isLoading}
            className={
                "group flex w-72 shrink-0 flex-col items-center justify-center gap-3 " +
                "rounded-merism-lg p-8 text-center " +
                "ring-1 ring-[color:var(--merism-hairline)] " +
                "transition-shadow duration-[var(--merism-duration-base)] ease-[var(--merism-ease)] " +
                "hover:shadow-merism-card " +
                "disabled:opacity-60"
            }
        >
            <span
                aria-hidden="true"
                className="flex h-10 w-10 items-center justify-center rounded-merism-full bg-merism-bg-subtle text-merism-text-muted transition-colors group-hover:bg-merism-accent-soft group-hover:text-merism-accent"
            >
                <Plus className="h-5 w-5" strokeWidth={1.8} />
            </span>
            <span className="text-merism-body font-medium text-merism-text">
                {t("home.new_study_card.title")}
            </span>
            <span className="text-merism-caption text-merism-text-muted">
                {t("home.new_study_card.body")}
            </span>
        </button>
    )
}

function ComingSoon({ label }: { label: string }): JSX.Element {
    return (
        <div className="flex min-h-64 items-center justify-center rounded-merism-lg bg-merism-surface p-16 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <p className="text-merism-body-sm text-merism-text-muted">
                {label}
            </p>
        </div>
    )
}

function EmptyHorizontalStrip({ text }: { text: string }): JSX.Element {
    return (
        <div className="flex h-44 items-center justify-center text-merism-label text-merism-text-muted">
            {text}
        </div>
    )
}
