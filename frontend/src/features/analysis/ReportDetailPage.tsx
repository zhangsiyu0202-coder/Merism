import { ArrowLeft, Download, Link2, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { useValues, useActions } from "kea";
import { useTranslation } from "react-i18next";

import {
  Button,
  Card,
  Dialog,
  DialogContent,
  DialogTitle,
  Input,
  Tabs,
  TabsList,
  TabsTrigger,
} from "~/lib/merism";

import { AnalysisChart } from "./AnalysisChart";
import type { ChartSpec } from "./AnalysisChart";
import { reportDetailLogic } from "./reportDetailLogic";
import type { ReportQuestion, ReportSegment } from "./reportsLogic";
import { GeneratingState, LoadingState } from "./StateComponents";

export function ReportDetailPage({
  reportId,
  onBack,
}: {
  reportId: string;
  onBack: () => void;
}): JSX.Element {
  const { t } = useTranslation();
  const { report, filteredQuestions, segments, isLoading, isGenerating } =
    useValues(reportDetailLogic);
  const { generateReport, togglePublic, setActiveSegment, addQuestion } =
    useActions(reportDetailLogic);
  const [showAddQ, setShowAddQ] = useState(false);
  const [newQTitle, setNewQTitle] = useState("");
  const [newQType, setNewQType] = useState("open_ended");

  if (isLoading) return <LoadingState message={t("reports.loading_report")} />;
  if (isGenerating) return <GeneratingState title={t("reports.generating")} />;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="rounded-merism-sm p-1.5 hover:bg-merism-bg-subtle"
          aria-label={t("reports.back_to_reports")}
        >
          <ArrowLeft className="h-4 w-4 text-merism-text-muted" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="text-merism-h2 font-display font-[450] text-merism-text truncate">
            {report?.title ?? t("reports.title")}
          </h1>
          <p className="text-merism-caption text-merism-text-muted">
            {report?.generated_at
              ? `${t("insights.kpi_last_updated")}: ${new Date(report.generated_at).toLocaleString()}`
              : t("reports.not_yet_generated")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={togglePublic}>
            <Link2 className="mr-1.5 h-3.5 w-3.5" />
            {report?.is_public ? t("reports.unshare") : t("reports.share")}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              window.open(
                `/api/custom-reports/${reportId}/export_csv/`,
                "_blank",
              )
            }
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            CSV
          </Button>
          <Button variant="primary" size="sm" onClick={generateReport}>
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            {t("insights.generate")}
          </Button>
        </div>
      </div>

      {report?.is_public && (
        <div className="flex items-center gap-2 rounded-merism-md bg-merism-accent/5 px-4 py-2 text-merism-body-sm text-merism-accent">
          <Link2 className="h-4 w-4" />
          <span>{t("reports.public_link_active")}</span>
          <button
            onClick={() =>
              report?.share_url &&
              navigator.clipboard.writeText(
                window.location.origin + report.share_url,
              )
            }
            className="ml-auto underline"
          >
            {t("recruit.copy_link")}
          </button>
        </div>
      )}

      {report?.ai_synthesis && (
        <Card className="p-5">
          <h2 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
            {t("insights.executive_summary")}
          </h2>
          <p className="text-merism-body-sm leading-relaxed text-merism-text">
            {report.ai_synthesis}
          </p>
        </Card>
      )}

      <div className="flex items-center gap-3">
        <Tabs
          defaultValue="all"
          onValueChange={(v) => setActiveSegment(v === "all" ? null : v)}
        >
          <TabsList>
            <TabsTrigger value="all">{t("studies.tabs.all")}</TabsTrigger>
            {segments.map((s: ReportSegment) => (
              <TabsTrigger key={s.id} value={s.id}>
                {s.name}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Button variant="secondary" size="sm" onClick={() => setShowAddQ(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          {t("outline.question_text")}
        </Button>
      </div>

      <div className="flex flex-col gap-6">
        {filteredQuestions.map((q: ReportQuestion) => (
          <QuestionBlock key={q.id} question={q} />
        ))}
      </div>

      <Dialog open={showAddQ} onOpenChange={setShowAddQ}>
        <DialogContent>
          <DialogTitle>{t("outline.question_text")}</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (newQTitle.trim()) {
                addQuestion(newQTitle.trim(), newQType);
                setNewQTitle("");
                setShowAddQ(false);
              }
            }}
            className="flex flex-col gap-4 pt-4"
          >
            <Input
              value={newQTitle}
              onChange={(e) => setNewQTitle(e.target.value)}
              placeholder={t("reports.question_placeholder")}
              autoFocus
            />
            <select
              value={newQType}
              onChange={(e) => setNewQType(e.target.value)}
              className="rounded-merism-md border border-[color:var(--merism-hairline)] bg-merism-surface px-3 py-2 text-merism-body-sm"
            >
              <option value="open_ended">
                {t("reports.question_types.open_ended")}
              </option>
              <option value="multi_select">
                {t("reports.question_types.multi_select")}
              </option>
              <option value="single_select">
                {t("reports.question_types.single_select")}
              </option>
              <option value="rating">
                {t("reports.question_types.rating")}
              </option>
              <option value="ranking">
                {t("reports.question_types.ranking")}
              </option>
            </select>
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowAddQ(false)}
                type="button"
              >
                {t("common.cancel")}
              </Button>
              <Button variant="primary" size="sm" type="submit">
                {t("common.create")}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function QuestionBlock({
  question,
}: {
  question: ReportQuestion;
}): JSX.Element {
  const { t } = useTranslation();
  const chartSpec = toChartSpec(question.chart_spec);
  const typeLabels: Record<string, string> = {
    open_ended: t("reports.question_types.open_ended"),
    multi_select: t("reports.question_types.multi_select"),
    single_select: t("reports.question_types.single_select"),
    rating: t("reports.question_types.rating"),
    ranking: t("reports.question_types.ranking"),
  };

  return (
    <Card className="overflow-hidden">
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

      {question.status === "ready" && (
        <div className="flex flex-col gap-5 p-5">
          {question.ai_summary && (
            <p className="text-merism-body-sm leading-relaxed text-merism-text">
              {question.ai_summary}
            </p>
          )}
          {chartSpec && <AnalysisChart spec={chartSpec} height={240} />}
          {question.themes.length > 0 && (
            <div>
              <h4 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                {t("insights.themes")}
              </h4>
              <div className="flex flex-col gap-2">
                {question.themes.map((th, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-merism-md bg-merism-bg-subtle px-3 py-2"
                  >
                    <div>
                      <span className="text-merism-body-sm font-medium text-merism-text">
                        {th.name}
                      </span>
                      {th.description && (
                        <p className="text-merism-caption text-merism-text-muted">
                          {th.description}
                        </p>
                      )}
                    </div>
                    <span className="text-merism-caption text-merism-text-muted">
                      {th.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {question.quotes.length > 0 && (
            <div>
              <h4 className="mb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                {t("insights.supporting_evidence")}
              </h4>
              <div className="flex flex-col gap-2">
                {question.quotes.map((q, i) => (
                  <blockquote
                    key={i}
                    className="border-l-2 border-merism-accent/40 pl-3 text-merism-body-sm italic text-merism-text-muted"
                  >
                    &ldquo;{q.text}&rdquo;
                    <cite className="mt-1 block text-merism-caption not-italic text-merism-text-subtle">
                      &mdash; {q.source}
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
          {t("reports.generating")}…
        </div>
      )}
    </Card>
  );
}

function toChartSpec(spec: Record<string, unknown>): ChartSpec | null {
  if (!isChartType(spec.type) || typeof spec.title !== "string") {
    return null;
  }
  return spec as unknown as ChartSpec;
}

function isChartType(value: unknown): value is ChartSpec["type"] {
  return value === "bar" || value === "pie" || value === "line";
}

function QuestionStatus({ status }: { status: string }): JSX.Element {
  const styles: Record<string, string> = {
    pending: "bg-merism-bg-subtle text-merism-text-muted",
    generating: "bg-merism-accent/10 text-merism-accent",
    ready: "bg-emerald-50 text-emerald-700",
    failed: "bg-red-50 text-red-700",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-merism-caption ${styles[status] ?? ""}`}
    >
      {status}
    </span>
  );
}

export default ReportDetailPage;
