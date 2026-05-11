/**
 * Frontend test fixtures.
 *
 * Mirrors the Python `merism.testing.factories` pattern: a factory per
 * domain object with sensible defaults and per-test overrides. Use these
 * instead of literal objects in tests — keeps shapes aligned with the
 * backend serializers and lets you grep for "how do I build a Study" once.
 */

export interface StudyFixture {
    id: string
    name: string
    research_goal: string
    status: "draft" | "ready" | "recruiting" | "active" | "closed" | "archived"
    interview_mode: "voice" | "video" | "text" | "offline"
    created_at: string
}

export function makeStudy(overrides: Partial<StudyFixture> = {}): StudyFixture {
    return {
        id: "study-test-1",
        name: "Test Study",
        research_goal: "Why do users bounce at signup?",
        status: "draft",
        interview_mode: "voice",
        created_at: "2026-01-01T00:00:00Z",
        ...overrides,
    }
}

export interface CitationFixture {
    session_id: string
    ts: number
    quote: string
    speaker: string
}

export function makeCitation(overrides: Partial<CitationFixture> = {}): CitationFixture {
    return {
        session_id: "sess-1",
        ts: 42.5,
        quote: "The pricing feels steep for students.",
        speaker: "Alice",
        ...overrides,
    }
}

export interface ChartSpecFixture {
    type: "bar" | "line" | "pie"
    title: string
    x: string[]
    y: number[]
    unit?: string
}

export function makeChartSpec(overrides: Partial<ChartSpecFixture> = {}): ChartSpecFixture {
    return {
        type: "bar",
        title: "Reasons cited",
        x: ["price", "taste", "packaging"],
        y: [18, 14, 9],
        unit: "mentions",
        ...overrides,
    }
}
