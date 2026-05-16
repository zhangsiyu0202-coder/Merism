import { useActions, useValues } from "kea"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
    Button,
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogTitle,
    Input,
    Select,
} from "~/lib/merism"

import { studiesLogic } from "./studiesLogic"

/**
 * CreateStudyDialog — the "新建研究" entry point.
 *
 * Flow: user clicks "+ New study" anywhere in the app →
 * this dialog opens → user fills in research goal, study type,
 * and optional context → submit → AI generates Discussion Guide →
 * navigates to Guide tab with content already populated.
 *
 * Fields:
 *   - Research goal (required): "What do you want to learn?"
 *   - Study type: Discovery / Concept Testing
 *   - Context (optional): background info for the AI
 */

const STUDY_TYPE_OPTIONS = [
    { value: "discovery", label: "Discovery" },
    { value: "concept_testing", label: "Concept Testing" },
] as const

export interface CreateStudyDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function CreateStudyDialog({
    open,
    onOpenChange,
}: CreateStudyDialogProps): JSX.Element {
    const { t } = useTranslation()
    const { createStudy } = useActions(studiesLogic)
    const { newStudyLoading } = useValues(studiesLogic)

    const [researchGoal, setResearchGoal] = useState("")
    const [studyType, setStudyType] = useState("discovery")
    const [context, setContext] = useState("")

    const canSubmit = researchGoal.trim().length > 0 && !newStudyLoading

    const handleSubmit = (): void => {
        if (!canSubmit) return
        createStudy({
            research_goal: researchGoal.trim(),
            study_type: studyType,
            context: context.trim(),
        })
        onOpenChange(false)
        // Reset form
        setResearchGoal("")
        setStudyType("discovery")
        setContext("")
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-xl">
                <DialogTitle className="font-display text-xl font-[500] text-merism-text">
                    {t("create_study.title")}
                </DialogTitle>
                <DialogDescription className="mt-1 text-merism-body-sm text-merism-text-muted">
                    {t("create_study.description")}
                </DialogDescription>

                <div className="mt-6 flex flex-col gap-5">
                    {/* Research Goal */}
                    <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium text-merism-text">
                            {t("create_study.research_goal_label")}
                        </label>
                        <textarea
                            value={researchGoal}
                            onChange={(e) => setResearchGoal(e.target.value)}
                            rows={3}
                            placeholder={t("create_study.research_goal_placeholder")}
                            className={
                                "w-full resize-none rounded-merism-lg border border-[color:var(--merism-hairline)] " +
                                "bg-merism-surface p-3 text-sm text-merism-text outline-none " +
                                "placeholder:text-merism-text-muted " +
                                "focus:border-merism-accent-outline focus:ring-2 focus:ring-merism-accent-outline/40"
                            }
                            autoFocus
                        />
                        <span className="text-xs text-merism-text-muted">
                            {t("create_study.research_goal_hint")}
                        </span>
                    </div>

                    {/* Study Type */}
                    <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium text-merism-text">
                            {t("create_study.study_type_label")}
                        </label>
                        <Select
                            value={studyType}
                            onValueChange={setStudyType}
                            options={STUDY_TYPE_OPTIONS.map((opt) => ({
                                value: opt.value,
                                label: t(`create_study.study_type.${opt.value}`),
                            }))}
                            size="sm"
                        />
                    </div>

                    {/* Context for AI */}
                    <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium text-merism-text">
                            {t("create_study.context_label")}
                        </label>
                        <textarea
                            value={context}
                            onChange={(e) => setContext(e.target.value)}
                            rows={3}
                            placeholder={t("create_study.context_placeholder")}
                            className={
                                "w-full resize-none rounded-merism-lg border border-[color:var(--merism-hairline)] " +
                                "bg-merism-surface p-3 text-sm text-merism-text outline-none " +
                                "placeholder:text-merism-text-muted " +
                                "focus:border-merism-accent-outline focus:ring-2 focus:ring-merism-accent-outline/40"
                            }
                        />
                        <span className="text-xs text-merism-text-muted">
                            {t("create_study.context_hint")}
                        </span>
                    </div>
                </div>

                {/* Actions */}
                <div className="mt-8 flex items-center justify-end gap-3">
                    <DialogClose asChild>
                        <Button variant="ghost" size="sm">
                            {t("common.cancel")}
                        </Button>
                    </DialogClose>
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={handleSubmit}
                        disabled={!canSubmit}
                        isLoading={newStudyLoading}
                    >
                        {t("create_study.submit")}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}
