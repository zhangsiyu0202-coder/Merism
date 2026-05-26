import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useActions, useMountedLogic, useValues } from "kea";
import {
  FileImage,
  FileText,
  Film,
  GripVertical,
  Link2,
  Plus,
  Shuffle,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { studyLogic } from "~/features/studies/studyLogic";
import { api } from "~/lib/api";
import { Button, Input, SectionLabel, Select, Tag } from "~/lib/merism";
import { useCSRFToken } from "~/lib/hooks/useCSRFToken";

import {
  conceptBlocksLogic,
  type ConceptBlockRow,
  type ConceptRow,
  type Rotation,
} from "./conceptBlocksLogic";

// ── Stimulus Library types ────────────────────────────────────

interface StimulusRecord {
  id: string;
  kind: string;
  title: string;
  description: string;
  content: { url?: string; content_type?: string; size?: number };
  created_at: string;
}

const KIND_ICONS: Record<string, JSX.Element> = {
  image: <FileImage className="h-4 w-4" />,
  video: <Film className="h-4 w-4" />,
  pdf: <FileText className="h-4 w-4" />,
  text: <FileText className="h-4 w-4" />,
  link: <Link2 className="h-4 w-4" />,
};

export default function StimuliTab(): JSX.Element {
  useMountedLogic(conceptBlocksLogic);
  const { blocks, blocksLoading, error } = useValues(conceptBlocksLogic);
  const { createBlock, setError } = useActions(conceptBlocksLogic);

  return (
    <div className="flex flex-col gap-10">
      {/* Stimulus Library — upload + list */}
      <StimulusLibrary />

      {/* Concept Blocks — existing functionality */}
      <section className="flex flex-col gap-6">
        <header className="flex items-center justify-between">
          <SectionLabel>Concept blocks</SectionLabel>
          <Button
            variant="primary"
            size="sm"
            iconLeft={<Plus className="h-4 w-4" />}
            onClick={() => createBlock("New concept block")}
          >
            New block
          </Button>
        </header>

        {error && (
          <div className="flex items-center justify-between rounded-merism-md border border-merism-danger/30 bg-merism-danger/5 px-4 py-2 text-sm text-merism-danger">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-merism-danger/70 hover:text-merism-danger"
            >
              dismiss
            </button>
          </div>
        )}

        {blocksLoading && blocks.length === 0 ? (
          <div className="rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-10 text-center text-sm text-merism-text-muted">
            Loading concept blocks…
          </div>
        ) : blocks.length === 0 ? (
          <div className="rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-10 text-center text-sm text-merism-text-muted">
            No concept blocks yet. Create one to run side-by-side comparative
            concept testing.
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {blocks.map((block) => (
              <BlockCard key={block.id} block={block} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Per-block card ─────────────────────────────────────────────

const ROTATION_OPTIONS: Array<{ value: Rotation; label: string }> = [
  { value: "fixed", label: "Fixed order" },
  { value: "random_per_session", label: "Random per session" },
  { value: "latin_square", label: "Latin-square balanced" },
];

function BlockCard({ block }: { block: ConceptBlockRow }) {
  const { setRotation, deleteBlock, reorderConcept } =
    useActions(conceptBlocksLogic);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragEnd = (event: DragEndEvent): void => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const from = block.concepts.findIndex((c) => c.id === active.id);
    const to = block.concepts.findIndex((c) => c.id === over.id);
    if (from === -1 || to === -1) return;
    reorderConcept(block.id, from, to);
  };

  return (
    <section className="flex flex-col gap-4 rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6">
      <header className="flex flex-wrap items-center gap-3">
        <h3 className="font-display text-[length:var(--text-merism-title)] font-[500] text-merism-text">
          {block.title}
        </h3>
        <Tag variant="outline">
          {block.concept_count}{" "}
          {block.concept_count === 1 ? "concept" : "concepts"}
        </Tag>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Shuffle className="h-4 w-4 text-merism-text-muted" />
            <Select
              aria-label="Rotation order"
              value={block.rotation}
              onValueChange={(nextValue) =>
                setRotation(block.id, nextValue as Rotation)
              }
              size="sm"
              className="min-w-[12rem]"
              options={ROTATION_OPTIONS}
            />
          </div>
          <button
            type="button"
            onClick={() => deleteBlock(block.id)}
            aria-label="Delete concept block"
            className="text-merism-text-subtle transition-colors hover:text-merism-danger"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </header>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={block.concepts.map((c) => c.id)}
          strategy={verticalListSortingStrategy}
        >
          <ol className="flex flex-col gap-2">
            {block.concepts.map((c) => (
              <ConceptRowCard key={c.id} blockId={block.id} concept={c} />
            ))}
          </ol>
        </SortableContext>
      </DndContext>

      <AddConceptForm blockId={block.id} />
    </section>
  );
}

// ── Concept row ────────────────────────────────────────────────

function ConceptRowCard({
  blockId,
  concept,
}: {
  blockId: string;
  concept: ConceptRow;
}) {
  const { removeConcept } = useActions(conceptBlocksLogic);
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: concept.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.7 : 1,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="group flex items-center gap-3 rounded-merism-md bg-merism-bg-subtle ring-1 ring-[color:var(--merism-hairline)] px-3 py-2"
    >
      <button
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        className="cursor-grab text-merism-text-subtle active:cursor-grabbing"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <Tag variant="outline" size="sm">
        #{concept.rank + 1}
      </Tag>

      <span className="font-medium text-merism-text">{concept.label}</span>
      <span className="truncate text-xs text-merism-text-muted">
        · {concept.stimulus_kind} · {concept.stimulus_title || concept.stimulus}
      </span>

      <button
        type="button"
        onClick={() => removeConcept(blockId, concept.id)}
        aria-label="Remove concept"
        className="ml-auto text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100 hover:text-merism-danger"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </li>
  );
}

// ── Add-concept form with real stimulus picker ─────────────────

interface StimulusBrief {
  id: string;
  title: string;
  kind: string;
}

function AddConceptForm({ blockId }: { blockId: string }) {
  const { addConcept } = useActions(conceptBlocksLogic);
  const { blocks } = useValues(conceptBlocksLogic);
  const { study } = useValues(studyLogic);
  const [label, setLabel] = useState("");
  const [stimulusId, setStimulusId] = useState("");
  const [stimuli, setStimuli] = useState<StimulusBrief[]>([]);
  const [loading, setLoading] = useState(false);

  // Load stimuli for this study once the study id is known.
  useEffect(() => {
    if (!study?.id) return;
    setLoading(true);
    api
      .list<StimulusBrief>("/api/stimuli/", { study: study.id })
      .then((res) => setStimuli(res.results ?? []))
      .catch(() => setStimuli([]))
      .finally(() => setLoading(false));
  }, [study?.id]);

  // Hide stimuli that are already linked into concepts of any block —
  // prevents accidental duplicates inside the same comparison.
  const usedStimulusIds = new Set(
    blocks.flatMap((b) => b.concepts.map((c) => c.stimulus)),
  );
  const available = stimuli.filter((s) => !usedStimulusIds.has(s.id));

  const disabled = !stimulusId;

  const onSubmit = (): void => {
    if (disabled) return;
    addConcept(blockId, { label: label.trim(), stimulus: stimulusId });
    setLabel("");
    setStimulusId("");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="flex flex-wrap items-center gap-2 rounded-merism-md border border-dashed border-merism-border bg-merism-bg-subtle px-3 py-2"
    >
      <Input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Label (e.g. Concept A)"
        className="w-44"
      />
      <Select
        aria-label="Stimulus"
        value={stimulusId}
        onValueChange={setStimulusId}
        className="min-w-56 flex-1"
        placeholder={
          loading
            ? "Loading stimuli…"
            : available.length === 0
              ? "No stimuli available — upload one first"
              : "Pick a stimulus…"
        }
        emptyText="No stimuli available — upload one first"
        options={available.map((stimulus) => ({
          value: stimulus.id,
          label: stimulus.title || stimulus.id.slice(0, 8),
          description: stimulus.kind,
        }))}
      />
      <Button
        type="submit"
        size="sm"
        variant="secondary"
        disabled={disabled}
        iconLeft={<Plus className="h-4 w-4" />}
      >
        Add concept
      </Button>
    </form>
  );
}

// ── Stimulus Library ───────────────────────────────────────────

function StimulusLibrary(): JSX.Element {
  const { study } = useValues(studyLogic);
  const [stimuli, setStimuli] = useState<StimulusRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const csrfToken = useCSRFToken();

  const loadStimuli = useCallback(() => {
    if (!study?.id) return;
    setLoading(true);
    api
      .list<StimulusRecord>("/api/stimuli/", { study: study.id })
      .then((res) => setStimuli(res.results ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [study?.id]);

  useEffect(() => {
    loadStimuli();
  }, [loadStimuli]);

  const handleUpload = async (file: File): Promise<void> => {
    if (!study?.id) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("study", study.id);
      formData.append("title", file.name);

      const res = await fetch("/api/stimuli/upload/", {
        method: "POST",
        body: formData,
        headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
        credentials: "include",
      });
      if (res.ok) {
        loadStimuli();
      }
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string): Promise<void> => {
    await api.delete(`/api/stimuli/${id}/`);
    setStimuli((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <SectionLabel>Stimulus Library</SectionLabel>
        <Button
          variant="secondary"
          size="sm"
          iconLeft={<Upload className="h-4 w-4" />}
          onClick={() => fileInputRef.current?.click()}
          isLoading={uploading}
        >
          Upload
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,video/*,application/pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
            e.target.value = "";
          }}
        />
      </header>

      {loading && stimuli.length === 0 ? (
        <div className="rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-8 text-center text-sm text-merism-text-muted">
          Loading…
        </div>
      ) : stimuli.length === 0 ? (
        <div
          className="flex flex-col items-center gap-3 rounded-merism-lg border border-dashed border-merism-border bg-merism-surface p-10 text-center cursor-pointer hover:border-merism-accent/50 transition-colors"
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="h-8 w-8 text-merism-text-subtle" />
          <p className="text-sm text-merism-text-muted">
            Drop files here or click to upload images, videos, or PDFs
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {stimuli.map((s) => (
            <div
              key={s.id}
              className="group flex items-center gap-3 rounded-merism-md bg-merism-surface px-4 py-3 ring-1 ring-[color:var(--merism-hairline)] transition-shadow hover:shadow-merism-card"
            >
              <span className="text-merism-text-muted">
                {KIND_ICONS[s.kind] ?? <FileText className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-merism-text">
                  {s.title}
                </p>
                <p className="text-xs text-merism-text-muted">
                  {s.kind} · {new Date(s.created_at).toLocaleDateString()}
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(s.id)}
                className="text-merism-text-subtle opacity-0 group-hover:opacity-100 hover:text-merism-danger transition-opacity"
                aria-label="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
