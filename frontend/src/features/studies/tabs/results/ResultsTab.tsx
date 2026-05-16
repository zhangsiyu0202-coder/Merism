import { useValues } from "kea"
import { BarChart3 } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Card } from "~/lib/merism"
import { studyLogic } from "~/features/studies/studyLogic"

/**
 * ResultsTab — analysis & insights after interviews complete (Outset.ai "Results" tab).
 *
 * Placeholder for now. Will show:
 *   - Themes & codes extracted by AI
 *   - Quantitative breakdown (ratings, sentiment)
 *   - Key quotes & highlights
 *   - Export options
 */
export default function ResultsTab(): JSX.Element {
    const { t } = useTranslation()
    const { study } = useValues(studyLogic)

    if (!study) {
        return <div className="text-merism-text-muted">{t("common.loading")}</div>
    }

    return (
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 py-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-merism-accent-soft">
                <BarChart3 className="h-7 w-7 text-merism-accent" />
            </div>
            <h2 className="text-xl font-semibold text-merism-text">
                {t("results.empty_title")}
            </h2>
            <p className="max-w-md text-sm text-merism-text-muted">
                {t("results.empty_body")}
            </p>
        </div>
    )
}
