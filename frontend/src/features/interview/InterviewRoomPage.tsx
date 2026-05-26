import { useActions, useValues } from "kea";
import { Mic, MicOff, Paperclip, Square, Trash2, Video, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { Button, Input, Tag } from "~/lib/merism";

import { interviewRoomLogic } from "./interviewRoomLogic";
import TextInterviewPage from "./TextInterviewPage";
import type {
  InterviewMode,
  InterviewTurn,
  LocalAttachment,
  Stimulus,
} from "./types";
import { voiceStreamLogic } from "./voiceStreamLogic";

import { MicCheck } from "./voice/MicCheck";

/**
 * Interview Room surface — four phases:
 *
 *   1. ModeSelector — voice vs video
 *   2. MicCheck      — permission + RMS meter smoke
 *   3. LiveRoom      — 2/3 preview + 1/3 right column (PRODUCT.md §3.5)
 *   4. TextOnlyRoom  — fallback when mic is unavailable
 *
 * Layout references PRODUCT.md §3.5:
 *   - Centered logo header
 *   - Left 2/3: AI Interviewer label + big question text + big "Begin
 *     response" PTT button + aspect-video preview stage (waveform /
 *     camera / stimulus overlay)
 *   - Right 1/3: attachment uploader + transcript stream + text fallback
 *   - Bottom-right orange "自测模式" badge when ?preview=1
 */

type UiPhase = "mode" | "mic-check" | "live" | "text-only";

export default function InterviewRoomPage() {
  // Text-mode studies render a typed-conversation page, not the
  // voice/video shell. ParticipantEntryPage appends ?mode=text to the
  // interview URL when it routes a text-mode session in.
  if (typeof window !== "undefined") {
    const mode = new URLSearchParams(window.location.search).get("mode");
    if (mode === "text") {
      return <TextInterviewPage />;
    }
  }

  const {
    mode,
    sessionId,
    error: startError,
    previewMode,
  } = useValues(interviewRoomLogic);
  const {
    selectMode,
    startSession,
    clear: clearStart,
    setPreviewMode,
  } = useActions(interviewRoomLogic);

  const {
    turns,
    phase,
    partialCaption,
    agentCaption,
    error: streamError,
  } = useValues(voiceStreamLogic);
  const {
    connect,
    attachCapture,
    clear: clearStream,
    sendTextInput,
  } = useActions(voiceStreamLogic);

  const [uiPhase, setUiPhase] = useState<UiPhase>("mode");

  // Detect ?preview=1 once on mount.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setPreviewMode(params.get("preview") === "1");
  }, [setPreviewMode]);

  useEffect(
    () => () => {
      clearStart();
      clearStream();
    },
    [clearStart, clearStream],
  );

  const error = streamError || startError;

  if (error) {
    return (
      <ErrorView
        message={error}
        onRetry={() => {
          clearStart();
          clearStream();
          setUiPhase("mode");
        }}
      />
    );
  }

  if (uiPhase === "mode") {
    return (
      <ModeSelector
        mode={mode}
        onSelect={selectMode}
        onContinue={() => setUiPhase("mic-check")}
      />
    );
  }

  if (uiPhase === "mic-check") {
    return (
      <MicCheck
        onReady={(capture) => {
          attachCapture(capture);
          startSession();
          setUiPhase("live");
        }}
        onFallbackToText={() => setUiPhase("text-only")}
      />
    );
  }

  if (uiPhase === "live") {
    return (
      <LiveRoom
        sessionId={sessionId}
        mode={mode}
        phase={phase}
        turns={turns}
        partialCaption={partialCaption}
        agentCaption={agentCaption}
        previewMode={previewMode}
        onConnectNeeded={connect}
        onSendText={sendTextInput}
      />
    );
  }

  return (
    <TextOnlyRoom
      sessionId={sessionId}
      turns={turns}
      onStart={() => startSession()}
      onSendText={sendTextInput}
    />
  );
}

// ── Error / mode selector (unchanged) ──────────────────────────

function ErrorView({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex h-screen items-center justify-center bg-merism-bg-subtle">
      <div className="max-w-sm text-center">
        <h1 className="mb-2 text-lg font-semibold">Something went wrong</h1>
        <p className="mb-4 text-sm text-merism-text-muted">{message}</p>
        <Button onClick={onRetry}>Try again</Button>
      </div>
    </div>
  );
}

interface ModeSelectorProps {
  mode: InterviewMode;
  onSelect: (mode: InterviewMode) => void;
  onContinue: () => void;
}

function ModeSelector({ mode, onSelect, onContinue }: ModeSelectorProps) {
  return (
    <div className="flex h-screen items-center justify-center bg-merism-bg-subtle p-6">
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
        className="w-full max-w-md rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6 shadow-merism-md"
      >
        <h1 className="mb-1 font-merism-display text-xl font-semibold">
          Ready when you are
        </h1>
        <p className="mb-6 text-sm text-merism-text-muted">
          Choose how you'd like to take part. You'll speak; the AI moderator
          will guide the conversation.
        </p>
        <fieldset className="mb-6 flex gap-3">
          <ModeTile
            active={mode === "voice"}
            icon={<Mic className="h-5 w-5" />}
            label="Voice only"
            description="Microphone. No camera."
            onSelect={() => onSelect("voice")}
          />
          <ModeTile
            active={mode === "video"}
            icon={<Video className="h-5 w-5" />}
            label="Voice + video"
            description="Camera on; richer feedback."
            onSelect={() => onSelect("video")}
          />
        </fieldset>
        <Button onClick={onContinue} size="lg" className="w-full">
          Continue to mic check
        </Button>
      </motion.div>
    </div>
  );
}

interface ModeTileProps {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  description: string;
  onSelect: () => void;
}

function ModeTile({
  active,
  icon,
  label,
  description,
  onSelect,
}: ModeTileProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={
        "flex flex-1 flex-col items-start gap-1 rounded-merism-md border p-3 text-left " +
        "transition-colors " +
        (active
          ? "border-merism-accent bg-merism-accent/5"
          : "border-merism-border bg-merism-surface hover:bg-merism-bg-subtle")
      }
    >
      <span className="text-merism-accent">{icon}</span>
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xs text-merism-text-muted">{description}</span>
    </button>
  );
}

// ── LiveRoom (PRODUCT.md §3.5) ─────────────────────────────────

interface LiveRoomProps {
  sessionId: string | null;
  mode: InterviewMode;
  phase: string;
  turns: ReadonlyArray<InterviewTurn>;
  partialCaption: string;
  agentCaption: string;
  previewMode: boolean;
  onConnectNeeded: (sessionId: string) => void;
  onSendText: (text: string) => void;
}

function LiveRoom({
  sessionId,
  mode,
  phase,
  turns,
  partialCaption,
  agentCaption,
  previewMode,
  onConnectNeeded,
  onSendText,
}: LiveRoomProps) {
  const { pttActive, botSpeaking, micLevel } = useValues(voiceStreamLogic);
  const { pttPress } = useActions(voiceStreamLogic);
  const { activeStimulus, attachments } = useValues(interviewRoomLogic);
  const { hideStimulus, attachFile, removeAttachment } =
    useActions(interviewRoomLogic);

  useEffect(() => {
    if (sessionId) onConnectNeeded(sessionId);
  }, [sessionId, onConnectNeeded]);

  // Space toggles PTT unless typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat) return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA")
      )
        return;
      e.preventDefault();
      pttPress();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pttPress]);

  if (!sessionId) {
    return (
      <div className="flex h-screen items-center justify-center bg-merism-bg-subtle">
        <span className="text-sm text-merism-text-muted">
          Starting session…
        </span>
      </div>
    );
  }

  return (
    <div className="relative flex h-screen flex-col bg-merism-bg-subtle">
      <RoomHeader phase={phase} />

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[2fr_1fr]">
        <LeftColumn
          mode={mode}
          agentCaption={agentCaption || lastAgentText(turns)}
          micLevel={micLevel}
          pttActive={pttActive}
          botSpeaking={botSpeaking}
          activeStimulus={activeStimulus}
          onPttPress={pttPress}
          onCloseStimulus={hideStimulus}
        />
        <RightColumn
          turns={turns}
          partialCaption={partialCaption}
          agentCaption={agentCaption}
          attachments={attachments}
          onAttach={attachFile}
          onRemoveAttachment={removeAttachment}
          onSendText={onSendText}
        />
      </div>

      {previewMode && <PreviewBadge />}
    </div>
  );
}

// ── Header ─────────────────────────────────────────────────────

function RoomHeader({ phase }: { phase: string }) {
  return (
    <header className="relative flex h-14 shrink-0 items-center justify-center border-b border-[color:var(--merism-hairline)] bg-merism-surface px-4">
      <span className="font-merism-display text-base font-[500] tracking-tight">
        Merism
      </span>
      <span className="absolute right-4 text-xs text-merism-text-muted">
        {phase}
      </span>
    </header>
  );
}

// ── Left 2/3 ───────────────────────────────────────────────────

interface LeftColumnProps {
  mode: InterviewMode;
  agentCaption: string;
  micLevel: number;
  pttActive: boolean;
  botSpeaking: boolean;
  activeStimulus: Stimulus | null;
  onPttPress: () => void;
  onCloseStimulus: () => void;
}

function LeftColumn({
  mode,
  agentCaption,
  micLevel,
  pttActive,
  botSpeaking,
  activeStimulus,
  onPttPress,
  onCloseStimulus,
}: LeftColumnProps) {
  return (
    <section className="flex min-h-0 flex-col gap-6 px-8 py-6">
      <Tag variant="neutral">AI Interviewer</Tag>

      <motion.div
        key={agentCaption.slice(0, 40) || "placeholder"}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
        className="font-merism-display text-merism-headline font-medium text-merism-text"
      >
        {agentCaption}
      </motion.div>

      <div className="flex justify-center">
        <PTTButton
          pttActive={pttActive}
          botSpeaking={botSpeaking}
          onPress={onPttPress}
        />
      </div>

      <PreviewStage
        mode={mode}
        micLevel={micLevel}
        activeStimulus={activeStimulus}
        onCloseStimulus={onCloseStimulus}
      />
    </section>
  );
}

// ── Big PTT button (PRODUCT.md: "Begin response", 圆形 + ● 前缀) ──

interface PTTButtonProps {
  pttActive: boolean;
  botSpeaking: boolean;
  onPress: () => void;
}

function PTTButton({
  pttActive,
  botSpeaking,
  onPress,
}: PTTButtonProps) {
  // Three states only — barge-in is disabled product-wide so the
  // "interrupt AI" path no longer exists. The button is:
  //   1. ``pttActive``: user is recording. Coral-red, pulsing.
  //   2. ``botSpeaking``: bot is speaking. Disabled, with a soundwave
  //      indicator so the disabled state reads as "AI 正在说话, 请稍候"
  //      not "the button is broken" (Bug 2026-05-25).
  //   3. idle: ready for the user to start. Coral, mic icon.
  const blocked = botSpeaking && !pttActive;
  const label = pttActive
    ? "结束回答"
    : blocked
      ? "AI 正在说话"
      : "开始回答";

  const Icon = pttActive ? Square : blocked ? MicOff : Mic;

  const bg = pttActive
    ? "bg-[oklch(0.62_0.20_25)] text-white"
    : blocked
      ? "bg-merism-bg-subtle text-merism-text-muted cursor-not-allowed"
      : "bg-merism-accent text-white hover:brightness-[1.05]";

  return (
    <button
      type="button"
      onClick={onPress}
      disabled={blocked}
      aria-disabled={blocked}
      aria-label={label}
      aria-busy={blocked}
      className={
        "inline-flex items-center gap-2 rounded-merism-full px-7 py-3 " +
        "font-merism-display text-base font-medium shadow-merism-md " +
        "transition-transform hover:scale-[1.02] active:scale-[0.99] disabled:hover:scale-100 " +
        bg +
        (pttActive ? " animate-pulse" : "")
      }
    >
      {blocked ? (
        // Three animated bars — reads as "AI is currently speaking,
        // wait for it to finish". Replaces the earlier solid-dot icon
        // which was visually identical to the idle state and made
        // users think the button was just broken.
        <span
          aria-hidden="true"
          className="inline-flex items-end gap-[2px] h-3"
        >
          <span className="w-[2px] h-2 bg-current rounded-sm animate-[wave_900ms_ease-in-out_infinite]" />
          <span className="w-[2px] h-3 bg-current rounded-sm animate-[wave_900ms_ease-in-out_infinite] [animation-delay:120ms]" />
          <span className="w-[2px] h-2 bg-current rounded-sm animate-[wave_900ms_ease-in-out_infinite] [animation-delay:240ms]" />
        </span>
      ) : (
        <span aria-hidden="true" className="text-sm leading-none">
          ●
        </span>
      )}
      <Icon className="h-4 w-4" />
      <span>{label}</span>
      <span className="ml-2 text-merism-caption opacity-70">Space</span>
    </button>
  );
}

// ── Preview stage: waveform / camera / stimulus overlay ────────

interface PreviewStageProps {
  mode: InterviewMode;
  micLevel: number;
  activeStimulus: Stimulus | null;
  onCloseStimulus: () => void;
}

function PreviewStage({
  mode,
  micLevel,
  activeStimulus,
  onCloseStimulus,
}: PreviewStageProps) {
  // Key the overlay on stimulus id + concept_index so AnimatePresence
  // does a crossfade on every concept switch within one rotation.
  const overlayKey = activeStimulus
    ? `${activeStimulus.id}-${activeStimulus.concept_index ?? "x"}`
    : "empty";

  return (
    <div className="relative flex aspect-video min-h-0 flex-1 items-center justify-center overflow-hidden rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card">
      <AnimatePresence mode="wait">
        <motion.div
          key={overlayKey}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
          className="absolute inset-0 flex items-center justify-center"
        >
          {activeStimulus ? (
            <StimulusOverlay
              stimulus={activeStimulus}
              onClose={onCloseStimulus}
            />
          ) : mode === "video" ? (
            <CameraPreview />
          ) : (
            <Waveform micLevel={micLevel} />
          )}
        </motion.div>
      </AnimatePresence>

      {activeStimulus &&
        activeStimulus.concept_index !== undefined &&
        activeStimulus.concept_count !== undefined && (
          <ConceptProgress
            index={activeStimulus.concept_index}
            total={activeStimulus.concept_count}
          />
        )}
    </div>
  );
}

interface ConceptProgressProps {
  index: number; // 0-based
  total: number;
}

function ConceptProgress({ index, total }: ConceptProgressProps) {
  // Participants see a NUMBER, not the internal label (PRODUCT.md §3.5).
  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
      aria-live="polite"
      className="absolute left-3 top-3 flex items-center gap-2 rounded-merism-full bg-black/55 px-3 py-2 text-xs text-white backdrop-blur"
    >
      <span className="font-merism-mono uppercase tracking-merism-caps-tight">
        Concept {index + 1} of {total}
      </span>
      <span className="flex items-center gap-1">
        {Array.from({ length: total }, (_, i) => {
          const done = i < index;
          const current = i === index;
          return (
            <span
              key={i}
              aria-hidden="true"
              className={
                "inline-block rounded-full transition-all duration-[var(--merism-duration-fast)] " +
                "ease-[var(--merism-ease)] " +
                (current
                  ? "h-2 w-2 bg-merism-accent ring-2 ring-merism-accent/40"
                  : done
                    ? "h-2 w-2 bg-merism-accent/80"
                    : "h-2 w-2 bg-white/40")
              }
            />
          );
        })}
      </span>
    </motion.div>
  );
}

function Waveform({ micLevel }: { micLevel: number }) {
  const BAR_COUNT = 24;
  // Multiple phases give a fuller wave look than flat bars.
  const bars = Array.from({ length: BAR_COUNT }, (_, i) => {
    const phase = Math.sin((i / BAR_COUNT) * Math.PI * 2);
    // Baseline 12% + dynamic 0–100% scaled from RMS (≈0–0.3 typical).
    const height =
      12 + Math.min(88, micLevel * 300 * (0.6 + 0.4 * Math.abs(phase)));
    return height;
  });
  return (
    <div
      aria-label="Microphone level"
      className="flex h-1/2 items-center gap-2"
    >
      {bars.map((h, i) => (
        <span
          key={i}
          className="w-2 rounded-full bg-merism-accent/70 transition-[height] duration-75 ease-out"
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  );
}

function CameraPreview() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia({ video: { width: 1280, height: 720 }, audio: false })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Camera denied."),
      );

    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  if (error) {
    return (
      <span className="text-sm text-merism-text-muted">
        Camera unavailable · {error}
      </span>
    );
  }

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      className="h-full w-full object-cover"
    />
  );
}

function StimulusOverlay({
  stimulus,
  onClose,
}: {
  stimulus: Stimulus;
  onClose: () => void;
}) {
  return (
    <>
      {stimulus.kind === "image" ? (
        <img
          src={stimulus.url}
          alt={stimulus.title}
          className="h-full w-full object-contain"
        />
      ) : stimulus.kind === "video" ? (
        <video src={stimulus.url} autoPlay controls className="h-full w-full" />
      ) : (
        <iframe
          src={stimulus.url}
          title={stimulus.title}
          className="h-full w-full"
        />
      )}
      <button
        type="button"
        aria-label="Close stimulus"
        onClick={onClose}
        className="absolute right-3 top-3 rounded-merism-full bg-black/40 p-2 text-white backdrop-blur hover:bg-black/60"
      >
        <X className="h-4 w-4" />
      </button>
      <span className="absolute bottom-3 left-3 rounded-merism-md bg-black/50 px-2 py-1 text-xs text-white backdrop-blur">
        {stimulus.title}
      </span>
    </>
  );
}

// ── Right 1/3: attachments + transcript + text fallback ────────

interface RightColumnProps {
  turns: ReadonlyArray<InterviewTurn>;
  partialCaption: string;
  agentCaption: string;
  attachments: ReadonlyArray<LocalAttachment>;
  onAttach: (file: File) => void;
  onRemoveAttachment: (id: string) => void;
  onSendText: (text: string) => void;
}

function RightColumn({
  turns,
  partialCaption,
  agentCaption,
  attachments,
  onAttach,
  onRemoveAttachment,
  onSendText,
}: RightColumnProps) {
  const [text, setText] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSendText(trimmed);
    setText("");
  }

  return (
    <aside className="flex min-h-0 flex-col border-l border-[color:var(--merism-hairline)] bg-merism-surface">
      <AttachmentArea
        attachments={attachments}
        onAttach={onAttach}
        onRemove={onRemoveAttachment}
      />

      <header className="shrink-0 border-b border-[color:var(--merism-hairline)] px-4 py-3 text-sm font-medium text-merism-text">
        Live transcript
      </header>

      <div className="flex min-h-0 flex-1 flex-col-reverse overflow-y-auto px-4 py-3">
        <div className="flex flex-col gap-3">
          {turns.length === 0 && !agentCaption && !partialCaption ? (
            <p className="m-auto text-sm text-merism-text-muted">
              The AI will start the conversation.
            </p>
          ) : (
            <>
              {turns.map((t, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
                  className={
                    "rounded-merism-md px-3 py-2 text-sm " +
                    (t.role === "agent"
                      ? "bg-merism-bg-subtle text-merism-text"
                      : t.role === "participant"
                        ? "self-end bg-merism-accent/10 text-merism-text"
                        : "text-center text-xs text-merism-text-muted")
                  }
                >
                  {t.text}
                </motion.div>
              ))}
              {partialCaption && (
                <div className="self-end rounded-merism-md bg-merism-accent/5 px-3 py-2 text-sm italic text-merism-text-muted">
                  {partialCaption}…
                </div>
              )}
              {agentCaption && (
                <div className="rounded-merism-md bg-merism-bg-subtle px-3 py-2 text-sm text-merism-text">
                  {agentCaption}
                  <span
                    aria-label="Generating"
                    className="ml-1 inline-flex gap-1 align-middle"
                  >
                    <span className="h-1 w-1 animate-pulse rounded-full bg-merism-text-muted" />
                    <span className="h-1 w-1 animate-pulse rounded-full bg-merism-text-muted [animation-delay:100ms]" />
                    <span className="h-1 w-1 animate-pulse rounded-full bg-merism-text-muted [animation-delay:200ms]" />
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex shrink-0 items-center gap-2 border-t border-[color:var(--merism-hairline)] p-3"
        aria-label="Text input fallback"
      >
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type if you'd rather not speak…"
          className="flex-1"
        />
        <Button type="submit" size="sm" disabled={!text.trim()}>
          Send
        </Button>
      </form>
    </aside>
  );
}

interface AttachmentAreaProps {
  attachments: ReadonlyArray<LocalAttachment>;
  onAttach: (file: File) => void;
  onRemove: (id: string) => void;
}

function AttachmentArea({
  attachments,
  onAttach,
  onRemove,
}: AttachmentAreaProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;
    for (const f of Array.from(files)) onAttach(f);
    e.target.value = "";
  }

  return (
    <div className="shrink-0 border-b border-[color:var(--merism-hairline)] px-4 py-3">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="flex w-full items-center gap-2 rounded-merism-md border border-dashed border-merism-border bg-merism-bg-subtle px-3 py-2 text-sm text-merism-text-muted transition-colors hover:border-merism-accent hover:text-merism-text"
      >
        <Paperclip className="h-4 w-4" />
        <span>Attach image, video, or PDF</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*,application/pdf"
        multiple
        hidden
        onChange={handleChange}
      />

      {attachments.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {attachments.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between gap-2 rounded-merism-md bg-merism-bg-subtle px-2 py-2 text-xs"
            >
              <div className="flex min-w-0 items-center gap-2">
                {a.kind === "image" && (
                  <img
                    src={a.previewUrl}
                    alt=""
                    className="h-7 w-7 shrink-0 rounded object-cover"
                  />
                )}
                <span className="truncate text-merism-text">{a.file.name}</span>
                <span className="shrink-0 text-merism-text-muted">
                  {formatSize(a.file.size)}
                </span>
              </div>
              <button
                type="button"
                aria-label="Remove attachment"
                onClick={() => onRemove(a.id)}
                className="shrink-0 text-merism-text-muted hover:text-merism-text"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ── 自测模式 badge ─────────────────────────────────────────────

function PreviewBadge() {
  return (
    <div className="pointer-events-none absolute bottom-4 right-4 select-none rounded-merism-md bg-[oklch(0.72_0.18_60)] px-3 py-2 font-merism-mono text-xs font-medium text-white shadow-merism-md">
      自测模式 · Preview
    </div>
  );
}

// ── Text-only fallback ─────────────────────────────────────────

interface TextOnlyRoomProps {
  sessionId: string | null;
  turns: ReadonlyArray<InterviewTurn>;
  onStart: () => void;
  onSendText: (text: string) => void;
}

function TextOnlyRoom({
  sessionId,
  turns,
  onStart,
  onSendText,
}: TextOnlyRoomProps) {
  useEffect(() => {
    if (!sessionId) onStart();
  }, [sessionId, onStart]);

  return (
    <div className="flex h-screen flex-col bg-merism-bg-subtle">
      <header className="flex h-14 shrink-0 items-center justify-center border-b border-[color:var(--merism-hairline)] bg-merism-surface px-4">
        <span className="font-merism-display text-base font-[500]">Merism</span>
        <Tag variant="neutral" className="absolute right-4">
          Text mode
        </Tag>
      </header>
      <RightColumn
        turns={turns}
        partialCaption=""
        agentCaption=""
        attachments={[]}
        onAttach={() => {
          /* disabled in text mode */
        }}
        onRemoveAttachment={() => {
          /* disabled */
        }}
        onSendText={onSendText}
      />
    </div>
  );
}

function lastAgentText(turns: ReadonlyArray<InterviewTurn>): string {
  for (let i = turns.length - 1; i >= 0; i--) {
    if (turns[i]?.role === "agent") return turns[i]?.text ?? "";
  }
  return "Let's begin. Can you tell me a little about your role?";
}
