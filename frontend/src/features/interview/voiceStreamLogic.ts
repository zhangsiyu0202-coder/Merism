import { actions, kea, listeners, path, reducers } from "kea"

import { AudioCapture, AudioPlayback } from "./voice"
import type { InterviewTurn, SessionStatus } from "./types"
import type { voiceStreamLogicType } from "./voiceStreamLogicType"

/**
 * voiceStreamLogic — PTT-driven WebSocket voice channel.
 *
 * User interaction model (PTT):
 *   1. Press button once → start recording (AudioCapture gate opens),
 *      server receives a ``vad_speaking_start`` carrying the current
 *      ``audio_played_ms`` so any in-flight bot response gets truncated
 *      at the exact hear-point.
 *   2. Press again → stop recording (gate closes), server receives a
 *      ``vad_speaking_end``. The accumulated transcript ends the turn.
 *   3. Press while bot is speaking → acts as an interrupt + start (same
 *      as #1). Server truncates bot history to what was actually heard.
 *
 * Silero VAD still runs, but purely for UI affordances (level meter,
 * probability glow). It no longer drives state transitions.
 */

export interface ServerMessage {
    type: string
    [key: string]: unknown
}

export const voiceStreamLogic = kea<voiceStreamLogicType>([
    path(["scenes", "interview_room", "voiceStreamLogic"]),

    actions({
        attachCapture: (capture: AudioCapture) => ({ capture }),
        connect: (sessionId: string) => ({ sessionId }),
        disconnect: true,
        serverMessage: (message: ServerMessage) => ({ message }),
        appendCaption: (turn: InterviewTurn) => ({ turn }),
        setPartialCaption: (text: string) => ({ text }),
        setAgentCaption: (text: string) => ({ text }),
        setMicLevel: (level: number) => ({ level }),
        setPhase: (phase: SessionStatus) => ({ phase }),
        setBargeInEnabled: (enabled: boolean) => ({ enabled }),
        setError: (error: string | null) => ({ error }),
        setPttActive: (active: boolean) => ({ active }),
        setBotSpeaking: (speaking: boolean) => ({ speaking }),
        pttPress: true,
        sendTextInput: (text: string) => ({ text }),
        clear: true,
    }),

    reducers({
        connected: [
            false,
            {
                connect: () => true,
                disconnect: () => false,
                clear: () => false,
            },
        ],
        phase: [
            "pending" as SessionStatus,
            {
                setPhase: (_, { phase }) => phase,
                clear: () => "pending",
            },
        ],
        bargeInEnabled: [
            false,
            {
                setBargeInEnabled: (_, { enabled }) => enabled,
            },
        ],
        pttActive: [
            false,
            {
                setPttActive: (_, { active }) => active,
                clear: () => false,
                disconnect: () => false,
            },
        ],
        botSpeaking: [
            false,
            {
                setBotSpeaking: (_, { speaking }) => speaking,
                clear: () => false,
                disconnect: () => false,
            },
        ],
        partialCaption: [
            "",
            {
                setPartialCaption: (_, { text }) => text,
                appendCaption: () => "",
            },
        ],
        agentCaption: [
            "",
            {
                setAgentCaption: (_, { text }) => text,
                appendCaption: () => "",
            },
        ],
        turns: [
            [] as InterviewTurn[],
            {
                appendCaption: (state, { turn }) => [...state, turn],
                clear: () => [],
            },
        ],
        micLevel: [
            0,
            {
                setMicLevel: (_, { level }) => level,
            },
        ],
        error: [
            null as string | null,
            {
                setError: (_, { error }) => error,
                clear: () => null,
            },
        ],
    }),

    listeners(({ actions: a, values }) => {
        let ws: WebSocket | null = null
        let capture: AudioCapture | null = null
        let player: AudioPlayback | null = null
        let agentDeltaBuffer = ""

        function sendJson(msg: object): void {
            if (!ws || ws.readyState !== WebSocket.OPEN) return
            ws.send(JSON.stringify(msg))
        }

        async function buildCapture(): Promise<AudioCapture> {
            return AudioCapture.create({
                onPCMFrame: (pcm) => {
                    if (ws?.readyState === WebSocket.OPEN) {
                        ws.send(pcm.buffer)
                    }
                },
                onLevel: (level) => a.setMicLevel(level),
                onReady: () => {
                    /* noop — connect orchestrates start order */
                },
                onError: (err) => a.setError(err.message),
            })
        }

        return {
            attachCapture: ({ capture: incoming }) => {
                // MicCheck pre-built the capture; keep it but we still own
                // the gate (it starts closed — no audio streamed until the
                // user presses the PTT button).
                capture = incoming
                incoming.setGate(false)
                player = new AudioPlayback(incoming.getAudioContext())
            },

            connect: async ({ sessionId }) => {
                if (!capture) {
                    try {
                        capture = await buildCapture()
                        player = new AudioPlayback(capture.getAudioContext())
                    } catch (err) {
                        a.setError(err instanceof Error ? err.message : "Mic unavailable.")
                        return
                    }
                } else {
                    // MicCheck handed over a capture — re-create with our
                    // streaming callbacks so ``onPCMFrame`` forwards to the
                    // live WS rather than MicCheck's local level meter.
                    const preserved = capture
                    capture = await buildCapture()
                    preserved.stop()
                    player = new AudioPlayback(capture.getAudioContext())
                }
                capture.setGate(false)

                const proto = location.protocol === "https:" ? "wss" : "ws"
                ws = new WebSocket(
                    `${proto}://${location.host}/ws/sessions/${sessionId}/voice/`,
                )
                ws.binaryType = "arraybuffer"

                ws.addEventListener("open", () => {
                    sendJson({
                        type: "session_start",
                        sample_rate: 16000,
                        client_prefers_barge_in: false,
                    })
                })
                ws.addEventListener("message", (event) => {
                    if (event.data instanceof ArrayBuffer) {
                        void player?.enqueue(event.data)
                        return
                    }
                    try {
                        const parsed = JSON.parse(String(event.data)) as ServerMessage
                        a.serverMessage(parsed)
                    } catch {
                        /* non-JSON text frame — ignore */
                    }
                })
                ws.addEventListener("close", () => a.disconnect())
                ws.addEventListener("error", () =>
                    a.setError("Voice channel lost. Please rejoin."),
                )
            },

            pttPress: () => {
                if (!capture || !ws || ws.readyState !== WebSocket.OPEN) return

                if (values.pttActive) {
                    // Releasing the turn.
                    capture.setGate(false)
                    sendJson({
                        type: "vad_speaking_end",
                        ts: performance.now() / 1000,
                    })
                    a.setPttActive(false)
                    return
                }

                // Beginning a new turn. If the bot is currently speaking,
                // this is also an interrupt — the same message carries the
                // played-ms so history truncates precisely.
                const playedMs = player?.getPlayedMs() ?? 0
                sendJson({
                    type: "vad_speaking_start",
                    ts: performance.now() / 1000,
                    audio_played_ms: playedMs,
                })
                if (values.botSpeaking) {
                    // Tear down local playback instantly so there's no
                    // tail while the server processes the interruption.
                    player?.interrupt()
                    agentDeltaBuffer = ""
                }
                capture.setGate(true)
                a.setPttActive(true)
            },

            sendTextInput: ({ text }) => {
                if (!text.trim()) return
                sendJson({ type: "text_input", text })
            },

            disconnect: () => {
                a.clear()
            },

            serverMessage: ({ message }) => {
                switch (message.type) {
                    case "session_ready":
                        a.setBargeInEnabled(Boolean(message.barge_in_enabled))
                        a.setPhase("active")
                        break
                    case "partial_transcript":
                        a.setPartialCaption(String(message.text ?? ""))
                        break
                    case "final_transcript":
                        a.appendCaption({
                            role: "participant",
                            text: String(message.text ?? ""),
                        })
                        break
                    case "agent_text_delta":
                        agentDeltaBuffer += String(message.delta ?? "")
                        a.setAgentCaption(agentDeltaBuffer)
                        break
                    case "agent_text_done":
                        a.appendCaption({
                            role: "agent",
                            text: String(message.text ?? agentDeltaBuffer),
                        })
                        agentDeltaBuffer = ""
                        player?.markResponseBoundary()
                        break
                    case "bot_started_speaking":
                        a.setBotSpeaking(true)
                        break
                    case "bot_stopped_speaking":
                        a.setBotSpeaking(false)
                        player?.markResponseBoundary()
                        break
                    case "phase_change":
                        a.setPhase((message.phase as SessionStatus) ?? "active")
                        break
                    case "stimulus_show": {
                        // Build a Stimulus from the wire message + delegate
                        // to interviewRoomLogic which owns activeStimulus.
                        const content = (message.content ?? {}) as Record<
                            string,
                            unknown
                        >
                        const url =
                            typeof content.url === "string"
                                ? content.url
                                : typeof content.href === "string"
                                  ? content.href
                                  : ""
                        const title =
                            typeof content.title === "string" ? content.title : ""
                        const kind =
                            (message.kind as
                                | "image"
                                | "video"
                                | "pdf"
                                | "text"
                                | "link") ?? "image"
                        // Lazy-import interviewRoomLogic to avoid a circular
                        // kea dependency at module load.
                        void import("./interviewRoomLogic").then(
                            ({ interviewRoomLogic }) => {
                                interviewRoomLogic.actions.showStimulus({
                                    id: String(message.stimulus_id ?? ""),
                                    kind,
                                    title,
                                    url,
                                    concept_index:
                                        typeof message.concept_index === "number"
                                            ? message.concept_index
                                            : undefined,
                                    concept_count:
                                        typeof message.concept_count === "number"
                                            ? message.concept_count
                                            : undefined,
                                    block_title:
                                        typeof message.block_title === "string"
                                            ? message.block_title
                                            : undefined,
                                })
                            },
                        )
                        break
                    }
                    case "barge_in_accepted":
                        player?.interrupt()
                        agentDeltaBuffer = ""
                        a.setBotSpeaking(false)
                        break
                    case "error":
                        a.setError(String(message.message ?? "Voice channel error."))
                        break
                }
            },

            clear: () => {
                capture?.stop()
                player?.stop()
                ws?.close()
                ws = null
                capture = null
                player = null
                agentDeltaBuffer = ""
            },
        }
    }),
])
