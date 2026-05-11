import { arrayMove } from "@dnd-kit/sortable"
import { actions, afterMount, connect, kea, listeners, path, reducers } from "kea"
import { loaders } from "kea-loaders"

import { studyLogic } from "~/features/studies/studyLogic"
import { api } from "~/lib/api"

import type { screenerLogicType } from './screenerLogicType'

export type ScreenerQuestionType = "single_choice" | "multi_choice" | "free_text"

export interface ScreenerQuestion {
    id: string
    text: string
    type: ScreenerQuestionType
    options: string[]
    /**
     * For choice types: indices into ``options`` that count as "pass".
     * Empty array ⇒ no pass criteria defined yet (warned in summary).
     */
    pass_option_indices: number[]
    required: boolean
}

const DEFAULT_QUESTIONS: ScreenerQuestion[] = [
    {
        id: "sc1",
        text: "哪个年龄段最接近你？",
        type: "single_choice",
        options: ["18-24", "25-34", "35-44", "45+"],
        pass_option_indices: [0, 1, 2],
        required: true,
    },
    {
        id: "sc2",
        text: "过去 30 天你是否使用过该产品？",
        type: "single_choice",
        options: ["是", "否"],
        pass_option_indices: [0],
        required: true,
    },
]

/**
 * screenerLogic — participant-screener editor.
 *
 * MVP scope: one screener per study, list of questions with
 * pass-criteria (subset of options). Logic is client-side until the
 * backend screener endpoint lands; the state shape matches
 * ``merism.models.Screener.questions`` + ``pass_logic`` so the swap
 * is mechanical.
 */
export const screenerLogic = kea<screenerLogicType>([
    path(["features", "studies", "tabs", "screener", "screenerLogic"]),

    connect(() => ({ values: [studyLogic, ["studyId"]] })),

    actions({
        loadQuestions: (questions: ScreenerQuestion[]) => ({ questions }),
        addQuestion: (type: ScreenerQuestionType = "single_choice") => ({ type }),
        removeQuestion: (id: string) => ({ id }),
        updateText: (id: string, text: string) => ({ id, text }),
        setType: (id: string, type: ScreenerQuestionType) => ({ id, type }),
        toggleRequired: (id: string) => ({ id }),
        moveQuestion: (from: number, to: number) => ({ from, to }),
        setOptions: (id: string, options: string[]) => ({ id, options }),
        togglePassOption: (id: string, optionIndex: number) => ({ id, optionIndex }),
    }),

    reducers({
        questions: [
            DEFAULT_QUESTIONS,
            {
                loadQuestions: (_, { questions }) => questions,
                addQuestion: (state, { type }) => [
                    ...state,
                    {
                        id: `sc${state.length + 1}-${Math.random().toString(36).slice(2, 6)}`,
                        text: "",
                        type,
                        options:
                            type === "free_text" ? [] : ["Option A", "Option B"],
                        pass_option_indices: [],
                        required: true,
                    },
                ],
                removeQuestion: (state, { id }) => state.filter((q) => q.id !== id),
                updateText: (state, { id, text }) =>
                    state.map((q) => (q.id === id ? { ...q, text } : q)),
                setType: (state, { id, type }) =>
                    state.map((q) =>
                        q.id === id
                            ? {
                                  ...q,
                                  type,
                                  options:
                                      type === "free_text"
                                          ? []
                                          : q.options.length > 0
                                            ? q.options
                                            : ["Option A", "Option B"],
                                  pass_option_indices: [],
                              }
                            : q,
                    ),
                toggleRequired: (state, { id }) =>
                    state.map((q) =>
                        q.id === id ? { ...q, required: !q.required } : q,
                    ),
                moveQuestion: (state, { from, to }) => arrayMove(state, from, to),
                setOptions: (state, { id, options }) =>
                    state.map((q) =>
                        q.id === id
                            ? {
                                  ...q,
                                  options,
                                  // Drop any pass indices now out of range.
                                  pass_option_indices: q.pass_option_indices.filter(
                                      (i) => i < options.length,
                                  ),
                              }
                            : q,
                    ),
                togglePassOption: (state, { id, optionIndex }) =>
                    state.map((q) => {
                        if (q.id !== id) return q
                        const has = q.pass_option_indices.includes(optionIndex)
                        return {
                            ...q,
                            pass_option_indices: has
                                ? q.pass_option_indices.filter((i) => i !== optionIndex)
                                : [...q.pass_option_indices, optionIndex].sort(
                                      (a, b) => a - b,
                                  ),
                        }
                    }),
            },
        ],
    }),
    loaders(({ values }) => ({
        loadedScreener: [
            null as { id: string } | null,
            {
                loadScreener: async () => {
                    const studyId = values.studyId
                    if (!studyId) return null
                    const resp = await api.list<{ id: string; questions: ScreenerQuestion[] }>(
                        "/api/screeners/",
                        { study: studyId },
                    )
                    const row = resp.results?.[0]
                    return row ? { id: row.id } : null
                },
                saveScreener: async () => {
                    const studyId = values.studyId
                    if (!studyId) return null
                    const existing = values.loadedScreener
                    if (existing?.id) {
                        await api.update(`/api/screeners/${existing.id}/`, {
                            questions: values.questions,
                        })
                        return existing
                    }
                    const created = await api.create<{ id: string }>("/api/screeners/", {
                        study: studyId,
                        questions: values.questions,
                    })
                    return { id: created.id }
                },
            },
        ],
    })),

    listeners(({ actions: a }) => ({
        loadScreenerSuccess: async ({ loadedScreener }) => {
            if (loadedScreener?.id) {
                const full = await api.get<{ questions: ScreenerQuestion[] }>(
                    `/api/screeners/${loadedScreener.id}/`,
                )
                if (full.questions && full.questions.length > 0) {
                    a.loadQuestions(full.questions)
                }
            }
        },
    })),

    afterMount(({ actions, values }) => {
        if (values.studyId) actions.loadScreener()
    }),
])
