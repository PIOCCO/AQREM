import { askChat, type AuthSession } from "./api";
import type { ChatCitation, ChatMessageMeta } from "./conversations";
import { truncateText } from "./textPreview";

export type AssistantReply = {
  content: string;
  meta: ChatMessageMeta;
};

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

function formatLibraryAnswer(answer: string, fromLibrary: boolean, status?: string) {
  if (fromLibrary) {
    return `**Approved answer** from the answer library:\n\n${answer.trim()}`;
  }
  return answer.trim();
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

  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

  try {
    const data = await askChat(session, { query: trimmed, project_id: projectId });
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

    const citations = mapCitations((data.citations ?? []) as CitationPayload[]);
    const outcome = typeof data.outcome === "string" ? data.outcome : undefined;
    const insufficient =
      data.evidence_sufficiency === "insufficient" ||
      outcome === "insufficient_evidence" ||
      outcome === "source_unavailable";
    const fromLibrary = Boolean(data.from_library);

    let content = formatLibraryAnswer(data.answer ?? "", fromLibrary);
    if (!fromLibrary && insufficient && !content.trim()) {
      content =
        "I could not find enough indexed evidence to support a confident answer in the current project scope.";
    }
    if (
      !fromLibrary &&
      !insufficient &&
      data.reasoning_summary &&
      outcome !== "conflicting_evidence" &&
      outcome !== "partially_answered"
    ) {
      content += `\n\n_${data.reasoning_summary}_`;
    }

    return {
      content,
      meta: {
        isDraft: data.is_draft !== false,
        fromLibrary,
        libraryEntryId: data.library_entry_id ?? undefined,
        libraryStatus: fromLibrary ? "approved" : undefined,
        insufficientEvidence: insufficient,
        outcome,
        needsReview: Boolean(data.needs_review),
        citations,
      },
    };
  } catch (e) {
    const message = e instanceof Error ? e.message : "Chat request failed";
    return {
      content: message,
      meta: { isDraft: true, error: true },
    };
  }
}
