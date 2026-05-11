/**
 * Route registry — binds each :class:`Scene` to (a) its lazy-loaded
 * component and (b) its display / auth config.
 *
 * Keep dynamic imports here so each feature ships in its own chunk.
 */

import { Scene } from "./routes"
import type { SceneConfigMap, SceneImportMap } from "./sceneTypes"

export const sceneImports: SceneImportMap = {
    [Scene.Home]: () => import("~/features/home/HomePage"),
    [Scene.Ask]: () => import("~/features/ask/AskPage"),
    [Scene.Inbox]: () => import("~/features/inbox/InboxPage"),
    [Scene.Repository]: () => import("~/features/repository/RepositoryPage"),
    [Scene.Decisions]: () => import("~/features/decisions/DecisionsPage"),
    [Scene.Settings]: () => import("~/features/settings/SettingsPage"),
    [Scene.Studies]: () => import("~/features/studies/StudiesPage"),
    [Scene.Study]: () => import("~/features/studies/StudyPage"),
    [Scene.InterviewRoom]: () => import("~/features/interview/InterviewRoomPage"),
    [Scene.ParticipantEntry]: () => import("~/features/participant/ParticipantEntryPage"),
    [Scene.Login]: () => import("~/features/authentication/LoginPage"),
    [Scene.Error404]: () => import("~/layout/Error404"),
}

export const sceneConfigs: SceneConfigMap = {
    [Scene.Home]: { name: "Home" },
    [Scene.Ask]: { name: "Ask Merism" },
    [Scene.Inbox]: { name: "Inbox" },
    [Scene.Repository]: { name: "Repository" },
    [Scene.Decisions]: { name: "Decisions" },
    [Scene.Settings]: { name: "Settings" },
    [Scene.Studies]: { name: "Studies" },
    [Scene.Study]: { name: "Study", hideFromNav: true },
    [Scene.InterviewRoom]: {
        name: "Interview",
        layout: "participant",
        allowUnauthenticated: true,
        hideFromNav: true,
    },
    [Scene.ParticipantEntry]: {
        name: "Invitation",
        layout: "plain",
        allowUnauthenticated: true,
        hideFromNav: true,
    },
    [Scene.Login]: {
        name: "Log in",
        layout: "plain",
        allowUnauthenticated: true,
        hideFromNav: true,
    },
    [Scene.Error404]: {
        name: "Not found",
        layout: "plain",
        allowUnauthenticated: true,
        hideFromNav: true,
    },
}
