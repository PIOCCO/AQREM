import {
  fetchAnswerLibrary,
  previewRetrieval,
  type AuthSession,
} from "./api";
import type { ChatCitation, ChatMessageMeta } from "./conversations";
import { truncateText } from "./textPreview";

export type AssistantReply = {
  content: string;
  meta: ChatMessageMeta;
};

type EvidenceItem = {
  id: string;
  file_name?: string;
  file_path: string;
  line_start?: number;
  line_end?: number;
  content?: string;
  evidence_strength?: string;
};

type LibraryEntry = {
  id: string;
  question_text: string;
  answer_text: string;
  status: string;
};

function mapCitations(items: EvidenceItem[]): ChatCitation[] {
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

function buildRetrievalMarkdown(query: string, items: EvidenceItem[]): AssistantReply {
  const citations = mapCitations(items);
  if (items.length === 0) {
    return {
      content:
        "I could not find indexed evidence that matches your question in the current project scope.\n\n" +
        "Try connecting a source and waiting for indexing to finish, or broaden your project filter.",
      meta: {
        isDraft: true,
        insufficientEvidence: true,
        citations: [],
      },
    };
  }

  const lines = items.map((item, i) => {
    const loc =
      item.line_start != null
        ? ` (lines ${item.line_start}${item.line_end != null ? `–${item.line_end}` : ""})`
        : "";
    const path = item.file_path || item.file_name || "document";
    const excerpt = truncateText(item.content ?? "", 320).replace(/\n/g, " ");
    return `${i + 1}. **${path}**${loc}\n   ${excerpt}`;
  });

  return {
    content:
      `Here is the most relevant evidence I retrieved for your question:\n\n` +
      `> ${query.trim()}\n\n` +
      lines.join("\n\n") +
      `\n\n---\n\n` +
      `_This is a retrieval preview — not a full generated answer. Expand sources below for details, or open **Questionnaires** to draft formal responses._`,
    meta: {
      isDraft: true,
      insufficientEvidence: false,
      citations,
    },
  };
}

export async function generateAssistantReply(
  session: AuthSession,
  query: string,
  projectId: string | null,
  signal?: AbortSignal,
): Promise<AssistantReply> {
  const trimmed = query.trim();
  if (!trimmed) {
    return { content: "Please enter a question.", meta: { isDraft: true } };
  }

  let library: LibraryEntry[] = [];
  try {
    library = await fetchAnswerLibrary(session, {
      query: trimmed,
      projectId,
      limit: 3,
    });
  } catch {
    /* library optional */
  }

  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

  const approved = library.find((e) => e.status === "approved") ?? library[0];
  if (approved && approved.answer_text?.trim()) {
    const citations: ChatCitation[] = [];
    return {
      content:
        `**${approved.status === "approved" ? "Approved answer" : "Library match"}** from the answer library:\n\n` +
        approved.answer_text.trim() +
        `\n\n_Original question: ${approved.question_text}_`,
      meta: {
        isDraft: approved.status !== "approved",
        fromLibrary: true,
        libraryEntryId: approved.id,
        libraryStatus: approved.status,
        insufficientEvidence: false,
        citations,
      },
    };
  }

  const preview = await previewRetrieval(session, {
    query: trimmed,
    project_id: projectId ?? undefined,
    limit: 8,
  });

  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

  const items = (preview.items ?? []) as EvidenceItem[];
  return buildRetrievalMarkdown(trimmed, items);
}
