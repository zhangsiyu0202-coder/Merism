import { ArrowRight } from "lucide-react";

import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  StatusDot,
  Tag,
} from "../primitives";

export interface StudyCardProps {
  id: string;
  name: string;
  researchGoal: string;
  status: "draft" | "ready" | "recruiting" | "active" | "closed" | "archived";
  completedCount?: number;
  onOpen: (id: string) => void;
}

const STATUS_TO_DOT: Record<
  StudyCardProps["status"],
  { status: "ok" | "warn" | "error" | "neutral"; label: string }
> = {
  draft: { status: "neutral", label: "Draft" },
  ready: { status: "neutral", label: "Ready" },
  recruiting: { status: "warn", label: "Recruiting" },
  active: { status: "ok", label: "Active" },
  closed: { status: "neutral", label: "Closed" },
  archived: { status: "neutral", label: "Archived" },
};

export function StudyCard({
  id,
  name,
  researchGoal,
  status,
  completedCount,
  onOpen,
}: StudyCardProps) {
  const dot = STATUS_TO_DOT[status];
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <StatusDot {...dot} />
          <Tag variant={status === "active" ? "success" : "neutral"}>
            {status}
          </Tag>
        </div>
        <CardTitle className="line-clamp-1">{name}</CardTitle>
        <CardDescription className="line-clamp-2">
          {researchGoal}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <span className="text-xs text-merism-text-muted">
          {completedCount ?? 0} interviews
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onOpen(id)}
          iconRight={<ArrowRight className="h-4 w-4" />}
        >
          Open
        </Button>
      </CardContent>
    </Card>
  );
}
