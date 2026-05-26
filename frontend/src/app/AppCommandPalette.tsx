import { useActions, useValues } from "kea";
import { router } from "kea-router";
import {
  FlaskConical,
  Home,
  Inbox,
  Lightbulb,
  MessageCircle,
  PlusCircle,
  Repeat,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { urls } from "~/app/routes";
import { userLogic } from "~/models/userLogic";
import { studiesLogic } from "~/features/studies/studiesLogic";
import { CommandPalette, type CommandPaletteCommand } from "~/lib/merism";

/**
 * AppCommandPalette — wires the design-system CommandPalette to the
 * app's actual routes + Kea actions.
 *
 * Commands are split into sections:
 *   - Go to        — navigation to each top-level scene.
 *   - Actions      — create-new-study, open admin (superuser).
 *   - Studies      — quick-pick the 20 most-recent studies.
 */
export function AppCommandPalette(): JSX.Element {
  const { t } = useTranslation();
  const { user } = useValues(userLogic);
  const { studies } = useValues(studiesLogic);
  const { createStudy } = useActions(studiesLogic);

  const commands = useMemo<CommandPaletteCommand[]>(() => {
    const nav = (path: string) => () => router.actions.push(path);
    const base: CommandPaletteCommand[] = [
      {
        id: "go-home",
        label: t("command_palette.commands.go_home"),
        section: t("command_palette.sections.go_to"),
        icon: <Home className="h-4 w-4" />,
        keywords: ["dashboard", "overview"],
        onRun: nav(urls.home()),
      },
      {
        id: "go-ask",
        label: t("command_palette.commands.go_ask"),
        section: t("command_palette.sections.go_to"),
        icon: <MessageCircle className="h-4 w-4" />,
        keywords: ["chat", "llm", "query"],
        onRun: nav(urls.ask()),
      },
      {
        id: "go-inbox",
        label: t("command_palette.commands.go_inbox"),
        section: t("command_palette.sections.go_to"),
        icon: <Inbox className="h-4 w-4" />,
        onRun: nav(urls.inbox()),
      },
      {
        id: "go-repository",
        label: t("command_palette.commands.go_repository"),
        section: t("command_palette.sections.go_to"),
        icon: <Search className="h-4 w-4" />,
        keywords: ["knowledge", "archive"],
        onRun: nav(urls.repository()),
      },
      {
        id: "go-decisions",
        label: t("command_palette.commands.go_decisions"),
        section: t("command_palette.sections.go_to"),
        icon: <Lightbulb className="h-4 w-4" />,
        onRun: nav(urls.decisions()),
      },
      {
        id: "go-settings",
        label: t("command_palette.commands.go_settings"),
        section: t("command_palette.sections.go_to"),
        icon: <Settings className="h-4 w-4" />,
        onRun: nav(urls.settings()),
      },
      {
        id: "new-study",
        label: t("command_palette.commands.new_study"),
        section: t("command_palette.sections.actions"),
        icon: <PlusCircle className="h-4 w-4" />,
        hint: t("common.draft"),
        keywords: ["add", "create", "research"],
        onRun: () => createStudy(),
      },
      {
        id: "refresh",
        label: t("command_palette.commands.reload"),
        section: t("command_palette.sections.actions"),
        icon: <Repeat className="h-4 w-4" />,
        onRun: () => window.location.reload(),
      },
    ];

    if (user?.is_superuser) {
      base.push({
        id: "open-admin",
        label: t("command_palette.commands.open_admin"),
        section: t("command_palette.sections.actions"),
        icon: <ShieldCheck className="h-4 w-4" />,
        hint: t("command_palette.commands.open_admin_hint"),
        keywords: ["platform", "superuser", "cross-tenant"],
        onRun: () => {
          window.open("/admin/", "_blank", "noopener,noreferrer");
        },
      });
    }

    // Recent studies — quick-jump.
    for (const study of studies.slice(0, 20)) {
      base.push({
        id: `study-${study.id}`,
        label: study.name || study.research_goal.slice(0, 48),
        section: t("command_palette.sections.studies"),
        icon: <FlaskConical className="h-4 w-4" />,
        hint: study.status,
        keywords: [study.research_goal],
        onRun: nav(urls.study(study.id)),
      });
    }
    return base;
  }, [t, user?.is_superuser, studies, createStudy]);

  return <CommandPalette commands={commands} />;
}
