export type InterviewMode = "voice" | "video" | "text" | "offline";

export type SessionStatus = "pending" | "active" | "completed" | "failed";

export type TurnRole = "agent" | "participant" | "system";

export interface InterviewTurn {
  role: TurnRole;
  text: string;
  ts?: number;
  /** Optional stimulus reference — if set, the room overlays this on the preview. */
  stimulus_id?: string;
}

export type AttachmentKind = "image" | "video" | "pdf" | "other";

export interface LocalAttachment {
  /** Client-generated id; replaced by server-side id after upload (future). */
  id: string;
  file: File;
  kind: AttachmentKind;
  /** Object URL for local preview; revoked on removal. */
  previewUrl: string;
  createdAt: number;
}

export interface Stimulus {
  id: string;
  kind: "image" | "video" | "pdf" | "text" | "link";
  title: string;
  url: string;
  /** Optional caption injected into AI prompt. */
  description?: string;
  /** Concept Testing 2.0 — rendered by <ConceptProgress /> on the preview stage. */
  concept_index?: number;
  concept_count?: number;
  block_title?: string;
}
