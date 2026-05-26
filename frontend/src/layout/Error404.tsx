import { useActions } from "kea";
import { router } from "kea-router";

import { urls } from "~/app/routes";
import { Button } from "~/lib/merism/primitives/Button";

export default function Error404(): JSX.Element {
  const { push } = useActions(router);

  return (
    <div className="flex flex-col gap-6 text-center">
      <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
        Error · 404
      </div>
      <h1 className="font-display text-[length:var(--text-merism-display)] font-[450] leading-[var(--text-merism-display--line-height)] tracking-[var(--text-merism-display--letter-spacing)] text-merism-text">
        Not here.
      </h1>
      <p className="mx-auto max-w-[46ch] text-merism-body text-merism-text-muted">
        The page you followed doesn't exist, or you don't have access to it.
        Head back to the workspace.
      </p>
      <div className="mx-auto">
        <Button onClick={() => push(urls.ask())}>Back to Ask</Button>
      </div>
    </div>
  );
}
