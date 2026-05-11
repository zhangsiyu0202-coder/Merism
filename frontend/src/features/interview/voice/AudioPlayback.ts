/**
 * AudioPlayback — streaming TTS audio queue.
 *
 * Takes compressed audio chunks (CosyVoice ships MP3 frames) and schedules
 * them on a shared AudioContext. Shared context avoids the ~100 ms
 * `AudioContext` init cost and keeps `currentTime` stable across chunks,
 * so sequential frames play back seamlessly.
 *
 * Barge-in (ADR 0002): when the user's VAD fires, the orchestration layer
 * (a) queries {@link getPlayedMs} to know how much of the current response
 * was actually heard, (b) sends that alongside the Interruption message so
 * the server can truncate conversation history to what was HEARD (the
 * `conversation.item.truncate` semantic from OpenAI's Realtime API). Then
 * the orchestration layer calls {@link interrupt} to kill all scheduled
 * sources for instant silence.
 */
export class AudioPlayback {
    private readonly context: AudioContext
    private playheadTime: number
    private sources: AudioBufferSourceNode[] = []
    private readonly ownedContext: boolean

    /**
     * When the first chunk of the CURRENT response starts playing.
     * ``null`` when no response is actively being rendered. Reset on
     * {@link interrupt} and when the caller signals a new response via
     * {@link markResponseBoundary}.
     */
    private currentResponseStartTime: number | null = null

    /** Pass in an existing context (preferred) or let us allocate one. */
    constructor(context?: AudioContext) {
        if (context) {
            this.context = context
            this.ownedContext = false
        } else {
            this.context = new AudioContext()
            this.ownedContext = true
        }
        this.playheadTime = this.context.currentTime
    }

    async enqueue(data: ArrayBuffer): Promise<void> {
        if (data.byteLength === 0) return
        try {
            const audioBuffer = await this.context.decodeAudioData(data.slice(0))
            const source = this.context.createBufferSource()
            source.buffer = audioBuffer
            source.connect(this.context.destination)
            const startAt = Math.max(this.context.currentTime, this.playheadTime)
            source.start(startAt)

            // First audio chunk of a response anchors the playback clock.
            if (this.currentResponseStartTime === null) {
                this.currentResponseStartTime = startAt
            }

            this.playheadTime = startAt + audioBuffer.duration
            source.onended = () => {
                const i = this.sources.indexOf(source)
                if (i >= 0) this.sources.splice(i, 1)
            }
            this.sources.push(source)
        } catch {
            // Frame wasn't decodable (raw PCM, truncated MP3). Swallow
            // because we don't want one bad frame to kill playback.
        }
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
        if (this.currentResponseStartTime === null) return 0
        const elapsed = this.context.currentTime - this.currentResponseStartTime
        return Math.max(0, Math.floor(elapsed * 1000))
    }

    /**
     * Called by the orchestration layer at response boundaries
     * (agent_text_done / next user turn) to reset the playback clock.
     * Next audio chunk will re-anchor.
     */
    markResponseBoundary(): void {
        this.currentResponseStartTime = null
    }

    /** Kill all queued sources — used on barge-in or turn cleanup. */
    interrupt(): void {
        for (const s of this.sources) {
            try {
                s.stop()
            } catch {
                /* already stopped */
            }
        }
        this.sources = []
        this.playheadTime = this.context.currentTime
        this.currentResponseStartTime = null
    }

    stop(): void {
        this.interrupt()
        if (this.ownedContext) {
            void this.context.close()
        }
    }
}
