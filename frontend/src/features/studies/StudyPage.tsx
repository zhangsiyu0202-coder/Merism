import { useActions, useMountedLogic, useValues } from "kea"
import { router } from "kea-router"
import { MoreVertical, Play } from "lucide-react"
import { lazy, Suspense, type ComponentType } from "react"
import { useTranslation } from "react-i18next"

import { urls, type StudyTab } from "~/app/routes"
import { Button, Tag, type TabRailItem } from "~/lib/merism"

import { studyLogic } from "./studyLogic"

/**
 * StudyPage — the tabbed shell for a single study.
 *
 * Topbar matches the Outset.ai reference:
 *   Row 1: Study name  ⋮  [STATUS pill]
 *   Row 2: Overview | Guide | Screener | Recruit | Results
 *   Right side: [Add section randomization] [Test Interview ▾]
 *
 * URL: ``/studies/:id/:tab``. Tabs are lazy-loaded.
 */

const tabComponents: Record<StudyTab, () => Promise<{ default: ComponentType }>> = {
    overview: () => import("./tabs/overview/OverviewTab"),
    guide: () => import("./tabs/guide/GuideTab"),
    screener: () => import("./tabs/screener/ScreenerTab"),
    recruit: () => import("./tabs/recruit/RecruitTab"),
    results: () => import("./tabs/results/ResultsTab"),
}

const tabCache = new Map<StudyTab, ComponentType>()
function tabFor(tab: StudyTab): ComponentType {
    const cached = tabCache.get(tab)
    if (cached) return cached
    const component = lazy(tabComponents[tab] ?? tabComponents.guide)
    tabCache.set(tab, component)
    return component
}

export default function StudyPage(): JSX.Element {
    const { t } = useTranslation()
    useMountedLogic(studyLogic)
    const { study, studyLoading, studyId, activeTab } = useValues(studyLogic)
    const { push } = useActions(router)

    if (!studyId) {
        return <div className="text-merism-text-muted">—</div>
    }

    const TabComponent = tabFor((activeTab as StudyTab) || "guide")

    const TABS: TabRailItem[] = [
        { value: "overview", label: t("study.tabs.overview") },
        { value: "guide", label: t("study.tabs.guide") },
        { value: "screener", label: t("study.tabs.screener") },
        { value: "recruit", label: t("study.tabs.recruit") },
        { value: "results", label: t("study.tabs.results") },
    ]

    return (
        <div className="flex flex-col">
            {/* ── Topbar: title + status + actions + tabs ────── */}
            <header className="border-b border-[color:var(--merism-hairline)]">
                {/* Title row */}
                <div className="flex items-center justify-between px-0 pb-4">
                    <div className="flex items-center gap-3">
                        <h1 className="text-xl font-semibold text-merism-text">
                            {study?.name ?? (studyLoading ? t("common.loading") : "—")}
                        </h1>
                        <button
                            type="button"
                            className="flex h-7 w-7 items-center justify-center rounded-md text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text"
                            aria-label={t("study.actions.menu")}
                        >
                            <MoreVertical className="h-4 w-4" />
                        </button>
                        {study && (
                            <Tag
                                variant={study.status === "draft" ? "neutral" : "accent"}
                                size="sm"
                                case="capitalize"
                            >
                                {t(`studies.status.${study.status}`, { defaultValue: study.status })}
                            </Tag>
                        )}
                    </div>

                    {/* Right-side actions */}
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {/* TODO: section randomization */}}
                        >
                            {t("study.actions.add_section_randomization")}
                        </Button>
                        <Button
                            size="sm"
                            variant="primary"
                            iconLeft={<Play className="h-3.5 w-3.5" />}
                            onClick={() => {/* TODO: test interview */}}
                        >
                            {t("study.actions.test_interview")}
                        </Button>
                    </div>
                </div>

                {/* Tab rail */}
                <nav className="flex gap-0">
                    {TABS.map((tab) => {
                        const isActive = activeTab === tab.value
                        return (
                            <button
                                key={tab.value}
                                type="button"
                                onClick={() => push(urls.study(studyId, tab.value as StudyTab))}
                                className={
                                    "relative px-4 pb-3 pt-1 text-sm font-medium transition-colors " +
                                    (isActive
                                        ? "text-merism-text"
                                        : "text-merism-text-muted hover:text-merism-text")
                                }
                            >
                                {tab.label}
                                {isActive && (
                                    <span className="absolute inset-x-0 bottom-0 h-[2px] bg-merism-accent" />
                                )}
                            </button>
                        )
                    })}
                </nav>
            </header>

            {/* ── Tab content ────────────────────────────────── */}
            <div className="pt-8">
                <Suspense fallback={<div className="text-merism-text-muted">{t("common.loading")}</div>}>
                    <TabComponent />
                </Suspense>
            </div>
        </div>
    )
}
