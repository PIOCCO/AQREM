import { STARTER_PROMPTS } from "../../lib/chatIntent";
import ChatScopeBar from "./ChatScopeBar";

type Props = {
  name: string;
  projectName: string | null;
  projectId: string | null;
  sourcesCount: number | null;
  projects: { id: string; name: string }[];
  onSelectProject: (id: string) => void;
  onPickPrompt: (text: string) => void;
};

export default function ChatEmptyState({
  name,
  projectName,
  projectId,
  sourcesCount,
  projects,
  onSelectProject,
  onPickPrompt,
}: Props) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 pb-6 w-full max-w-[var(--chat-column-max)] mx-auto">
      <h1 className="mb-2 text-2xl font-semibold text-chat-fg text-center">How can I help, {name}?</h1>
      <p className="mb-6 text-sm text-chat-muted text-center max-w-md">
        Ask questions grounded in{" "}
        <span className="text-chat-fg font-medium">{projectName ?? "your project"}</span>. Citations link to
        evidence in your workspace.
      </p>
      <div className="w-full mb-6">
        <ChatScopeBar
          projectName={projectName}
          projectId={projectId}
          sourcesCount={sourcesCount}
          projects={projects}
          onSelectProject={onSelectProject}
        />
      </div>
      <div className="grid gap-2 w-full sm:grid-cols-2" role="list" aria-label="Suggested prompts">
        {STARTER_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            role="listitem"
            className="ref-starter-prompt"
            onClick={() => onPickPrompt(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
