import { fetchSyncJob, type AuthSession } from "./api";

export async function pollSyncJob(
  session: AuthSession,
  jobId: string,
  onUpdate: (status: string) => void,
) {
  for (let i = 0; i < 120; i++) {
    const job = await fetchSyncJob(session, jobId);
    onUpdate(job.status);
    if (job.status === "completed" || job.status === "failed") return job;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Sync timed out. Check Activity or retry.");
}
