import { Navigate } from "react-router-dom";

/** Legacy route — source management lives under Projects. */
export default function SourcesPage() {
  return <Navigate to="/projects" replace />;
}
