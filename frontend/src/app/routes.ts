/**
 * Route registry — single source of truth for every URL in the app.
 *
 * To add a route:
 *   1. Add a value to :class:`Scene`.
 *   2. Add a path builder in :data:`urls`.
 *   3. Add a ``path pattern`` → ``Scene`` mapping in :data:`routes`.
 *   4. Add a dynamic import in :file:`routeRegistry.ts`.
 *
 * The ``urls.xxx()`` builders are typed; consumers should NEVER
 * concatenate paths manually — makes route rename a one-file edit.
 */

export enum Scene {
    // top-level surfaces
    Home = "Home",
    Ask = "Ask",
    Inbox = "Inbox",
    Repository = "Repository",
    Decisions = "Decisions",
    Settings = "Settings",

    // studies
    Studies = "Studies",
    Study = "Study",


    // participant-facing
    InterviewRoom = "InterviewRoom",
    ParticipantEntry = "ParticipantEntry",

    // auth
    Login = "Login",

    // errors
    Error404 = "Error404",
}

export type StudyTab =
    | "brief"
    | "outline"
    | "screener"
    | "stimuli"
    | "recruit"
    | "analysis"
    | "report"
    | "sessions"
    | "settings"

export const urls = {
    default: (): string => "/",

    home: (tab?: string): string => (tab ? `/?tab=${tab}` : "/"),
    ask: (): string => "/ask",
    inbox: (): string => "/inbox",
    repository: (): string => "/repository",
    decisions: (): string => "/decisions",
    settings: (section?: string): string =>
        section ? `/settings/${section}` : "/settings",

    studies: (): string => "/studies",
    study: (id: string, tab: StudyTab = "brief"): string => `/studies/${id}/${tab}`,

    interviewRoom: (sessionId: string): string => `/interview/${sessionId}`,
    participantEntry: (slug: string): string => `/i/${slug}`,

    login: (next?: string): string =>
        next ? `/login?next=${encodeURIComponent(next)}` : "/login",

    error404: (): string => "/404",
} as const

/**
 * kea-router route patterns. Keys = URL patterns, values = Scene.
 *
 * Order matters — more specific routes first. ``sceneLogic`` scans these
 * sequentially via ``urlToAction`` handlers.
 */
export const routes: Record<string, Scene> = {
    "/": Scene.Home,
    "/ask": Scene.Ask,
    "/inbox": Scene.Inbox,
    "/repository": Scene.Repository,
    "/decisions": Scene.Decisions,
    "/settings": Scene.Settings,
    "/settings/:section": Scene.Settings,
    "/studies": Scene.Studies,
    "/studies/:id": Scene.Study,
    "/studies/:id/:tab": Scene.Study,
    "/interview/:sessionId": Scene.InterviewRoom,
    "/i/:slug": Scene.ParticipantEntry,
    "/login": Scene.Login,
    "/404": Scene.Error404,
}
