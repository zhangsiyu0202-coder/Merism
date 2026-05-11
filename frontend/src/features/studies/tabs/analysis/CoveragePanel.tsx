import { useEffect, useState } from "react"

import { api } from "~/lib/api"
import { SectionLabel, Tag } from "~/lib/merism"

import type { components } from "~/generated/api"

type CoverageSnapshot = components["schemas"]["CoverageSnapshot"]
type StudyGoal = components["schemas"]["StudyGoal"]

interface Props {
    studyId: string
}

/**
 * CoveragePanel — research-goal coverage heatmap + gap recommendations.
 *
 * Reads the latest CoverageSnapshot for the study + the list of StudyGoals.
 * Renders:
 *   - Overall coverage header (% weighted by P0/P1/P2)
 *   - Per-goal bars with priority tags + coverage ratio
 *   - Recommendations callout (under-covered P0/P1 goals)
 */
export function CoveragePanel({ studyId }: Props): JSX.Element {
    const [snapshot, setSnapshot] = useState<CoverageSnapshot | null>(null)
    const [goals, setGoals] = useState<StudyGoal[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const load = async (): Promise<void> => {
            setLoading(true)
            try {
                const [snapResp, goalResp] = await Promise.all([
                    api.get<{ results: CoverageSnapshot[] }>(
                        "/api/coverage-snapshots/",
                        { study: studyId },
                    ),
                    api.get<{ results: StudyGoal[] }>(
                        "/api/study-goals/",
                        { study: studyId },
                    ),
                ])
                const snaps =
                    snapResp.results ?? (snapResp as unknown as CoverageSnapshot[])
                setSnapshot(snaps[0] ?? null)
                setGoals(goalResp.results ?? (goalResp as unknown as StudyGoal[]))
            } finally {
                setLoading(false)
            }
        }
        void load()
    }, [studyId])

    if (loading) {
        return <p className="text-merism-text-muted text-merism-body-sm">Loading coverage…</p>
    }

    if (!snapshot || goals.length === 0) {
        return (
            <div className="rounded-merism-lg border border-merism-border bg-merism-surface p-6">
                <p className="text-merism-body text-merism-text-muted">
                    No coverage data yet. Add research goals in the Brief tab and
                    wait for 5+ sessions to complete for meaningful coverage
                    measurements.
                </p>
            </div>
        )
    }

    const coverageByGoal = (snapshot.goal_coverage ?? {}) as Record<string, number>

    return (
        <div className="flex flex-col gap-6">
            <div className="rounded-merism-lg border border-merism-border bg-merism-surface p-6">
                <SectionLabel>Overall coverage</SectionLabel>
                <div className="flex items-baseline gap-3 mt-2">
                    <span className="font-display text-4xl font-medium text-merism-text tabular-nums">
                        {Math.round((snapshot.overall_coverage ?? 0) * 100)}%
                    </span>
                    <span className="text-merism-text-muted text-merism-body-sm">
                        weighted by P0/P1/P2 priorities · {snapshot.session_count ?? 0} sessions analyzed
                    </span>
                </div>
            </div>

            <section className="flex flex-col gap-3">
                <SectionLabel>Per-goal coverage</SectionLabel>
                {goals.map((g) => {
                    const cov = coverageByGoal[g.id] ?? 0
                    const pct = Math.round(cov * 100)
                    return (
                        <div
                            key={g.id}
                            className="rounded-merism-md border border-merism-border px-4 py-3"
                        >
                            <div className="flex items-center justify-between gap-3 mb-2">
                                <div className="flex items-center gap-2 flex-1">
                                    <Tag>{g.priority}</Tag>
                                    <span className="text-merism-text">{g.text}</span>
                                </div>
                                <span className="font-mono tabular-nums text-merism-text">
                                    {pct}%
                                </span>
                            </div>
                            <div className="h-2 bg-merism-bg-subtle rounded-full overflow-hidden">
                                <div
                                    className={
                                        "h-full transition-all " +
                                        (pct >= 70
                                            ? "bg-[color:var(--merism-status-success)]"
                                            : pct >= 30
                                              ? "bg-merism-accent"
                                              : "bg-merism-danger")
                                    }
                                    style={{ width: `${Math.max(2, pct)}%` }}
                                />
                            </div>
                        </div>
                    )
                })}
            </section>

            {((snapshot.recommendations as string[] | null)?.length ?? 0) > 0 && (
                <section className="rounded-merism-md border border-merism-border bg-merism-bg-subtle p-4">
                    <SectionLabel>Recommendations</SectionLabel>
                    <ul className="list-disc pl-5 space-y-1 mt-2 text-merism-body-sm text-merism-text">
                        {(snapshot.recommendations as string[] | null)?.map(
                            (r, i) => <li key={i}>{r}</li>,
                        )}
                    </ul>
                </section>
            )}
        </div>
    )
}
