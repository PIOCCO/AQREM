import { Link } from "react-router-dom";
import type { ChatMessageMeta } from "../../lib/conversations";
import { PRODUCT_V1 } from "../../lib/productV1";

type Props = {
  meta: ChatMessageMeta;
};

export default function InsufficientEvidencePanel(_props: Props) {
  if (PRODUCT_V1) return null;

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
