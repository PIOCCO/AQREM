import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchProjects, loadSession, type AuthSession } from "./api";

export type ProjectOption = { id: string; name: string };

type ProjectContextValue = {
  session: AuthSession | null;
  projects: ProjectOption[];
  projectId: string | null;
  setProjectId: (id: string | null) => void;
  projectName: string | null;
  reloadProjects: () => Promise<void>;
};

const ProjectContext = createContext<ProjectContextValue | null>(null);

const STORAGE_KEY = "aqrem_project_id";

export function ProjectProvider({ children }: { children: ReactNode }) {
  const session = useMemo(() => loadSession(), []);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [projectId, setProjectIdState] = useState<string | null>(() =>
    localStorage.getItem(STORAGE_KEY),
  );

  async function reloadProjects() {
    if (!session) return;
    const rows = await fetchProjects(session);
    setProjects(rows.map((p: { id: string; name: string }) => ({ id: p.id, name: p.name })));
  }

  useEffect(() => {
    reloadProjects().catch(() => setProjects([]));
  }, [session?.organizationId]);

  useEffect(() => {
    if (projectId) localStorage.setItem(STORAGE_KEY, projectId);
    else localStorage.removeItem(STORAGE_KEY);
  }, [projectId]);

  const setProjectId = (id: string | null) => setProjectIdState(id);

  const projectName = useMemo(() => {
    if (!projectId) return null;
    return projects.find((p) => p.id === projectId)?.name ?? null;
  }, [projectId, projects]);

  const value = useMemo<ProjectContextValue>(
    () => ({
      session,
      projects,
      projectId,
      setProjectId,
      projectName,
      reloadProjects,
    }),
    [session, projects, projectId, projectName],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProjectContext() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProjectContext must be used within ProjectProvider");
  return ctx;
}
