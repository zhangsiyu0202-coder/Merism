import { actions, connect, kea, path, reducers, selectors } from "kea"
import { loaders } from "kea-loaders"

import { studyLogic } from "~/features/studies/studyLogic"
import { api } from "~/lib/api"
import type { RecruitmentQuota, Study } from "~/types"

import type { recruitPlanLogicType } from './recruitPlanLogicType'

/**
 * recruitPlanLogic — edit state for the Recruit tab.
 *
 * Holds draft values for ``target_audience``, ``target_completed_count``,
 * and ``recruitment_quotas``. ``saveRecruitmentPlan`` PATCHes the study
 * and triggers a studyLogic reload so the outer page sees the new values.
 *
 * Quota editor is modal-based — ``openQuotaDialog`` / ``closeQuotaDialog``
 * toggle + ``setDraftQuota`` stages the quota being built.
 */

export const recruitPlanLogic = kea<recruitPlanLogicType>([
    path(["features", "studies", "tabs", "recruit", "recruitPlanLogic"]),

    connect(() => ({
        values: [studyLogic, ["study", "studyId"]],
        actions: [studyLogic, ["loadStudy"]],
    })),

    actions({
        hydrateFromStudy: (study: Study) => ({ study }),
        setAudience: (audience: string) => ({ audience }),
        setCompletedCount: (count: number) => ({ count }),
        setQuotas: (quotas: RecruitmentQuota[]) => ({ quotas }),

        // Quota dialog state
        openQuotaDialog: (quotaIndex: number | null = null) => ({ quotaIndex }),
        closeQuotaDialog: true,
        setDraftQuota: (quota: RecruitmentQuota | null) => ({ quota }),
        upsertQuota: (index: number | null, quota: RecruitmentQuota) => ({
            index,
            quota,
        }),
        removeQuota: (index: number) => ({ index }),
    }),

    reducers({
        draftAudience: [
            "",
            {
                setAudience: (_, { audience }) => audience,
                hydrateFromStudy: (_, { study }) => study.target_audience ?? "",
            },
        ],
        draftCount: [
            10,
            {
                setCompletedCount: (_, { count }) => Math.max(1, count),
                hydrateFromStudy: (_, { study }) => study.target_completed_count ?? 10,
            },
        ],
        draftQuotas: [
            [] as RecruitmentQuota[],
            {
                setQuotas: (_, { quotas }) => quotas,
                hydrateFromStudy: (_, { study }) => study.recruitment_quotas ?? [],
                upsertQuota: (state, { index, quota }) => {
                    if (index === null || index < 0 || index >= state.length) {
                        return [...state, quota]
                    }
                    const next = [...state]
                    next[index] = quota
                    return next
                },
                removeQuota: (state, { index }) =>
                    state.filter((_, i) => i !== index),
            },
        ],

        // Dialog state
        dialogOpen: [
            false,
            {
                openQuotaDialog: () => true,
                closeQuotaDialog: () => false,
                upsertQuota: () => false,
            },
        ],
        editingIndex: [
            null as number | null,
            {
                openQuotaDialog: (_, { quotaIndex }) => quotaIndex,
                closeQuotaDialog: () => null,
            },
        ],
        stagedQuota: [
            null as RecruitmentQuota | null,
            {
                openQuotaDialog: (_, { quotaIndex }) =>
                    quotaIndex === null ? _blank_quota() : _blank_quota(),
                setDraftQuota: (_, { quota }) => quota,
                closeQuotaDialog: () => null,
            },
        ],
    }),

    loaders(({ values, actions }) => ({
        savedAt: [
            null as string | null,
            {
                saveRecruitmentPlan: async () => {
                    const id = values.studyId
                    if (!id) return null
                    const payload = {
                        target_audience: values.draftAudience,
                        target_completed_count: values.draftCount,
                        recruitment_quotas: values.draftQuotas,
                    }
                    await api.update<Study>(`/api/studies/${id}/`, payload)
                    actions.loadStudy()
                    return new Date().toISOString()
                },
            },
        ],
    })),

    selectors({
        totalQuotaTargets: [
            (s) => [s.draftQuotas],
            (quotas: RecruitmentQuota[]) =>
                quotas.reduce(
                    (sum, q) =>
                        sum + q.segments.reduce((s2, seg) => s2 + seg.target, 0),
                    0,
                ),
        ],
        hasUnsavedChanges: [
            (s) => [s.study, s.draftAudience, s.draftCount, s.draftQuotas],
            (study, audience, count, quotas) => {
                if (!study) return false
                return (
                    (study.target_audience ?? "") !== audience ||
                    (study.target_completed_count ?? 10) !== count ||
                    JSON.stringify(study.recruitment_quotas ?? []) !==
                        JSON.stringify(quotas)
                )
            },
        ],
    }),
])

function _blank_quota(): RecruitmentQuota {
    return { dimension: "age", label: "Age", segments: [] }
}
