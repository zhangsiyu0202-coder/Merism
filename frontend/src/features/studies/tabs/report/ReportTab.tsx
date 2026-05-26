import { SectionLabel } from "~/lib/merism";

export default function ReportTab(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <SectionLabel>Report</SectionLabel>
      <div className="rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-10 text-center text-merism-text-muted">
        Report placeholder — 4-panel StudyReport (summary / highlights /
        personas / tasks) per PRODUCT.md §4.
      </div>
    </div>
  );
}
