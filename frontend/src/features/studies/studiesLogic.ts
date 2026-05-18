import { actions, afterMount, kea, listeners, path, reducers, selectors } from "kea"
import { loaders } from "kea-loaders"
import { router } from "kea-router"

import { urls } from "~/app/routes"
import { api } from "~/lib/api"
import type { Study } from "~/types"

import type { studiesLogicType } from './studiesLogicType'

/**
 * studiesLogic — state for the Studies list page + the shared
 * "create a new study" action that the Sidebar and Home page both
 * trigger.
 */
export const studiesLogic = kea<studiesLogicType>([
    path(["features", "studies", "studiesLogic"]),

    actions({
        createStudy: true,
        setPage: (page: number) => ({ page }),
        setPageSize: (size: number) => ({ size }),
    }),

    reducers({
        page: [
            0,
            {
                setPage: (_, { page }) => Math.max(0, page),
            },
        ],
        pageSize: [
            20,
            {
                setPageSize: (_, { size }) => Math.max(10, Math.min(100, size)),
            },
        ],
    }),

    loaders(() => ({
        studies: [
            [] as Study[],
            {
                loadStudies: async () => {
                    const response = await api.list<Study>("/api/studies/", {
                        page_size: 200,
                    })
                    return response.results
                },
            },
        ],
        newStudy: [
            null as Study | null,
            {
                createStudy: async () => {
                    return await api.create<Study>("/api/studies/", {
                        name: "Untitled study",
                        research_goal: "(Draft — set a research goal)",
                    })
                },
            },
        ],
    })),

    listeners({
        createStudySuccess: ({ newStudy }) => {
            if (newStudy?.id) {
                const url = urls.study(newStudy.id, "settings")
                router.actions.push(url)
                setTimeout(() => {
                    if (!window.location.pathname.includes(newStudy.id)) {
                        window.location.href = url
                    }
                }, 300)
            }
        },
        createStudyFailure: ({ error }) => {
            console.error("[studiesLogic] createStudy failed:", error)
            alert(`创建研究失败: ${error}`)
        },
        loadStudiesFailure: ({ error }) => {
            console.error("[studiesLogic] loadStudies failed:", error)
        },
    }),

    afterMount(({ actions }) => {
        actions.loadStudies()
    }),

    selectors({
        draftStudies: [(s) => [s.studies], (v) => v.filter((s) => s.status === "draft")],
        liveStudies: [
            (s) => [s.studies],
            (v) => v.filter((s) => s.status === "live"),
        ],
        archivedStudies: [
            (s) => [s.studies],
            (v) => v.filter((s) => s.status === "closed"),
        ],
        // Kept for back-compat with StudiesPage's old name.
        closedStudies: [
            (s) => [s.studies],
            (v) => v.filter((s) => s.status === "closed"),
        ],
        pageCount: [
            (s) => [s.studies, s.pageSize],
            (studies, pageSize) => Math.max(1, Math.ceil(studies.length / pageSize)),
        ],
    }),
])
