import { Clock, FileText, MoreHorizontal, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { useValues, useActions } from "kea"

import { Button, Card, Dialog, DialogContent, DialogTitle, Input } from "~/lib/merism"

import { reportsLogic } from "./reportsLogic"
import type { CustomReportData } from "./reportsLogic"
import { EmptyState, LoadingState } from "./StateComponents"

export function ReportsListPage({
    onSelectReport,
}: {
    onSelectReport: (reportId: string) => void
}): JSX.Element {
    const { reports, isLoading } = useValues(reportsLogic)
    const { createReport, deleteReport } = useActions(reportsLogic)
    const [showCreate, setShowCreate] = useState(false)
    const [newTitle, setNewTitle] = useState("")

    if (isLoading) return <LoadingState message="Loading reports..." />

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-end">
                <Button variant="primary" size="sm" onClick={() => setShowCreate(true)}>
                    <Plus className="mr-2 h-3.5 w-3.5" />
                    New Report
                </Button>
            </div>

            {reports.length === 0 ? (
                <EmptyState
                    icon={<FileText className="h-6 w-6" />}
                    title="No reports yet"
                    description="Create a custom report to ask new research questions of your interview data."
                    action={{ label: "Create Report", onClick: () => setShowCreate(true) }}
                />
            ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {reports.map((report: CustomReportData) => (
                        <ReportCard
                            key={report.id}
                            report={report}
                            onClick={() => onSelectReport(report.id)}
                            onDelete={() => deleteReport(report.id)}
                        />
                    ))}
                </div>
            )}

            {/* Create dialog */}
            <Dialog open={showCreate} onOpenChange={setShowCreate}>
                <DialogContent>
                    <DialogTitle>New Report</DialogTitle>
                    <form
                        onSubmit={(e) => {
                            e.preventDefault()
                            if (newTitle.trim()) {
                                createReport(newTitle.trim())
                                setNewTitle("")
                                setShowCreate(false)
                            }
                        }}
                        className="flex flex-col gap-4 pt-4"
                    >
                        <Input
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            placeholder="Report title..."
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <Button variant="secondary" size="sm" onClick={() => setShowCreate(false)} type="button">
                                Cancel
                            </Button>
                            <Button variant="primary" size="sm" type="submit">
                                Create
                            </Button>
                        </div>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    )
}

function ReportCard({
    report,
    onClick,
    onDelete,
}: {
    report: CustomReportData
    onClick: () => void
    onDelete: () => void
}): JSX.Element {
    const [menuOpen, setMenuOpen] = useState(false)

    return (
        <Card
            className="group relative cursor-pointer p-5 transition-shadow hover:shadow-merism-float"
            onClick={onClick}
        >
            <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                    <h3 className="text-merism-body-sm font-medium text-merism-text truncate">
                        {report.title}
                    </h3>
                    <div className="mt-2 flex items-center gap-3 text-merism-caption text-merism-text-muted">
                        <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {report.generated_at
                                ? new Date(report.generated_at).toLocaleDateString()
                                : "Not generated"}
                        </span>
                        <span>{report.questions_count} questions</span>
                    </div>
                    <div className="mt-2">
                        <StatusBadge status={report.status} />
                    </div>
                </div>
                <button
                    onClick={(e) => {
                        e.stopPropagation()
                        setMenuOpen(!menuOpen)
                    }}
                    className="rounded-merism-sm p-1 opacity-0 transition-opacity hover:bg-merism-bg-subtle group-hover:opacity-100"
                    aria-label="Report actions"
                >
                    <MoreHorizontal className="h-4 w-4 text-merism-text-muted" />
                </button>
            </div>
            {menuOpen && (
                <div className="absolute right-4 top-12 z-10 rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface p-1 shadow-merism-float">
                    <button
                        onClick={(e) => {
                            e.stopPropagation()
                            onDelete()
                            setMenuOpen(false)
                        }}
                        className="flex w-full items-center gap-2 rounded-merism-sm px-3 py-1.5 text-merism-caption text-merism-danger hover:bg-merism-bg-subtle"
                    >
                        <Trash2 className="h-3 w-3" />
                        Delete
                    </button>
                </div>
            )}
        </Card>
    )
}

function StatusBadge({ status }: { status: string }): JSX.Element {
    const styles: Record<string, string> = {
        draft: "bg-merism-bg-subtle text-merism-text-muted",
        generating: "bg-merism-accent/10 text-merism-accent",
        ready: "bg-emerald-50 text-emerald-700",
        failed: "bg-red-50 text-red-700",
    }
    return (
        <span className={`inline-block rounded-full px-2 py-0.5 text-merism-caption ${styles[status] ?? styles.draft}`}>
            {status}
        </span>
    )
}

export default ReportsListPage
