/**
 * Ask Merism domain types. Shape mirrors merism.reports.schema.CustomReportAnswer
 * on the backend — see merism-app/merism/reports/schema.py.
 */

export interface AskMerismCitation {
  session_id: string;
  ts: number;
  quote: string;
  speaker: string;
  study_id?: string | null;
  study_name?: string;
}

export interface AskMerismChart {
  type: "bar" | "line" | "pie";
  title: string;
  x: string[];
  y: number[];
  unit?: string | null;
}

export interface AskMerismAnswer {
  answer_markdown: string;
  chart: AskMerismChart | null;
  citations: AskMerismCitation[];
}

export type AskMerismRole = "user" | "assistant";

export interface AskMerismMessage {
  id: string;
  role: AskMerismRole;
  content: string;
  streaming?: boolean;
  errored?: boolean;
  chart?: AskMerismChart;
  citations?: AskMerismCitation[];
}
