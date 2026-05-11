/**
 * pcm-capture.worklet.js — AudioWorkletProcessor that forwards 16 kHz
 * mono PCM frames (512 samples ≈ 32 ms) to the main thread.
 *
 * Runs inside an AudioWorkletGlobalScope so there's no access to DOM,
 * no `require`, no ES module imports. Must stay plain ES2020 JS.
 *
 * Usage (main thread):
 *   const ctx = new AudioContext({ sampleRate: 16000 })
 *   await ctx.audioWorklet.addModule("/pcm-capture.worklet.js")
 *   const node = new AudioWorkletNode(ctx, "pcm-capture")
 *   node.port.onmessage = (e) => {  // e.data is Float32Array(512)
 *     ...
 *   }
 *   micSource.connect(node)
 *
 * Why 512 samples: matches what DashScope Paraformer expects as a
 * reasonable frame size (~30 ms at 16 kHz) and is cheap to post
 * every quantum boundary (4 quanta of 128 samples each).
 */

const FRAME_SIZE = 512

class PCMCaptureProcessor extends AudioWorkletProcessor {
    constructor() {
        super()
        this._buf = new Float32Array(FRAME_SIZE)
        this._off = 0
    }

    process(inputs) {
        const input = inputs[0]
        if (!input || input.length === 0) return true
        const channel = input[0]
        if (!channel) return true

        // Accumulate into the 512-sample frame buffer.
        for (let i = 0; i < channel.length; i++) {
            this._buf[this._off++] = channel[i]
            if (this._off >= FRAME_SIZE) {
                // Post a copy — the internal buffer is reused.
                this.port.postMessage(new Float32Array(this._buf))
                this._off = 0
            }
        }
        return true
    }
}

registerProcessor("pcm-capture", PCMCaptureProcessor)
