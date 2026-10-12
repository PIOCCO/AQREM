import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  saveConversation,
  type ChatConversation,
} from "./conversations";

type ConversationContextValue = {
  conversations: ChatConversation[];
  refresh: () => void;
  createNew: (projectId?: string | null) => ChatConversation;
  remove: (id: string) => void;
  rename: (id: string, title: string) => void;
  upsert: (conversation: ChatConversation) => ChatConversation;
  get: (id: string) => ChatConversation | null;
};

const ConversationContext = createContext<ConversationContextValue | null>(null);

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<ChatConversation[]>(() => listConversations());

  const refresh = useCallback(() => {
    setConversations(listConversations());
  }, []);

  const createNew = useCallback(
    (projectId: string | null = null) => {
      const conv = createConversation(projectId);
      refresh();
      return conv;
    },
    [refresh],
  );

  const remove = useCallback(
    (id: string) => {
      deleteConversation(id);
      refresh();
    },
    [refresh],
  );

  const rename = useCallback(
    (id: string, title: string) => {
      renameConversation(id, title);
      refresh();
    },
    [refresh],
  );

  const upsert = useCallback(
    (conversation: ChatConversation) => {
      const saved = saveConversation(conversation);
      refresh();
      return saved;
    },
    [refresh],
  );

  const get = useCallback((id: string) => getConversation(id), []);

  const value = useMemo(
    () => ({ conversations, refresh, createNew, remove, rename, upsert, get }),
    [conversations, refresh, createNew, remove, rename, upsert, get],
  );

  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>;
}

export function useConversations() {
  const ctx = useContext(ConversationContext);
  if (!ctx) throw new Error("useConversations must be used within ConversationProvider");
  return ctx;
}
