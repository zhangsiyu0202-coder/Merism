import { afterMount, connect, kea, path } from "kea"
import { loaders } from "kea-loaders"

import { studyLogic } from "~/features/studies/studyLogic"
import { api } from "~/lib/api"

import type { broadcastsLogicType } from './broadcastsLogicType'

/**
 * broadcastsLogic — read-only counters for recruitment broadcasts.
 *
 * Researchers configure channels + send broadcasts via Django admin
 * (see merism/admin.py). This logic just renders the current status
 * on the Recruit tab so researchers can see delivery progress without
 * leaving the SPA.
 */

export interface BroadcastRow {
    id: string
    status: string
    channel: string | null
    channel_name?: string | null
    counters: Record<string, number>
    retry_count: number
    created_at: string | null
}

export interface StudyLinkRow {
    id: string
    slug: string
    is_active: boolean
    expires_at: string | null
}

export const broadcastsLogic = kea<broadcastsLogicType>([
    path(["features", "studies", "tabs", "recruit", "broadcastsLogic"]),

    connect(() => ({
        values: [studyLogic, ["studyId"]],
    })),

    loaders(({ values }) => ({
        broadcasts: [
            [] as BroadcastRow[],
            {
                loadBroadcasts: async () => {
                    if (!values.studyId) return []
                    const resp = await api.list<BroadcastRow>("/api/broadcasts/", {
                        page_size: 50,
                        study: values.studyId,
                    })
                    return resp.results
                },
            },
        ],
        studyLinks: [
            [] as StudyLinkRow[],
            {
                loadStudyLinks: async () => {
                    if (!values.studyId) return []
                    const resp = await api.list<StudyLinkRow>("/api/study-links/", {
                        study: values.studyId,
                    })
                    return resp.results
                },
                createStudyLink: async () => {
                    if (!values.studyId) return []
                    await api.create("/api/study-links/", {
                        study: values.studyId,
                    })
                    const resp = await api.list<StudyLinkRow>("/api/study-links/", {
                        study: values.studyId,
                    })
                    return resp.results
                },
            },
        ],
    })),

    afterMount(({ actions, values }) => {
        if (values.studyId) {
            actions.loadBroadcasts()
            actions.loadStudyLinks()
        }
    }),
])
