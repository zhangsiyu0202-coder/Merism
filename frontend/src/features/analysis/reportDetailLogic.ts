import { kea, path, actions, reducers, listeners, selectors, props } from "kea"
import { loaders } from "kea-loaders"
import { api } from "~/lib/api"

import type { reportDetailLogicType } from "./reportDetailLogicType"
import type { CustomReportData, ReportQuestion, ReportSegment } from "./reportsLogic"

export interface ReportDetailLogicProps {
    reportId: string
}

export const reportDetailLogic = kea<reportDetailLogicType>([
    path(["features", "analysis", "reportDetailLogic"]),
    props({} as ReportDetailLogicProps),

    actions({
        setReportId: (reportId: string) => ({ reportId }),
        generateReport: true,
        togglePublic: true,
        setActiveSegment: (segmentId: string | null) => ({ segmentId }),
        addQuestion: (title: string, questionType: string) => ({ title, questionType }),
    }),

    reducers({
        reportId: [
            "" as string,
            { setReportId: (_, { reportId }) => reportId },
        ],
        activeSegment: [
            null as string | null,
            { setActiveSegment: (_, { segmentId }) => segmentId },
        ],
    }),

    loaders(({ values }) => ({
        report: [
            null as CustomReportData | null,
            {
                loadReport: async () => {
                    if (!values.reportId) return null
                    return await api.get(`/api/custom-reports/${values.reportId}/`)
                },
            },
        ],
        questions: [
            [] as ReportQuestion[],
            {
                loadQuestions: async () => {
                    if (!values.reportId) return []
                    const res = await api.get(`/api/report-questions/?report=${values.reportId}`)
                    return res.results ?? res
                },
            },
        ],
        segments: [
            [] as ReportSegment[],
            {
                loadSegments: async () => {
                    if (!values.reportId) return []
                    const res = await api.get(`/api/report-segments/?report=${values.reportId}`)
                    return res.results ?? res
                },
            },
        ],
    })),

    listeners(({ actions, values }) => ({
        setReportId: () => {
            actions.loadReport()
            actions.loadQuestions()
            actions.loadSegments()
        },
        generateReport: async () => {
            if (!values.reportId) return
            await api.post(`/api/custom-reports/${values.reportId}/generate/`)
            actions.loadReport()
            actions.loadQuestions()
        },
        togglePublic: async () => {
            if (!values.reportId) return
            await api.post(`/api/custom-reports/${values.reportId}/toggle_public/`)
            actions.loadReport()
        },
        addQuestion: async ({ title, questionType }) => {
            await api.post("/api/report-questions/", {
                report: values.reportId,
                title,
                question_type: questionType,
                question_number: values.questions.length + 1,
            })
            actions.loadQuestions()
        },
    })),

    selectors({
        isLoading: [
            (s) => [s.reportLoading, s.questionsLoading],
            (a, b) => a || b,
        ],
        isGenerating: [
            (s) => [s.report],
            (report) => report?.status === "generating",
        ],
        filteredQuestions: [
            (s) => [s.questions, s.activeSegment],
            (questions, segment) =>
                segment ? questions.filter((q) => q.segment === segment || !q.segment) : questions,
        ],
    }),
])
