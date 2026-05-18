import { kea, path, actions, reducers, listeners, selectors, beforeUnmount } from "kea"
import { loaders } from "kea-loaders"
import { api } from "~/lib/api"

import type { reportDetailLogicType } from "./reportDetailLogicType"
import type { CustomReportData, ReportQuestion, ReportSegment } from "./reportsLogic"

export const reportDetailLogic = kea<reportDetailLogicType>([
    path(["features", "analysis", "reportDetailLogic"]),

    actions({
        setReportId: (reportId: string) => ({ reportId }),
        generateReport: true,
        togglePublic: true,
        setActiveSegment: (segmentId: string | null) => ({ segmentId }),
        addQuestion: (title: string, questionType: string) => ({ title, questionType }),
        startPolling: true,
        stopPolling: true,
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
                    return (res as any).results ?? res
                },
            },
        ],
        segments: [
            [] as ReportSegment[],
            {
                loadSegments: async () => {
                    if (!values.reportId) return []
                    const res = await api.get(`/api/report-segments/?report=${values.reportId}`)
                    return (res as any).results ?? res
                },
            },
        ],
    })),

    listeners(({ actions, values, cache }) => ({
        setReportId: () => {
            actions.stopPolling()
            actions.loadReport()
            actions.loadQuestions()
            actions.loadSegments()
        },
        loadReportSuccess: () => {
            if (values.report?.status === "generating") {
                actions.startPolling()
            } else {
                actions.stopPolling()
            }
        },
        generateReport: async () => {
            if (!values.reportId) return
            await api.action(`/api/custom-reports/${values.reportId}/generate/`)
            actions.loadReport()
            actions.loadQuestions()
        },
        togglePublic: async () => {
            if (!values.reportId) return
            await api.action(`/api/custom-reports/${values.reportId}/toggle_public/`)
            actions.loadReport()
        },
        addQuestion: async ({ title, questionType }) => {
            await api.create("/api/report-questions/", {
                report: values.reportId,
                title,
                question_type: questionType,
                question_number: values.questions.length + 1,
            })
            actions.loadQuestions()
        },
        startPolling: () => {
            if (cache.pollTimer) clearInterval(cache.pollTimer)
            cache.pollTimer = setInterval(() => {
                actions.loadReport()
                actions.loadQuestions()
            }, 3000)
        },
        stopPolling: () => {
            if (cache.pollTimer) {
                clearInterval(cache.pollTimer)
                cache.pollTimer = null
            }
        },
    })),

    beforeUnmount(({ cache }) => {
        if (cache.pollTimer) {
            clearInterval(cache.pollTimer)
            cache.pollTimer = null
        }
    }),

    selectors({
        isLoading: [
            (s) => [s.reportLoading, s.questionsLoading],
            (a: boolean, b: boolean) => a || b,
        ],
        isGenerating: [
            (s) => [s.report],
            (report: CustomReportData | null) => report?.status === "generating",
        ],
        filteredQuestions: [
            (s) => [s.questions, s.activeSegment],
            (questions: ReportQuestion[], segment: string | null) =>
                segment ? questions.filter((q) => q.segment === segment || !q.segment) : questions,
        ],
    }),
])
