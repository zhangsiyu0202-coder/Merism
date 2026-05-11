import { cn } from "../utils/cn"
import { Tabs, TabsList, TabsTrigger } from "../primitives/Tabs"

export interface TabRailItem {
    value: string
    label: string
    disabled?: boolean
}

export interface TabRailProps {
    tabs: TabRailItem[]
    activeTab: string
    onTabChange: (value: string) => void
    className?: string
}

/**
 * TabRail — tabs-only strip (no title, no actions).
 *
 * Pair with :pattern:`PageHeading` on pages where the display title
 * is rendered separately for editorial effect. For simpler pages that
 * want title + tabs in one block, use :pattern:`TabBar` instead.
 */
export function TabRail({ tabs, activeTab, onTabChange, className }: TabRailProps): JSX.Element {
    return (
        <Tabs
            value={activeTab}
            onValueChange={onTabChange}
            className={cn("w-full", className)}
        >
            <TabsList>
                {tabs.map((t) => (
                    <TabsTrigger key={t.value} value={t.value} disabled={t.disabled}>
                        {t.label}
                    </TabsTrigger>
                ))}
            </TabsList>
        </Tabs>
    )
}
