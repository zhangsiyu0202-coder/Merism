import {
  actions,
  connect,
  kea,
  listeners,
  path,
  reducers,
  selectors,
} from "kea";
import { loaders } from "kea-loaders";

import { api } from "~/lib/api";
import { studyLogic } from "~/features/studies/studyLogic";
import type { Study } from "~/types";

import type { studySettingsLogicType } from "./studySettingsLogicType";

/**
 * studySettingsLogic — edit state for the Project settings tab.
 *
 * Surfaces on the page today (2026-05-24):
 *   - Project details (``name``)
 *   - Research goal     (the bullet list of goals — backed by
 *                        ``research_objectives`` for shape and
 *                        ``research_goal`` for the AI prompt anchor)
 *
 * **Why one list section feeds two backend fields**: per PRODUCT.md §1
 * ``research_goal: TextField`` is the single anchor every AI step reads
 * (guide / moderator prompt / analysis / report), and
 * ``research_objectives: list[str]`` is the supplementary UI-facing
 * list. We expose only **one** "Research goal" list to researchers and
 * mirror it into both fields on save: ``research_objectives`` gets the
 * raw list, ``research_goal`` gets the same items joined with
 * ``\\n`` + numbering so the AI prompt has a clean multi-line goal.
 *
 * This avoids the historical bug where two visible fields drifted
 * (or got copy-pasted with the same content) and confused researchers.
 */

export type SettingsSection = "details" | "goals" | null;

function joinGoals(items: string[]): string {
  return items
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map((s, i) => `${i + 1}. ${s}`)
    .join("\n");
}

export const studySettingsLogic = kea<studySettingsLogicType>([
  path(["features", "studies", "tabs", "settings", "studySettingsLogic"]),

  connect(() => ({
    values: [studyLogic, ["study", "studyId"]],
    actions: [studyLogic, ["loadStudy"]],
  })),

  actions({
    startEdit: (section: Exclude<SettingsSection, null>) => ({ section }),
    cancelEdit: true,

    setDraftName: (name: string) => ({ name }),
    setDraftGoals: (goals: string[]) => ({ goals }),

    hydrateFromStudy: (study: Study) => ({ study }),
  }),

  reducers({
    editingSection: [
      null as SettingsSection,
      {
        startEdit: (_, { section }) => section,
        cancelEdit: () => null,
        saveSuccess: () => null,
      },
    ],
    draftName: [
      "",
      {
        setDraftName: (_, { name }) => name,
        hydrateFromStudy: (_, { study }) => study.name,
      },
    ],
    draftGoals: [
      [] as string[],
      {
        setDraftGoals: (_, { goals }) => goals,
        hydrateFromStudy: (_, { study }) => study.research_objectives ?? [],
      },
    ],
  }),

  loaders(({ values, actions }) => ({
    saveSuccess: [
      false,
      {
        saveAll: async () => {
          const id = values.studyId;
          if (!id) return false;
          const study = values.study;
          const payload: Partial<
            Pick<Study, "name" | "research_goal" | "research_objectives">
          > = {};
          if (study && values.draftName !== study.name) {
            payload.name = values.draftName;
          }
          // Mirror the goal list into both fields:
          //  - research_objectives: the raw list (UI canonical form)
          //  - research_goal:       the same list joined into a numbered
          //    multi-line string so the AI prompt has a single field to
          //    read (PRODUCT.md §1 — North Star).
          const goals = values.draftGoals
            .map((s) => s.trim())
            .filter((s) => s.length > 0);
          payload.research_objectives = goals;
          payload.research_goal = joinGoals(goals);
          await api.update<Study>(`/api/studies/${id}/`, payload);
          actions.loadStudy();
          return true;
        },
      },
    ],
  })),

  listeners(({ actions }) => ({
    saveSuccessSuccess: () => {
      actions.cancelEdit();
    },
  })),

  selectors({
    isEditing: [(s) => [s.editingSection], (section) => section !== null],
    isSavingSettings: [(s) => [s.saveSuccessLoading], (loading) => loading],
  }),
]);
