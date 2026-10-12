import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import ChatComposer, { type PendingAttachment } from "../components/chat/ChatComposer";
import ChatConversationHeader from "../components/chat/ChatConversationHeader";
import ChatEmptyState from "../components/chat/ChatEmptyState";
import ChatScopeBar from "../components/chat/ChatScopeBar";
import MessageList from "../components/chat/MessageList";
import { IconSidebar } from "../components/icons/Icons";
import { fetchSources, uploadSourceFiles } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { generateAssistantReply } from "../lib/chatAssistant";
import { classifyChatIntent } from "../lib/chatIntent";
import { conversationTitleAfterUserMessage } from "../lib/chatTitle";
import {
  createConversation,
  getConversation,
  saveConversation,
  type ChatConversation,
  type ChatMessage,
} from "../lib/conversations";
import { useConversations } from "../lib/conversationContext";
import { useProjectContext } from "../lib/projectContext";
import { newUuid } from "../lib/uuid";

const UPLOAD_SOURCE_TYPES = new Set(["folder_archive", "file_upload", "local_files"]);

type ChatOutletContext = {
  openMobileSidebar?: () => void;
  sidebarCollapsed?: boolean;
  expandSidebar?: () => void;
};

function formatAttachmentMeta(files: PendingAttachment[]) {
  return files.map((a) => ({
    name: a.file.name,
    sizeLabel: a.file.size ? `${Math.max(1, Math.round(a.file.size / 1024))} KB` : undefined,
  }));
}

function greetingName(fullName?: string, email?: string) {
  const first = fullName?.trim().split(/\s+/)[0];
  if (first) return first;
  return email?.split("@")[0] ?? "there";
}

export default function ChatPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const { session, user } = useAuth();
  const { projectId, projectName, projects, setProjectId } = useProjectContext();
  const { upsert } = useConversations();

  const [conversation, setConversation] = useState<ChatConversation | null>(null);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [retrievalStatus, setRetrievalStatus] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastQueryRef = useRef<string | null>(null);
  const [uploadSourceId, setUploadSourceId] = useState<string | null>(null);
  const [sourcesCount, setSourcesCount] = useState<number | null>(null);
  const [uploadSourceLoading, setUploadSourceLoading] = useState(false);
  const outlet = useOutletContext<ChatOutletContext | null>();

  useEffect(() => {
    if (!conversationId) {
      const conv = createConversation(projectId);
      navigate(`/c/${conv.id}`, { replace: true });
      return;
    }
    let conv = getConversation(conversationId);
    if (!conv) {
      conv = createConversation(projectId);
      navigate(`/c/${conv.id}`, { replace: true });
      return;
    }
    if (conv.projectId !== projectId) {
      conv = saveConversation({ ...conv, projectId });
    }
    setConversation(conv);
  }, [conversationId, projectId, navigate]);

  useEffect(() => {
    if (!session || !projectId) {
      setUploadSourceId(null);
      setSourcesCount(null);
      return;
    }
    setUploadSourceLoading(true);
    fetchSources(session, projectId)
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : [];
        setSourcesCount(list.filter((s: { project_id?: string }) => s.project_id === projectId).length);
        const match = list.find(
          (s: { project_id?: string; source_type: string; id: string }) =>
            s.project_id === projectId && UPLOAD_SOURCE_TYPES.has(s.source_type),
        );
        setUploadSourceId(match?.id ?? list.find((s: { project_id?: string }) => s.project_id === projectId)?.id ?? null);
      })
      .catch(() => {
        setUploadSourceId(null);
        setSourcesCount(null);
      })
      .finally(() => setUploadSourceLoading(false));
  }, [session, projectId]);

  const uploadDisabledReason = useMemo(() => {
    if (uploadSourceLoading) return "Loading sources…";
    if (!projectId) return "Select a project to attach files";
    if (!uploadSourceId) return "Add a file source in Projects first";
    return null;
  }, [projectId, uploadSourceId, uploadSourceLoading]);

  const scopeBar = (
    <ChatScopeBar
      projectName={projectName}
      projectId={projectId}
      sourcesCount={sourcesCount}
      projects={projects}
      onSelectProject={setProjectId}
      compact={false}
    />
  );

  const persist = useCallback(
    (next: ChatConversation) => {
      const saved = upsert(next);
      setConversation(saved);
      return saved;
    },
    [upsert],
  );

  const onPickFiles = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    const added: PendingAttachment[] = Array.from(files).map((file) => ({
      id: newUuid(),
      file,
      status: "pending" as const,
    }));
    setAttachments((prev) => [...prev, ...added]);
  }, []);

  const onRemoveAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  async function uploadAttachments(): Promise<string | undefined> {
    if (!session || !uploadSourceId || attachments.length === 0) return undefined;
    const pending = attachments.filter((a) => a.status === "pending");
    if (pending.length === 0) return undefined;

    setAttachments((prev) => prev.map((a) => (a.status === "pending" ? { ...a, status: "uploading" } : a)));
    try {
      await uploadSourceFiles(
        session,
        uploadSourceId,
        pending.map((p) => p.file),
      );
      setAttachments((prev) => prev.map((a) => (a.status === "uploading" ? { ...a, status: "done" } : a)));
      return `Uploaded ${pending.length} file(s). Indexing runs in the background — ask again once sync completes.`;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setAttachments((prev) =>
        prev.map((a) => (a.status === "uploading" ? { ...a, status: "error", error: msg } : a)),
      );
      throw e;
    }
  }

  async function streamReply(text: string, conv: ChatConversation) {
    if (!session) return;
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    lastQueryRef.current = text;

    setLoading(true);
    setStreamingText(null);
    if (!classifyChatIntent(text)) {
      const n = sourcesCount ?? 0;
      setRetrievalStatus(`Searching ${n} source${n === 1 ? "" : "s"}…`);
    } else {
      setRetrievalStatus(null);
    }

    try {
      const reply = await generateAssistantReply(session, text, conv.projectId, ac.signal, {
        projectName,
        sourcesCount: sourcesCount ?? 0,
      });
      if (ac.signal.aborted) return;

      setRetrievalStatus(null);
      setStreamingText("");

      const chars = reply.content.split("");
      let built = "";
      for (let i = 0; i < chars.length; i++) {
        if (ac.signal.aborted) return;
        built += chars[i];
        setStreamingText(built);
        if (i % 3 === 0) await new Promise((r) => setTimeout(r, 8));
      }

      const assistantMsg: ChatMessage = {
        id: newUuid(),
        role: "assistant",
        content: reply.content,
        createdAt: new Date().toISOString(),
        meta: reply.meta,
      };

      persist({ ...conv, messages: [...conv.messages, assistantMsg] });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setRetrievalStatus(null);
      const assistantMsg: ChatMessage = {
        id: newUuid(),
        role: "assistant",
        content: "We couldn't reach the server. Check your connection and try again.",
        createdAt: new Date().toISOString(),
        meta: { error: true, isDraft: true, userQuery: text },
      };
      persist({ ...conv, messages: [...conv.messages, assistantMsg] });
    } finally {
      setStreamingText(null);
      setRetrievalStatus(null);
      setLoading(false);
      abortRef.current = null;
    }
  }

  async function onSend() {
    if (!session || !conversation) return;
    const text = input.trim();
    const hasPendingFiles = attachments.some((a) => a.status === "pending");
    if (!text && !hasPendingFiles) return;

    let uploadNote: string | undefined;
    try {
      uploadNote = await uploadAttachments();
    } catch {
      return;
    }

    const attachmentMeta = formatAttachmentMeta(attachments.filter((a) => a.status !== "error"));
    const userContent = text || "(Attached files)";
    const userMsg: ChatMessage = {
      id: newUuid(),
      role: "user",
      content: userContent,
      createdAt: new Date().toISOString(),
      meta: {
        ...(uploadNote ? { uploadNote } : {}),
        ...(attachmentMeta.length ? { attachments: attachmentMeta } : {}),
      },
    };

    let conv = conversation;
    conv = {
      ...conv,
      title: text ? conversationTitleAfterUserMessage(conv.title, text) : conv.title,
      messages: [...conv.messages, userMsg],
    };
    conv = persist(conv);
    setInput("");
    setAttachments([]);

    if (text) await streamReply(text, conv);
    else if (uploadNote) {
      const assistantMsg: ChatMessage = {
        id: newUuid(),
        role: "assistant",
        content: uploadNote,
        createdAt: new Date().toISOString(),
        meta: { isDraft: true },
      };
      persist({ ...conv, messages: [...conv.messages, assistantMsg] });
    }
  }

  function onStop() {
    abortRef.current?.abort();
    setStreamingText(null);
    setRetrievalStatus(null);
    setLoading(false);
  }

  function onFeedback(messageId: string, feedback: "good" | "bad") {
    if (!conversation) return;
    const messages = conversation.messages.map((m) =>
      m.id === messageId ? { ...m, meta: { ...m.meta, feedback } } : m,
    );
    persist({ ...conversation, messages });
  }

  function onRetry() {
    const q = lastQueryRef.current;
    if (!conversation || !q) return;
    const trimmed = conversation.messages;
    const withoutError = trimmed[trimmed.length - 1]?.meta?.error ? trimmed.slice(0, -1) : trimmed;
    const conv = persist({ ...conversation, messages: withoutError });
    void streamReply(q, conv);
  }

  if (!session || !conversation) return null;

  const empty = conversation.messages.length === 0 && !streamingText && !retrievalStatus;
  const name = greetingName(user?.fullName, user?.email);

  async function onRegenerate(userQuery: string) {
    if (!conversation || loading) return;
    const latest = getConversation(conversation.id) ?? conversation;
    await streamReply(userQuery, latest);
  }

  return (
    <div className="flex flex-col h-full min-h-0 bg-chat-main">
      <ChatConversationHeader
        conversationTitle={conversation.title}
        onOpenSidebar={outlet?.openMobileSidebar}
        onExpandSidebar={outlet?.sidebarCollapsed ? outlet.expandSidebar : undefined}
      />

      {empty ? (
        <>
          <ChatEmptyState
            name={name}
            projectName={projectName}
            projectId={projectId}
            sourcesCount={sourcesCount}
            projects={projects}
            onSelectProject={setProjectId}
            onPickPrompt={setInput}
          />
          <div className="w-full shrink-0 ref-composer-dock">
            <ChatComposer
              value={input}
              onChange={setInput}
              onSend={onSend}
              onStop={onStop}
              streaming={loading && streamingText != null}
              loading={loading}
              disabled={loading}
              attachments={attachments}
              onPickFiles={onPickFiles}
              onRemoveAttachment={onRemoveAttachment}
              uploadDisabledReason={uploadDisabledReason}
              centered
            />
          </div>
        </>
      ) : (
        <>
          <MessageList
            messages={conversation.messages}
            streamingText={streamingText}
            retrievalStatus={retrievalStatus}
            onRegenerate={onRegenerate}
            onRetry={onRetry}
            onFeedback={onFeedback}
          />
          <div className="shrink-0 ref-composer-dock">
            <ChatComposer
              value={input}
              onChange={setInput}
              onSend={onSend}
              onStop={onStop}
              streaming={loading && streamingText != null}
              loading={loading}
              disabled={loading}
              attachments={attachments}
              onPickFiles={onPickFiles}
              onRemoveAttachment={onRemoveAttachment}
              uploadDisabledReason={uploadDisabledReason}
              scopeSlot={scopeBar}
            />
          </div>
        </>
      )}
    </div>
  );
}

/** Mobile header toggle lives in AppShell — export icon for reuse */
export function ChatMobileMenuButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="chat-icon-btn lg:hidden focus-visible:ref-focus-ring" onClick={onClick} aria-label="Open sidebar">
      <IconSidebar className="h-5 w-5" />
    </button>
  );
}
