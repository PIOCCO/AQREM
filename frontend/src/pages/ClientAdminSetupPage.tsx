import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/authContext";
import { fetchOrgOverview, recordEmployeeLinkCopied, type SetupStep } from "../lib/orgAdminApi";

function StepIcon({ status }: { status: string }) {
  if (status === "complete") {
    return (
      <span className="w-6 h-6 rounded-full bg-[var(--admin-status-active-bg)] text-[var(--admin-status-active-text)] flex items-center justify-center text-xs">
        ✓
      </span>
    );
  }
  if (status === "in_progress") {
    return <span className="w-6 h-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" aria-hidden />;
  }
  if (status === "locked") {
    return <span className="w-6 h-6 rounded-full bg-chat-surface-subtle text-chat-muted flex items-center justify-center text-xs">🔒</span>;
  }
  return <span className="w-6 h-6 rounded-full border-2 border-chat-border" aria-hidden />;
}

const STEP_LINKS: Record<string, { to: string; label: string }> = {
  model_token: { to: "/org-admin/model-token", label: "Connect token" },
  postgres_database: { to: "/org-admin/data-storage", label: "Configure database" },
  documents: { to: "/org-admin/documents", label: "Upload documents" },
  access: { to: "/org-admin/users", label: "Set up access" },
  employee_link: { to: "/org-admin/users", label: "Configure access first" },
};

function SetupRow({ step }: { step: SetupStep }) {
  const link = STEP_LINKS[step.id];
  return (
    <li className="flex gap-4 py-4 border-b border-chat-border last:border-0">
      <StepIcon status={step.status} />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm">{step.title}</p>
        <p className="text-sm text-chat-muted mt-0.5">{step.detail}</p>
      </div>
      {link && step.status !== "complete" && step.status !== "locked" ? (
        <Link to={link.to} className="text-sm text-[var(--chat-brand-mark)] self-center">
          {link.label}
        </Link>
      ) : null}
    </li>
  );
}

export default function ClientAdminSetupPage() {
  const { session } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof fetchOrgOverview>> | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!session) return;
    fetchOrgOverview(session)
      .then(setOverview)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
      .finally(() => setLoading(false));
  }, [session]);

  async function copyEmployeeLink() {
    if (!overview?.employee_link.enabled || !session) return;
    const url = `${window.location.origin}${overview.employee_link.url_path}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    try {
      await recordEmployeeLinkCopied(session);
    } catch {
      /* non-blocking */
    }
  }

  if (loading) return <p className="p-8 text-sm text-chat-muted">Loading setup…</p>;
  if (error) {
    return (
      <div className="p-8 admin-inline-alert border rounded-lg m-6" role="alert">
        {error}
      </div>
    );
  }

  const checklist = overview?.setup;
  const orgName = overview?.organization?.name ?? "Organization";
  const linkEnabled = overview?.employee_link.enabled ?? false;

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10 min-w-0">
      <header className="flex flex-wrap items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-fg">Set up your private assistant</h1>
          <p className="text-chat-muted mt-2 max-w-xl">
            Finish these steps so employees can ask questions about your documents in <strong>{orgName}</strong>.
          </p>
        </div>
        <div className="text-right text-sm">
          <p className="font-medium">
            {checklist?.completed_count ?? 0} of {checklist?.total_count ?? 0} steps complete
          </p>
          <div className="w-48 h-2 rounded-full bg-chat-surface-subtle mt-2 overflow-hidden">
            <div className="h-full bg-[var(--chat-brand-mark)]" style={{ width: `${checklist?.percent ?? 0}%` }} />
          </div>
        </div>
      </header>

      <div className="grid lg:grid-cols-3 gap-6">
        <section className="admin-card lg:col-span-2 p-6">
          <h2 className="font-medium mb-2">Setup checklist</h2>
          <ul>{checklist?.steps.map((s) => <SetupRow key={s.id} step={s} />)}</ul>
        </section>

        <aside className="space-y-4">
          <div className="admin-card p-4">
            <h3 className="text-sm font-medium">Employee assistant link</h3>
            <p className="text-xs text-chat-muted mt-1">Share when access is configured.</p>
            <code className="block mt-2 text-xs bg-chat-surface-subtle p-2 rounded break-all">
              {window.location.origin}/chat
            </code>
            <button
              type="button"
              className="aq-btn-secondary w-full mt-3 text-sm"
              disabled={!linkEnabled}
              onClick={() => void copyEmployeeLink()}
              aria-label="Copy employee assistant link"
            >
              {linkEnabled ? (copied ? "Copied" : "Copy link") : "Link locked"}
            </button>
            {!linkEnabled ? (
              <p className="text-xs admin-inline-alert border rounded px-2 py-1 mt-2" role="status">
                Invite at least one employee before sharing.
              </p>
            ) : null}
          </div>
          <div className="admin-card p-4">
            <h3 className="text-sm font-medium">Model token</h3>
            <p className="text-sm mt-1 capitalize">{checklist?.model_token_status?.replace(/_/g, " ")}</p>
            <Link to="/org-admin/model-token" className="text-xs text-[var(--chat-brand-mark)] mt-2 inline-block">
              Manage token →
            </Link>
          </div>
          <div className="admin-card p-4">
            <h3 className="text-sm font-medium">PostgreSQL</h3>
            <p className="text-sm mt-1 capitalize">
              {checklist?.postgres_database_status?.replace(/_/g, " ") ?? "Not configured"}
            </p>
            <Link to="/org-admin/data-storage" className="text-xs text-[var(--chat-brand-mark)] mt-2 inline-block">
              Data storage →
            </Link>
          </div>
          <div className="admin-card p-4">
            <h3 className="text-sm font-medium">Privacy</h3>
            <ul className="text-xs text-chat-muted mt-2 space-y-1 list-disc pl-4">
              <li>Your documents stay in your environment.</li>
              <li>Secrets are not stored in the platform database.</li>
              <li>Master console receives metadata only.</li>
            </ul>
            <Link to="/admin/privacy" className="text-xs text-[var(--chat-brand-mark)] mt-2 inline-block">
              What Azelos can see →
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
