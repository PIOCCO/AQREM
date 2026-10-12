import { useId, useState } from "react";
import { Link } from "react-router-dom";
import type { ChatMessageMeta } from "../../lib/conversations";
import { IconAlert, IconChevronDown } from "../icons/Icons";

type Props = {
  meta: ChatMessageMeta;
};

export default function InsufficientEvidencePanel({ meta }: Props) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();

  const project = meta.projectName ?? "this project";
  const sources = meta.sourcesSearched ?? 0;
  const queryMs = meta.queryTimeMs;

  return (
    <div className="mt-4 space-y-3">
      <button
        type="button"
        className="ref-insufficient-badge"
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={() => setOpen((v) => !v)}
        title="Insufficient evidence — click for search details"
      >
        <IconAlert className="h-4 w-4 shrink-0" aria-hidden />
        <span>Insufficient evidence</span>
        <IconChevronDown className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {open ? (
        <div id={detailsId} className="ref-insufficient-details text-sm text-chat-fg">
          <p>
            <span className="text-chat-muted">Project:</span> {project}
          </p>
          <p>
            <span className="text-chat-muted">Sources searched:</span> {sources}
          </p>
          {queryMs != null ? (
            <p>
              <span className="text-chat-muted">Query time:</span> {queryMs} ms
            </p>
          ) : null}
          <Link to="/review-queue" className="ref-scope-link inline-block mt-2">
            Open Review Queue
          </Link>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2" role="group" aria-label="Suggested actions">
        <Link to="/projects" className="ref-evidence-action-btn">
          Upload a document
        </Link>
        <Link to={meta.projectName ? "/projects" : "/projects"} className="ref-evidence-action-btn">
          Add a source
        </Link>
        <Link to="/projects" className="ref-evidence-action-btn">
          Switch project
        </Link>
        <Link to="/review-queue" className="ref-evidence-action-btn">
          Send to Review Queue
        </Link>
      </div>
    </div>
  );
}
