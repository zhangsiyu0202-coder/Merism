import { afterMount, kea, path } from "kea"
import { loaders } from "kea-loaders"

import { api } from "~/lib/api"

import type { inboxLogicType } from './inboxLogicType'

export interface InboxItem {
    id: string
    kind:
        | "session_completed"
        | "insight_ready"
        | "study_completed"
        | "study_stuck"
    ref_kind: string
    ref_id: string
    title: string
    body: string
    payload: Record<string, unknown>
    read_by: string[]
    trace_id: string | null
    created_at: string
}

export const inboxLogic = kea<inboxLogicType>([
    path(["features", "inbox", "inboxLogic"]),

    loaders(() => ({
        items: [
            [] as InboxItem[],
            {
                loadInbox: async () => {
                    const resp = await api.list<InboxItem>("/api/inbox-items/", {
                        page_size: 50,
                    })
                    return resp.results
                },
                markRead: async (id: string) => {
                    await api.create(`/api/inbox-items/${id}/mark-read/`, {})
                    const resp = await api.list<InboxItem>("/api/inbox-items/", {
                        page_size: 50,
                    })
                    return resp.results
                },
            },
        ],
    })),

    afterMount(({ actions }) => {
        actions.loadInbox()
    }),
])
