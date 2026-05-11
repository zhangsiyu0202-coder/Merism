import { actions, connect, kea, listeners, path, reducers, selectors } from "kea"
import { forms } from "kea-forms"
import { z } from "zod"

import { api } from "~/lib/api"
import { studyLogic } from "~/features/studies/studyLogic"
import type { Study, StudyFormat } from "~/types"

import type { briefWizardLogicType } from './briefWizardLogicType'

/** 5-step wizard per PRODUCT.md §3.2 — single research goal, mode, plan. */
export const WIZARD_STEPS = ["goal", "mode", "plan", "review", "done"] as const
export type WizardStep = (typeof WIZARD_STEPS)[number]

// Zod schema — the source of truth for validation + eventual schema export.
const briefSchema = z.object({
    research_goal: z
        .string()
        .trim()
        .min(20, "Describe the research goal in a full sentence (20+ chars)")
        .max(500, "Keep the research goal under 500 chars — add details to the hypothesis field"),
    research_background: z.string().trim().default(""),
    hypothesis: z.string().trim().default(""),
    interview_mode: z.enum(["voice", "video", "text", "offline"]),
    estimated_minutes: z
        .number({ invalid_type_error: "Estimated duration must be a number" })
        .int("Use whole minutes")
        .min(5, "Interviews shorter than 5 min rarely yield depth")
        .max(90, "90 min is the absolute upper bound (most participants drop off)"),
    barge_in_enabled: z.boolean(),
})

export type BriefFormValues = z.infer<typeof briefSchema>

export const briefWizardLogic = kea<briefWizardLogicType>([
    path(["features", "studies", "briefWizardLogic"]),

    connect(() => ({
        values: [studyLogic, ["study"]],
        actions: [studyLogic, ["loadStudy"]],
    })),

    actions({
        goToStep: (step: WizardStep) => ({ step }),
        next: true,
        back: true,
        hydrateFromStudy: (study: Study) => ({ study }),
    }),

    reducers({
        step: [
            "goal" as WizardStep,
            {
                goToStep: (_, { step }) => step,
                next: (state) => {
                    const idx = WIZARD_STEPS.indexOf(state)
                    return WIZARD_STEPS[Math.min(idx + 1, WIZARD_STEPS.length - 1)] ?? state
                },
                back: (state) => {
                    const idx = WIZARD_STEPS.indexOf(state)
                    return WIZARD_STEPS[Math.max(idx - 1, 0)] ?? state
                },
            },
        ],
    }),

    forms(({ actions, values }) => ({
        brief: {
            defaults: {
                research_goal: "",
                research_background: "",
                hypothesis: "",
                interview_mode: "voice" as StudyFormat,
                estimated_minutes: 20,
                barge_in_enabled: false,
            } as BriefFormValues,
            errors: (formValues) => {
                const parsed = briefSchema.safeParse(formValues)
                if (parsed.success) return {}
                const errors: Record<string, string> = {}
                for (const issue of parsed.error.issues) {
                    const key = issue.path[0]
                    if (typeof key === "string" && !(key in errors)) {
                        errors[key] = issue.message
                    }
                }
                return errors
            },
            submit: async (formValues) => {
                const current = values.study
                if (!current) {
                    throw new Error("No study loaded — cannot save brief.")
                }
                await api.update<Study>(`/api/studies/${current.id}/`, formValues)
                actions.loadStudy()
                actions.goToStep("done")
            },
        },
    })),

    selectors({
        currentStepIndex: [(s) => [s.step], (step) => WIZARD_STEPS.indexOf(step)],
        canGoBack: [(s) => [s.step], (step) => WIZARD_STEPS.indexOf(step) > 0],
        isLastStep: [(s) => [s.step], (step) => step === "review"],
        schema: [() => [], () => briefSchema],
    }),

    listeners(({ actions }) => ({
        hydrateFromStudy: ({ study }) => {
            actions.setBriefValues({
                research_goal: study.research_goal,
                research_background: (study as Study & { research_background?: string }).research_background ?? "",
                hypothesis: (study as Study & { hypothesis?: string }).hypothesis ?? "",
                interview_mode: study.interview_mode,
                estimated_minutes: study.estimated_minutes,
                barge_in_enabled: study.barge_in_enabled,
            })
        },
    })),
])
