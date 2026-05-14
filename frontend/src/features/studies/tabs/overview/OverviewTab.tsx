import { useValues } from "kea"
import { BarChart3, Calendar, Clock, MessageSquare, Users } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Card, Tag } from "~/lib/merism"
import { studyLogic } from "~/features/studies/studyLogic"

/**
 * OverviewTab — study history & status overview (Outset.ai "Overview" tab).
 *
 * This is NOT a configuration page. It shows:
 *   - Study status & key metadata
 *   - Progress metrics (sessions completed, participants recruited, etc.)
 *   - Timeline / activity log
 *
 * Available once a study is created; primarily useful once interviews
 * are running. For a brand-new draft study this will show a minimal
 * "Get started" state pointing the user to Guide tab.
 */
export default function OverviewTab(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    if (!study) {
        return <div className="text-merism-text-muted">{t("common.loading")}</div>
    }

    const isDraft = study.status === "draft" || study.status === "ready"

    if (isDraft) {
        return <DraftOverview />
    }

    return <ActiveOverview />
}

// ── Draft state: point user to Guide ───────────────────────

function DraftOverview(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    return (
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 py-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-merism-accent-soft">
                <MessageSquare className="h-7 w-7 text-merism-accent" />
            </div>
            <div className="flex flex-col gap-2">
                <h2 className="text-xl font-semibold text-merism-text">
                    {t("overview.draft_title")}
                </h2>
                <p className="max-w-md text-sm text-merism-text-muted">
                    {t("overview.draft_body")}
                </p>
            </div>
            <div className="mt-4 flex flex-col gap-3 rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-6 text-left">
                <h3 className="text-sm font-semibold text-merism-text">
                    {t("overview.study_info")}
                </h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                    <span className="text-merism-text-muted">{t("overview.goal")}:</span>
                    <span className="text-merism-text">{study?.research_goal || "—"}</span>
                    <span className="text-merism-text-muted">{t("overview.status")}:</span>
                    <Tag variant="neutral" size="sm">{t(`studies.status.${study?.status}`)}</Tag>
                    <span className="text-merism-text-muted">{t("overview.mode")}:</span>
                    <span className="text-merism-text capitalize">{study?.interview_mode || "—"}</span>
                    <span className="text-merism-text-muted">{t("overview.created")}:</span>
                    <span className="text-merism-text">{study?.created_at ? new Date(study.created_at).toLocaleDateString() : "—"}</span>
                </div>
            </div>
        </div>
    )
}

// ── Active/Live state: metrics & activity ──────────────────

function ActiveOverview(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    // TODO: load real metrics from /api/studies/:id/metrics/
    const metrics = {
        sessions_completed: 0,
        sessions_target: study?.target_completed_count || 30,
        participants_recruited: 0,
        avg_duration_min: study?.estimated_minutes || 0,
    }

    return (
        <div className="flex flex-col gap-8">
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <MetricCard
                    icon={<Users className="h-4 w-4" />}
                    label={t("overview.participants")}
                    value={`${metrics.participants_recruited}`}
                />
                <MetricCard
                    icon={<MessageSquare className="h-4 w-4" />}
                    label={t("overview.sessions_completed")}
                    value={`${metrics.sessions_completed} / ${metrics.sessions_target}`}
                />
                <MetricCard
                    icon={<Clock className="h-4 w-4" />}
                    label={t("overview.avg_duration")}
                    value={`${metrics.avg_duration_min} min`}
                />
                <MetricCard
                    icon={<BarChart3 className="h-4 w-4" />}
                    label={t("overview.completion_rate")}
                    value="—"
                />
            </div>

            {/* Study details */}
            <Card className="flex flex-col gap-4 p-6">
                <h3 className="text-sm font-semibold text-merism-text">{t("overview.study_info")}</h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
                    <span className="text-merism-text-muted">{t("overview.goal")}:</span>
                    <span className="text-merism-text">{study?.research_goal || "—"}</span>
                    <span className="text-merism-text-muted">{t("overview.status")}:</span>
                    <Tag variant="accent" size="sm">{t(`studies.status.${study?.status}`)}</Tag>
                    <span className="text-merism-text-muted">{t("overview.mode")}:</span>
                    <span className="text-merism-text capitalize">{study?.interview_mode || "—"}</span>
                    <span className="text-merism-text-muted">{t("overview.created")}:</span>
                    <span className="text-merism-text">{study?.created_at ? new Date(study.created_at).toLocaleDateString() : "—"}</span>
                </div>
            </Card>

            {/* Activity timeline placeholder */}
            <Card className="flex flex-col gap-3 p-6">
                <h3 className="text-sm font-semibold text-merism-text">{t("overview.activity")}</h3>
                <p className="text-sm text-merism-text-muted">{t("overview.activity_empty")}</p>
            </Card>
        </div>
    )
}

// ── Small metric card ──────────────────────────────────────

function MetricCard({
    icon,
    label,
    value,
}: {
    icon: React.ReactNode
    label: string
    value: string
}): JSX.Element {
    return (
        <Card className="flex flex-col gap-2 p-4">
            <div className="flex items-center gap-2 text-merism-text-muted">
                {icon}
                <span className="text-xs">{label}</span>
            </div>
            <span className="text-lg font-semibold text-merism-text">{value}</span>
        </Card>
    )
}
