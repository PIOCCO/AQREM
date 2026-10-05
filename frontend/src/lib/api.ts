const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchMetrics(token: string, organizationId: string) {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/metrics`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Organization-Id": organizationId,
    },
  });
  if (!res.ok) throw new Error("Failed to load metrics");
  return res.json();
}
