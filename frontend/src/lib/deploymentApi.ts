import { readApiError } from "./errors";
import { resolveApiBase } from "./apiBase";

export type SetupStatus = {
  deployment_mode: "shared" | "dedicated";
  setup_required: boolean;
  organization_name: string | null;
  setup_token_configured: boolean;
  license_state?: string | null;
  license_message?: string | null;
  expires_at?: string | null;
};

/** Setup screen state as seen through /api/v1/setup/status. */
export type SetupProbe =
  | { kind: "open"; status: SetupStatus }
  | { kind: "not_found" } // closed, not dedicated, or not reachable from this network (identical to unknown route)
  | { kind: "expired"; message: string }
  | { kind: "locked"; retryAfterSeconds: number }
  | { kind: "error" };

async function detail(res: Response): Promise<{ message?: string; retry_after_seconds?: number }> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === "object" && body.detail ? (body.detail as Record<string, never>) : {};
  } catch {
    return {};
  }
}

export async function probeSetup(): Promise<SetupProbe> {
  try {
    const res = await fetch(`${resolveApiBase()}/api/v1/setup/status`);
    if (res.ok) return { kind: "open", status: (await res.json()) as SetupStatus };
    if (res.status === 404) return { kind: "not_found" };
    if (res.status === 410) {
      const d = await detail(res);
      return { kind: "expired", message: d.message ?? "The setup token has expired." };
    }
    if (res.status === 429) {
      const d = await detail(res);
      const header = Number(res.headers.get("Retry-After"));
      return { kind: "locked", retryAfterSeconds: d.retry_after_seconds ?? (Number.isFinite(header) ? header : 900) };
    }
    return { kind: "error" };
  } catch {
    return { kind: "error" };
  }
}

/** Deployment mode from the public /api/v1/version endpoint (setup/status 404s once setup is done). */
export async function fetchDeploymentMode(): Promise<"shared" | "dedicated" | null> {
  try {
    const res = await fetch(`${resolveApiBase()}/api/v1/version`);
    if (!res.ok) return null;
    const body = (await res.json()) as { deployment_mode?: string };
    return body.deployment_mode === "dedicated" ? "dedicated" : "shared";
  } catch {
    return null;
  }
}

export class SetupApiError extends Error {
  constructor(message: string, readonly status: number, readonly retryAfterSeconds?: number) {
    super(message);
  }
}

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
  if (!res.ok) {
    const retry = Number(res.headers.get("Retry-After"));
    throw new SetupApiError(
      await readApiError(res, "Setup failed"),
      res.status,
      Number.isFinite(retry) && retry > 0 ? retry : undefined,
    );
  }
  return res.json();
}
