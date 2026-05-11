import { kea, path, selectors } from "kea"
import { loaders } from "kea-loaders"

import { api } from "~/lib/api"
import type { Study } from "~/types"

import type { studiesModelType } from './studiesModelType'

/**
 * studiesModel — a thin app-global cache of recent studies.
 *
 * NOT the primary list (that lives in ``studiesLogic`` inside the
 * Studies feature). This model exists so the navigation sidebar,
 * breadcrumb, and study-link pickers can read a list of studies
 * without the Studies feature being mounted.
 */
export const studiesModel = kea<studiesModelType>([
    path(["models", "studiesModel"]),

    loaders({
        studies: [
            [] as Study[],
            {
                loadStudies: async () => {
                    const response = await api.list<Study>("/api/studies/")
                    return response.results
                },
            },
        ],
    }),

    selectors({
        studyById: [
            (s) => [s.studies],
            (studies): ((id: string) => Study | undefined) =>
                (id) =>
                    studies.find((study) => study.id === id),
        ],
        activeStudies: [
            (s) => [s.studies],
            (studies) =>
                studies.filter((s) => !["closed", "archived"].includes(s.status)),
        ],
    }),
])
