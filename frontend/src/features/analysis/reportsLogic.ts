import { kea, path, actions, reducers, listeners, selectors } from "kea"
import { loaders } from "kea-loaders"
import { api } from "~/lib/api"

import type { reportsLogicType } from "./reportsLogicType"

export interface CustomReportData {
    id: string
    study: string
    title: string
    status: "draft" | "generating" | "ready" | "failed"
    ai_synthesis: string
    share_token: string
    is_public: boolean
    share_url: string
    questions_count: number
    segments_count: number
    generated_at: string | null
    error_message: string
    created_at: string
}

export interface ReportSegment {
    id: string
    report: string
    name: string
    selector: Record<string, unknown>
    participation_ids: string[]
}

export interface ReportQuestion {
    id: string
    report: string
    question_number: number
    title: string
    question_type: string
    status: "pending" | "generating" | "ready" | "failed"
    ai_summary: string
    chart_spec: Record<string, unknown>
    themes: { name: string; count: number; description: string; sentiment?: string }[]
    quotes: { text: string; source: string; theme: string }[]
    segment: string | null
}

export const reportsLogic = kea<reportsLogicType>([
    path(["features", "analysis", "reportsLogic"]),

    actions({
        setStudyId: (studyId: string) => ({ studyId }),
        createReport: (title: string) => ({ title }),
        deleteReport: (reportId: string) => ({ reportId }),
    }),

    reducers({
        studyId: [
            "" as string,
            { setStudyId: (_, { studyId }) => studyId },
        ],
    }),

    loaders(({ values }) => ({
        reports: [
            [] as CustomReportData[],
            {
                loadReports: async () => {
                    if (!values.studyId) return []
                    const res = await api.get(`/api/custom-reports/?study=${values.studyId}`)
                    return res.results ?? res
                },
            },
        ],
    })),

    listeners(({ actions, values }) => ({
        setStudyId: () => {
            actions.loadReports()
        },
        createReport: async ({ title }) => {
            await api.post("/api/custom-reports/", { study: values.studyId, title })
            actions.loadReports()
        },
        deleteReport: async ({ reportId }) => {
            await api.delete(`/api/custom-reports/${reportId}/`)
            actions.loadReports()
        },
    })),

    selectors({
        isLoading: [(s) => [s.reportsLoading], (loading) => loading],
    }),
])
