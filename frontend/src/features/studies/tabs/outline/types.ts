export type OutlineOp =
    | { op: "modify_question"; question_id: string; new_text: string; reason?: string }
    | {
          op: "insert_question"
          after_question_id: string
          new_question: Record<string, unknown>
          reason?: string
      }
    | { op: "remove_question"; question_id: string; reason?: string }

export interface OutlineReviewResponse {
    reply_markdown: string
    proposed_changes: OutlineOp[]
    awaiting_user_decision: boolean
}

export interface OutlineReviewChatMessage {
    id: string
    role: "researcher" | "assistant"
    text: string
    proposed_changes?: OutlineOp[]
}

export type OutlineSectionScope = "global" | "per_concept" | "comparative"

export interface OutlineSection {
    id: string
    title: string
    /**
     * Concept Testing 2.0:
     *   - "global"       — runs once per session (warmup, closing)
     *   - "per_concept"  — runs once per concept in the named block
     *   - "comparative"  — runs once after all concepts (cross-concept wrap-up)
     */
    scope?: OutlineSectionScope
    /** Required when ``scope === "per_concept"``. */
    concept_block_id?: string | null
    questions: Array<{
        id: string
        text: string
        /** Sprint 1: what this question aims to produce + probing direction. */
        intent: string
        /** Sprint 1: server-enforced probing policy. */
        probe_policy: "none" | "light" | "deep"
        /** Sprint 1: hard cap on probes (1-5). */
        max_probes: number
        required?: boolean
        linked_stimulus_ids?: string[]
        /** @deprecated kept for wire back-compat; ignore in new code. */
        followup_depth?: number
    }>
}
