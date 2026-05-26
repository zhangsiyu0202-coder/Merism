import { useValues } from "kea";
import { ArrowLeft, Copy, Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { urls } from "~/app/routes";
import { sceneLogic } from "~/app/sceneLogic";
import { api } from "~/lib/api";
import { Button } from "~/lib/merism";

interface TranscriptTurn {
  role: "user" | "assistant" | "agent" | "participant";
  text: string;
  timestamp?: string;
}

interface SessionDetail {
  id: string;
  status: string;
  transcript: TranscriptTurn[];
  study?: string;
}

/**
 * SessionTranscriptPage — transcript-only viewer.
 *
 * Per the 2026-05-20 simplification, this page renders ONLY the
 * transcript. No participant info, no metadata, no insights, no
 * decision log, no statistics. Backend keeps writing all those fields;
 * we just don't render them here.
 *
 * Three actions only:
 *   - 返回访谈列表
 *   - 复制转写
 *   - 导出 TXT
 */
export default function SessionTranscriptPage(): JSX.Element {
  const { sceneParams } = useValues(sceneLogic);
  const sessionId = sceneParams.params.sessionId as string | undefined;

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    api
      .get<SessionDetail>(`/api/sessions/${sessionId}/`)
      .then((data) => {
        setSession(data);
        setError(null);
      })
      .catch((err) => setError(err.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const transcript = session?.transcript ?? [];
  const studyId = session?.study;

  const transcriptText = useMemo(
    () => formatTranscript(transcript),
    [transcript],
  );

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(transcriptText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  }

  function handleExport(): void {
    const blob = new Blob([transcriptText], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcript-${sessionId?.slice(0, 8) ?? "session"}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  if (!sessionId) {
    return <div className="p-8 text-merism-text-muted">无效的访谈 ID</div>;
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center text-merism-text-muted">
        加载中…
      </div>
    );
  }

  if (error) {
    return <div className="p-8 text-merism-danger">{error}</div>;
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Back button only */}
      {studyId && (
        <a
          href={urls.study(studyId, "sessions")}
          className="inline-flex w-fit items-center gap-2 text-merism-body-sm text-merism-text-muted hover:text-merism-text"
        >
          <ArrowLeft className="h-4 w-4" />
          返回访谈列表
        </a>
      )}

      <div className="flex items-center justify-between">
        <h1 className="font-display text-merism-headline font-[500] text-merism-text">
          转写内容
        </h1>
        {transcript.length > 0 && (
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              iconLeft={<Copy className="h-4 w-4" />}
              onClick={handleCopy}
            >
              {copied ? "已复制" : "复制转写"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              iconLeft={<Download className="h-4 w-4" />}
              onClick={handleExport}
            >
              导出 TXT
            </Button>
          </div>
        )}
      </div>

      {transcript.length === 0 ? (
        <div className="rounded-merism-lg bg-merism-surface px-8 py-16 text-center text-merism-text-muted ring-1 ring-[color:var(--merism-hairline)]">
          暂无转写内容
        </div>
      ) : (
        <div className="w-full max-w-4xl space-y-1">
          {transcript.map((turn, i) => (
            <TranscriptBubble key={i} turn={turn} />
          ))}
        </div>
      )}
    </div>
  );
}

function isAssistantRole(role: string): boolean {
  return role === "assistant" || role === "agent";
}

function TranscriptBubble({ turn }: { turn: TranscriptTurn }): JSX.Element {
  const isAI = isAssistantRole(turn.role);
  return (
    <div
      className={`flex gap-4 px-4 py-3 rounded-merism-md transition-colors hover:bg-merism-surface/60 ${
        isAI ? "" : "bg-merism-accent-soft/20"
      }`}
    >
      <div className="w-20 shrink-0 pt-0.5">
        <span
          className={`inline-block rounded-merism-sm px-2 py-0.5 font-mono text-[11px] uppercase tracking-merism-caps ${
            isAI
              ? "bg-merism-surface text-merism-text-subtle ring-1 ring-[color:var(--merism-hairline)]"
              : "bg-merism-accent/10 text-merism-accent"
          }`}
        >
          {isAI ? "AI" : "受访者"}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] leading-[2] text-merism-text whitespace-pre-wrap">
          {turn.text}
        </p>
      </div>
    </div>
  );
}

function formatTranscript(transcript: TranscriptTurn[]): string {
  return transcript
    .map((turn) => {
      const speaker = isAssistantRole(turn.role) ? "AI" : "受访者";
      return `${speaker}：\n${turn.text}\n`;
    })
    .join("\n");
}
