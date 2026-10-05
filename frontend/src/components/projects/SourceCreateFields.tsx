type Props = {
  idPrefix?: string;
  defaultSourceName?: string;
};

export function SourceCreateFields({ idPrefix = "", defaultSourceName = "" }: Props) {
  const p = idPrefix ? `${idPrefix}-` : "";
  return (
    <fieldset className="space-y-3 border border-border rounded-control p-4">
      <legend className="text-sm font-medium text-slate-900 px-1">Source code</legend>
      <p className="text-xs text-slate-500 -mt-1">
        Connect a repository, folder path, or document upload source for this project. Leave the source name empty to
        skip and add later.
      </p>
      <input
        name="source_name"
        defaultValue={defaultSourceName}
        placeholder="Source name (e.g. Product repo)"
        className="aq-input"
      />
      <select name="source_type" className="aq-select" defaultValue="folder_archive">
        <option value="folder_archive">Folder archive (server path)</option>
        <option value="file_upload">Document upload</option>
        <option value="github">GitHub repository</option>
      </select>
      <input
        name="demo_path"
        placeholder="Folder path on server (folder archive), e.g. /app/tests/fixtures/demo_saas_repo"
        className="aq-input"
      />
      <input name="repository" placeholder="GitHub owner/repo (GitHub only)" className="aq-input" />
      <input name="branch" placeholder="Branch (default main)" className="aq-input" />
      <input
        name="github_token"
        type="password"
        placeholder="GitHub token (dev only, optional)"
        className="aq-input"
        autoComplete="off"
      />
    </fieldset>
  );
}
