import { kea, path, actions, reducers, listeners, selectors, afterMount, beforeUnmount } from "kea"
import { loaders } from "kea-loaders"
import { actionToUrl, urlToAction } from "kea-router"
import { api } from "~/lib/api"

import type { insightsLogicType } from "./insightsLogicType"

export interface StudyInsightsData {
    id: string
    study: string
    status: "pending" | "generating" | "ready" | "failed"
    completed_interviews: number
    avg_session_minutes: number
    interview_topics: string[]
    executive_summary: string
    generated_at: string | null
    error_message: string
    highlights_count: number
    findings_count: number
}

export interface InsightHighlight {
    id: string
    headline: string
    summary: string
    icon: string
    display_order: number
    linked_finding: string | null
}

export interface InsightFinding {
    id: string
    title: string
    summary: string
    display_order: number
    chart_spec: Record<string, unknown>
    chart_interpretation: string
    themes: { name: string; count: number; description: string }[]
    subthemes: { name: string; parent: string; description: string }[]
    insight_nuggets: { label: string; value: string; unit: string }[]
    supporting_evidence: { quote: string; source: string; context: string }[]
}

export const insightsLogic = kea<insightsLogicType>([
    path(["features", "analysis", "insightsLogic"]),

    actions({
        setStudyId: (studyId: string) => ({ studyId }),
        toggleFinding: (findingId: string) => ({ findingId }),
        rerunInsights: true,
        startPolling: true,
        stopPolling: true,
    }),

    reducers({
        studyId: [
            "" as string,
            { setStudyId: (_, { studyId }) => studyId },
        ],
        expandedFindings: [
            {} as Record<string, boolean>,
            {
                toggleFinding: (state, { findingId }) => ({
                    ...state,
                    [findingId]: !state[findingId],
                }),
            },
        ],
        _pollTimer: [
            null as ReturnType<typeof setInterval> | null,
            {
                startPolling: () => null, // handled in listener
                stopPolling: () => null,
            },
        ],
    }),

    loaders(({ values }) => ({
        insights: [
            null as StudyInsightsData | null,
            {
                loadInsights: async () => {
                    if (!values.studyId) return null
                    const res = await api.get(`/api/study-insights/?study=${values.studyId}`)
                    const results = (res as any).results ?? res
                    return (results as StudyInsightsData[])[0] ?? null
                },
            },
        ],
        highlights: [
            [] as InsightHighlight[],
            {
                loadHighlights: async () => {
                    if (!values.insights?.id) return []
                    const res = await api.get(`/api/insight-highlights/?insights=${values.insights.id}`)
                    return (res as any).results ?? res
                },
            },
        ],
        findings: [
            [] as InsightFinding[],
            {
                loadFindings: async () => {
                    if (!values.insights?.id) return []
                    const res = await api.get(`/api/insight-findings/?insights=${values.insights.id}`)
                    return (res as any).results ?? res
                },
            },
        ],
    })),

    listeners(({ actions, values, cache }) => ({
        setStudyId: () => {
            actions.stopPolling()
            actions.loadInsights()
        },
        loadInsightsSuccess: () => {
            if (values.insights?.status === "generating") {
                actions.startPolling()
            } else {
                actions.stopPolling()
                if (values.insights) {
                    actions.loadHighlights()
                    actions.loadFindings()
                }
            }
        },
        rerunInsights: async () => {
            if (!values.insights?.id) return
            await api.action(`/api/study-insights/${values.insights.id}/rerun/`)
            actions.loadInsights()
        },
        startPolling: () => {
            if (cache.pollTimer) clearInterval(cache.pollTimer)
            cache.pollTimer = setInterval(() => {
                actions.loadInsights()
            }, 3000)
        },
        stopPolling: () => {
            if (cache.pollTimer) {
                clearInterval(cache.pollTimer)
                cache.pollTimer = null
            }
        },
    })),

    // Persist studyId to URL ?study=xxx
    actionToUrl(({ values }) => ({
        setStudyId: () => ["/insights", { study: values.studyId || undefined }],
    })),

    urlToAction(({ actions, values }) => ({
        "/insights": (_, searchParams) => {
            const urlStudy = (searchParams as Record<string, string>).study || ""
            if (urlStudy && urlStudy !== values.studyId) {
                actions.setStudyId(urlStudy)
            }
        },
    })),

    afterMount(({ values, actions }) => {
        // If studyId was set from URL, load
        if (values.studyId) {
            actions.loadInsights()
        }
    }),

    beforeUnmount(({ cache }) => {
        if (cache.pollTimer) {
            clearInterval(cache.pollTimer)
            cache.pollTimer = null
        }
    }),

    selectors({
        isLoading: [
            (s) => [s.insightsLoading, s.highlightsLoading, s.findingsLoading],
            (a: boolean, b: boolean, c: boolean) => a || b || c,
        ],
        isGenerating: [
            (s) => [s.insights],
            (insights: StudyInsightsData | null) => insights?.status === "generating",
        ],
        isEmpty: [
            (s) => [s.insights],
            (insights: StudyInsightsData | null) => !insights || insights.status === "pending",
        ],
    }),
])
