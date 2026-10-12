import { Link } from "react-router-dom";
import { IconChevronDown } from "../icons/Icons";

type Props = {
  projectName: string | null;
  projectId: string | null;
  sourcesCount: number | null;
  projects: { id: string; name: string }[];
  onSelectProject: (id: string) => void;
  compact?: boolean;
};

export default function ChatScopeBar({
  projectName,
  projectId,
  sourcesCount,
  projects,
  onSelectProject,
  compact,
}: Props) {
  const label = projectName ?? "All projects";
  const sources =
    sourcesCount == null ? "…" : `${sourcesCount} source${sourcesCount === 1 ? "" : "s"}`;

  return (
    <div className={`ref-scope-bar ${compact ? "ref-scope-bar-compact" : ""}`}>
      <span className="text-xs text-chat-muted shrink-0">Scope</span>
      <div className="relative min-w-0 flex-1">
        <label className="sr-only" htmlFor="chat-scope-project">
          Active project
        </label>
        <div className="flex items-center gap-2 min-w-0">
          <select
            id="chat-scope-project"
            className="ref-scope-select"
            value={projectId ?? ""}
            onChange={(e) => onSelectProject(e.target.value)}
          >
            {projects.length === 0 ? (
              <option value="">No projects</option>
            ) : (
              projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))
            )}
          </select>
          <IconChevronDown className="h-4 w-4 text-chat-muted pointer-events-none absolute right-2 top-1/2 -translate-y-1/2" aria-hidden />
        </div>
      </div>
      <span className="text-xs text-chat-muted shrink-0 truncate max-w-[8rem]" title={label}>
        {sources}
      </span>
      <Link to={projectId ? `/projects/${projectId}` : "/projects"} className="ref-scope-link text-xs shrink-0">
        Manage
      </Link>
    </div>
  );
}
