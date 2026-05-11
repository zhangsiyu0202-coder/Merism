import { type ReactNode } from "react"

import { StatusDot, type StatusDotProps } from "../primitives/StatusDot"
import { Tabs, TabsList, TabsTrigger } from "../primitives/Tabs"
import { cn } from "../utils/cn"

export interface TabDescriptor {
    value: string
    label: string
    disabled?: boolean
}

export interface TabBarProps {
    breadcrumb?: ReactNode
    title: ReactNode
    statusDot?: Omit<StatusDotProps, "className">
    actions?: ReactNode
    tabs: TabDescriptor[]
    activeTab: string
    onTabChange: (value: string) => void
    children?: ReactNode
    className?: string
}

/**
 * TabBar — header row for multi-tab pages (Study detail, Report, Settings).
 *
 *   [breadcrumb]   [title] [●status]                      [actions]
 *   ─────────────────────────────────────────────────────────────────
 *   [tab] [tab] [tab] …
 *
 * Uses the Tabs primitive for keyboard / ARIA behaviour. Always controlled —
 * the caller owns `activeTab`.
 */
export function TabBar({
    breadcrumb,
    title,
    statusDot,
    actions,
    tabs,
    activeTab,
    onTabChange,
    children,
    className,
}: TabBarProps) {
    return (
        <div className={cn("flex flex-col gap-3", className)}>
            <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 flex-col gap-1">
                    {breadcrumb && (
                        <div className="text-xs text-merism-text-muted">{breadcrumb}</div>
                    )}
                    <div className="flex items-center gap-2">
                        <h1 className="truncate font-merism-display text-xl font-semibold text-merism-text">
                            {title}
                        </h1>
                        {statusDot && <StatusDot {...statusDot} />}
                    </div>
                </div>
                {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
            </div>

            <Tabs value={activeTab} onValueChange={onTabChange}>
                <TabsList>
                    {tabs.map((t) => (
                        <TabsTrigger key={t.value} value={t.value} disabled={t.disabled}>
                            {t.label}
                        </TabsTrigger>
                    ))}
                </TabsList>
                {children}
            </Tabs>
        </div>
    )
}
