/**
 * Global domain types for the Merism frontend.
 *
 * Keep this file small; import types from scene-local ``types.ts`` files
 * when they are scene-specific. Types here are shared across ≥ 2 scenes
 * or appear in :file:`models/`.
 *
 * Backend source of truth lives in :mod:`merism.api.serializers`. When
 * the Django serializers change we regenerate via drf-spectacular +
 * openapi-zod-client (see ``pnpm build:api`` once wired), but these
 * hand-maintained types cover the shape for now.
 */

// ── identity ────────────────────────────────────────────

export interface User {
    id: string
    email: string
    first_name: string
    last_name: string
    is_superuser?: boolean
    organization: Organization | null
    team: Team | null
}

export interface Organization {
    id: string
    name: string
    slug: string
}

export interface Team {
    id: string
    name: string
    organization: string
}

// ── study ───────────────────────────────────────────────

export enum StudyFormat {
    Voice = "voice",
    Video = "video",
    Text = "text",
    Offline = "offline",
}

export enum StudyStatus {
    Draft = "draft",
    Ready = "ready",
    Recruiting = "recruiting",
    Active = "active",
    Closed = "closed",
    Archived = "archived",
}

export interface Study {
    id: string
    name: string
    research_goal: string
    research_objectives: string[]
    interview_mode: StudyFormat
    status: StudyStatus
    estimated_minutes: number
    barge_in_enabled: boolean
    target_audience?: string
    target_completed_count?: number
    recruitment_quotas?: RecruitmentQuota[]
    codebook?: CodebookEntry[]
    created_at: string
    updated_at: string
}

export interface RecruitmentQuotaSegment {
    label: string
    target: number
}

export interface RecruitmentQuota {
    dimension: string           // "age" | "gender" | custom key
    label: string                // display name
    segments: RecruitmentQuotaSegment[]
}

export interface CodebookEntry {
    code_id: string
    name: string
    description: string
    examples: string[]
    source: "seeded" | "inductive" | "manual"
}

// ── interview session ───────────────────────────────────

export enum SessionStatus {
    Scheduled = "scheduled",
    InProgress = "in_progress",
    Completed = "completed",
    Abandoned = "abandoned",
    Excluded = "excluded",
}

export interface InterviewSession {
    id: string
    study: string
    participant: string | null
    status: SessionStatus
    started_at: string | null
    ended_at: string | null
}

export interface SessionInsight {
    id: string
    session: string
    summary: string
    tags: Record<string, unknown>
    highlights: Array<{ text: string; ts_start: number; ts_end: number; importance: number }>
    extracted_tasks: Array<{
        title: string
        category: string
        priority: string
        evidence_quote_id?: string
    }>
}

// ── participant + recruitment ───────────────────────────

export enum ChannelType {
    Feishu = "feishu",
    WeCom = "wecom",
    QQ = "qq",
    Email = "email",
}

export interface ChannelConfig {
    id: string
    channel_type: ChannelType
    display_name: string
    is_active: boolean
}

export interface Participant {
    id: string
    external_id: string
    display_name: string
    channel_type: ChannelType
    created_at: string
}

// ── api envelope ────────────────────────────────────────

export interface Paginated<T> {
    count: number
    next: string | null
    previous: string | null
    results: T[]
}

export interface ApiError {
    detail: string
    code?: string
}
