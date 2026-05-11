import { afterMount, kea, path, selectors } from "kea"
import { loaders } from "kea-loaders"

import { api } from "~/lib/api"
import type { User } from "~/types"

import type { userLogicType } from './userLogicType'

/**
 * userLogic — the currently authenticated user + their team scope.
 *
 * Mounted by sceneLogic on every authenticated scene so downstream
 * logics can ``connect`` to its ``user`` / ``currentTeamId`` selectors.
 *
 * Unauthenticated scenes (login / 404 / participant room) skip mounting
 * this logic — the ``connect`` in scene logics should be conditional.
 */
export const userLogic = kea<userLogicType>([
    path(["models", "userLogic"]),

    loaders({
        user: [
            null as User | null,
            {
                loadUser: async () => {
                    try {
                        return await api.get<User>("/api/users/me/")
                    } catch (err) {
                        // 401 / 403 — user not authenticated yet
                        return null
                    }
                },
            },
        ],
    }),

    selectors({
        isAuthenticated: [(s) => [s.user], (u) => u !== null],
        currentTeamId: [(s) => [s.user], (u) => u?.team?.id ?? null],
    }),

    afterMount(({ actions }) => {
        actions.loadUser()
    }),
])
