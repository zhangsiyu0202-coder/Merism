import { useActions, useMountedLogic, useValues } from "kea"
import { router } from "kea-router"
import {
    BookMarked,
    ChevronsUpDown,
    FileText,
    FlaskConical,
    Home,
    Inbox,
    Lightbulb,
    PanelLeftClose,
    PanelLeftOpen,
    Plus,
    Search,
    Settings,
    Sparkles,
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
 *
 * Ask is intentionally NOT in the main nav — it's a right-side slide-out
 * panel (like PostHog's Max). Toggle via the TopBar icon button.
 */
const ENTITY_NAV: NavItem[] = [
    { scene: Scene.Home, i18nKey: "nav.home", label: "Home", path: urls.home(), icon: Home },
    { scene: Scene.Studies, i18nKey: "nav.studies", label: "Studies", path: urls.studies(), icon: FlaskConical },
    { scene: Scene.Insights, label: "Insights", path: urls.insights(), icon: Sparkles },
    { scene: Scene.Reports, label: "Reports", path: urls.reports(), icon: FileText },
    { scene: Scene.Inbox, i18nKey: "nav.inbox", label: "Inbox", path: urls.inbox(), icon: Inbox },
    { scene: Scene.Repository, i18nKey: "nav.repository", label: "Repository", path: urls.repository(), icon: BookMarked },
    { scene: Scene.Decisions, i18nKey: "nav.decisions", label: "Decisions", path: urls.decisions(), icon: Lightbulb },
]

/**
 * NavigationSidebar — 4-zone left rail with collapse/expand.
 *
 *   Zone 1 · WorkspaceAnchor (team identity)
 *   Zone 2 · Search trigger
 *   Zone 3 · Core nav + pinned studies
 *   Zone 4 · Settings + User + Collapse toggle
 *
 * Width driven by CSS var --spacing-merism-sidebar / --spacing-merism-sidebar-collapsed.
 * Animated with 100ms ease-out on the width property (matches PostHog's pace).
 */
export function NavigationSidebar(): JSX.Element {
    useMountedLogic(studiesLogic)
    useMountedLogic(sidebarLogic)
    const { activeScene } = useValues(sceneLogic)
    const { isCollapsed } = useValues(sidebarLogic)
    const { push } = useActions(router)

    return (
        <aside
            aria-label="Primary"
            className={cn(
                "flex shrink-0 flex-col border-r border-[color:var(--merism-hairline)] bg-merism-surface",
                "transition-[width] ease-[var(--merism-ease)] will-change-[width]",
            )}
            style={{
                width: isCollapsed
                    ? "var(--spacing-merism-sidebar-collapsed)"
                    : "var(--spacing-merism-sidebar)",
                transitionDuration: "var(--merism-duration-layout)",
            }}
        >
            <WorkspaceAnchor
                isCollapsed={isCollapsed}
                onClick={() => push(urls.settings())}
            />

            <SearchTrigger isCollapsed={isCollapsed} />

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto overflow-x-hidden px-2 pt-2">
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
                                isCollapsed={isCollapsed}
                                onNavigate={push}
                            />
                        )
                    })}
                </div>

                {!isCollapsed && <PinnedStudiesZone />}
            </div>

            <BottomZone activeScene={activeScene} isCollapsed={isCollapsed} onNavigate={push} />
        </aside>
    )
}

/* ── Zone 1: Workspace anchor ─────────────────────────────── */

function WorkspaceAnchor({
    isCollapsed,
    onClick,
}: {
    isCollapsed: boolean
    onClick: () => void
}): JSX.Element {
    const { user } = useValues(userLogic)
    const teamName = user?.team?.name ?? "Merism"
    const initial = (teamName[0] ?? "M").toUpperCase()

    return (
        <button
            type="button"
            onClick={onClick}
            title={isCollapsed ? teamName : undefined}
            className={cn(
                "group m-2 flex items-center gap-3 rounded-merism-md text-left",
                isCollapsed ? "justify-center px-0 py-1.5" : "px-3 py-2.5",
                "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                "hover:bg-merism-bg-subtle/80",
            )}
        >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-merism-sm bg-merism-accent text-merism-accent-ink">
                <span className="font-display text-merism-body-sm font-[600] leading-none">
                    {initial}
                </span>
            </div>
            {!isCollapsed && (
                <>
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
                </>
            )}
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
                    "mt-1 flex items-center gap-3 rounded-merism-md px-3 py-1.5 text-left text-merism-label",
                    "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                    "text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text",
                    "disabled:opacity-60",
                )}
            >
                <Plus className="h-4 w-4 shrink-0" strokeWidth={1.6} />
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
                "relative flex items-center gap-3 rounded-merism-md px-3 py-1.5 text-left text-merism-label",
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

/* ── Zone 4: Settings + User badge + Collapse toggle ──── */

function BottomZone({
    activeScene,
    isCollapsed,
    onNavigate,
}: {
    activeScene: Scene
    isCollapsed: boolean
    onNavigate: (path: string) => void
}): JSX.Element {
    const { toggleCollapsed } = useActions(sidebarLogic)

    return (
        <div className="border-t border-[color:var(--merism-hairline)] p-2">
            <NavLink
                item={{
                    scene: Scene.Settings,
                    label: "设置",
                    path: urls.settings(),
                    icon: Settings,
                }}
                isActive={activeScene === Scene.Settings}
                isCollapsed={isCollapsed}
                onNavigate={onNavigate}
            />
            <button
                type="button"
                onClick={toggleCollapsed}
                aria-label={isCollapsed ? "展开" : "收起"}
                title={isCollapsed ? "展开" : "收起"}
                className={cn(
                    "mt-1 flex items-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-text",
                    isCollapsed
                        ? "justify-center w-full py-2"
                        : "gap-3 px-3 py-1.5",
                )}
            >
                {isCollapsed ? (
                    <PanelLeftOpen className="h-4 w-4 shrink-0" strokeWidth={1.6} />
                ) : (
                    <>
                        <PanelLeftClose className="h-4 w-4 shrink-0" strokeWidth={1.6} />
                        <span className="flex-1 text-left text-merism-label">收起</span>
                    </>
                )}
            </button>
        </div>
    )
}

/* ── Shared NavLink row ─────────────────────────────────── */

function NavLink({
    item,
    isActive,
    isCollapsed,
    onNavigate,
}: {
    item: NavItem
    isActive: boolean
    isCollapsed?: boolean
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
            title={isCollapsed ? displayLabel : undefined}
            className={cn(
                "relative flex w-full items-center rounded-merism-md text-left text-[var(--text-merism-label)]",
                "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
                isCollapsed ? "justify-center px-0 py-2" : "gap-3 px-3 py-1.5",
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
                    "h-4 w-4 shrink-0",
                    isActive ? "text-merism-accent" : "text-merism-text-subtle",
                )}
                strokeWidth={1.6}
            />
            {!isCollapsed && <span className="flex-1 truncate">{displayLabel}</span>}
        </button>
    )
}


/**
 * SearchTrigger — clickable hint that opens the command palette.
 *
 * Dispatches a synthetic Cmd+K keydown so we don't need to lift the
 * palette's uncontrolled open state out of ``CommandPalette``.
 */
function SearchTrigger({ isCollapsed }: { isCollapsed: boolean }): JSX.Element {
    const { t } = useTranslation()
    const open = (): void => {
        window.dispatchEvent(
            new KeyboardEvent("keydown", { key: "k", metaKey: true, ctrlKey: true }),
        )
    }
    if (isCollapsed) {
        return (
            <button
                type="button"
                onClick={open}
                title={t("common.search")}
                className="mx-2 mt-2 flex items-center justify-center rounded-merism-md border border-[color:var(--merism-hairline-strong)] bg-merism-surface py-2 text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
            >
                <Search className="h-3.5 w-3.5 shrink-0" />
            </button>
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
        </button>
    )
}
