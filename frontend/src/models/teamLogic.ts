import { connect, kea, path, selectors } from "kea"

import { userLogic } from "./userLogic"

import type { teamLogicType } from './teamLogicType'

/**
 * teamLogic — the currently-selected team. For now just a view onto
 * ``userLogic.user.team``; once multi-team UI lands, add a
 * ``switchTeam`` action that PATCHes /api/users/me/.
 */
export const teamLogic = kea<teamLogicType>([
    path(["models", "teamLogic"]),

    connect(() => ({
        values: [userLogic, ["user"]],
    })),

    selectors({
        currentTeam: [(s) => [s.user], (user) => user?.team ?? null],
        currentTeamId: [(s) => [s.user], (user) => user?.team?.id ?? null],
        currentOrganization: [(s) => [s.user], (user) => user?.organization ?? null],
    }),
])
