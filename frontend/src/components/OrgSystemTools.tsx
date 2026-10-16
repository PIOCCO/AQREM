import { useEffect, useState } from "react";
import { fetchSetupStatus } from "../lib/deploymentApi";
import SystemToolsCard from "./SystemToolsCard";

/** Dedicated environments only: the org admin operates the whole environment. */
export default function OrgSystemTools() {
  const [dedicated, setDedicated] = useState(false);
  useEffect(() => {
    void fetchSetupStatus().then((s) => setDedicated(s?.deployment_mode === "dedicated"));
  }, []);
  return dedicated ? <SystemToolsCard scope="org" /> : null;
}
