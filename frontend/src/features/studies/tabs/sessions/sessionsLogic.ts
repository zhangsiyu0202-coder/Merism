import { kea, path } from "kea"
import { loaders } from "kea-loaders"

import { api } from "~/lib/api"
import type { InterviewSession } from "~/types"

import type { sessionsLogicType } from './sessionsLogicType'

export const sessionsLogic = kea<sessionsLogicType>([
    path(["features", "studies", "tabs", "sessions", "sessionsLogic"]),

    loaders({
        sessions: [
            [] as InterviewSession[],
            {
                loadSessions: async (studyId: string) => {
                    const response = await api.list<InterviewSession>("/api/sessions/", {
                        study: studyId,
                        page_size: 200,
                    })
                    return response.results
                },
            },
        ],
    }),
])
