import { readApiError } from "./errors";
import { resolveApiBase } from "./apiBase";

export type SetupStatus = {
  deployment_mode: "shared" | "dedicated";
  setup_required: boolean;
  organization_name: string | null;
  setup_token_configured: boolean;
  license_state?: string | null;
  license_message?: string | null;
};

export async function fetchSetupStatus(): Promise<SetupStatus | null> {
  try {
    const res = await fetch(`${resolveApiBase()}/api/v1/setup/status`);
    if (!res.ok) return null;
    return (await res.json()) as SetupStatus;
  } catch {
    return null;
  }
}

export async function createFirstAdmin(payload: {
  setup_token: string;
  email: string;
  full_name: string;
  password: string;
  organization_name?: string;
}): Promise<{ organization_id: string; organization_name: string; email: string }> {
  const res = await fetch(`${resolveApiBase()}/api/v1/setup/first-admin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Setup failed"));
  return res.json();
}
