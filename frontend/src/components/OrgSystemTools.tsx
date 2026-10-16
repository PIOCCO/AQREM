import { useEffect, useState } from "react";
import { fetchDeploymentMode } from "../lib/deploymentApi";
import SystemToolsCard from "./SystemToolsCard";

/** Dedicated environments only: the org admin operates the whole environment. */
export default function OrgSystemTools() {
  const [dedicated, setDedicated] = useState(false);
  useEffect(() => {
    void fetchDeploymentMode().then((m) => setDedicated(m === "dedicated"));
  }, []);
  return dedicated ? <SystemToolsCard scope="org" /> : null;
}
