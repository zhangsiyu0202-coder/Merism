import { useActions, useMountedLogic, useValues } from "kea"
import { router } from "kea-router"
import {
    BookMarked,
    ChevronsUpDown,
    FlaskConical,
    Home,
    Inbox,
    Lightbulb,
    LogOut,
    MessageCircle,
    Plus,
    Search,
    Settings,
    ShieldCheck,
    type LucideIcon,
} from "lucide-react"

import { sceneLogic } from "~/app/sceneLogic"
import { Scene, urls } from "~/app/routes"
import { studiesLogic } from "~/features/studies/studiesLogic"
import { userLogic } from "~/models/userLogic"
import { useTranslation } from "react-i18next"

import { cn } from "~/lib/merism/utils/cn"
import type { Study } from "~/types"

import { sidebarLogic } from "./sidebarLogic"

interface NavItem {
    scene: Scene
    label: string
    i18nKey?: string
    path: string
    icon: LucideIcon
}

/**
 * Core business-entity navigation — flat (no group labels).
 * Order follows the research lifecycle:
 *   overview → plan → input → output.
 */
const ENTITY_NAV: NavItem[] = [
    { scene: Scene.Home, i18nKey: "nav.home", label: "Home", path: urls.home(), icon: Home },
    { scene: Scene.Studies, i18nKey: "nav.studies", label: "Studies", path: urls.studies(), icon: FlaskConical },
    { scene: Scene.Ask, i18nKey: "nav.ask", label: "Ask", path: urls.ask(), icon: MessageCircle },
    { scene: Scene.Inbox, i18nKey: "nav.inbox", label: "Inbox", path: urls.inbox(), icon: Inbox },
    { scene: Scene.Repository, i18nKey: "nav.repository", label: "Repository", path: urls.repository(), icon: BookMarked },
    { scene: Scene.Decisions, i18nKey: "nav.decisions", label: "Decisions", path: urls.decisions(), icon: Lightbulb },
]

/**
 * NavigationSidebar — 4-zone left rail (Outset architecture).
 *
 *   Zone 1 · WorkspaceAnchor (team identity)
 *   Zone 2 · Core business entities (flat)
 *   Zone 3 · Dynamic pinned studies
 *   Zone 4 · Settings + User
 */
export function NavigationSidebar(): JSX.Element {
    useMountedLogic(studiesLogic)
    useMountedLogic(sidebarLogic)
    const { activeScene } = useValues(sceneLogic)
    const { push } = useActions(router)

    return (
        <aside
            aria-label="Primary"
            className="flex w-[var(--spacing-merism-sidebar)] shrink-0 flex-col border-r border-[color:var(--merism-hairline)] bg-merism-surface"
        >
            <WorkspaceAnchor onClick={() => push(urls.settings())} />

            <SearchTrigger />

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto px-2 pt-2">
                <div className="flex flex-col gap-1">
                    {ENTITY_NAV.map((item) => {
                        const isActive =
                            activeScene === item.scene ||
                            (item.scene === Scene.Studies && activeScene === Scene.Study)
                        return (
                            <NavLink
                                key={item.scene}
                                item={item}
                                isActive={isActive}
                                onNavigate={push}
                            />
                        )
                    })}
                </div>

                <PinnedStudiesZone />
            </div>

            <BottomZone activeScene={activeScene} onNavigate={push} />
        </aside>
    )
}

/* ── Zone 1: Workspace anchor ─────────────────────────────── */

function WorkspaceAnchor({ onClick }: { onClick: () => void }): JSX.Element {
    const { user } = useValues(userLogic)
    const teamName = user?.team?.name ?? "Merism"
    const initial = (teamName[0] ?? "M").toUpperCase()

    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "group m-2 flex items-center gap-3 rounded-merism-md px-3 py-2.5 text-left",
                "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                "hover:bg-merism-bg-subtle/80",
            )}
        >
            <div className="flex h-7 w-7 items-center justify-center rounded-merism-sm bg-merism-accent text-merism-accent-ink">
                <span className="font-display text-merism-body-sm font-[600] leading-none">
                    {initial}
                </span>
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="truncate text-merism-label font-medium text-merism-text">
                    {teamName}
                </span>
                <span className="truncate text-merism-caption text-merism-text-subtle">
                    Workspace
                </span>
            </div>
            <ChevronsUpDown
                className="h-3.5 w-3.5 shrink-0 text-merism-text-subtle opacity-60 transition-opacity group-hover:opacity-100"
                strokeWidth={1.8}
            />
        </button>
    )
}

/* ── Zone 3: Pinned studies ─────────────────────────────── */

function PinnedStudiesZone(): JSX.Element | null {
    const { pinnedStudies } = useValues(sidebarLogic)
    const { createStudy } = useActions(studiesLogic)
    const { newStudyLoading } = useValues(studiesLogic)
    const { sceneParams, activeScene } = useValues(sceneLogic)
    const { push } = useActions(router)

    const currentStudyId =
        activeScene === Scene.Study ? sceneParams.params.id : undefined

    return (
        <div className="mt-4 flex flex-col gap-1 border-t border-[color:var(--merism-hairline)] pt-4">
            <div className="px-3 pb-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Current
            </div>
            {pinnedStudies.length === 0 ? (
                <div className="px-3 py-1 text-merism-caption text-merism-text-subtle">
                    No recent studies
                </div>
            ) : (
                pinnedStudies.map((study) => (
                    <PinnedStudyRow
                        key={study.id}
                        study={study}
                        isActive={currentStudyId === study.id}
                        onClick={() => push(urls.study(study.id))}
                    />
                ))
            )}
            <button
                type="button"
                onClick={createStudy}
                disabled={newStudyLoading}
                className={cn(
                    "mt-1 flex items-center gap-3 rounded-merism-md px-3 py-2 text-left text-merism-label",
                    "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                    "text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text",
                    "disabled:opacity-60",
                )}
            >
                <Plus className="h-[1.05rem] w-[1.05rem] shrink-0" strokeWidth={1.6} />
                <span className="flex-1">New study</span>
            </button>
        </div>
    )
}

function PinnedStudyRow({
    study,
    isActive,
    onClick,
}: {
    study: Study
    isActive: boolean
    onClick: () => void
}): JSX.Element {
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "relative flex items-center gap-3 rounded-merism-md px-3 py-2 text-left text-merism-label",
                "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                isActive
                    ? "bg-merism-accent-soft font-medium text-merism-text"
                    : "text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text",
            )}
        >
            {isActive && (
                <span
                    aria-hidden="true"
                    className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-merism-accent"
                />
            )}
            <span
                aria-hidden="true"
                className={cn(
                    "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
                    isActive
                        ? "bg-merism-accent"
                        : "bg-merism-text-subtle/60",
                )}
            />
            <span className="flex-1 truncate">{study.name || "Untitled"}</span>
        </button>
    )
}

/* ── Zone 4: Settings + User badge ──────────────────────── */

function BottomZone({
    activeScene,
    onNavigate,
}: {
    activeScene: Scene
    onNavigate: (path: string) => void
}): JSX.Element {
    const { t } = useTranslation()
    const { user } = useValues(userLogic)
    return (
        <div className="border-t border-[color:var(--merism-hairline)] p-2">
            {user?.is_superuser && (
                <a
                    href="/admin/"
                    target="_blank"
                    rel="noreferrer"
                    className="group mx-1 my-0.5 flex items-center gap-3 rounded-merism-md px-3 py-2 text-merism-label text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
                    title="Open Django admin (staff only)"
                >
                    <ShieldCheck className="h-4 w-4 shrink-0 text-merism-text-subtle group-hover:text-merism-text" />
                    <span>{t("nav.admin")}</span>
                </a>
            )}
            <NavLink
                item={{
                    scene: Scene.Settings,
                    label: "Settings",
                    path: urls.settings(),
                    icon: Settings,
                }}
                isActive={activeScene === Scene.Settings}
                onNavigate={onNavigate}
            />
            <UserBadge />
        </div>
    )
}

function UserBadge(): JSX.Element | null {
    const { user } = useValues(userLogic)
    if (!user) return null

    const displayName =
        [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email
    const initial = (displayName[0] ?? "U").toUpperCase()

    async function handleLogout(): Promise<void> {
        // Best-effort — Django allauth logout on the server.
        try {
            await fetch("/accounts/logout/", { method: "POST", credentials: "include" })
        } catch {
            // ignore; user will retry
        }
        window.location.assign(urls.login())
    }

    return (
        <div className="mt-1 flex items-center gap-3 rounded-merism-md px-3 py-2">
            <div
                className="flex h-7 w-7 items-center justify-center rounded-merism-full bg-merism-bg-subtle text-merism-text"
                aria-hidden="true"
            >
                <span className="font-display text-merism-caption font-[600]">
                    {initial}
                </span>
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-0">
                <span className="truncate text-merism-label font-medium text-merism-text">
                    {displayName}
                </span>
                <span className="truncate text-merism-caption text-merism-text-subtle">
                    {user.email}
                </span>
            </div>
            <button
                type="button"
                onClick={handleLogout}
                aria-label="Sign out"
                className="inline-flex h-6 w-6 items-center justify-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
            >
                <LogOut className="h-3.5 w-3.5" strokeWidth={1.8} />
            </button>
        </div>
    )
}

/* ── Shared NavLink row ─────────────────────────────────── */

function NavLink({
    item,
    isActive,
    onNavigate,
}: {
    item: NavItem
    isActive: boolean
    onNavigate: (path: string) => void
}): JSX.Element {
    const { t } = useTranslation()
    const Icon = item.icon
    const displayLabel = item.i18nKey ? t(item.i18nKey) : item.label
    return (
        <button
            type="button"
            onClick={() => onNavigate(item.path)}
            aria-current={isActive ? "page" : undefined}
            className={cn(
                "relative flex w-full items-center gap-3 rounded-merism-md px-3 py-2 text-left text-[var(--text-merism-label)]",
                "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                isActive
                    ? "bg-merism-accent-soft font-medium text-merism-text"
                    : "text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text",
            )}
        >
            {isActive && (
                <span
                    aria-hidden="true"
                    className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-merism-accent"
                />
            )}
            <Icon
                className={cn(
                    "h-[1.05rem] w-[1.05rem] shrink-0",
                    isActive ? "text-merism-accent" : "text-merism-text-subtle",
                )}
                strokeWidth={1.6}
            />
            <span className="flex-1 truncate">{displayLabel}</span>
        </button>
    )
}


/**
 * SearchTrigger — clickable hint that opens the command palette.
 *
 * Dispatches a synthetic Cmd+K keydown so we don't need to lift the
 * palette's uncontrolled open state out of ``CommandPalette``.
 */
function SearchTrigger(): JSX.Element {
    const { t } = useTranslation()
    const open = (): void => {
        window.dispatchEvent(
            new KeyboardEvent("keydown", { key: "k", metaKey: true, ctrlKey: true }),
        )
    }
    return (
        <button
            type="button"
            onClick={open}
            className="mx-2 mt-2 flex items-center gap-3 rounded-merism-md border border-[color:var(--merism-hairline-strong)] bg-merism-surface px-3 py-1.5 text-left text-merism-label text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
        >
            <Search className="h-3.5 w-3.5 shrink-0 text-merism-text-subtle" />
            <span className="flex-1 truncate">{t("common.search")}</span>
            <kbd className="rounded-merism-sm bg-merism-bg-subtle px-1.5 py-0.5 font-mono text-[10px] text-merism-text-subtle">
                ⌘K
            </kbd>
        </button>
    )
}
