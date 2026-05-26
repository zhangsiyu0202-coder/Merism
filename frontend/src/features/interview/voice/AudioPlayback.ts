/**
 * AudioPlayback — streaming TTS audio queue.
 *
 * Takes TTS audio chunks and schedules them on a shared AudioContext.
 * The live DashScope TTS path currently emits raw PCM16 at 24 kHz, but
 * the player also keeps a decodeAudioData path for encoded chunks so the
 * transport can evolve without forcing another frontend rewrite.
 *
 * Shared context avoids the ~100 ms `AudioContext` init cost and keeps
 * `currentTime` stable across chunks, so sequential frames play back
 * seamlessly.
 *
 * Barge-in (ADR 0002): when the user signals an interrupt / PTT start,
 * the orchestration layer (a) queries {@link getPlayedMs} to know how
 * much of the current response was actually heard, (b) sends that
 * alongside the Interruption message so the server can truncate
 * conversation history to what was HEARD (the
 * `conversation.item.truncate` semantic from OpenAI's Realtime API).
 * Then the orchestration layer calls
 * {@link interrupt} to kill all scheduled sources for instant silence.
 */
export class AudioPlayback {
  private readonly context: AudioContext;
  private playheadTime: number;
  private sources: AudioBufferSourceNode[] = [];
  private readonly ownedContext: boolean;
  private readonly outputSampleRate: number;
  private pcmCarry: Uint8Array | null = null;

  /**
   * When the first chunk of the CURRENT response starts playing.
   * ``null`` when no response is actively being rendered. Reset on
   * {@link interrupt} and when the caller signals a new response via
   * {@link markResponseBoundary}.
   */
  private currentResponseStartTime: number | null = null;

  /** Pass in an existing context (preferred) or let us allocate one. */
  constructor(context?: AudioContext, outputSampleRate: number = 24000) {
    if (context) {
      this.context = context;
      this.ownedContext = false;
    } else {
      this.context = new AudioContext();
      this.ownedContext = true;
    }
    this.outputSampleRate = outputSampleRate;
    this.playheadTime = this.context.currentTime;
  }

  async enqueue(data: ArrayBuffer): Promise<boolean> {
    if (data.byteLength === 0) return false;
    try {
      const audioBuffer = await this.decodeAudioChunk(data);
      if (!audioBuffer) return false;
      const source = this.context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.context.destination);
      const startAt = Math.max(this.context.currentTime, this.playheadTime);
      source.start(startAt);

      // First audio chunk of a response anchors the playback clock.
      if (this.currentResponseStartTime === null) {
        this.currentResponseStartTime = startAt;
      }

      this.playheadTime = startAt + audioBuffer.duration;
      source.onended = () => {
        const i = this.sources.indexOf(source);
        if (i >= 0) this.sources.splice(i, 1);
      };
      this.sources.push(source);
      return true;
    } catch {
      // Frame wasn't decodable (raw PCM, truncated MP3). Swallow
      // because we don't want one bad frame to kill playback.
      return false;
    }
  }

  private async decodeAudioChunk(
    data: ArrayBuffer,
  ): Promise<AudioBuffer | null> {
    try {
      return await this.context.decodeAudioData(data.slice(0));
    } catch {
      return this.decodePcm16(data);
    }
  }

  private decodePcm16(data: ArrayBuffer): AudioBuffer | null {
    const incoming = new Uint8Array(data);
    const combined =
      this.pcmCarry && this.pcmCarry.byteLength > 0
        ? concatUint8(this.pcmCarry, incoming)
        : incoming;
    const usableBytes = combined.byteLength - (combined.byteLength % 2);
    if (usableBytes <= 0) return null;
    this.pcmCarry =
      usableBytes === combined.byteLength ? null : combined.slice(usableBytes);

    const samples = new Int16Array(
      combined.buffer.slice(
        combined.byteOffset,
        combined.byteOffset + usableBytes,
      ),
    );
    const audioBuffer = this.context.createBuffer(
      1,
      samples.length,
      this.outputSampleRate,
    );
    const channel = audioBuffer.getChannelData(0);
    for (let i = 0; i < samples.length; i += 1) {
      const sample = samples[i] ?? 0;
      channel[i] = sample < 0 ? sample / 0x8000 : sample / 0x7fff;
    }
    return audioBuffer;
  }

  /**
   * How many ms of the current response's audio the user has actually
   * heard by now. 0 when nothing is playing (between turns).
   *
   * Uses the AudioContext clock, which is tied to the audio output
   * device — so this reflects WALL-CLOCK heard time, not "scheduled"
   * or "queued" time.
   */
  getPlayedMs(): number {
    if (this.currentResponseStartTime === null) return 0;
    const elapsed = this.context.currentTime - this.currentResponseStartTime;
    return Math.max(0, Math.floor(elapsed * 1000));
  }

  /**
   * Called by the orchestration layer at response boundaries
   * (agent_text_done / next user turn) to reset the playback clock.
   * Next audio chunk will re-anchor.
   */
  markResponseBoundary(): void {
    this.currentResponseStartTime = null;
  }

  /** Kill all queued sources — used on barge-in or turn cleanup. */
  interrupt(): void {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    }
    this.sources = [];
    this.playheadTime = this.context.currentTime;
    this.currentResponseStartTime = null;
    this.pcmCarry = null;
  }

  stop(): void {
    this.interrupt();
    if (this.ownedContext) {
      void this.context.close();
    }
  }
}

function concatUint8(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out = new Uint8Array(a.byteLength + b.byteLength);
  out.set(a, 0);
  out.set(b, a.byteLength);
  return out;
}
