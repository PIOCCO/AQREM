import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useToast } from "../components/ui/Toast";
import ChatComposer from "../components/chat/ChatComposer";
import ChatFileDropOverlay from "../components/chat/ChatFileDropOverlay";
import ChatComposerDock from "../components/chat/ChatComposerDock";
import ChatMainColumn from "../components/chat/ChatMainColumn";
import ChatConversationHeader from "../components/chat/ChatConversationHeader";
import ChatEmptyState from "../components/chat/ChatEmptyState";
import ScopePicker from "../components/chat/ScopePicker";
import MessageList from "../components/chat/MessageList";
import { IconSidebar } from "../components/icons/Icons";
import { fetchSources } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useChatAttachments } from "../hooks/useChatAttachments";
import { canEditContent } from "../lib/roles";
import { generateAssistantReply } from "../lib/chatAssistant";
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

type ChatOutletContext = {
  openMobileSidebar?: () => void;
  sidebarCollapsed?: boolean;
  expandSidebar?: () => void;
  openCommandPalette?: () => void;
};

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
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [retrievalStatus, setRetrievalStatus] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastQueryRef = useRef<string | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const { push: toast } = useToast();
  const [sourcesCount, setSourcesCount] = useState<number | null>(null);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const outlet = useOutletContext<ChatOutletContext | null>();
  const canUpload = Boolean(user?.role && canEditContent(user.role));
  const {
    limits,
    attachments,
    bannerError,
    addFiles,
    removeAttachment,
    retryAttachment,
    clearAttachments,
    documentIds,
    sendBlocked,
  } = useChatAttachments(session, canUpload);

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
      setSourcesCount(null);
      return;
    }
    setSourcesLoading(true);
    fetchSources(session, projectId)
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : [];
        setSourcesCount(list.filter((s: { project_id?: string }) => s.project_id === projectId).length);
      })
      .catch(() => setSourcesCount(null))
      .finally(() => setSourcesLoading(false));
  }, [session, projectId]);

  const uploadDisabledReason = useMemo(() => {
    if (sourcesLoading) return "Loading…";
    if (!canUpload) return "Viewers cannot upload files. Ask an editor or administrator.";
    return null;
  }, [canUpload, sourcesLoading]);

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

  async function streamReply(text: string, conv: ChatConversation, attachmentDocumentIds?: string[]) {
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
        attachmentDocumentIds,
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
    if (!session) return;
    let conv = conversation ?? (conversationId ? getConversation(conversationId) : null);
    if (!conv) {
      conv = createNew(projectId);
      setConversation(conv);
      if (!conversationId) navigate(`/c/${conv.id}`, { replace: true });
    }
    const text = input.trim();
    const hasAttachments = attachments.some((a) => a.status === "ready" || a.status === "indexing");
    if (!text && !hasAttachments) return;
    if (sendBlocked) return;

    const attachmentMeta = attachments
      .filter((a) => a.status !== "failed")
      .map((a) => ({
        name: a.file.name,
        sizeLabel: a.file.size ? `${Math.max(1, Math.round(a.file.size / 1024))} KB` : undefined,
      }));
    const userContent = text || "(Attached files)";
    const idsForAsk = [...documentIds];
    const userMsg: ChatMessage = {
      id: newUuid(),
      role: "user",
      content: userContent,
      createdAt: new Date().toISOString(),
      meta: {
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
    clearAttachments();
    const focusComposer = () => composerRef.current?.focus();
    requestAnimationFrame(focusComposer);
    window.setTimeout(focusComposer, 0);

    if (text || idsForAsk.length) await streamReply(text || "Summarize the attached documents.", conv, idsForAsk);
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
    <>
      {bannerError ? (
        <div className="text-xs text-[var(--color-danger)] mb-2 px-1" role="alert">
          {bannerError}
        </div>
      ) : null}
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
        onPickFiles={addFiles}
        onRemoveAttachment={removeAttachment}
        onRetryAttachment={retryAttachment}
        uploadDisabledReason={uploadDisabledReason}
        helperText={limits?.helper_text}
        sendBlocked={sendBlocked}
        conversationKey={conversationId ?? "home"}
      />
    </>
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
      <ChatFileDropOverlay
        className="chat-view bg-chat-main flex flex-col min-h-0 flex-1"
        disabled={Boolean(uploadDisabledReason)}
        disabledReason={uploadDisabledReason}
        onFiles={addFiles}
      >
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
      </ChatFileDropOverlay>
    );
  }

  const empty = conversation!.messages.length === 0 && !streamingText && !retrievalStatus;

  async function onRegenerate(userQuery: string) {
    if (!conversation || loading) return;
    const latest = getConversation(conversation.id) ?? conversation;
    await streamReply(userQuery, latest);
  }

  return (
    <ChatFileDropOverlay
      className="chat-view bg-chat-main flex flex-col min-h-0 flex-1"
      disabled={Boolean(uploadDisabledReason)}
      disabledReason={uploadDisabledReason}
      onFiles={addFiles}
    >
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
    </ChatFileDropOverlay>
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
