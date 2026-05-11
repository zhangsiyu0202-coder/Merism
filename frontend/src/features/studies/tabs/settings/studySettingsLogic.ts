import { actions, connect, kea, listeners, path, reducers, selectors } from "kea"
import { loaders } from "kea-loaders"

import { api } from "~/lib/api"
import { studyLogic } from "~/features/studies/studyLogic"
import type { Study } from "~/types"

import type { studySettingsLogicType } from './studySettingsLogicType'

/**
 * studySettingsLogic — edit state for the Project settings tab.
 *
 * Surfaces on the page today:
 *   - Project details (``name``)
 *   - Research objectives (``research_objectives: string[]``)
 *
 * Each section has its own draft reducer + isolated edit state. A
 * single ``saveAll`` action PATCHes ``/api/studies/:id/`` with only
 * the fields that actually changed and reloads ``studyLogic`` on
 * success so the outer page reflects the new values immediately.
 */

export type SettingsSection = "details" | "objectives" | null

export const studySettingsLogic = kea<studySettingsLogicType>([
    path(["features", "studies", "tabs", "settings", "studySettingsLogic"]),

    connect(() => ({
        values: [studyLogic, ["study", "studyId"]],
        actions: [studyLogic, ["loadStudy"]],
    })),

    actions({
        // Section-level edit-mode toggles
        startEdit: (section: Exclude<SettingsSection, null>) => ({ section }),
        cancelEdit: true,

        // Draft-field setters
        setDraftName: (name: string) => ({ name }),
        setDraftObjectives: (objectives: string[]) => ({ objectives }),

        // Hydrate draft from the loaded study when needed
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
        draftObjectives: [
            [] as string[],
            {
                setDraftObjectives: (_, { objectives }) => objectives,
                hydrateFromStudy: (_, { study }) => study.research_objectives ?? [],
            },
        ],
    }),

    loaders(({ values, actions }) => ({
        saveSuccess: [
            false,
            {
                saveAll: async () => {
                    const id = values.studyId
                    if (!id) return false
                    const study = values.study
                    const payload: Partial<
                        Pick<Study, "name" | "research_objectives">
                    > = {}
                    if (study && values.draftName !== study.name) {
                        payload.name = values.draftName
                    }
                    // Always send objectives when editing either section — the
                    // serializer filters out blank lines, and comparing arrays
                    // by reference is noisy.
                    payload.research_objectives = values.draftObjectives
                    await api.update<Study>(`/api/studies/${id}/`, payload)
                    actions.loadStudy()
                    return true
                },
            },
        ],
    })),

    listeners(({ actions }) => ({
        saveSuccessSuccess: () => {
            // Reset the one-shot flag; editingSection is handled by reducer.
            actions.cancelEdit()
        },
    })),

    selectors({
        isEditing: [(s) => [s.editingSection], (section) => section !== null],
        isSavingSettings: [(s) => [s.saveSuccessLoading], (loading) => loading],
    }),
])
