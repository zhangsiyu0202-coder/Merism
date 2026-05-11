import { useEffect, useState } from "react"

import { api } from "~/lib/api"
import { Button, SettingsSection, Tag } from "~/lib/merism"

// ── Types ────────────────────────────────────────────────

interface LLMProvider {
    id: string
    display_name: string
    protocol: "http" | "ws"
    base_url: string
    model: string
    has_credentials: boolean
    is_active: boolean
    extra_headers: Record<string, string> | null
}

interface LLMRoute {
    id: string
    logical_name: string
    primary: string
    primary_display: string
    fallback: string | null
    fallback_display: string | null
    temperature: number
    max_output_tokens: number | null
    timeout_seconds: number
    max_retries: number
}

interface LLMBudget {
    id: string
    period: string
    monthly_cap_usd: string
    soft_limit_pct: number
    hard_limit_action: "alert_only" | "degrade" | "block"
    current_spent_usd: string
    is_over_soft_limit: boolean
    is_over_hard_limit: boolean
}

interface Preset {
    label: string
    protocol: "http" | "ws"
    base_url: string
    model: string
    serves: string[]
}

// ── Main Section ─────────────────────────────────────────

export function LLMGatewaySection(): JSX.Element {
    return (
        <div className="flex flex-col gap-6">
            <ProvidersPanel />
            <RoutesPanel />
            <BudgetPanel />
        </div>
    )
}

// ── Providers ────────────────────────────────────────────

function ProvidersPanel(): JSX.Element {
    const [providers, setProviders] = useState<LLMProvider[]>([])
    const [presets, setPresets] = useState<Preset[]>([])
    const [showForm, setShowForm] = useState(false)
    const [editId, setEditId] = useState<string | null>(null)

    const load = (): void => {
        api.get<{ results: LLMProvider[] }>("/api/llm/providers/").then((r) =>
            setProviders(r.results ?? (r as unknown as LLMProvider[])),
        )
    }

    useEffect(() => {
        load()
        api.get<Preset[]>("/api/llm/providers/presets/").then(setPresets)
    }, [])

    return (
        <SettingsSection
            title="Providers"
            description="LLM providers available to this team. Credentials are encrypted at rest."
        >
            <div className="flex flex-col gap-3">
                {providers.length === 0 && (
                    <p className="text-merism-text-muted text-merism-body">
                        No providers configured. Add one from a preset or manually.
                    </p>
                )}
                {providers.map((p) => (
                    <div
                        key={p.id}
                        className="flex items-center justify-between rounded-merism-md border border-merism-border px-4 py-3"
                    >
                        <div className="flex items-center gap-3">
                            <span className="font-medium text-merism-text">{p.display_name}</span>
                            <Tag>{p.protocol.toUpperCase()}</Tag>
                            <span className="text-merism-text-muted text-merism-caption">{p.model}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Tag>{p.is_active ? "Active" : "Inactive"}</Tag>
                            <Button size="sm" variant="ghost" onClick={() => { setEditId(p.id); setShowForm(true) }}>
                                Edit
                            </Button>
                        </div>
                    </div>
                ))}
                <div className="flex gap-2">
                    <Button size="sm" onClick={() => { setEditId(null); setShowForm(true) }}>
                        Add provider
                    </Button>
                </div>
                {showForm && (
                    <ProviderForm
                        presets={presets}
                        editId={editId}
                        providers={providers}
                        onDone={() => { setShowForm(false); load() }}
                        onCancel={() => setShowForm(false)}
                    />
                )}
            </div>
        </SettingsSection>
    )
}

function ProviderForm({
    presets,
    editId,
    providers,
    onDone,
    onCancel,
}: {
    presets: Preset[]
    editId: string | null
    providers: LLMProvider[]
    onDone: () => void
    onCancel: () => void
}): JSX.Element {
    const existing = editId ? providers.find((p) => p.id === editId) : null
    const [displayName, setDisplayName] = useState(existing?.display_name ?? "")
    const [protocol, setProtocol] = useState<"http" | "ws">(existing?.protocol ?? "http")
    const [baseUrl, setBaseUrl] = useState(existing?.base_url ?? "")
    const [model, setModel] = useState(existing?.model ?? "")
    const [apiKey, setApiKey] = useState("")
    const [saving, setSaving] = useState(false)

    const applyPreset = (preset: Preset): void => {
        setDisplayName(preset.label)
        setProtocol(preset.protocol)
        setBaseUrl(preset.base_url)
        setModel(preset.model)
    }

    const save = async (): Promise<void> => {
        setSaving(true)
        const body: Record<string, unknown> = {
            display_name: displayName,
            protocol,
            base_url: baseUrl,
            model,
        }
        if (apiKey) body.credentials = { api_key: apiKey }
        try {
            if (editId) {
                await api.update(`/api/llm/providers/${editId}/`, body)
            } else {
                await api.create("/api/llm/providers/", body)
            }
            onDone()
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="rounded-merism-md border border-merism-border bg-merism-bg-subtle p-4 flex flex-col gap-3">
            {!editId && presets.length > 0 && (
                <div className="flex flex-wrap gap-1">
                    {presets.filter((p) => p.protocol === protocol).slice(0, 8).map((p) => (
                        <button
                            key={p.label}
                            type="button"
                            onClick={() => applyPreset(p)}
                            className="rounded-merism-sm border border-merism-border px-2 py-1 text-merism-caption hover:bg-merism-accent-soft"
                        >
                            {p.label}
                        </button>
                    ))}
                </div>
            )}
            <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Display name</span>
                    <input className="input-merism" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
                </label>
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Protocol</span>
                    <select className="input-merism" value={protocol} onChange={(e) => setProtocol(e.target.value as "http" | "ws")}>
                        <option value="http">HTTP (LiteLLM)</option>
                        <option value="ws">WebSocket (Realtime)</option>
                    </select>
                </label>
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Base URL</span>
                    <input className="input-merism" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                </label>
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Model</span>
                    <input className="input-merism" value={model} onChange={(e) => setModel(e.target.value)} />
                </label>
                <label className="flex flex-col gap-1 col-span-2">
                    <span className="text-merism-caption text-merism-text-muted">
                        API Key {editId && "(leave blank to keep existing)"}
                    </span>
                    <input className="input-merism" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                </label>
            </div>
            <div className="flex gap-2 justify-end">
                <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
                <Button size="sm" onClick={save} disabled={saving || !displayName || !baseUrl || !model}>
                    {saving ? "Saving…" : editId ? "Update" : "Create"}
                </Button>
            </div>
        </div>
    )
}

// ── Routes ───────────────────────────────────────────────

function RoutesPanel(): JSX.Element {
    const [routes, setRoutes] = useState<LLMRoute[]>([])
    const [providers, setProviders] = useState<LLMProvider[]>([])
    const [showForm, setShowForm] = useState(false)

    const load = (): void => {
        api.get<{ results: LLMRoute[] }>("/api/llm/routes/").then((r) =>
            setRoutes(r.results ?? (r as unknown as LLMRoute[])),
        )
        api.get<{ results: LLMProvider[] }>("/api/llm/providers/").then((r) =>
            setProviders(r.results ?? (r as unknown as LLMProvider[])),
        )
    }

    useEffect(() => { load() }, [])

    const LOGICAL_NAMES = ["chat", "reasoner", "embedding", "vision", "asr_realtime", "tts_realtime", "omni_realtime"]

    return (
        <SettingsSection
            title="Routes"
            description="Map logical capabilities to providers. Each team can have one route per capability."
        >
            <div className="flex flex-col gap-3">
                {routes.length === 0 && (
                    <p className="text-merism-text-muted text-merism-body">
                        No routes configured. Create routes to start using the gateway.
                    </p>
                )}
                {routes.map((r) => (
                    <div
                        key={r.id}
                        className="flex items-center justify-between rounded-merism-md border border-merism-border px-4 py-3"
                    >
                        <div className="flex items-center gap-3">
                            <Tag>{r.logical_name}</Tag>
                            <span className="text-merism-text">{r.primary_display}</span>
                            {r.fallback_display && (
                                <span className="text-merism-text-muted text-merism-caption">
                                    → {r.fallback_display}
                                </span>
                            )}
                        </div>
                        <span className="text-merism-caption text-merism-text-muted">
                            temp={r.temperature} retries={r.max_retries}
                        </span>
                    </div>
                ))}
                <Button size="sm" onClick={() => setShowForm(true)}>Add route</Button>
                {showForm && (
                    <RouteForm
                        providers={providers}
                        logicalNames={LOGICAL_NAMES}
                        onDone={() => { setShowForm(false); load() }}
                        onCancel={() => setShowForm(false)}
                    />
                )}
            </div>
        </SettingsSection>
    )
}

function RouteForm({
    providers,
    logicalNames,
    onDone,
    onCancel,
}: {
    providers: LLMProvider[]
    logicalNames: string[]
    onDone: () => void
    onCancel: () => void
}): JSX.Element {
    const [logicalName, setLogicalName] = useState(logicalNames[0])
    const [primary, setPrimary] = useState(providers[0]?.id ?? "")
    const [fallback, setFallback] = useState("")
    const [saving, setSaving] = useState(false)

    const save = async (): Promise<void> => {
        setSaving(true)
        try {
            await api.create("/api/llm/routes/", {
                logical_name: logicalName,
                primary,
                fallback: fallback || null,
            })
            onDone()
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="rounded-merism-md border border-merism-border bg-merism-bg-subtle p-4 flex flex-col gap-3">
            <div className="grid grid-cols-3 gap-3">
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Capability</span>
                    <select className="input-merism" value={logicalName} onChange={(e) => setLogicalName(e.target.value)}>
                        {logicalNames.map((n) => <option key={n} value={n}>{n}</option>)}
                    </select>
                </label>
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Primary provider</span>
                    <select className="input-merism" value={primary} onChange={(e) => setPrimary(e.target.value)}>
                        {providers.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
                    </select>
                </label>
                <label className="flex flex-col gap-1">
                    <span className="text-merism-caption text-merism-text-muted">Fallback (optional)</span>
                    <select className="input-merism" value={fallback} onChange={(e) => setFallback(e.target.value)}>
                        <option value="">None</option>
                        {providers.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
                    </select>
                </label>
            </div>
            <div className="flex gap-2 justify-end">
                <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
                <Button size="sm" onClick={save} disabled={saving || !primary}>
                    {saving ? "Saving…" : "Create"}
                </Button>
            </div>
        </div>
    )
}

// ── Budget ───────────────────────────────────────────────

function BudgetPanel(): JSX.Element {
    const [budgets, setBudgets] = useState<LLMBudget[]>([])

    useEffect(() => {
        api.get<{ results: LLMBudget[] }>("/api/llm/budgets/").then((r) =>
            setBudgets(r.results ?? (r as unknown as LLMBudget[])),
        )
    }, [])

    return (
        <SettingsSection
            title="Budget"
            description="Monthly spend tracking per team. Reconciled hourly from Langfuse."
        >
            <div className="flex flex-col gap-3">
                {budgets.length === 0 && (
                    <p className="text-merism-text-muted text-merism-body">
                        No budget configured for the current period.
                    </p>
                )}
                {budgets.map((b) => (
                    <div
                        key={b.id}
                        className="rounded-merism-md border border-merism-border px-4 py-3 flex items-center justify-between"
                    >
                        <div className="flex items-center gap-3">
                            <span className="font-medium text-merism-text">{b.period}</span>
                            <span className="text-merism-body">
                                ${b.current_spent_usd} / ${b.monthly_cap_usd}
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Tag>{b.hard_limit_action}</Tag>
                            {b.is_over_soft_limit && <Tag>⚠️ Soft limit</Tag>}
                            {b.is_over_hard_limit && <Tag>🚫 Hard limit</Tag>}
                        </div>
                    </div>
                ))}
            </div>
        </SettingsSection>
    )
}
