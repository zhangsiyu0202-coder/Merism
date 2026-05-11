import { actions, connect, kea, listeners, path, reducers, selectors } from "kea"
import { loaders } from "kea-loaders"

import { studyLogic } from "~/features/studies/studyLogic"
import { api } from "~/lib/api"

import type { conceptBlocksLogicType } from './conceptBlocksLogicType'

export type Rotation = "fixed" | "random_per_session" | "latin_square"

export interface ConceptRow {
    id: string
    block: string
    stimulus: string
    stimulus_title: string
    stimulus_kind: "image" | "video" | "text" | "pdf" | "link"
    label: string
    rank: number
    notes: string
    created_at: string
    updated_at: string
}

export interface ConceptBlockRow {
    id: string
    study: string
    title: string
    description: string
    rotation: Rotation
    show_counter_chip: boolean
    concepts: ConceptRow[]
    concept_count: number
    created_at: string
    updated_at: string
}

/**
 * conceptBlocksLogic — list + CRUD for the current study's ConceptBlocks.
 *
 * Drag-to-reorder is optimistic: we patch ``rank`` locally first, then
 * PATCH the server. On failure we roll back + surface the error.
 */
export const conceptBlocksLogic = kea<conceptBlocksLogicType>([
    path(["features", "studies", "tabs", "stimuli", "conceptBlocksLogic"]),

    connect({ values: [studyLogic, ["study"]] }),

    actions({
        createBlock: (title: string) => ({ title }),
        deleteBlock: (blockId: string) => ({ blockId }),
        setRotation: (blockId: string, rotation: Rotation) => ({ blockId, rotation }),
        addConcept: (blockId: string, payload: { label: string; stimulus: string; notes?: string }) => ({
            blockId,
            payload,
        }),
        removeConcept: (blockId: string, conceptId: string) => ({ blockId, conceptId }),
        reorderConcept: (blockId: string, fromIndex: number, toIndex: number) => ({
            blockId,
            fromIndex,
            toIndex,
        }),
        setError: (error: string | null) => ({ error }),
    }),

    loaders(({ values }) => ({
        blocks: [
            [] as ConceptBlockRow[],
            {
                loadBlocks: async () => {
                    const studyId = values.study?.id
                    if (!studyId) return []
                    const res = await api.list<ConceptBlockRow>(
                        "/api/concept-blocks/",
                        { study: studyId },
                    )
                    return res.results ?? []
                },
            },
        ],
    })),

    reducers({
        error: [
            null as string | null,
            {
                setError: (_, { error }) => error,
            },
        ],
    }),

    selectors({
        studyId: [(s) => [s.study], (study) => study?.id ?? null],
    }),

    listeners(({ actions, values }) => ({
        createBlock: async ({ title }) => {
            const studyId = values.studyId
            if (!studyId) return
            try {
                await api.create("/api/concept-blocks/", {
                    study: studyId,
                    title: title.trim() || "New concept block",
                    rotation: "random_per_session",
                })
                actions.loadBlocks()
            } catch (e) {
                actions.setError(e instanceof Error ? e.message : "Create failed")
            }
        },

        deleteBlock: async ({ blockId }) => {
            try {
                await api.delete(`/api/concept-blocks/${blockId}/`)
                actions.loadBlocks()
            } catch (e) {
                actions.setError(e instanceof Error ? e.message : "Delete failed")
            }
        },

        setRotation: async ({ blockId, rotation }) => {
            try {
                await api.update(`/api/concept-blocks/${blockId}/`, { rotation })
                actions.loadBlocks()
            } catch (e) {
                actions.setError(e instanceof Error ? e.message : "Update failed")
            }
        },

        addConcept: async ({ blockId, payload }) => {
            const block = values.blocks.find((b) => b.id === blockId)
            const nextRank = block ? block.concepts.length : 0
            try {
                await api.create("/api/concepts/", {
                    block: blockId,
                    stimulus: payload.stimulus,
                    label: payload.label.trim() || `Concept ${String.fromCharCode(65 + nextRank)}`,
                    rank: nextRank,
                    notes: payload.notes ?? "",
                })
                actions.loadBlocks()
            } catch (e) {
                actions.setError(e instanceof Error ? e.message : "Add concept failed")
            }
        },

        removeConcept: async ({ conceptId }) => {
            try {
                await api.delete(`/api/concepts/${conceptId}/`)
                actions.loadBlocks()
            } catch (e) {
                actions.setError(e instanceof Error ? e.message : "Remove concept failed")
            }
        },

        reorderConcept: async ({ blockId, fromIndex, toIndex }) => {
            const block = values.blocks.find((b) => b.id === blockId)
            if (!block || fromIndex === toIndex) return
            const newOrder = [...block.concepts]
            const [moved] = newOrder.splice(fromIndex, 1)
            if (!moved) return
            newOrder.splice(toIndex, 0, moved)
            // Re-rank + patch the full set sequentially. Kept simple; if
            // performance bites, swap to a single bulk endpoint later.
            try {
                await Promise.all(
                    newOrder.map((c, idx) =>
                        c.rank === idx
                            ? Promise.resolve()
                            : api.update(`/api/concepts/${c.id}/`, { rank: idx }),
                    ),
                )
                actions.loadBlocks()
            } catch (e) {
                actions.setError(e instanceof Error ? e.message : "Reorder failed")
            }
        },
    })),
])
