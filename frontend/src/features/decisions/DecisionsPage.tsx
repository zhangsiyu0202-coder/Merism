import { useState } from "react"
import { useTranslation } from "react-i18next"

import { Illustration, PageTopBar } from "~/lib/merism"

type DecisionsTab = "open" | "closed" | "linked"

const TABS = [
    { value: "open", label: "Open" },
    { value: "closed", label: "Closed" },
    { value: "linked", label: "Linked" },
]

/**
 * DecisionsPage — PRODUCT.md §3.10.
 */
export default function DecisionsPage(): JSX.Element {
    const { t } = useTranslation()
    const [tab, setTab] = useState<DecisionsTab>("open")

    return (
        <div className="flex flex-col gap-8">
            <PageTopBar
                title={t("decisions.title")}
                lede={t("decisions.lede")}
                tabs={TABS}
                activeTab={tab}
                onTabChange={(v) => setTab(v as DecisionsTab)}
            />
            <EmptyState />
        </div>
    )
}

function EmptyState(): JSX.Element {
    const { t } = useTranslation()
    return (
        <div className="mx-auto flex max-w-md flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-12 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <Illustration name="flag" size="xl" className="text-merism-text" />
            <div className="flex flex-col gap-2">
                <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
                    {t("decisions.empty_title")}
                </h2>
                <p className="text-merism-body text-merism-text-muted">
                    {t("decisions.empty_body")}
                </p>
            </div>
        </div>
    )
}
