import { useActions, useMountedLogic, useValues } from "kea";
import { useEffect } from "react";

import { Button, Input, OrderedList, SettingsSection } from "~/lib/merism";
import { studyLogic } from "~/features/studies/studyLogic";

import { studySettingsLogic } from "./studySettingsLogic";

/**
 * SettingsTab — the "Project settings" page.
 *
 * Two sections:
 *   1. Project details — ``study.name``
 *   2. Research goal   — bullet list of goals. Backed by both
 *                        ``research_objectives`` (raw list, UI form)
 *                        and ``research_goal`` (joined + numbered
 *                        string, AI prompt anchor) — see
 *                        ``studySettingsLogic`` for the merge.
 *
 * Each section is independently editable. Clicking Edit flips the
 * body into edit mode and reveals a Save / Cancel pair below. Save
 * PATCHes the study and refreshes ``studyLogic``.
 */
export default function SettingsTab(): JSX.Element {
  useMountedLogic(studySettingsLogic);
  const { study, studyLoading } = useValues(studyLogic);
  const { editingSection, draftName, draftGoals, isSavingSettings } =
    useValues(studySettingsLogic);
  const {
    startEdit,
    cancelEdit,
    setDraftName,
    setDraftGoals,
    saveAll,
    hydrateFromStudy,
  } = useActions(studySettingsLogic);

  // Hydrate drafts from the loaded study (runs once + on change).
  useEffect(() => {
    if (study) {
      hydrateFromStudy(study);
    }
  }, [study, hydrateFromStudy]);

  if (!study) {
    return (
      <div className="text-merism-text-muted">
        {studyLoading ? "Loading settings…" : "Study not found."}
      </div>
    );
  }

  const editingDetails = editingSection === "details";
  const editingGoals = editingSection === "goals";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-[var(--spacing-merism-section-y)]">
      <h1 className="text-merism-headline font-display font-[450] text-merism-text">
        Project settings
      </h1>

      {/* ── Section 1: Project details (name) ───────────── */}
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
          <p className="text-merism-body text-merism-text">
            {study.name || "Untitled study"}
          </p>
        )}
        {editingDetails && (
          <EditActions
            busy={isSavingSettings}
            onSave={saveAll}
            onCancel={cancelEdit}
          />
        )}
      </SettingsSection>

      {/* ── Section 2: Research goal (the bullet list) ───── */}
      {/* The North Star (PRODUCT.md §1). Anchors every AI step —
          guide generation, moderator prompt, session analysis,
          custom reports. The list is also persisted as
          ``research_goal`` (joined + numbered) so the AI prompt
          has a single text field to read. */}
      <SettingsSection
        title="Research goal"
        description="The questions this study is trying to answer. Anchors every AI step — guide generation, moderator prompt, analysis, reports."
        onEdit={editingGoals ? undefined : () => startEdit("goals")}
      >
        <OrderedList
          items={
            editingGoals ? draftGoals : (study.research_objectives ?? [])
          }
          onChange={editingGoals ? setDraftGoals : undefined}
          addLabel="Add goal"
          placeholder="e.g. 了解用户在前 5 分钟里做了什么、在哪里出现「啊哈时刻」"
        />
        {!editingGoals && (study.research_objectives?.length ?? 0) === 0 && (
          <p className="text-merism-body-sm text-merism-text-subtle">
            No goals defined yet. Click Edit to add some.
          </p>
        )}
        {editingGoals && (
          <EditActions
            busy={isSavingSettings}
            onSave={saveAll}
            onCancel={cancelEdit}
          />
        )}
      </SettingsSection>
    </div>
  );
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
  busy: boolean;
  onSave: () => void;
  onCancel: () => void;
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
  );
}
