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
        createStudy: (params?: {
            research_goal?: string
            study_type?: string
            context?: string
        }) => ({ params: params ?? {} }),
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
                setPage: () => 20, // reset pagesize to default whenever jumping (no-op)
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
                createStudy: async ({ params }: { params: { research_goal?: string; study_type?: string; context?: string } }) => {
                    return await api.create<Study>("/api/studies/", {
                        name: "Untitled study",
                        research_goal: params.research_goal || "(Draft — set a research goal)",
                        study_type: params.study_type || "discovery",
                        ai_context: params.context || "",
                    })
                },
            },
        ],
    })),

    listeners({
        createStudySuccess: ({ newStudy }) => {
            if (newStudy?.id) {
                router.actions.push(urls.study(newStudy.id, "guide"))
            }
        },
    }),

    afterMount(({ actions }) => {
        actions.loadStudies()
    }),

    selectors({
        draftStudies: [(s) => [s.studies], (v) => v.filter((s) => s.status === "draft")],
        liveStudies: [
            (s) => [s.studies],
            (v) => v.filter((s) => ["recruiting", "live", "active", "ready"].includes(s.status)),
        ],
        archivedStudies: [
            (s) => [s.studies],
            (v) => v.filter((s) => ["closed", "archived"].includes(s.status)),
        ],
        // Kept for back-compat with StudiesPage's old name.
        closedStudies: [
            (s) => [s.studies],
            (v) => v.filter((s) => ["closed", "archived"].includes(s.status)),
        ],
        pageCount: [
            (s) => [s.studies, s.pageSize],
            (studies, pageSize) => Math.max(1, Math.ceil(studies.length / pageSize)),
        ],
    }),
])
