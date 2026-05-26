import { Check, Mic, MicOff } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { Button } from "~/lib/merism";

import { AudioCapture } from "./AudioCapture";

/**
 * MicCheck — pre-session microphone sanity check.
 *
 * Implements the PRODUCT.md §2.2 step 4 contract (prep page mic/cam test)
 * and doubles as the Silero ONNX model warm-up screen (ADR 0003).
 *
 * State machine:
 *   loading → prompt (say something) → heard (green tick) → ready
 *   loading → error (mic denied) → text-mode-fallback
 *
 * Once in `heard` state, the parent can continue to the full interview —
 * but AudioCapture is kept alive to skip a second mic-permission prompt.
 */
export interface MicCheckProps {
  onReady: (capture: AudioCapture) => void;
  onFallbackToText: () => void;
}

type Phase = "loading" | "prompt" | "heard" | "error";

export function MicCheck({ onReady, onFallbackToText }: MicCheckProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [level, setLevel] = useState(0);
  const captureRef = useRef<AudioCapture | null>(null);

  useEffect(() => {
    let cancelled = false;

    AudioCapture.create({
      onPCMFrame: () => {
        /* mic-check doesn't stream frames anywhere yet */
      },
      onLevel: (rms) => {
        if (cancelled) return;
        setLevel(rms);
        // RMS threshold ~0.02 corresponds to a calm talking voice
        // against AEC-processed silence. One frame above is
        // enough to confirm the mic is alive.
        if (rms > 0.02) {
          setPhase((cur) => (cur === "prompt" ? "heard" : cur));
        }
      },
      onReady: () => {
        if (!cancelled) setPhase("prompt");
      },
      onError: (err) => {
        if (cancelled) return;
        setPhase("error");
        setErrorMsg(err.message);
      },
    }).then((capture) => {
      if (cancelled) {
        capture.stop();
        return;
      }
      captureRef.current = capture;
    });

    return () => {
      cancelled = true;
      // Only tear down if we didn't hand the capture off.
      if (captureRef.current && phase !== "heard") {
        captureRef.current.stop();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleBegin() {
    const capture = captureRef.current;
    if (!capture) return;
    onReady(capture);
  }

  return (
    <div className="flex h-screen items-center justify-center bg-merism-bg-subtle p-6">
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
        className="w-full max-w-md rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6 shadow-merism-md"
      >
        <h1 className="mb-1 font-merism-display text-xl font-semibold">
          Quick mic check
        </h1>
        <p className="mb-6 text-sm text-merism-text-muted">
          Let's make sure we can hear you clearly before we start.
        </p>

        <div className="mb-6 flex flex-col items-center gap-3">
          <MicCheckIcon phase={phase} level={level} />

          {phase === "loading" && (
            <p className="text-sm text-merism-text-muted">
              Loading speech detection…
            </p>
          )}
          {phase === "prompt" && (
            <p className="text-sm font-medium text-merism-text">
              Say something like "hello" to test your microphone.
            </p>
          )}
          {phase === "heard" && (
            <p className="text-sm font-medium text-merism-success">
              Great — we heard you.
            </p>
          )}
          {phase === "error" && (
            <p className="text-sm text-merism-danger">{errorMsg}</p>
          )}

          <LevelMeter
            rms={level}
            active={phase === "prompt" || phase === "heard"}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Button
            onClick={handleBegin}
            disabled={phase !== "heard"}
            size="lg"
            className="w-full"
          >
            Begin interview
          </Button>
          <button
            type="button"
            onClick={onFallbackToText}
            className="mx-auto mt-1 text-xs text-merism-text-muted underline hover:text-merism-text"
          >
            Mic not working? Use text instead
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function MicCheckIcon({ phase, level }: { phase: Phase; level: number }) {
  if (phase === "error") {
    return (
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-merism-danger/10 text-merism-danger">
        <MicOff className="h-7 w-7" />
      </div>
    );
  }
  if (phase === "heard") {
    return (
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
        className="flex h-16 w-16 items-center justify-center rounded-full bg-merism-success/10 text-merism-success"
      >
        <Check className="h-7 w-7" />
      </motion.div>
    );
  }
  // Prompt / loading — subtle pulse keyed to mic RMS.
  const scale = phase === "prompt" ? 1 + Math.min(level * 3, 0.5) : 1;
  return (
    <motion.div
      animate={{ scale }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className="flex h-16 w-16 items-center justify-center rounded-full bg-merism-accent/10 text-merism-accent"
    >
      <Mic className="h-7 w-7" />
    </motion.div>
  );
}

function LevelMeter({ rms, active }: { rms: number; active: boolean }) {
  const percent = Math.min(100, Math.round(rms * 400));
  return (
    <div
      className="h-2 w-48 overflow-hidden rounded-merism-full bg-merism-bg-subtle"
      role="meter"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Microphone level"
    >
      <div
        className={`h-full transition-all duration-100 ${
          active ? "bg-merism-accent" : "bg-merism-text-muted"
        }`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
