import { useState } from "react"
import { useValues, useActions, useMountedLogic } from "kea"

import { Select } from "~/lib/merism"
import { studiesLogic } from "~/features/studies/studiesLogic"

import { ReportsListPage } from "./ReportsListPage"
import { ReportDetailPage } from "./ReportDetailPage"
import { reportsLogic } from "./reportsLogic"
import { reportDetailLogic } from "./reportDetailLogic"
import { EmptyState } from "./StateComponents"
import { FileText } from "lucide-react"

export function ReportsPage(): JSX.Element {
    useMountedLogic(studiesLogic)
    const { studies } = useValues(studiesLogic)
    const { studyId } = useValues(reportsLogic)
    const { setStudyId } = useActions(reportsLogic)
    const { setReportId } = useActions(reportDetailLogic)
    const [selectedReportId, setSelectedReportId] = useState<string | null>(null)

    const studyOptions = (studies ?? []).map((s: { id: string; name: string }) => ({ value: s.id, label: s.name || "Untitled" }))

    const handleSelectReport = (reportId: string): void => {
        setSelectedReportId(reportId)
        setReportId(reportId)
    }

    return (
        <div className="flex flex-col gap-6 p-6">
            <div className="flex items-center gap-4">
                <h1 className="text-merism-h2 font-display font-[450] text-merism-text">Reports</h1>
                <Select options={studyOptions} value={studyId || ""} onChange={(val) => setStudyId(val)} placeholder="Select a study..." />
            </div>

            {!studyId && (
                <EmptyState
                    icon={<FileText className="h-6 w-6" />}
                    title="Select a study"
                    description="Choose a study to create and view custom AI research reports."
                />
            )}

            {studyId && !selectedReportId && (
                <ReportsListPage onSelectReport={handleSelectReport} />
            )}

            {studyId && selectedReportId && (
                <ReportDetailPage reportId={selectedReportId} onBack={() => setSelectedReportId(null)} />
            )}
        </div>
    )
}

export default ReportsPage
