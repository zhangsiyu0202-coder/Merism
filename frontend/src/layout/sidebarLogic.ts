import { actions, connect, kea, listeners, path, reducers, selectors } from "kea"

import { sceneLogic } from "~/app/sceneLogic"
import { Scene } from "~/app/routes"
import { studiesLogic } from "~/features/studies/studiesLogic"

import type { sidebarLogicType } from './sidebarLogicType'

/**
 * sidebarLogic — drives the "pinned studies" zone in the left nav.
 *
 * We track the most-recently-opened study IDs in ``localStorage``
 * so the pinned list survives refresh without costing a backend
 * field. When ``sceneLogic`` enters a Study scene we push the
 * current ``studyId`` to the front; when the user never returns
 * to a study within 30 opens it falls off the bottom.
 *
 * The resolved pinned list (IDs → Study objects) is derived from
 * ``studiesLogic.studies``; if the store hasn't loaded yet we just
 * skip unknown IDs.
 */

const STORAGE_KEY = "merism.sidebar.recentStudyIds"
const MAX_PINNED = 3

function readStored(): string[] {
    if (typeof window === "undefined") return []
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY)
        if (!raw) return []
        const parsed = JSON.parse(raw)
        if (!Array.isArray(parsed)) return []
        return parsed.filter((v): v is string => typeof v === "string")
    } catch {
        return []
    }
}

function writeStored(ids: string[]): void {
    if (typeof window === "undefined") return
    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
    } catch {
        // ignore quota / private mode failures
    }
}

export const sidebarLogic = kea<sidebarLogicType>([
    path(["layout", "sidebarLogic"]),

    connect(() => ({
        values: [studiesLogic, ["studies"], sceneLogic, ["sceneParams", "activeScene"]],
    })),

    actions({
        touchStudy: (studyId: string) => ({ studyId }),
    }),

    reducers({
        recentStudyIds: [
            readStored() as string[],
            {
                touchStudy: (current, { studyId }) => {
                    const next = [studyId, ...current.filter((id) => id !== studyId)].slice(
                        0,
                        MAX_PINNED,
                    )
                    writeStored(next)
                    return next
                },
            },
        ],
    }),

    selectors({
        pinnedStudies: [
            (s) => [s.recentStudyIds, s.studies],
            (ids, studies) => {
                const map = new Map(studies.map((st) => [st.id, st]))
                return ids
                    .map((id) => map.get(id))
                    .filter((s): s is NonNullable<typeof s> => !!s)
            },
        ],
    }),

    listeners(({ actions, values }) => ({
        // Whenever the URL leads us into a Study, bump that ID to front.
        [sceneLogic.actionTypes.setScene]: ({ scene, params }) => {
            if (scene === Scene.Study && params.params.id) {
                if (params.params.id !== values.recentStudyIds[0]) {
                    actions.touchStudy(params.params.id)
                }
            }
        },
    })),
])
