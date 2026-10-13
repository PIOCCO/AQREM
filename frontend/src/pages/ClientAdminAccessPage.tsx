import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../lib/authContext";
import { fetchAccessGroups, fetchDocumentsNeedingReview } from "../lib/orgAdminApi";

export default function ClientAdminAccessPage() {
  const { session } = useAuth();
  const [groups, setGroups] = useState<Array<{ id: string; name: string; member_count: number; is_system: boolean }>>(
    [],
  );
  const [reviewCount, setReviewCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!session) return;
    Promise.all([fetchAccessGroups(session), fetchDocumentsNeedingReview(session)])
      .then(([g, review]) => {
        setGroups(g);
        setReviewCount(review.count);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"));
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Access</h1>
        <p className="text-sm text-chat-muted mt-2">
          Groups control who can see which documents. Roles control what people can do in the assistant.
        </p>
      </header>

      {reviewCount > 0 ? (
        <div
          className="admin-card p-4 mb-6 border border-amber-500/40 bg-amber-500/10 text-sm"
          role="status"
        >
          {reviewCount} document{reviewCount === 1 ? "" : "s"} need a visibility setting. Open{" "}
          <a href="/admin/documents" className="text-[var(--color-link)] underline">
            Documents
          </a>{" "}
          to review.
        </div>
      ) : null}

      {error ? <p className="text-sm text-red-400 mb-4">{error}</p> : null}

      <section className="admin-card overflow-hidden">
        <h2 className="text-sm font-semibold px-4 py-3 border-b border-chat-border">Groups</h2>
        <ul className="divide-y divide-chat-border">
          {groups.map((g) => (
            <li key={g.id} className="px-4 py-3 flex justify-between text-sm">
              <span>
                {g.name}
                {g.is_system ? (
                  <span className="ml-2 text-xs text-chat-muted">(default)</span>
                ) : null}
              </span>
              <span className="text-chat-muted">{g.member_count} members</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
