import { arrayMove } from "@dnd-kit/sortable"
import { actions, afterMount, connect, kea, listeners, path, reducers } from "kea"
import { loaders } from "kea-loaders"

import { studyLogic } from "~/features/studies/studyLogic"
import { api } from "~/lib/api"

import type { outlineEditorLogicType } from "./outlineEditorLogicType"

export type ProbePolicy = "none" | "light" | "deep"
export type OutlineSectionScope = "global" | "per_concept" | "comparative"

/**
 * One question inside an Outline section.
 *
 * Sprint 1 schema (replaces followup_depth + probe_directions):
 *   - ``intent``        what signal this question should yield + any
 *                       hints for AI probing direction
 *   - ``probe_policy``  none / light / deep — enforced server-side
 *   - ``max_probes``    1-5 hard cap on follow-ups
 */
export interface OutlineQuestion {
    id: string
    text: string
    intent: string
    probe_policy: ProbePolicy
    max_probes: number
    linked_stimulus_ids?: string[]
    required?: boolean
}

/** A section groups questions (warmup / core / closing / …). */
export interface OutlineSection {
    id: string
    title: string
    scope: OutlineSectionScope
    concept_block_id: string | null
    questions: OutlineQuestion[]
}

/** Fresh starter outline. Each question ships sensible defaults. */
const DEFAULT_SECTIONS: OutlineSection[] = [
    {
        id: "warmup",
        title: "Warm-up",
        scope: "global",
        concept_block_id: null,
        questions: [
            {
                id: "warmup-1",
                text: "To start, tell me a bit about how you've been using the product.",
                intent:
                    "Get the participant talking comfortably. Surface any top-of-mind friction so later probes can revisit it.",
                probe_policy: "light",
                max_probes: 2,
            },
        ],
    },
    {
        id: "core",
        title: "Core",
        scope: "global",
        concept_block_id: null,
        questions: [
            {
                id: "core-1",
                text: "Walk me through the last time you tried to do X.",
                intent:
                    "Capture a concrete, recent story — the specific moment, what they tried, what happened, how it felt.",
                probe_policy: "deep",
                max_probes: 3,
            },
        ],
    },
    {
        id: "closing",
        title: "Closing",
        scope: "global",
        concept_block_id: null,
        questions: [
            {
                id: "closing-1",
                text: "If you had a magic wand, what would you change first?",
                intent: "Surface the participant's own priorities — unbiased by anything we showed.",
                probe_policy: "light",
                max_probes: 2,
            },
        ],
    },
]

export const outlineEditorLogic = kea<outlineEditorLogicType>([
    path(["features", "studies", "tabs", "outline", "outlineEditorLogic"]),

    connect(() => ({ values: [studyLogic, ["studyId"]] })),

    actions({
        loadSections: (sections: OutlineSection[]) => ({ sections }),
        moveQuestion: (sectionId: string, fromIndex: number, toIndex: number) => ({
            sectionId,
            fromIndex,
            toIndex,
        }),
        moveSection: (fromIndex: number, toIndex: number) => ({ fromIndex, toIndex }),
        addQuestion: (sectionId: string) => ({ sectionId }),
        updateQuestionText: (sectionId: string, questionId: string, text: string) => ({
            sectionId,
            questionId,
            text,
        }),
        updateQuestionIntent: (sectionId: string, questionId: string, intent: string) => ({
            sectionId,
            questionId,
            intent,
        }),
        updateQuestionProbePolicy: (
            sectionId: string,
            questionId: string,
            policy: ProbePolicy,
        ) => ({ sectionId, questionId, policy }),
        updateQuestionMaxProbes: (
            sectionId: string,
            questionId: string,
            maxProbes: number,
        ) => ({ sectionId, questionId, maxProbes }),
        toggleQuestionRequired: (sectionId: string, questionId: string) => ({
            sectionId,
            questionId,
        }),
        removeQuestion: (sectionId: string, questionId: string) => ({
            sectionId,
            questionId,
        }),
        setSectionScope: (
            sectionId: string,
            scope: OutlineSectionScope,
            conceptBlockId: string | null = null,
        ) => ({
            sectionId,
            scope,
            conceptBlockId,
        }),
    }),

    reducers({
        sections: [
            DEFAULT_SECTIONS,
            {
                loadSections: (_, { sections }) => sections,
                moveQuestion: (state, { sectionId, fromIndex, toIndex }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: arrayMove(s.questions, fromIndex, toIndex),
                              }
                            : s,
                    ),
                moveSection: (state, { fromIndex, toIndex }) =>
                    arrayMove(state, fromIndex, toIndex),
                addQuestion: (state, { sectionId }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: [
                                      ...s.questions,
                                      {
                                          id: `${sectionId}-${s.questions.length + 1}`,
                                          text: "",
                                          intent: "",
                                          probe_policy: "light" as ProbePolicy,
                                          max_probes: 3,
                                      },
                                  ],
                              }
                            : s,
                    ),
                updateQuestionText: (state, { sectionId, questionId, text }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: s.questions.map((q) =>
                                      q.id === questionId ? { ...q, text } : q,
                                  ),
                              }
                            : s,
                    ),
                updateQuestionIntent: (state, { sectionId, questionId, intent }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: s.questions.map((q) =>
                                      q.id === questionId ? { ...q, intent } : q,
                                  ),
                              }
                            : s,
                    ),
                updateQuestionProbePolicy: (state, { sectionId, questionId, policy }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: s.questions.map((q) =>
                                      q.id === questionId
                                          ? { ...q, probe_policy: policy }
                                          : q,
                                  ),
                              }
                            : s,
                    ),
                updateQuestionMaxProbes: (state, { sectionId, questionId, maxProbes }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: s.questions.map((q) =>
                                      q.id === questionId
                                          ? {
                                                ...q,
                                                max_probes: Math.max(
                                                    1,
                                                    Math.min(5, maxProbes),
                                                ),
                                            }
                                          : q,
                                  ),
                              }
                            : s,
                    ),
                toggleQuestionRequired: (state, { sectionId, questionId }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: s.questions.map((q) =>
                                      q.id === questionId
                                          ? { ...q, required: !q.required }
                                          : q,
                                  ),
                              }
                            : s,
                    ),
                removeQuestion: (state, { sectionId, questionId }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  questions: s.questions.filter((q) => q.id !== questionId),
                              }
                            : s,
                    ),
                setSectionScope: (state, { sectionId, scope, conceptBlockId }) =>
                    state.map((s) =>
                        s.id === sectionId
                            ? {
                                  ...s,
                                  scope,
                                  concept_block_id:
                                      scope === "per_concept" ? conceptBlockId : null,
                              }
                            : s,
                    ),
            },
        ],
    }),
    loaders(({ values }) => ({
        loadedGuide: [
            null as { id: string; sections: OutlineSection[] } | null,
            {
                loadGuide: async () => {
                    const studyId = values.studyId
                    if (!studyId) return null
                    const resp = await api.list<{ id: string; sections: OutlineSection[]; is_current: boolean }>(
                        "/api/guides/",
                        { study: studyId, is_current: true },
                    )
                    const guide = resp.results?.[0]
                    return guide ? { id: guide.id, sections: guide.sections ?? [] } : null
                },
                saveGuide: async () => {
                    const studyId = values.studyId
                    if (!studyId) return null
                    const existing = values.loadedGuide
                    if (existing?.id) {
                        await api.update(`/api/guides/${existing.id}/`, {
                            sections: values.sections,
                        })
                        return { id: existing.id, sections: values.sections }
                    }
                    const created = await api.create<{ id: string }>("/api/guides/", {
                        study: studyId,
                        sections: values.sections,
                        is_current: true,
                    })
                    return { id: created.id, sections: values.sections }
                },
            },
        ],
    })),

    listeners(({ actions: a }) => ({
        loadGuideSuccess: ({ loadedGuide }) => {
            if (loadedGuide?.sections && loadedGuide.sections.length > 0) {
                a.loadSections(loadedGuide.sections)
            }
        },
    })),

    afterMount(({ actions, values }) => {
        if (values.studyId) actions.loadGuide()
    }),
])
