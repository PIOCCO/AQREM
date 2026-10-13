import { Link } from "react-router-dom";
import type { ChatMessageMeta } from "../../lib/conversations";

type Props = {
  meta: ChatMessageMeta;
};

export default function InsufficientEvidencePanel(_props: Props) {
  return (
    <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Suggested actions">
      <Link to="/projects" className="ref-evidence-action-btn">
        Upload a document
      </Link>
      <Link to="/projects" className="ref-evidence-action-btn">
        Add a source
      </Link>
      <Link to="/projects" className="ref-evidence-action-btn">
        Switch project
      </Link>
      <Link to="/review-queue" className="ref-evidence-action-btn">
        Send to Review Queue
      </Link>
    </div>
  );
}
