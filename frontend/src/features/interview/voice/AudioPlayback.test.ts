import { describe, expect, it } from "vitest"

import { AudioPlayback } from "./AudioPlayback"

class FakeAudioBuffer {
    readonly duration: number
    readonly sampleRate: number
    private readonly channels: Float32Array[]

    constructor(numberOfChannels: number, length: number, sampleRate: number) {
        this.sampleRate = sampleRate
        this.duration = length / sampleRate
        this.channels = Array.from({ length: numberOfChannels }, () => new Float32Array(length))
    }

    getChannelData(channel: number): Float32Array {
        return this.channels[channel] ?? new Float32Array(0)
    }
}

class FakeAudioSource {
    buffer: FakeAudioBuffer | null = null
    startAt: number | null = null
    onended: (() => void) | null = null

    connect(_destination: unknown): void {}

    start(startAt: number): void {
        this.startAt = startAt
    }

    stop(): void {
        this.onended?.()
    }
}

class FakeAudioContext {
    readonly currentTime = 3.25
    readonly destination = {}
    readonly buffers: FakeAudioBuffer[] = []
    readonly sources: FakeAudioSource[] = []

    async decodeAudioData(_data: ArrayBuffer): Promise<AudioBuffer> {
        return Promise.reject(new Error("not encoded"))
    }

    createBuffer(channels: number, length: number, sampleRate: number): FakeAudioBuffer {
        const buffer = new FakeAudioBuffer(channels, length, sampleRate)
        this.buffers.push(buffer)
        return buffer
    }

    createBufferSource(): FakeAudioSource {
        const source = new FakeAudioSource()
        this.sources.push(source)
        return source
    }

    async close(): Promise<void> {
        return Promise.resolve()
    }
}

describe("AudioPlayback", () => {
    it("plays raw PCM16 chunks when decodeAudioData fails", async () => {
        const context = new FakeAudioContext()
        const playback = new AudioPlayback(context as unknown as AudioContext, 24000)
        const pcm = new Int16Array([0, 16384, -16384, 32767, -32768])

        const played = await playback.enqueue(pcm.buffer.slice(0))

        expect(played).toBe(true)

        expect(context.buffers).toHaveLength(1)
        expect(context.sources).toHaveLength(1)

        const buffer = context.buffers[0]
        if (!buffer) {
            throw new Error("expected decoded audio buffer")
        }
        const source = context.sources[0]
        if (!source) {
            throw new Error("expected scheduled audio source")
        }
        const channel = buffer.getChannelData(0)

        expect(buffer.sampleRate).toBe(24000)
        expect(channel[0]).toBeCloseTo(0, 6)
        expect(channel[1]).toBeCloseTo(0.5, 2)
        expect(channel[2]).toBeCloseTo(-0.5, 2)
        expect(channel[3]).toBeCloseTo(1, 6)
        expect(channel[4]).toBeCloseTo(-1, 6)
        expect(source.startAt).toBe(context.currentTime)
    })

    it("carries odd PCM tail bytes across chunks", async () => {
        const context = new FakeAudioContext()
        const playback = new AudioPlayback(context as unknown as AudioContext, 24000)
        const bytes = new Uint8Array(
            new Int16Array([256, 512, 1024]).buffer.slice(0),
        )

        const first = await playback.enqueue(bytes.slice(0, 3).buffer)
        const second = await playback.enqueue(bytes.slice(3).buffer)

        expect(first).toBe(true)
        expect(second).toBe(true)
        expect(context.buffers).toHaveLength(2)

        const firstChannel = context.buffers[0]?.getChannelData(0)
        const secondChannel = context.buffers[1]?.getChannelData(0)
        expect(firstChannel).toHaveLength(1)
        expect(secondChannel).toHaveLength(2)
        expect(firstChannel?.[0]).toBeCloseTo(256 / 0x7fff, 4)
        expect(secondChannel?.[0]).toBeCloseTo(512 / 0x7fff, 4)
        expect(secondChannel?.[1]).toBeCloseTo(1024 / 0x7fff, 4)
    })
})
