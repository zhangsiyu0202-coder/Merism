import { useValues } from "kea"
import { Crown, TrendingUp } from "lucide-react"
import { motion } from "motion/react"

import { SectionLabel, Tag } from "~/lib/merism"

import {
    conceptReportLogic,
    type ConceptReport,
    type ConceptReportRow,
} from "./conceptReportLogic"

/**
 * ConceptComparison — §3.6 extension: side-by-side comparative breakdown.
 *
 * For each ConceptBlock, render one card with N concept columns. MVP
 * metric is ``sessions_seen``; Winner is determined server-side (see
 * :meth:`ConceptBlockViewSet.report`). Dimensions arrive later when
 * the NLP aggregation lands; the UI already handles empty arrays.
 *
 * Design-system motion: 200ms fade-up on mount, coral accent for
 * winner column.
 */
export function ConceptComparison(): JSX.Element | null {
    const { reports, reportsLoading, hasReports } = useValues(conceptReportLogic)

    if (reportsLoading && !hasReports) {
        return (
            <div className="rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-6 text-center text-sm text-merism-text-muted">
                Loading concept comparisons…
            </div>
        )
    }
    if (!hasReports) return null

    return (
        <section className="flex flex-col gap-4">
            <SectionLabel>Concept comparison</SectionLabel>
            <div className="flex flex-col gap-6">
                {reports.map((report) => (
                    <ReportCard key={report.block_id} report={report} />
                ))}
            </div>
        </section>
    )
}

function ReportCard({ report }: { report: ConceptReport }) {
    return (
        <motion.article
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
            className="flex flex-col gap-4 rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6"
        >
            <header className="flex flex-wrap items-center gap-3">
                <h3 className="font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
                    {report.block_title}
                </h3>
                <Tag variant="outline">{report.concepts.length} concepts</Tag>
                <Tag variant="outline">
                    {report.total_sessions}{" "}
                    {report.total_sessions === 1 ? "session" : "sessions"}
                </Tag>
                <span className="ml-auto font-mono text-xs uppercase tracking-merism-caps-tight text-merism-text-subtle">
                    rotation · {report.rotation.replace(/_/g, " ")}
                </span>
            </header>

            {report.total_sessions === 0 ? (
                <div className="rounded-merism-md border border-dashed border-merism-border bg-merism-bg-subtle px-4 py-6 text-center text-sm text-merism-text-muted">
                    Awaiting first completed sessions. Per-concept metrics appear here as
                    participants go through the rotation.
                </div>
            ) : (
                <div
                    className="grid gap-3"
                    style={{
                        gridTemplateColumns: `repeat(${report.concepts.length}, minmax(0, 1fr))`,
                    }}
                >
                    {report.concepts.map((c) => (
                        <ConceptColumn
                            key={c.concept_id}
                            concept={c}
                            isWinner={c.concept_id === report.winner_concept_id}
                            totalSessions={report.total_sessions}
                        />
                    ))}
                </div>
            )}
        </motion.article>
    )
}

interface ConceptColumnProps {
    concept: ConceptReportRow
    isWinner: boolean
    totalSessions: number
}

function ConceptColumn({ concept, isWinner, totalSessions }: ConceptColumnProps) {
    const pct =
        totalSessions > 0
            ? Math.round((concept.sessions_seen / totalSessions) * 100)
            : 0

    return (
        <div
            className={
                "flex flex-col gap-3 rounded-merism-md border p-4 transition-colors " +
                "duration-[var(--merism-duration-base)] ease-[var(--merism-ease)] " +
                (isWinner
                    ? "border-merism-accent bg-merism-accent/5 ring-1 ring-merism-accent/30"
                    : "border-merism-border bg-merism-bg-subtle")
            }
        >
            <header className="flex items-center justify-between gap-2">
                <span className="font-medium text-merism-text">{concept.label}</span>
                {isWinner && (
                    <motion.span
                        initial={{ scale: 0.85, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
                        className="inline-flex items-center gap-1 rounded-merism-full bg-merism-accent px-2 py-1 font-mono text-merism-caption uppercase tracking-merism-caps text-white"
                    >
                        <Crown className="h-3 w-3" />
                        Winner
                    </motion.span>
                )}
            </header>

            <Metric
                label="Sessions seen"
                value={`${concept.sessions_seen}`}
                detail={`${pct}%`}
            />

            {concept.dimensions.length > 0 ? (
                <ul className="flex flex-col gap-2">
                    {concept.dimensions.map((d) => (
                        <li key={d.name} className="flex items-center justify-between text-xs">
                            <span className="text-merism-text-muted">{d.name}</span>
                            <span className="font-mono tabular-nums text-merism-text">
                                {d.value.toFixed(1)}
                            </span>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    <TrendingUp className="mr-1 inline h-3 w-3" /> dimensions pending
                </p>
            )}
        </div>
    )
}

function Metric({
    label,
    value,
    detail,
}: {
    label: string
    value: string
    detail?: string
}): JSX.Element {
    return (
        <div className="flex flex-col gap-1">
            <span className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                {label}
            </span>
            <div className="flex items-baseline gap-2">
                <span className="font-display text-xl font-medium tabular-nums text-merism-text">
                    {value}
                </span>
                {detail && (
                    <span className="font-mono text-xs text-merism-text-muted">{detail}</span>
                )}
            </div>
        </div>
    )
}
