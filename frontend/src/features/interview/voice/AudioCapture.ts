/**
 * AudioCapture — microphone streaming with a PTT gate.
 *
 * Architecture (pure Web Audio, no ML):
 *   MediaStreamSource → AudioWorkletNode("pcm-capture") → (discarded)
 *                    ↘ AnalyserNode (for RMS metering, never sinked)
 *
 * The worklet posts 512-sample Float32 frames (~32 ms @ 16 kHz). Frames
 * are forwarded to {@link AudioCaptureCallbacks.onPCMFrame} only when
 * the PTT gate is open. The RMS level is reported every frame
 * regardless of gate state, so the UI meter can always reassure the
 * participant that their mic is alive.
 *
 * Why no VAD:
 *   The interview room is push-to-talk; the PTT button is the sole
 *   source of truth for user-turn transitions (see voiceStreamLogic).
 *   Browser-side ML VAD (ONNX + Silero) was removed in favour of this
 *   minimal stack — 13 MB of wasm deleted, no Vite<->onnxruntime-web
 *   dep-optimizer skirmish, straightforward to reason about.
 */

export interface AudioCaptureCallbacks {
  onPCMFrame: (frame: Int16Array) => void;
  /**
   * Fires every frame with the real-time RMS level (0..1). UI uses
   * this for the mic meter + the "we hear you" glow in the PTT
   * button, regardless of whether the gate is open.
   */
  onLevel: (rms: number) => void;
  onReady: () => void;
  onError: (error: Error) => void;
}

export interface AudioCaptureStats {
  framesForwarded: number;
  framesSuppressed: number;
  lastLevel: number;
  gate: boolean;
}

const WORKLET_URL = "/pcm-capture.worklet.js";
const ANALYSER_FFT = 2048;

export class AudioCapture {
  static async create(callbacks: AudioCaptureCallbacks): Promise<AudioCapture> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
          channelCount: 1,
        },
      });
      const context = new AudioContext({ sampleRate: 16000 });
      // Resume on user gesture — many browsers start the context
      // suspended; caller must have already granted mic permission
      // at this point so the gesture chain is intact.
      if (context.state === "suspended") {
        await context.resume();
      }
      await context.audioWorklet.addModule(WORKLET_URL);
      const capture = new AudioCapture(stream, context, callbacks);
      capture.start();
      callbacks.onReady();
      return capture;
    } catch (err) {
      callbacks.onError(
        err instanceof Error
          ? err
          : new Error("Microphone permission denied or unavailable."),
      );
      throw err;
    }
  }

  private readonly source: MediaStreamAudioSourceNode;
  private readonly worklet: AudioWorkletNode;
  private readonly analyser: AnalyserNode;
  private readonly timeData: Float32Array<ArrayBuffer>;
  private rafId: number | null = null;
  private gateOpen = false;
  private readonly stats: AudioCaptureStats = {
    framesForwarded: 0,
    framesSuppressed: 0,
    lastLevel: 0,
    gate: false,
  };

  private constructor(
    private readonly stream: MediaStream,
    private readonly context: AudioContext,
    private readonly callbacks: AudioCaptureCallbacks,
  ) {
    this.source = context.createMediaStreamSource(stream);

    this.worklet = new AudioWorkletNode(context, "pcm-capture", {
      numberOfInputs: 1,
      numberOfOutputs: 0,
      channelCount: 1,
      channelCountMode: "explicit",
      channelInterpretation: "discrete",
    });
    this.worklet.port.onmessage = (event) => {
      const frame = event.data as Float32Array;
      if (this.gateOpen) {
        this.callbacks.onPCMFrame(toPCM16(frame));
        this.stats.framesForwarded += 1;
      } else {
        this.stats.framesSuppressed += 1;
      }
    };

    this.analyser = context.createAnalyser();
    this.analyser.fftSize = ANALYSER_FFT;
    this.analyser.smoothingTimeConstant = 0.6;
    this.timeData = new Float32Array(
      new ArrayBuffer(this.analyser.fftSize * 4),
    );
  }

  /** Expose the shared AudioContext so AudioPlayback can re-use it. */
  getAudioContext(): AudioContext {
    return this.context;
  }

  getStats(): AudioCaptureStats {
    return { ...this.stats };
  }

  /** Open / close the PTT gate. Frames only forward when open. */
  setGate(open: boolean): void {
    this.gateOpen = open;
    this.stats.gate = open;
  }

  private start(): void {
    // Mic → worklet (for PCM frames) AND mic → analyser (for level).
    // Neither path is connected to destination — we don't want to
    // hear ourselves.
    this.source.connect(this.worklet);
    this.source.connect(this.analyser);

    const loop = (): void => {
      this.analyser.getFloatTimeDomainData(this.timeData);
      let sumSq = 0;
      for (let i = 0; i < this.timeData.length; i++) {
        const v = this.timeData[i] ?? 0;
        sumSq += v * v;
      }
      const rms = Math.sqrt(sumSq / this.timeData.length);
      this.stats.lastLevel = rms;
      this.callbacks.onLevel(rms);
      this.rafId = requestAnimationFrame(loop);
    };
    this.rafId = requestAnimationFrame(loop);
  }

  stop(): void {
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.rafId = null;
    try {
      this.worklet.disconnect();
      this.analyser.disconnect();
      this.source.disconnect();
    } catch {
      /* ignore — graph already torn down */
    }
    for (const track of this.stream.getTracks()) {
      track.stop();
    }
    // Context is shared with AudioPlayback — don't close here.
  }
}

/**
 * Float32 [-1, 1] → Int16 PCM16 16 kHz. Clamps then scales; no dither.
 */
function toPCM16(frame: Float32Array): Int16Array {
  const out = new Int16Array(frame.length);
  for (let i = 0; i < frame.length; i++) {
    const sample = frame[i] ?? 0;
    const clamped = Math.max(-1, Math.min(1, sample));
    out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return out;
}
