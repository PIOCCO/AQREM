import { askChat, type AuthSession } from "./api";
import { buildConversationalReply, classifyChatIntent } from "./chatIntent";
import type { ChatCitation, ChatMessageMeta } from "./conversations";
import { formatNoEvidenceMessage } from "./noEvidenceMessage";
import { truncateText } from "./textPreview";

export type AssistantReply = {
  content: string;
  meta: ChatMessageMeta;
  skippedRetrieval?: boolean;
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

function formatLibraryAnswer(answer: string, fromLibrary: boolean) {
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
  scope?: { projectName?: string | null; sourcesCount?: number },
): Promise<AssistantReply> {
  const trimmed = query.trim();
  if (!trimmed) {
    return { content: "Please enter a question.", meta: { isDraft: true }, skippedRetrieval: true };
  }

  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

  const intent = classifyChatIntent(trimmed);
  if (intent) {
    return {
      content: buildConversationalReply(intent),
      meta: {
        conversational: true,
        isDraft: false,
        intent,
        starterPrompts: ["Complete a questionnaire", "Find evidence for a control", "Check an answer against sources"],
      },
      skippedRetrieval: true,
    };
  }

  try {
    const data = await askChat(session, { query: trimmed, project_id: projectId ?? null });
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

    const citations = mapCitations((data.citations ?? []) as CitationPayload[]);
    const outcome = typeof data.outcome === "string" ? data.outcome : undefined;
    const conversational = Boolean(data.conversational) || outcome === "conversational";
    const insufficient =
      !conversational &&
      (data.evidence_sufficiency === "insufficient" ||
        outcome === "insufficient_evidence" ||
        outcome === "source_unavailable");
    const fromLibrary = Boolean(data.from_library);

    let content = formatLibraryAnswer(data.answer ?? "", fromLibrary);
    if (!fromLibrary && insufficient) {
      content = formatNoEvidenceMessage(
        (data.project_name as string | undefined) ?? scope?.projectName,
        typeof data.sources_searched === "number" ? data.sources_searched : (scope?.sourcesCount ?? 0),
      );
    }
    if (
      !fromLibrary &&
      !insufficient &&
      !conversational &&
      data.reasoning_summary &&
      outcome !== "conflicting_evidence" &&
      outcome !== "partially_answered"
    ) {
      content += `\n\n_${data.reasoning_summary}_`;
    }

    return {
      content,
      meta: {
        isDraft: data.is_draft !== false && !conversational,
        fromLibrary,
        libraryEntryId: data.library_entry_id ?? undefined,
        libraryStatus: fromLibrary ? "approved" : undefined,
        insufficientEvidence: insufficient,
        conversational,
        intent: typeof data.intent === "string" ? data.intent : undefined,
        outcome,
        needsReview: Boolean(data.needs_review),
        citations,
        projectName: (data.project_name as string | undefined) ?? scope?.projectName ?? undefined,
        sourcesSearched:
          typeof data.sources_searched === "number" ? data.sources_searched : scope?.sourcesCount,
        queryTimeMs: typeof data.query_time_ms === "number" ? data.query_time_ms : undefined,
        userQuery: trimmed,
      },
      skippedRetrieval: false,
    };
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    const message = e instanceof Error ? e.message : "Chat request failed";
    throw new Error(message);
  }
}
