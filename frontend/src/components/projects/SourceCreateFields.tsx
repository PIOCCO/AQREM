import { useState } from "react";
import { Combobox } from "../ui/dialog/Combobox";
import { Field } from "../ui/dialog/Field";

const SOURCE_TYPES = [
  { value: "folder_archive", label: "Folder archive (server path)" },
  { value: "file_upload", label: "Document upload" },
  { value: "github", label: "GitHub repository" },
];

type Props = {
  defaultSourceName?: string;
};

export function SourceCreateFields({ defaultSourceName = "" }: Props) {
  const [sourceType, setSourceType] = useState("folder_archive");

  return (
    <fieldset className="space-y-3 border border-[var(--color-border)] rounded-lg p-4">
      <legend className="text-sm font-medium text-[var(--color-text-primary)] px-1">Source code</legend>
      <p className="text-xs text-[var(--color-text-muted)] -mt-1">
        Connect a repository, folder path, or document upload source for this project. Leave the source name empty to skip
        and add later.
      </p>
      <Field id="source_name" label="Source name" helper="Optional — e.g. Product repo">
        <input name="source_name" id="source_name" defaultValue={defaultSourceName} className="aq-input" />
      </Field>
      <Field id="source_type" label="Source type">
        <input type="hidden" name="source_type" value={sourceType} />
        <Combobox
          id="source_type_ui"
          value={sourceType}
          onChange={setSourceType}
          options={SOURCE_TYPES}
          data-testid="source-type-combobox"
        />
      </Field>
      <Field id="demo_path" label="Folder path" helper="For folder archive sources">
        <input
          name="demo_path"
          id="demo_path"
          placeholder="/app/tests/fixtures/demo_saas_repo"
          className="aq-input"
        />
      </Field>
      <Field id="repository" label="GitHub repository" helper="owner/repo when using GitHub">
        <input name="repository" id="repository" placeholder="owner/repo" className="aq-input" />
      </Field>
      <Field id="branch" label="Branch" helper="Defaults to main">
        <input name="branch" id="branch" placeholder="main" className="aq-input" />
      </Field>
      <Field id="github_token" label="GitHub token" helper="Development only — optional">
        <input
          name="github_token"
          id="github_token"
          type="password"
          className="aq-input"
          autoComplete="off"
        />
      </Field>
    </fieldset>
  );
}
