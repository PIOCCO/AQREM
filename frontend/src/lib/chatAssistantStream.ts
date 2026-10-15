import { askChatStream, type AuthSession, type ChatStreamEvent } from "./api";
import { buildConversationalReply, classifyChatIntent } from "./chatIntent";
import type { ChatCitation, ChatMessageMeta } from "./conversations";
import { truncateText } from "./textPreview";
import type { AssistantReply } from "./chatAssistant";

type CitationPayload = {
  id: string;
  file_name?: string;
  file_path: string;
  line_start?: number;
  line_end?: number;
  content?: string;
  evidence_strength?: string;
};

function mapCitations(items: CitationPayload[]): ChatCitation[] {
  return items.map((item) => ({
    evidenceId: item.id,
    fileName: item.file_name,
    filePath: item.file_path,
    lineStart: item.line_start,
    lineEnd: item.line_end,
    excerpt: truncateText(item.content ?? "", 480),
    evidenceStrength: item.evidence_strength,
  }));
}

export async function streamAssistantReply(
  session: AuthSession,
  query: string,
  projectId: string | null,
  handlers: {
    onToken: (text: string) => void;
    signal?: AbortSignal;
  },
): Promise<AssistantReply> {
  const trimmed = query.trim();
  if (!trimmed) {
    return { content: "Please enter a question.", meta: { isDraft: true }, skippedRetrieval: true };
  }
  if (handlers.signal?.aborted) throw new DOMException("Aborted", "AbortError");

  const intent = classifyChatIntent(trimmed);
  if (intent) {
    const content = buildConversationalReply(intent);
    handlers.onToken(content);
    return {
      content,
      meta: { conversational: true, isDraft: false, intent },
      skippedRetrieval: true,
    };
  }

  let content = "";
  let meta: ChatMessageMeta = { isDraft: true, userQuery: trimmed };

  await askChatStream(
    session,
    { query: trimmed, project_id: projectId ?? null },
    {
      signal: handlers.signal,
      onEvent: (event: ChatStreamEvent) => {
        if (event.type === "token") {
          content += event.text;
          handlers.onToken(content);
        } else if (event.type === "error") {
          throw new Error(event.message);
        } else if (event.type === "meta") {
          const citations = mapCitations((event.citations ?? []) as CitationPayload[]);
          meta = {
            ...meta,
            isDraft: event.is_draft !== false,
            conversational: Boolean(event.conversational),
            outcome: typeof event.outcome === "string" ? event.outcome : undefined,
            citations,
            insufficientEvidence: event.evidence_sufficiency === "insufficient",
            projectName: typeof event.project_name === "string" ? event.project_name : undefined,
            sourcesSearched:
              typeof event.sources_searched === "number" ? event.sources_searched : undefined,
          };
        }
      },
    },
  );

  return { content, meta, skippedRetrieval: false };
}
