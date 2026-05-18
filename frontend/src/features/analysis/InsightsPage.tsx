import { ChevronDown, ChevronRight, Clock, Lightbulb, RefreshCw, Sparkles, Users } from "lucide-react"
import { useValues, useActions, useMountedLogic } from "kea"
import { useTranslation } from "react-i18next"

import { Button, Card, Select } from "~/lib/merism"
import { ExecutiveSummary } from "~/lib/merism/patterns/ExecutiveSummary"
import { KpiCard } from "~/lib/merism/patterns/KpiCard"
import { studiesLogic } from "~/features/studies/studiesLogic"

import { AnalysisChart } from "./AnalysisChart"
import type { ChartSpec } from "./AnalysisChart"
import { insightsLogic } from "./insightsLogic"
import type { InsightFinding, InsightHighlight } from "./insightsLogic"
import { EmptyState, GeneratingState, LoadingState } from "./StateComponents"

const ICON_MAP: Record<string, typeof Lightbulb> = { lightbulb: Lightbulb, users: Users, clock: Clock }

export function InsightsPage(): JSX.Element {
    const { t } = useTranslation()
    useMountedLogic(studiesLogic)
    const { studies } = useValues(studiesLogic)
    const { insights, highlights, findings, expandedFindings, isLoading, isGenerating, isEmpty, studyId } = useValues(insightsLogic)
    const { rerunInsights, toggleFinding, setStudyId } = useActions(insightsLogic)

    const studyOptions = (studies ?? []).map((s: { id: string; name: string }) => ({ value: s.id, label: s.name || t("untitled") }))

    return (
        <div className="flex flex-col gap-6 p-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <h1 className="text-merism-h2 font-display font-[450] text-merism-text">{t("insights.title")}</h1>
                    <Select options={studyOptions} value={studyId || ""} onValueChange={(val) => setStudyId(val)} placeholder={t("select_study_placeholder")} />
                </div>
                {insights?.status === "ready" && (
                    <Button variant="secondary" size="sm" onClick={rerunInsights}><RefreshCw className="mr-2 h-3.5 w-3.5" />{t("insights.rerun")}</Button>
                )}
            </div>

            {!studyId && <EmptyState icon={<Sparkles className="h-6 w-6" />} title={t("insights.select_study")} description={t("insights.select_study_desc")} />}
            {studyId && isLoading && <LoadingState message={t("insights.loading")} />}
            {studyId && isGenerating && <GeneratingState />}
            {studyId && !isLoading && !isGenerating && isEmpty && (
                <EmptyState icon={<Lightbulb className="h-6 w-6" />} title={t("insights.no_insights")} description={t("insights.no_insights_desc")} action={{ label: t("insights.generate"), onClick: rerunInsights }} />
            )}

            {studyId && insights?.status === "ready" && (
                <>
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        <KpiCard label={t("insights.kpi_interviews")} value={String(insights.completed_interviews)} size="title" variant="card" />
                        <KpiCard label={t("insights.kpi_avg_session")} value={`${insights.avg_session_minutes}m`} size="title" variant="card" />
                        <KpiCard label={t("insights.kpi_topics")} value={String(insights.interview_topics?.length ?? 0)} size="title" variant="card" />
                        <KpiCard label={t("insights.kpi_last_updated")} value={insights.generated_at ? new Date(insights.generated_at).toLocaleDateString() : "\u2014"} size="title" variant="card" />
                    </div>
                    {insights.executive_summary && <ExecutiveSummary eyebrow={t("insights.executive_summary")} summary={insights.executive_summary} byline={t("insights.based_on", { count: insights.completed_interviews })} />}
                    {highlights.length > 0 && (
                        <section>
                            <h2 className="mb-4 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">{t("insights.highlights")}</h2>
                            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                                {highlights.map((h: InsightHighlight) => <HighlightCard key={h.id} highlight={h} />)}
                            </div>
                        </section>
                    )}
                    {findings.length > 0 && (
                        <section>
                            <h2 className="mb-4 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">{t("insights.findings")}</h2>
                            <div className="flex flex-col gap-2">
                                {findings.map((f: InsightFinding) => <FindingRow key={f.id} finding={f} expanded={!!expandedFindings[f.id]} onToggle={() => toggleFinding(f.id)} />)}
                            </div>
                        </section>
                    )}
                </>
            )}
        </div>
    )
}

function HighlightCard({ highlight }: { highlight: InsightHighlight }): JSX.Element {
    const Icon = ICON_MAP[highlight.icon] ?? Lightbulb
    return (
        <Card className="flex flex-col gap-3 p-5">
            <div className="flex items-center gap-2"><Icon className="h-4 w-4 text-merism-accent" /><h3 className="text-merism-body-sm font-medium text-merism-text">{highlight.headline}</h3></div>
            <p className="text-merism-body-sm leading-relaxed text-merism-text-muted">{highlight.summary}</p>
        </Card>
    )
}

function FindingRow({ finding, expanded, onToggle }: { finding: InsightFinding; expanded: boolean; onToggle: () => void }): JSX.Element {
    const Chevron = expanded ? ChevronDown : ChevronRight
    return (
        <div className="rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface">
            <button onClick={onToggle} aria-expanded={expanded} className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-merism-bg-subtle">
                <Chevron className="h-4 w-4 shrink-0 text-merism-text-muted" />
                <div className="min-w-0 flex-1">
                    <h3 className="text-merism-body-sm font-medium text-merism-text truncate">{finding.title}</h3>
                    <p className="text-merism-caption text-merism-text-muted truncate">{finding.summary}</p>
                </div>
            </button>
            {expanded && <FindingDetail finding={finding} />}
        </div>
    )
}

function FindingDetail({ finding }: { finding: InsightFinding }): JSX.Element {
    const { t } = useTranslation()
    const chartSpec = toChartSpec(finding.chart_spec)
    return (
        <div className="border-t border-[color:var(--merism-hairline)] px-5 py-5 flex flex-col gap-6">
            {chartSpec && (
                <div>
                    <AnalysisChart spec={chartSpec} />
                    {finding.chart_interpretation && <p className="mt-2 text-merism-body-sm text-merism-text-muted">{finding.chart_interpretation}</p>}
                </div>
            )}
            {finding.themes.length > 0 && (
                <div>
                    <h4 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">{t("insights.themes")}</h4>
                    <div className="flex flex-wrap gap-2">
                        {finding.themes.map((th, i) => (
                            <span key={i} className="inline-flex items-center gap-1.5 rounded-full bg-merism-bg-subtle px-3 py-1 text-merism-caption text-merism-text">
                                <span className="font-medium">{th.name}</span>
                                <span className="text-merism-text-muted">({th.count})</span>
                            </span>
                        ))}
                    </div>
                </div>
            )}
            {finding.insight_nuggets.length > 0 && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {finding.insight_nuggets.map((n, i) => (
                        <div key={i} className="rounded-merism-md bg-merism-bg-subtle p-3">
                            <div className="text-merism-title font-display font-[450] text-merism-text">
                                {n.value}{n.unit && <span className="ml-1 text-merism-caption text-merism-text-muted">{n.unit}</span>}
                            </div>
                            <div className="text-merism-caption text-merism-text-muted">{n.label}</div>
                        </div>
                    ))}
                </div>
            )}
            {finding.supporting_evidence.length > 0 && (
                <div>
                    <h4 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">{t("insights.supporting_evidence")}</h4>
                    <div className="flex flex-col gap-2">
                        {finding.supporting_evidence.map((e, i) => (
                            <blockquote key={i} className="border-l-2 border-merism-accent/40 pl-3 text-merism-body-sm italic text-merism-text-muted">
                                &ldquo;{e.quote}&rdquo;
                                <cite className="mt-1 block text-merism-caption not-italic text-merism-text-subtle">&mdash; {e.source}</cite>
                            </blockquote>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

function toChartSpec(spec: Record<string, unknown>): ChartSpec | null {
    if (!isChartType(spec.type) || typeof spec.title !== "string") {
        return null
    }
    return spec as unknown as ChartSpec
}

function isChartType(value: unknown): value is ChartSpec["type"] {
    return value === "bar" || value === "pie" || value === "line"
}

export default InsightsPage
