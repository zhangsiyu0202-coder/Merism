import { useEffect, useState } from "react"

import { api } from "~/lib/api"
import { Button, SettingsSection, Tag } from "~/lib/merism"

import type { components } from "~/generated/api"

type Glossary = components["schemas"]["Glossary"]

/**
 * GlossarySection — team-wide glossary management (Settings page).
 *
 * Each entry maps variants (ASR-likely misrecognitions) → canonical form.
 * Applied in stage1 of the cleaning pipeline before LLM polish.
 */
export function GlossarySection(): JSX.Element {
    const [entries, setEntries] = useState<Glossary[]>([])
    const [showForm, setShowForm] = useState(false)
    const [editing, setEditing] = useState<string | null>(null)

    const load = (): void => {
        api.get<{ results: Glossary[] }>("/api/glossaries/", { study: "team" }).then(
            (r) => setEntries(r.results ?? (r as unknown as Glossary[])),
        )
    }

    useEffect(() => load(), [])

    return (
        <SettingsSection
            title="Glossary"
            description="Term replacements applied during transcript cleaning. Useful for ASR-likely misrecognitions of product names, people, or jargon."
        >
            <div className="flex flex-col gap-3">
                {entries.length === 0 && (
                    <p className="text-merism-text-muted text-merism-body">
                        No glossary entries yet.
                    </p>
                )}
                {entries.map((e) => (
                    <div
                        key={e.id}
                        className="flex items-center justify-between rounded-merism-md border border-merism-border px-4 py-3"
                    >
                        <div className="flex items-center gap-3 flex-1">
                            <span className="font-medium text-merism-text">{e.canonical}</span>
                            <span className="text-merism-text-muted text-merism-caption">
                                ← {(e.variants as string[] | null)?.join(", ")}
                            </span>
                            {e.case_insensitive && <Tag>case-insensitive</Tag>}
                        </div>
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                                setEditing(e.id)
                                setShowForm(true)
                            }}
                        >
                            Edit
                        </Button>
                    </div>
                ))}
                <Button
                    size="sm"
                    onClick={() => {
                        setEditing(null)
                        setShowForm(true)
                    }}
                >
                    Add glossary entry
                </Button>
                {showForm && (
                    <GlossaryForm
                        editId={editing}
                        entries={entries}
                        onDone={() => {
                            setShowForm(false)
                            load()
                        }}
                        onCancel={() => setShowForm(false)}
                    />
                )}
            </div>
        </SettingsSection>
    )
}

function GlossaryForm({
    editId,
    entries,
    onDone,
    onCancel,
}: {
    editId: string | null
    entries: Glossary[]
    onDone: () => void
    onCancel: () => void
}): JSX.Element {
    const existing = editId ? entries.find((e) => e.id === editId) : null
    const [canonical, setCanonical] = useState(existing?.canonical ?? "")
    const [variantsText, setVariantsText] = useState(
        ((existing?.variants as string[] | null) ?? []).join(", "),
    )
    const [caseInsensitive, setCaseInsensitive] = useState(
        existing?.case_insensitive ?? true,
    )
    const [saving, setSaving] = useState(false)

    const save = async (): Promise<void> => {
        setSaving(true)
        const variants = variantsText
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean)
        const body = { canonical, variants, case_insensitive: caseInsensitive }
        try {
            if (editId) {
                await api.update(`/api/glossaries/${editId}/`, body)
            } else {
                await api.create("/api/glossaries/", body)
            }
            onDone()
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="rounded-merism-md border border-merism-border bg-merism-bg-subtle p-4 flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Canonical</span>
                    <input
                        className="input-merism"
                        placeholder="e.g. Merism"
                        value={canonical}
                        onChange={(e) => setCanonical(e.target.value)}
                    />
                </label>
                <label className="flex flex-col gap-1 col-span-2">
                    <span className="text-merism-caption text-merism-text-muted">
                        Variants (comma-separated)
                    </span>
                    <input
                        className="input-merism"
                        placeholder="e.g. 米瑞姆, merism, meriism"
                        value={variantsText}
                        onChange={(e) => setVariantsText(e.target.value)}
                    />
                </label>
                <label className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={caseInsensitive}
                        onChange={(e) => setCaseInsensitive(e.target.checked)}
                    />
                    <span className="text-merism-body-sm">Case-insensitive match</span>
                </label>
            </div>
            <div className="flex gap-2 justify-end">
                <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
                <Button
                    size="sm"
                    onClick={save}
                    disabled={saving || !canonical || !variantsText}
                >
                    {saving ? "Saving…" : editId ? "Update" : "Create"}
                </Button>
            </div>
        </div>
    )
}
