import { useActions, useValues } from "kea"
import { Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import {
    Button,
    Dialog,
    DialogContent,
    DialogTitle,
    Input,
} from "~/lib/merism"
import type { RecruitmentQuota, RecruitmentQuotaSegment } from "~/types"

import { recruitPlanLogic } from "./recruitPlanLogic"

/**
 * QuotaDialog — modal editor for one recruitment quota dimension.
 *
 * Preset dimensions (age / gender / location / usage_frequency) keep the
 * form fast; ``custom`` lets the researcher name their own dimension
 * (e.g. "past_purchases"). Each dimension holds a list of segments with
 * a target count — together they constrain the recruitment distribution.
 *
 * Validation: both dimension label and every segment label must be
 * non-empty; targets are clamped to >= 1; empty segments are dropped
 * on save.
 */

const PRESET_DIMENSIONS: Array<{
    dimension: string
    label: string
    defaultSegments: RecruitmentQuotaSegment[]
}> = [
    {
        dimension: "age",
        label: "Age ranges",
        defaultSegments: [
            { label: "18–24", target: 3 },
            { label: "25–34", target: 4 },
            { label: "35–44", target: 3 },
        ],
    },
    {
        dimension: "gender",
        label: "Gender",
        defaultSegments: [
            { label: "Female", target: 5 },
            { label: "Male", target: 5 },
        ],
    },
    {
        dimension: "location",
        label: "Location",
        defaultSegments: [
            { label: "Tier-1 city", target: 5 },
            { label: "Tier-2 city", target: 3 },
            { label: "Rural", target: 2 },
        ],
    },
    {
        dimension: "usage_frequency",
        label: "Usage frequency",
        defaultSegments: [
            { label: "Daily", target: 4 },
            { label: "Weekly", target: 4 },
            { label: "Monthly", target: 2 },
        ],
    },
]

export function QuotaDialog(): JSX.Element {
    const { dialogOpen, stagedQuota, editingIndex } = useValues(recruitPlanLogic)
    const { closeQuotaDialog, upsertQuota, setDraftQuota } =
        useActions(recruitPlanLogic)

    // Local mirror so typing doesn't cause an action per keystroke.
    const [working, setWorking] = useState<RecruitmentQuota>(
        () => stagedQuota ?? { dimension: "age", label: "Age", segments: [] },
    )

    useEffect(() => {
        if (stagedQuota) setWorking(stagedQuota)
    }, [stagedQuota])

    function applyPreset(preset: (typeof PRESET_DIMENSIONS)[number]) {
        const next: RecruitmentQuota = {
            dimension: preset.dimension,
            label: preset.label,
            segments: preset.defaultSegments.map((s) => ({ ...s })),
        }
        setWorking(next)
        setDraftQuota(next)
    }

    function updateLabel(label: string) {
        setWorking({ ...working, label })
    }

    function updateSegmentLabel(i: number, label: string) {
        const segments = working.segments.map((s, idx) =>
            idx === i ? { ...s, label } : s,
        )
        setWorking({ ...working, segments })
    }

    function updateSegmentTarget(i: number, target: number) {
        const clamped = Math.max(1, target || 1)
        const segments = working.segments.map((s, idx) =>
            idx === i ? { ...s, target: clamped } : s,
        )
        setWorking({ ...working, segments })
    }

    function addSegment() {
        setWorking({
            ...working,
            segments: [...working.segments, { label: "", target: 1 }],
        })
    }

    function removeSegment(i: number) {
        setWorking({
            ...working,
            segments: working.segments.filter((_, idx) => idx !== i),
        })
    }

    function save() {
        const cleaned = {
            ...working,
            segments: working.segments
                .filter((s) => s.label.trim() !== "")
                .map((s) => ({
                    label: s.label.trim(),
                    target: Math.max(1, s.target || 1),
                })),
        }
        upsertQuota(editingIndex, cleaned)
    }

    return (
        <Dialog
            open={dialogOpen}
            onOpenChange={(open) => (open ? undefined : closeQuotaDialog())}
        >
            <DialogContent className="max-w-lg">
                <div className="flex flex-col gap-1 pb-4">
                    <DialogTitle className="font-display text-merism-h2 font-[500] text-merism-text">
                        {editingIndex === null ? "Add quota" : "Edit quota"}
                    </DialogTitle>
                    <p className="text-merism-body-sm text-merism-text-muted">
                        Split your target sample across segments of one dimension.
                    </p>
                </div>

                <div className="flex flex-col gap-6 py-2">
                        {/* Presets */}
                        <div className="flex flex-col gap-2">
                            <label className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                                Preset
                            </label>
                            <div className="flex flex-wrap gap-2">
                                {PRESET_DIMENSIONS.map((p) => (
                                    <button
                                        key={p.dimension}
                                        type="button"
                                        onClick={() => applyPreset(p)}
                                        className={
                                            "rounded-merism-full bg-merism-bg-subtle/70 px-3 py-1 text-merism-label " +
                                            "text-merism-text-muted transition-colors " +
                                            "hover:bg-merism-accent-soft hover:text-merism-accent " +
                                            "ring-1 ring-[color:var(--merism-hairline)]"
                                        }
                                    >
                                        {p.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Label */}
                        <div className="flex flex-col gap-2">
                            <label
                                htmlFor="quota-label"
                                className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle"
                            >
                                Dimension name
                            </label>
                            <Input
                                id="quota-label"
                                value={working.label}
                                onChange={(e) => updateLabel(e.target.value)}
                                placeholder="e.g. Age ranges"
                            />
                        </div>

                        {/* Segments */}
                        <div className="flex flex-col gap-2">
                            <label className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                                Segments
                            </label>
                            <div className="flex flex-col gap-2">
                                {working.segments.map((seg, i) => (
                                    <div key={i} className="flex items-center gap-2">
                                        <Input
                                            value={seg.label}
                                            onChange={(e) =>
                                                updateSegmentLabel(i, e.target.value)
                                            }
                                            placeholder="Segment label"
                                            className="flex-1"
                                        />
                                        <Input
                                            type="number"
                                            min={1}
                                            value={seg.target}
                                            onChange={(e) =>
                                                updateSegmentTarget(
                                                    i,
                                                    parseInt(e.target.value, 10),
                                                )
                                            }
                                            className="w-20 text-right"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => removeSegment(i)}
                                            aria-label="Remove segment"
                                            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-danger"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    </div>
                                ))}
                                <button
                                    type="button"
                                    onClick={addSegment}
                                    className="inline-flex items-center gap-2 self-start rounded-merism-md px-2 py-1 text-merism-label text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
                                >
                                    <Plus className="h-3.5 w-3.5" />
                                    Add segment
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center justify-end gap-2 border-t border-[color:var(--merism-hairline)] pt-4">
                        <Button
                            type="button"
                            variant="ghost"
                            onClick={closeQuotaDialog}
                        >
                            Cancel
                        </Button>
                        <Button type="button" onClick={save}>
                            Save quota
                        </Button>
                    </div>
            </DialogContent>
        </Dialog>
    )
}
