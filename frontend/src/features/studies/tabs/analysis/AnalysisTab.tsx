import { useActions, useMountedLogic, useValues } from "kea"
import {
    BarChart3,
    ClipboardList,
    Lightbulb,
    MessageSquare,
    Sparkles,
    TrendingUp,
    Users,
} from "lucide-react"
import { useEffect, useState } from "react"

import {
    Button,
    ExecutiveSummary,
    Illustration,
    KpiCard,
    KpiGrid,
    PageTopBar,
    SectionLabel,
} from "~/lib/merism"
import { studyLogic } from "~/features/studies/studyLogic"

import { analysisLogic } from "./analysisLogic"
import { ConceptComparison } from "./ConceptComparison"
import { CoveragePanel } from "./CoveragePanel"
import { CrossSessionThemesPanel } from "./CrossSessionThemesPanel"
import { CustomReportSidebar } from "./CustomReportSidebar"
import { customReportLogic } from "./customReportLogic"
import { SentimentTrendChart } from "./SentimentTrendChart"
import { TaskList } from "./TaskList"
import { ThemeDistributionChart } from "./ThemeDistributionChart"

type AnalysisSubTab = "overview" | "themes" | "coverage" | "sentiment" | "tasks" | "concepts"

const TABS = [
    { value: "overview", label: "Overview" },
    { value: "themes", label: "Themes" },
    { value: "coverage", label: "Coverage" },
    { value: "sentiment", label: "Sentiment" },
    { value: "tasks", label: "Action items" },
    { value: "concepts", label: "Concepts" },
]

/**
 * AnalysisTab — research report surface.
 *
 * Sprint 4 rewrite. Reads the backend
 * ``/api/studies/:id/analysis/`` aggregate + ``/narrative/`` LLM
 * summary and composes them into an Outset-style dashboard:
 *
 *   PageTopBar (Overview / Themes / Sentiment / Tasks / Concepts)
 *     ↓
 *   ExecutiveSummary (LLM narrative · always on top of Overview)
 *     ↓
 *   KpiGrid — 4 headline numbers
 *     ↓
 *   Per-tab content panels.
 */
export default function AnalysisTab(): JSX.Element {
    useMountedLogic(analysisLogic)
    const { study } = useValues(studyLogic)
    const {
        aggregate,
        narrative,
        aggregateLoading,
        narrativeLoading,
        hasData,
    } = useValues(analysisLogic)
    const { refreshNarrative, loadAggregate } = useActions(analysisLogic)
    const { openFor } = useActions(customReportLogic)

    const [tab, setTab] = useState<AnalysisSubTab>("overview")

    useEffect(() => {
        if (study?.id) {
            loadAggregate()
        }
    }, [study?.id, loadAggregate])

    const handleAsk = (): void => {
        if (!study) return
        openFor(study.id)
    }

    const kpi = aggregate?.kpi

    return (
        <div className="flex flex-col gap-8">
            <PageTopBar
                title="Analysis"
                actions={
                    <div className="flex items-center gap-2">
                        <Button
                            variant="secondary"
                            size="sm"
                            iconLeft={<Sparkles className="h-4 w-4" />}
                            onClick={refreshNarrative}
                            isLoading={narrativeLoading}
                        >
                            Regenerate summary
                        </Button>
                        <Button
                            size="sm"
                            iconLeft={<MessageSquare className="h-4 w-4" />}
                            onClick={handleAsk}
                        >
                            Ask Merism
                        </Button>
                    </div>
                }
                tabs={TABS}
                activeTab={tab}
                onTabChange={(v) => setTab(v as AnalysisSubTab)}
            />

            {!hasData && !aggregateLoading && <EmptyAnalysis />}

            {hasData && tab === "overview" && (
                <div className="flex flex-col gap-10">
                    {narrative && (
                        <ExecutiveSummary
                            eyebrow={narrative.eyebrow}
                            summary={narrative.summary}
                            byline={narrative.byline}
                            isLoading={narrativeLoading}
                        />
                    )}

                    {kpi && (
                        <KpiGrid columns={4}>
                            <KpiCard
                                label="Sessions"
                                value={kpi.session_completed}
                                subtitle={`of ${kpi.session_count} recruited`}
                                icon={<Users className="h-3 w-3" />}
                                size="title"
                            />
                            <KpiCard
                                label="Quotes"
                                value={kpi.quote_count}
                                subtitle={`across ${kpi.theme_count} themes`}
                                icon={<MessageSquare className="h-3 w-3" />}
                                size="title"
                            />
                            <KpiCard
                                label="Insights"
                                value={kpi.insight_count}
                                subtitle="generated per session"
                                icon={<Lightbulb className="h-3 w-3" />}
                                size="title"
                            />
                            <KpiCard
                                label="Talk time"
                                value={`${kpi.talk_time_hours.toFixed(1)}h`}
                                subtitle="completed interviews"
                                icon={<TrendingUp className="h-3 w-3" />}
                                size="title"
                            />
                        </KpiGrid>
                    )}

                    <TopThemesPreview themes={aggregate?.top_themes ?? []} />
                    <ConceptComparison />
                </div>
            )}

            {hasData && tab === "themes" && (
                <section className="flex flex-col gap-8">
                    <div className="flex flex-col gap-4">
                        <SectionLabel>Theme distribution (by tag)</SectionLabel>
                        <ThemeDistributionChart themes={aggregate?.top_themes ?? []} />
                    </div>
                    {study?.id && <CrossSessionThemesPanel studyId={study.id} />}
                </section>
            )}

            {hasData && tab === "coverage" && study?.id && (
                <CoveragePanel studyId={study.id} />
            )}

            {hasData && tab === "sentiment" && (
                <section className="flex flex-col gap-4">
                    <SectionLabel>Sentiment over time</SectionLabel>
                    <SentimentTrendChart
                        points={aggregate?.sentiment_over_time ?? []}
                    />
                </section>
            )}

            {hasData && tab === "tasks" && (
                <section className="flex flex-col gap-4">
                    <SectionLabel>Action items</SectionLabel>
                    <TaskList tasks={aggregate?.top_tasks ?? []} />
                </section>
            )}

            {hasData && tab === "concepts" && <ConceptComparison />}

            <CustomReportSidebar />
        </div>
    )
}

// ── Overview preview of top 5 themes (compact) ─────────────

function TopThemesPreview({
    themes,
}: {
    themes: { code_id: string; name: string; count: number; description: string }[]
}): JSX.Element {
    const preview = themes.slice(0, 5)
    if (preview.length === 0) return <></>

    return (
        <section className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
                <SectionLabel>Top themes</SectionLabel>
                <BarChart3
                    className="h-3.5 w-3.5 text-merism-text-subtle"
                    strokeWidth={1.8}
                />
            </div>
            <ThemeDistributionChart themes={preview} />
        </section>
    )
}

// ── Empty state ──────────────────────────────────────────────

function EmptyAnalysis(): JSX.Element {
    return (
        <div className="mx-auto flex max-w-md flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-12 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <Illustration name="painting" size="xl" className="text-merism-text" />
            <div className="flex flex-col gap-2">
                <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
                    No analysis yet
                </h2>
                <p className="text-merism-body text-merism-text-muted">
                    Run a few interviews — quote extraction and coding happen
                    automatically after each session completes. Charts and
                    insights will appear here.
                </p>
            </div>
            <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                <ClipboardList className="mr-1 inline h-3 w-3" /> Analysis auto-updates
            </span>
        </div>
    )
}
