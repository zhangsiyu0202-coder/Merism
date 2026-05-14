import {
    ArrowLeft,
    Download,
    Filter,
    Link2,
    Plus,
    Sparkles,
} from "lucide-react"
import { useState } from "react"
import { useValues, useActions } from "kea"

import { Button, Card, Dialog, DialogContent, DialogTitle, Input, Tabs, TabsContent, TabsList, TabsTrigger } from "~/lib/merism"

import { AnalysisChart } from "./AnalysisChart"
import type { ChartSpec } from "./AnalysisChart"
import { reportDetailLogic } from "./reportDetailLogic"
import type { ReportQuestion } from "./reportsLogic"
import { GeneratingState, LoadingState } from "./StateComponents"

export function ReportDetailPage({
    reportId,
    onBack,
}: {
    reportId: string
    onBack: () => void
}): JSX.Element {
    const { report, filteredQuestions, segments, isLoading, isGenerating } =
        useValues(reportDetailLogic)
    const { generateReport, togglePublic, setActiveSegment, addQuestion } =
        useActions(reportDetailLogic)
    const [showAddQ, setShowAddQ] = useState(false)
    const [newQTitle, setNewQTitle] = useState("")
    const [newQType, setNewQType] = useState("open_ended")

    if (isLoading) return <LoadingState message="Loading report..." />
    if (isGenerating) return <GeneratingState title="Generating report analysis" />

    const handleExportCSV = (): void => {
        window.open(`/api/custom-reports/${reportId}/export_csv/`, "_blank")
    }
    const handleExportPDF = (): void => {
        window.open(`/api/custom-reports/${reportId}/export_pdf/`, "_blank")
    }
    const handleCopyShareLink = (): void => {
        if (report?.share_url) {
            navigator.clipboard.writeText(window.location.origin + report.share_url)
        }
    }

    return (
        <div className="flex flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <button
                    onClick={onBack}
                    className="rounded-merism-sm p-1.5 hover:bg-merism-bg-subtle"
                    aria-label="Back to reports"
                >
                    <ArrowLeft className="h-4 w-4 text-merism-text-muted" />
                </button>
                <div className="min-w-0 flex-1">
                    <h1 className="text-merism-h2 font-display font-[450] text-merism-text truncate">
                        {report?.title ?? "Report"}
                    </h1>
                    <p className="text-merism-caption text-merism-text-muted">
                        {report?.generated_at
                            ? `Last run: ${new Date(report.generated_at).toLocaleString()}`
                            : "Not yet generated"}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={togglePublic}>
                        <Link2 className="mr-1.5 h-3.5 w-3.5" />
                        {report?.is_public ? "Unshare" : "Share"}
                    </Button>
                    <Button variant="secondary" size="sm" onClick={handleExportCSV}>
                        <Download className="mr-1.5 h-3.5 w-3.5" />
                        CSV
                    </Button>
                    <Button variant="secondary" size="sm" onClick={handleExportPDF}>
                        <Download className="mr-1.5 h-3.5 w-3.5" />
                        PDF
                    </Button>
                    <Button variant="primary" size="sm" onClick={generateReport}>
                        <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                        Generate
                    </Button>
                </div>
            </div>

            {/* Share link notice */}
            {report?.is_public && (
                <div className="flex items-center gap-2 rounded-merism-md bg-merism-accent/5 px-4 py-2 text-merism-body-sm text-merism-accent">
                    <Link2 className="h-4 w-4" />
                    <span>Public link active</span>
                    <button onClick={handleCopyShareLink} className="ml-auto underline">
                        Copy link
                    </button>
                </div>
            )}

            {/* AI Synthesis */}
            {report?.ai_synthesis && (
                <Card className="p-5">
                    <h2 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                        AI-Powered Synthesis
                    </h2>
                    <p className="text-merism-body-sm leading-relaxed text-merism-text">
                        {report.ai_synthesis}
                    </p>
                </Card>
            )}

            {/* Segment tabs */}
            <div className="flex items-center gap-3">
                <Tabs defaultValue="all" onValueChange={(v) => setActiveSegment(v === "all" ? null : v)}>
                    <TabsList>
                        <TabsTrigger value="all">All</TabsTrigger>
                        {segments.map((s) => (
                            <TabsTrigger key={s.id} value={s.id}>
                                {s.name}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </Tabs>
                <Button variant="secondary" size="sm" onClick={() => setShowAddQ(true)}>
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Question
                </Button>
            </div>

            {/* Questions */}
            <div className="flex flex-col gap-6">
                {filteredQuestions.map((q: ReportQuestion) => (
                    <QuestionBlock key={q.id} question={q} />
                ))}
            </div>

            {/* Add question dialog */}
            <Dialog open={showAddQ} onOpenChange={setShowAddQ}>
                <DialogContent>
                    <DialogTitle>Add Question</DialogTitle>
                    <form
                        onSubmit={(e) => {
                            e.preventDefault()
                            if (newQTitle.trim()) {
                                addQuestion(newQTitle.trim(), newQType)
                                setNewQTitle("")
                                setShowAddQ(false)
                            }
                        }}
                        className="flex flex-col gap-4 pt-4"
                    >
                        <Input
                            value={newQTitle}
                            onChange={(e) => setNewQTitle(e.target.value)}
                            placeholder="Research question..."
                            autoFocus
                        />
                        <select
                            value={newQType}
                            onChange={(e) => setNewQType(e.target.value)}
                            className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface px-3 py-2 text-merism-body-sm"
                        >
                            <option value="open_ended">Open-ended</option>
                            <option value="multi_select">Multi-select</option>
                            <option value="single_select">Single-select</option>
                            <option value="rating">Rating</option>
                            <option value="ranking">Ranking</option>
                        </select>
                        <div className="flex justify-end gap-2">
                            <Button variant="secondary" size="sm" onClick={() => setShowAddQ(false)} type="button">
                                Cancel
                            </Button>
                            <Button variant="primary" size="sm" type="submit">
                                Add
                            </Button>
                        </div>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    )
}

function QuestionBlock({ question }: { question: ReportQuestion }): JSX.Element {
    const typeLabels: Record<string, string> = {
        open_ended: "Open-ended question",
        multi_select: "Multi-select question",
        single_select: "Single-select question",
        rating: "Rating question",
        ranking: "Ranking question",
    }

    return (
        <Card className="overflow-hidden">
            {/* Question header */}
            <div className="border-b border-[color:var(--merism-hairline)] px-5 py-4">
                <div className="flex items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-merism-accent/10 text-merism-caption font-medium text-merism-accent">
                        Q{question.question_number}
                    </span>
                    <div className="min-w-0 flex-1">
                        <h3 className="text-merism-body-sm font-medium text-merism-text">
                            {question.title}
                        </h3>
                        <p className="text-merism-caption text-merism-text-muted">
                            {typeLabels[question.question_type] ?? question.question_type}
                        </p>
                    </div>
                    <QuestionStatus status={question.status} />
                </div>
            </div>

            {/* Analysis content */}
            {question.status === "ready" && (
                <div className="flex flex-col gap-5 p-5">
                    {/* AI Summary */}
                    {question.ai_summary && (
                        <p className="text-merism-body-sm leading-relaxed text-merism-text">
                            {question.ai_summary}
                        </p>
                    )}

                    {/* Chart */}
                    {question.chart_spec?.type && (
                        <AnalysisChart spec={question.chart_spec as ChartSpec} height={240} />
                    )}

                    {/* Themes */}
                    {question.themes.length > 0 && (
                        <div>
                            <h4 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                                Themes
                            </h4>
                            <div className="flex flex-col gap-2">
                                {question.themes.map((t, i) => (
                                    <div
                                        key={i}
                                        className="flex items-center justify-between rounded-merism-md bg-merism-bg-subtle px-3 py-2"
                                    >
                                        <div>
                                            <span className="text-merism-body-sm font-medium text-merism-text">
                                                {t.name}
                                            </span>
                                            {t.description && (
                                                <p className="text-merism-caption text-merism-text-muted">
                                                    {t.description}
                                                </p>
                                            )}
                                        </div>
                                        <span className="text-merism-caption text-merism-text-muted">
                                            {t.count} mentions
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Quotes */}
                    {question.quotes.length > 0 && (
                        <div>
                            <h4 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                                Supporting Quotes
                            </h4>
                            <div className="flex flex-col gap-2">
                                {question.quotes.map((q, i) => (
                                    <blockquote
                                        key={i}
                                        className="border-l-2 border-merism-accent/40 pl-3 text-merism-body-sm italic text-merism-text-muted"
                                    >
                                        "{q.text}"
                                        <cite className="mt-1 block text-merism-caption not-italic text-merism-text-subtle">
                                            — {q.source}
                                            {q.theme && (
                                                <span className="ml-2 rounded-full bg-merism-bg-subtle px-2 py-0.5 not-italic">
                                                    {q.theme}
                                                </span>
                                            )}
                                        </cite>
                                    </blockquote>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {question.status === "generating" && (
                <div className="flex items-center gap-2 px-5 py-4 text-merism-body-sm text-merism-accent">
                    <Sparkles className="h-4 w-4 animate-pulse" />
                    Analyzing...
                </div>
            )}
        </Card>
    )
}

function QuestionStatus({ status }: { status: string }): JSX.Element {
    const styles: Record<string, string> = {
        pending: "bg-merism-bg-subtle text-merism-text-muted",
        generating: "bg-merism-accent/10 text-merism-accent",
        ready: "bg-emerald-50 text-emerald-700",
        failed: "bg-red-50 text-red-700",
    }
    return (
        <span className={`rounded-full px-2 py-0.5 text-merism-caption ${styles[status] ?? ""}`}>
            {status}
        </span>
    )
}

export default ReportDetailPage
