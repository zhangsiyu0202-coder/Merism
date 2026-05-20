import {
    createColumnHelper,
    flexRender,
    getCoreRowModel,
    getFilteredRowModel,
    getSortedRowModel,
    useReactTable,
    type ColumnDef,
    type SortingState,
} from "@tanstack/react-table"
import { useActions, useMountedLogic, useValues } from "kea"
import { ChevronDown, ChevronUp, Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { studyLogic } from "~/features/studies/studyLogic"
import { Input, SectionLabel, Tag } from "~/lib/merism"
import type { InterviewSession, SessionStatus } from "~/types"

import { sessionsLogic } from "./sessionsLogic"

/**
 * SessionsTab — headless table via @tanstack/react-table.
 *
 * Borrowed pattern: Shopify Polaris and Airbnb use TanStack Table for
 * their admin tables. The table itself is just logic — we own all the
 * markup, which lets us keep the editorial aesthetic (mono cells,
 * Coral-soft hover, no stripes).
 *
 * Features:
 *   - Column sorting (click header)
 *   - Global text search
 *   - Status tag column
 *   - Mono short-ID and timestamp columns
 */
export default function SessionsTab(): JSX.Element {
    useMountedLogic(sessionsLogic)
    const { studyId } = useValues(studyLogic)
    const { sessions, sessionsLoading } = useValues(sessionsLogic)
    const { loadSessions } = useActions(sessionsLogic)

    useEffect(() => {
        if (studyId) loadSessions(studyId)
    }, [studyId, loadSessions])

    const columns = useMemo(() => buildColumns(), [])
    const [sorting, setSorting] = useState<SortingState>([
        { id: "started_at", desc: true },
    ])
    const [query, setQuery] = useState("")

    const table = useReactTable({
        data: sessions,
        columns,
        state: { sorting, globalFilter: query },
        onSortingChange: setSorting,
        onGlobalFilterChange: setQuery,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
        getFilteredRowModel: getFilteredRowModel(),
    })

    return (
        <div className="flex flex-col gap-6">
            <header className="flex items-center justify-between">
                <SectionLabel>访谈列表 · {sessions.length}</SectionLabel>
                <div className="relative max-w-sm">
                    <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-merism-text-subtle" />
                    <Input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="搜索受访者 / 编号 / 状态…"
                        className="pl-8"
                    />
                </div>
            </header>

            <div className="overflow-x-auto rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card">
                <table className="w-full border-collapse text-merism-label">
                    <thead>
                        {table.getHeaderGroups().map((hg) => (
                            <tr key={hg.id} className="border-b border-[color:var(--merism-hairline)]">
                                {hg.headers.map((header) => {
                                    const canSort = header.column.getCanSort()
                                    const dir = header.column.getIsSorted()
                                    return (
                                        <th
                                            key={header.id}
                                            onClick={
                                                canSort
                                                    ? header.column.getToggleSortingHandler()
                                                    : undefined
                                            }
                                            className={
                                                "select-none px-4 py-2 text-left font-mono text-merism-caption " +
                                                "uppercase tracking-merism-caps text-merism-text-subtle " +
                                                (canSort ? "cursor-pointer hover:text-merism-text" : "")
                                            }
                                        >
                                            <span className="inline-flex items-center gap-1">
                                                {flexRender(
                                                    header.column.columnDef.header,
                                                    header.getContext(),
                                                )}
                                                {dir === "asc" && <ChevronUp className="h-3 w-3" />}
                                                {dir === "desc" && <ChevronDown className="h-3 w-3" />}
                                            </span>
                                        </th>
                                    )
                                })}
                            </tr>
                        ))}
                    </thead>
                    <tbody>
                        {sessionsLoading && sessions.length === 0 ? (
                            <EmptyRow colspan={columns.length}>Loading…</EmptyRow>
                        ) : sessions.length === 0 ? (
                            <EmptyRow colspan={columns.length}>
                                还没有访谈记录。复制访谈链接发给受访者就能开始。
                            </EmptyRow>
                        ) : (
                            table.getRowModel().rows.map((row) => (
                                <tr
                                    key={row.id}
                                    className="border-b border-[color:var(--merism-hairline)]/70 transition-colors hover:bg-merism-accent-soft/40 last:border-b-0"
                                >
                                    {row.getVisibleCells().map((cell) => (
                                        <td key={cell.id} className="px-4 py-3">
                                            {flexRender(
                                                cell.column.columnDef.cell,
                                                cell.getContext(),
                                            )}
                                        </td>
                                    ))}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

// ── columns ────────────────────────────────────────────────

const col = createColumnHelper<InterviewSession>()

function buildColumns(): ColumnDef<InterviewSession, unknown>[] {
    return [
        col.accessor((row) => row.participant_name || "", {
            id: "participant",
            header: () => "受访者",
            cell: (info) => {
                const name = info.getValue() as string
                if (name) {
                    return <span className="text-merism-body-sm text-merism-text">{name}</span>
                }
                return (
                    <span className="text-merism-body-sm italic text-merism-text-subtle">
                        匿名受访者
                    </span>
                )
            },
        }),
        col.accessor((row) => row.interview_number ?? 0, {
            id: "interview_number",
            header: () => "访谈编号",
            cell: (info) => {
                const n = info.getValue() as number
                return (
                    <span className="font-mono text-merism-caption text-merism-text-muted">
                        {n > 0 ? `#${n}` : "—"}
                    </span>
                )
            },
        }),
        col.accessor("status", {
            header: () => "状态",
            cell: (info) => <StatusCell status={info.getValue() as SessionStatus} />,
        }),
        col.accessor("started_at", {
            header: () => "开始时间",
            cell: (info) => {
                const v = info.getValue() as string | null
                return (
                    <span className="font-mono text-merism-caption text-merism-text-muted">
                        {v ? new Date(v).toLocaleString() : "—"}
                    </span>
                )
            },
            sortingFn: (a, b) => {
                const av = a.getValue<string | null>("started_at") ?? ""
                const bv = b.getValue<string | null>("started_at") ?? ""
                return av.localeCompare(bv)
            },
        }),
        col.display({
            id: "duration",
            header: () => "时长",
            cell: ({ row }) => {
                const s = row.original
                if (!s.started_at) return <span className="text-merism-text-subtle">—</span>
                const end = s.ended_at ? new Date(s.ended_at) : new Date()
                const start = new Date(s.started_at)
                const mins = Math.round((end.getTime() - start.getTime()) / 60_000)
                return (
                    <span className="font-mono text-merism-caption text-merism-text-muted">
                        {mins} min
                    </span>
                )
            },
        }),
        col.accessor((row) => row.turn_count ?? 0, {
            id: "turn_count",
            header: () => "轮次",
            cell: (info) => {
                const n = info.getValue() as number
                return (
                    <span className="font-mono text-merism-caption text-merism-text-muted">
                        {n}
                    </span>
                )
            },
        }),
        col.display({
            id: "actions",
            header: () => "",
            cell: ({ row }) => (
                <a
                    href={`/sessions/${row.original.id}/transcript`}
                    className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-accent hover:underline"
                >
                    查看详情 →
                </a>
            ),
        }),
    ] as ColumnDef<InterviewSession, unknown>[]
}

function StatusCell({ status }: { status: SessionStatus }): JSX.Element {
    const variant =
        status === "in_progress"
            ? "accent"
            : status === "completed"
              ? "success"
              : status === "abandoned" || status === "excluded"
                ? "danger"
                : "neutral"
    return <Tag variant={variant as "accent" | "success" | "danger" | "neutral"}>{status}</Tag>
}

function EmptyRow({
    colspan,
    children,
}: {
    colspan: number
    children: React.ReactNode
}): JSX.Element {
    return (
        <tr>
            <td
                colSpan={colspan}
                className="px-4 py-12 text-center text-merism-text-muted"
            >
                {children}
            </td>
        </tr>
    )
}
