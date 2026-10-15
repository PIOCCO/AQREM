import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useToast } from "../components/ui/Toast";
import ChatComposer, { type PendingAttachment } from "../components/chat/ChatComposer";
import ChatComposerDock from "../components/chat/ChatComposerDock";
import ChatMainColumn from "../components/chat/ChatMainColumn";
import ChatConversationHeader from "../components/chat/ChatConversationHeader";
import ChatEmptyState from "../components/chat/ChatEmptyState";
import ScopePicker from "../components/chat/ScopePicker";
import MessageList from "../components/chat/MessageList";
import { IconSidebar } from "../components/icons/Icons";
import { fetchSources, uploadSourceFiles } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { streamAssistantReply } from "../lib/chatAssistantStream";
import { classifyChatIntent } from "../lib/chatIntent";
import { conversationTitleAfterUserMessage } from "../lib/chatTitle";
import {
  getConversation,
  type ChatConversation,
  type ChatMessage,
} from "../lib/conversations";
import { useConversations } from "../lib/conversationContext";
import { useProjectContext } from "../lib/projectContext";
import { newUuid } from "../lib/uuid";
import { FOCUS_COMPOSER_EVENT } from "../lib/chatHome";
import { LoadingState } from "../components/ui/States";

const UPLOAD_SOURCE_TYPES = new Set(["folder_archive", "file_upload", "local_files"]);

type ChatOutletContext = {
  openMobileSidebar?: () => void;
  sidebarCollapsed?: boolean;
  expandSidebar?: () => void;
  openCommandPalette?: () => void;
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
  const { upsert, createNew } = useConversations();

  const [conversation, setConversation] = useState<ChatConversation | null>(null);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [retrievalStatus, setRetrievalStatus] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastQueryRef = useRef<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const { push: toast } = useToast();
  const [uploadSourceId, setUploadSourceId] = useState<string | null>(null);
  const [sourcesCount, setSourcesCount] = useState<number | null>(null);
  const [uploadSourceLoading, setUploadSourceLoading] = useState(false);
  const outlet = useOutletContext<ChatOutletContext | null>();

  useKeyboardShortcuts([
    {
      key: "/",
      handler: () => {
        composerRef.current?.focus();
      },
    },
  ]);

  useEffect(() => {
    if (!conversationId) {
      setConversation(null);
      return;
    }
    const conv = getConversation(conversationId);
    if (!conv) {
      setConversation(null);
      navigate("/", { replace: true });
      return;
    }
    setConversation(conv);
    if (conv.projectId && conv.projectId !== projectId) {
      setProjectId(conv.projectId);
    }
  }, [conversationId, navigate, projectId, setProjectId]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, [conversationId]);

  useEffect(() => {
    function onFill(e: Event) {
      const detail = (e as CustomEvent<string>).detail;
      if (typeof detail === "string") setInput(detail);
    }
    function onFocusComposer() {
      composerRef.current?.focus();
    }
    window.addEventListener("aqrem-fill-composer", onFill);
    window.addEventListener(FOCUS_COMPOSER_EVENT, onFocusComposer);
    return () => {
      window.removeEventListener("aqrem-fill-composer", onFill);
      window.removeEventListener(FOCUS_COMPOSER_EVENT, onFocusComposer);
    };
  }, []);

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

  const persist = useCallback(
    (next: ChatConversation) => {
      const saved = upsert(next);
      if (getConversation(next.id)) {
        setConversation(saved);
      }
      return saved;
    },
    [upsert],
  );

  const onSelectScope = useCallback(
    (id: string | null) => {
      setProjectId(id);
      const label = id ? projects.find((p) => p.id === id)?.name ?? "Project" : "All projects";
      toast(`Scope: ${label}`);
      if (conversation) {
        persist({ ...conversation, projectId: id });
      }
    },
    [conversation, persist, projects, setProjectId, toast],
  );

  const scopePicker = (
    <ScopePicker
      projects={projects.map((p) => ({
        id: p.id,
        name: p.name,
        sourcesCount: p.id === projectId ? (sourcesCount ?? undefined) : undefined,
      }))}
      projectId={projectId}
      onSelectProject={onSelectScope}
      sourcesCount={sourcesCount}
    />
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
      setRetrievalStatus(null);
      setStreamingText("");
      const reply = await streamAssistantReply(session, text, conv.projectId, {
        signal: ac.signal,
        onToken: (built) => setStreamingText(built),
      });
      if (ac.signal.aborted) return;

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
    if (!session) return;
    let conv = conversation ?? (conversationId ? getConversation(conversationId) : null);
    if (!conv) {
      conv = createNew(projectId);
      setConversation(conv);
      if (!conversationId) navigate(`/c/${conv.id}`, { replace: true });
    }
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

    conv = {
      ...conv,
      title: text ? conversationTitleAfterUserMessage(conv.title, text) : conv.title,
      messages: [...conv.messages, userMsg],
    };
    conv = persist(conv);
    setInput("");
    setAttachments([]);
    const focusComposer = () => composerRef.current?.focus();
    requestAnimationFrame(focusComposer);
    window.setTimeout(focusComposer, 0);

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
    toast(feedback === "good" ? "Thanks for the feedback" : "Feedback recorded — we'll use this to improve answers");
  }

  function onRetry() {
    const q = lastQueryRef.current;
    if (!conversation || !q) return;
    const trimmed = conversation.messages;
    const withoutError = trimmed[trimmed.length - 1]?.meta?.error ? trimmed.slice(0, -1) : trimmed;
    const conv = persist({ ...conversation, messages: withoutError });
    void streamReply(q, conv);
  }

  if (!session) return null;

  const name = greetingName(user?.fullName, user?.email);
  const atHome = !conversationId;

  const composer = (
    <ChatComposer
      ref={composerRef}
      value={input}
      onChange={setInput}
      onSend={onSend}
      onStop={onStop}
      streaming={loading && streamingText != null}
      loading={loading}
      disabled={false}
      attachments={attachments}
      onPickFiles={onPickFiles}
      onRemoveAttachment={onRemoveAttachment}
      uploadDisabledReason={uploadDisabledReason}
      conversationKey={conversationId ?? "home"}
    />
  );

  if (conversationId && !conversation) {
    return (
      <div className="chat-view bg-chat-main flex items-center justify-center min-h-[40vh]">
        <LoadingState label="Loading conversation…" />
      </div>
    );
  }

  if (atHome) {
    return (
      <div className="chat-view bg-chat-main">
        <ChatConversationHeader
          conversationTitle="New chat"
          onOpenSidebar={outlet?.openMobileSidebar}
          session={session}
          conversation={conversation}
        />
        <div className="min-h-0 min-w-0 overflow-y-auto overflow-x-hidden flex flex-col">
          <ChatMainColumn className="flex flex-1 flex-col min-h-0" data-testid="chat-scroll-column">
            <ChatEmptyState name={name} projectName={projectName} onPickPrompt={setInput} />
          </ChatMainColumn>
        </div>
        <ChatComposerDock scopePicker={scopePicker}>{composer}</ChatComposerDock>
      </div>
    );
  }

  const empty = conversation!.messages.length === 0 && !streamingText && !retrievalStatus;

  async function onRegenerate(userQuery: string) {
    if (!conversation || loading) return;
    const latest = getConversation(conversation.id) ?? conversation;
    await streamReply(userQuery, latest);
  }

  return (
    <div className="chat-view bg-chat-main">
      <ChatConversationHeader
        conversationTitle={conversation!.title}
        onOpenSidebar={outlet?.openMobileSidebar}
        session={session}
        conversation={conversation}
      />

      {empty ? (
        <>
          <div className="min-h-0 min-w-0 overflow-y-auto overflow-x-hidden flex flex-col">
            <ChatMainColumn className="flex flex-1 flex-col min-h-0" data-testid="chat-scroll-column">
              <ChatEmptyState name={name} projectName={projectName} onPickPrompt={setInput} />
            </ChatMainColumn>
          </div>
          <ChatComposerDock scopePicker={scopePicker}>{composer}</ChatComposerDock>
        </>
      ) : (
        <>
          <MessageList
            messages={conversation!.messages}
            streamingText={streamingText}
            retrievalStatus={retrievalStatus}
            onRegenerate={onRegenerate}
            onRetry={onRetry}
            onFeedback={onFeedback}
          />
          <ChatComposerDock scopePicker={scopePicker}>{composer}</ChatComposerDock>
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
