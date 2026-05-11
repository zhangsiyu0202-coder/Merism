import { useActions, useMountedLogic, useValues } from "kea"
import { useEffect } from "react"

import {
    Button,
    Input,
    OrderedList,
    SettingsSection,
} from "~/lib/merism"
import { studyLogic } from "~/features/studies/studyLogic"

import { studySettingsLogic } from "./studySettingsLogic"

/**
 * SettingsTab — the "Project settings" page.
 *
 * Layout:
 *   H1 "Project settings"
 *   ├── SettingsSection "Project details"  (study.name)
 *   └── SettingsSection "Research objectives"  (study.research_objectives)
 *
 * Each section is independently editable. Clicking Edit on a section
 * flips the body into input / OrderedList edit mode and reveals a
 * Save / Cancel pair below. Save PATCHes the study + refreshes the
 * parent ``studyLogic``.
 *
 * Everything here is strictly left-aligned and vertical, per the
 * Outset.ai settings-page reference.
 */
export default function SettingsTab(): JSX.Element {
    useMountedLogic(studySettingsLogic)
    const { study, studyLoading } = useValues(studyLogic)
    const {
        editingSection,
        draftName,
        draftObjectives,
        isSavingSettings,
    } = useValues(studySettingsLogic)
    const {
        startEdit,
        cancelEdit,
        setDraftName,
        setDraftObjectives,
        saveAll,
        hydrateFromStudy,
    } = useActions(studySettingsLogic)

    // Hydrate drafts from the loaded study (runs once + on change).
    useEffect(() => {
        if (study) {
            hydrateFromStudy(study)
        }
    }, [study, hydrateFromStudy])

    if (!study) {
        return (
            <div className="text-merism-text-muted">
                {studyLoading ? "Loading settings…" : "Study not found."}
            </div>
        )
    }

    const editingDetails = editingSection === "details"
    const editingObjectives = editingSection === "objectives"

    return (
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-[var(--spacing-merism-section-y)]">
            <h1 className="text-merism-headline font-display font-[450] text-merism-text">
                Project settings
            </h1>

            {/* ── Section 1: Project details ───────────────────── */}
            <SettingsSection
                title="Project details"
                onEdit={editingDetails ? undefined : () => startEdit("details")}
            >
                {editingDetails ? (
                    <Input
                        value={draftName}
                        onChange={(e) => setDraftName(e.target.value)}
                        placeholder="Study name"
                        autoFocus
                    />
                ) : (
                    <>
                        <p className="text-merism-body text-merism-text">
                            {study.name || "Untitled study"}
                        </p>
                        {study.research_goal && (
                            <p className="mt-1 text-merism-body-sm text-merism-text-muted">
                                {study.research_goal}
                            </p>
                        )}
                    </>
                )}
                {editingDetails && (
                    <EditActions
                        busy={isSavingSettings}
                        onSave={saveAll}
                        onCancel={cancelEdit}
                    />
                )}
            </SettingsSection>

            {/* ── Section 2: Research objectives ─────────────────── */}
            <SettingsSection
                title="Research objectives"
                description="The concrete questions this study aims to answer."
                onEdit={
                    editingObjectives ? undefined : () => startEdit("objectives")
                }
            >
                <OrderedList
                    items={
                        editingObjectives
                            ? draftObjectives
                            : study.research_objectives ?? []
                    }
                    onChange={editingObjectives ? setDraftObjectives : undefined}
                    addLabel="Add objective"
                    placeholder="e.g. Understand what was confusing about the checkout flow…"
                />
                {!editingObjectives &&
                    (study.research_objectives?.length ?? 0) === 0 && (
                        <p className="text-merism-body-sm text-merism-text-subtle">
                            No objectives defined yet. Click Edit to add some.
                        </p>
                    )}
                {editingObjectives && (
                    <EditActions
                        busy={isSavingSettings}
                        onSave={saveAll}
                        onCancel={cancelEdit}
                    />
                )}
            </SettingsSection>
        </div>
    )
}

/**
 * Save / Cancel action pair — appears below any section that's in
 * edit mode. Save is a primary Button; Cancel is a ghost.
 */
function EditActions({
    busy,
    onSave,
    onCancel,
}: {
    busy: boolean
    onSave: () => void
    onCancel: () => void
}): JSX.Element {
    return (
        <div className="mt-4 flex items-center gap-2">
            <Button
                type="button"
                size="sm"
                variant="primary"
                onClick={onSave}
                isLoading={busy}
            >
                Save
            </Button>
            <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={onCancel}
                disabled={busy}
            >
                Cancel
            </Button>
        </div>
    )
}
