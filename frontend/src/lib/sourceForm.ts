import {
  connectGithubRepo,
  createSource,
  type AuthSession,
} from "./api";

export type SourceFormValues = {
  sourceName: string;
  sourceType: string;
  demoPath?: string;
  repository?: string;
  branch?: string;
  githubToken?: string;
};

export function readSourceForm(form: FormData): SourceFormValues {
  return {
    sourceName: String(form.get("source_name") || "").trim(),
    sourceType: String(form.get("source_type") || "folder_archive"),
    demoPath: String(form.get("demo_path") || "").trim() || undefined,
    repository: String(form.get("repository") || "").trim() || undefined,
    branch: String(form.get("branch") || "").trim() || undefined,
    githubToken: String(form.get("github_token") || "").trim() || undefined,
  };
}

export function buildInitialSourcePayload(values: SourceFormValues) {
  if (!values.sourceName) return undefined;
  const config: Record<string, unknown> = {};
  if (values.demoPath) config.demo_path = values.demoPath;
  return {
    name: values.sourceName,
    source_type: values.sourceType,
    config,
    repository_full_name: values.repository,
    branch: values.branch || "main",
    access_token: values.githubToken,
  };
}

/** Create a source for an existing project using existing source APIs. */
export async function createSourceForProject(
  session: AuthSession,
  projectId: string,
  values: SourceFormValues,
) {
  const config: Record<string, unknown> = {};
  if (values.demoPath) config.demo_path = values.demoPath;

  const created = await createSource(session, {
    name: values.sourceName,
    source_type: values.sourceType,
    project_id: projectId,
    config,
  });

  if (values.sourceType === "github" && values.repository) {
    await connectGithubRepo(session, {
      source_id: created.id,
      repository_full_name: values.repository,
      branch: values.branch || "main",
      access_token: values.githubToken,
    });
  }
  return created;
}
