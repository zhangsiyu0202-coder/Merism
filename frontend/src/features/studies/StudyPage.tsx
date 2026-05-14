import { useActions, useMountedLogic, useValues } from "kea"
import { router } from "kea-router"
import {
    Archive,
    Copy,
    MoreHorizontal,
    Pencil,
    Play,
    Share2,
    Trash2,
} from "lucide-react"
import {
    lazy,
    Suspense,
    useEffect,
    useRef,
    useState,
    type ComponentType,
    type ReactNode,
} from "react"
import { useTranslation } from "react-i18next"

import { urls, type StudyTab } from "~/app/routes"
import {
    Button,
    PageTopBar,
    Tag,
    cn,
    type TabRailItem,
} from "~/lib/merism"

import { studyLogic } from "./studyLogic"

/**
 * StudyPage — the tabbed shell for a single study.
 *
 * Masthead matches the Outset.ai reference: title + status + kebab on
 * the left, a right-side action cluster (``Test interview`` primary,
 * ``Add section randomization`` secondary), and the tab rail directly
 * below the title — all inside a single ``PageTopBar`` so the title
 * row and tabs read as one unit (not two stripes).
 *
 * URL: ``/studies/:id/:tab``. Tabs are lazy-loaded so we don't ship all
 * eight in the Study bundle. Each tab is its own folder under ``tabs/``
 * with a single ``<TabName>Tab.tsx`` default export.
 */

const tabComponents: Record<StudyTab, () => Promise<{ default: ComponentType }>> = {
    brief: () => import("./tabs/brief/BriefTab"),
    outline: () => import("./tabs/outline/OutlineTab"),
    screener: () => import("./tabs/screener/ScreenerTab"),
    stimuli: () => import("./tabs/stimuli/StimuliTab"),
    recruit: () => import("./tabs/recruit/RecruitTab"),
    report: () => import("./tabs/report/ReportTab"),
    sessions: () => import("./tabs/sessions/SessionsTab"),
    settings: () => import("./tabs/settings/SettingsTab"),
}

const tabCache = new Map<StudyTab, ComponentType>()
function tabFor(tab: StudyTab): ComponentType {
    const cached = tabCache.get(tab)
    if (cached) return cached
    const component = lazy(tabComponents[tab] ?? tabComponents.brief)
    tabCache.set(tab, component)
    return component
}

export default function StudyPage(): JSX.Element {
    const { t } = useTranslation()
    useMountedLogic(studyLogic)
    const { study, studyLoading, studyId, activeTab } = useValues(studyLogic)
    const { push } = useActions(router)

    if (!studyId) {
        return <div className="text-merism-text-muted">—</div>
    }

    const TabComponent = tabFor((activeTab as StudyTab) || "brief")

    const TABS: TabRailItem[] = [
        { value: "brief", label: t("study.tabs.brief") },
        { value: "outline", label: t("study.tabs.outline") },
        { value: "screener", label: t("study.tabs.screener") },
        { value: "stimuli", label: t("study.tabs.stimuli") },
        { value: "recruit", label: t("study.tabs.recruit") },
        { value: "report", label: t("study.tabs.report") },
        { value: "sessions", label: t("study.tabs.sessions") },
        { value: "settings", label: t("study.tabs.settings") },
    ]

    // ── Title row: name + kebab + status pill ─────────────
    const titleNode = study ? (
        <span className="flex items-center gap-2">
            <span>
                {study.name || t("common.draft")}
                {study.status === "draft" && (
                    <span className="ml-2 font-display text-merism-text-subtle">
                        ({t(`studies.status.${study.status}`, { defaultValue: study.status })})
                    </span>
                )}
            </span>
            <StudyKebabMenu />
        </span>
    ) : (
        (studyLoading ? t("common.loading") : "—")
    )

    // ── Status: only the lifecycle pill (mode goes inline w/ actions
    //    on the right, like the reference's "PAUSED" pill).
    const statusNode = study && (
        <Tag variant={statusVariantFor(study.status)} case="capitalize">
            {t(`studies.status.${study.status}`, { defaultValue: study.status })}
        </Tag>
    )

    // ── Right-side actions: secondary + primary, mirroring the
    //    reference's "Add section randomization" + "Test Interview ▾".
    const actionsNode = (
        <div className="flex items-center gap-2">
            <Button
                size="sm"
                variant="ghost"
                onClick={() => {/* TODO: section randomization */}}
            >
                {t("study.actions.add_section_randomization")}
            </Button>
            <Button
                size="sm"
                variant="primary"
                iconLeft={<Play className="h-3.5 w-3.5" />}
                onClick={() => {/* TODO: test interview launcher */}}
            >
                {t("study.actions.test_interview")}
            </Button>
        </div>
    )

    return (
        <div className="flex flex-col gap-8">
            <PageTopBar
                eyebrow={`${t("studies.title")} · ${studyId.slice(0, 8)}`}
                title={titleNode}
                status={statusNode}
                actions={actionsNode}
                lede={study?.research_goal || undefined}
                tabs={TABS}
                activeTab={activeTab}
                onTabChange={(value) => push(urls.study(studyId, value as StudyTab))}
            />

            <Suspense fallback={<div className="text-merism-text-muted">{t("common.loading")}</div>}>
                <TabComponent />
            </Suspense>
        </div>
    )
}

// ── Status pill colour mapping ─────────────────────────────

function statusVariantFor(
    status: string,
): "accent" | "neutral" | "outline" {
    if (status === "recruiting" || status === "active") return "accent"
    if (status === "draft" || status === "ready") return "neutral"
    return "outline"
}

// ── Kebab menu next to the title ───────────────────────────

interface MenuItemConfig {
    label: ReactNode
    icon?: ReactNode
    onClick: () => void
    danger?: boolean
}

/**
 * Title-adjacent kebab — Rename / Duplicate / Share / Archive / Delete.
 *
 * Sits inline with the title (matching the three-dot dot-stack glyph
 * in the Outset.ai reference) so the affordance is read as
 * "actions on this study", not generic page chrome.
 */
function StudyKebabMenu(): JSX.Element {
    const { t } = useTranslation()
    const items: MenuItemConfig[] = [
        {
            label: t("study.actions.rename"),
            icon: <Pencil className="h-4 w-4" />,
            onClick: () => {/* TODO: open rename dialog */},
        },
        {
            label: t("study.actions.duplicate"),
            icon: <Copy className="h-4 w-4" />,
            onClick: () => {/* TODO: duplicate study */},
        },
        {
            label: t("study.actions.share"),
            icon: <Share2 className="h-4 w-4" />,
            onClick: () => {/* TODO: open share dialog */},
        },
        {
            label: t("study.actions.archive"),
            icon: <Archive className="h-4 w-4" />,
            onClick: () => {/* TODO: archive study */},
        },
        {
            label: t("study.actions.delete"),
            icon: <Trash2 className="h-4 w-4" />,
            danger: true,
            onClick: () => {/* TODO: delete study */},
        },
    ]
    return (
        <InlineMenu
            ariaLabel={t("study.actions.menu") as string}
            trigger={<MoreHorizontal className="h-4 w-4" />}
            triggerClassName="inline-flex h-7 w-7 items-center justify-center rounded-merism-md text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
            items={items}
        />
    )
}

// ── Tiny inline menu (extracted from outline/InlineMenu) ───
//
// Not lifted to lib/merism yet — that's a follow-up once we agree
// on a final API and a11y model. Keeps StudyPage self-contained
// while we iterate on the masthead.

function InlineMenu({
    trigger,
    items,
    align = "right",
    triggerClassName,
    ariaLabel,
}: {
    trigger: ReactNode
    items: MenuItemConfig[]
    align?: "left" | "right"
    triggerClassName?: string
    ariaLabel?: string
}): JSX.Element {
    const [open, setOpen] = useState(false)
    const rootRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        if (!open) return
        const handlePointerDown = (event: PointerEvent): void => {
            if (
                rootRef.current &&
                event.target instanceof Node &&
                !rootRef.current.contains(event.target)
            ) {
                setOpen(false)
            }
        }
        const handleKeyDown = (event: KeyboardEvent): void => {
            if (event.key === "Escape") setOpen(false)
        }
        document.addEventListener("pointerdown", handlePointerDown)
        document.addEventListener("keydown", handleKeyDown)
        return () => {
            document.removeEventListener("pointerdown", handlePointerDown)
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [open])

    return (
        <div ref={rootRef} className="relative inline-flex">
            <button
                type="button"
                aria-label={ariaLabel}
                aria-haspopup="menu"
                aria-expanded={open}
                onClick={() => setOpen((next) => !next)}
                className={triggerClassName}
            >
                {trigger}
            </button>
            {open && (
                <div
                    role="menu"
                    className={cn(
                        "absolute top-full z-30 mt-1 min-w-[12rem] overflow-hidden rounded-merism-lg border border-[color:var(--merism-hairline)] bg-merism-surface p-1 shadow-merism-pop",
                        align === "right" ? "right-0" : "left-0",
                    )}
                >
                    {items.map((item, idx) => (
                        <button
                            key={idx}
                            type="button"
                            role="menuitem"
                            onClick={() => {
                                setOpen(false)
                                item.onClick()
                            }}
                            className={cn(
                                "flex w-full items-center gap-2 rounded-merism-md px-3 py-2 text-left text-sm transition-colors hover:bg-merism-bg-subtle",
                                item.danger && "text-merism-danger",
                            )}
                        >
                            <span className="text-merism-text-subtle">{item.icon}</span>
                            <span>{item.label}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}
