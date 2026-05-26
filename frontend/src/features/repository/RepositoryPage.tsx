import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Illustration, PageTopBar } from "~/lib/merism";

type RepositoryTab = "documents" | "chunks" | "templates";

const TABS = [
  { value: "documents", label: "Documents" },
  { value: "chunks", label: "Chunks" },
  { value: "templates", label: "Templates" },
];

/**
 * RepositoryPage — cross-study knowledge library (PRODUCT.md §3.9).
 */
export default function RepositoryPage(): JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<RepositoryTab>("documents");

  return (
    <div className="flex flex-col gap-8">
      <PageTopBar
        title={t("repository.title")}
        lede={t("repository.lede")}
        tabs={TABS}
        activeTab={tab}
        onTabChange={(v) => setTab(v as RepositoryTab)}
      />
      <EmptyState />
    </div>
  );
}

function EmptyState(): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-12 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <Illustration name="painting" size="xl" className="text-merism-text" />
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
          {t("repository.empty_title")}
        </h2>
        <p className="text-merism-body text-merism-text-muted">
          {t("repository.empty_body")}
        </p>
      </div>
    </div>
  );
}
