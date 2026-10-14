import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AuthSession } from "../lib/api";
import {
  deleteChatAttachment,
  fetchChatAttachmentLimits,
  fetchChatAttachmentStatus,
  uploadChatAttachment,
  type ChatAttachmentLimits,
} from "../lib/chatAttachmentsApi";
import { validateChatFileClient } from "../lib/chatAttachmentValidation";
import { newUuid } from "../lib/uuid";

export type ChatAttachmentChip = {
  clientId: string;
  file: File;
  documentId?: string;
  status: "queued" | "uploading" | "indexing" | "ready" | "failed";
  progress: number;
  error?: string;
};

export function useChatAttachments(session: AuthSession | null, canUpload: boolean) {
  const [limits, setLimits] = useState<ChatAttachmentLimits | null>(null);
  const [attachments, setAttachments] = useState<ChatAttachmentChip[]>([]);
  const [bannerError, setBannerError] = useState<string | null>(null);
  const uploadQueueRef = useRef<Promise<void>>(Promise.resolve());
  const pollTimers = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    fetchChatAttachmentLimits()
      .then(setLimits)
      .catch(() => {
        setLimits(null);
      });
  }, []);

  useEffect(() => {
    return () => {
      pollTimers.current.forEach((t) => window.clearInterval(t));
      pollTimers.current.clear();
    };
  }, []);

  const stopPoll = useCallback((clientId: string) => {
    const t = pollTimers.current.get(clientId);
    if (t != null) window.clearInterval(t);
    pollTimers.current.delete(clientId);
  }, []);

  const startPoll = useCallback(
    (clientId: string, documentId: string) => {
      if (!session) return;
      stopPoll(clientId);
      const tick = () => {
        void fetchChatAttachmentStatus(session, documentId)
          .then((st) => {
            setAttachments((prev) =>
              prev.map((a) => {
                if (a.clientId !== clientId) return a;
                if (st.status === "indexed") {
                  stopPoll(clientId);
                  return { ...a, status: "ready", progress: 100 };
                }
                if (st.status === "failed") {
                  stopPoll(clientId);
                  return {
                    ...a,
                    status: "failed",
                    error: st.failure_reason ?? "Indexing failed",
                    progress: 0,
                  };
                }
                return {
                  ...a,
                  status: "indexing",
                  progress: Math.max(a.progress, st.index_progress ?? 30),
                };
              }),
            );
          })
          .catch(() => {});
      };
      tick();
      pollTimers.current.set(clientId, window.setInterval(tick, 2000));
    },
    [session, stopPoll],
  );

  const runUpload = useCallback(
    (clientId: string, file: File) => {
      if (!session) return;
      uploadQueueRef.current = uploadQueueRef.current.then(async () => {
        setAttachments((prev) =>
          prev.map((a) => (a.clientId === clientId ? { ...a, status: "uploading", progress: 10 } : a)),
        );
        try {
          const res = await uploadChatAttachment(session, file);
          setAttachments((prev) =>
            prev.map((a) =>
              a.clientId === clientId
                ? { ...a, documentId: res.id, status: "indexing", progress: 40 }
                : a,
            ),
          );
          startPoll(clientId, res.id);
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Upload failed";
          setAttachments((prev) =>
            prev.map((a) => (a.clientId === clientId ? { ...a, status: "failed", error: msg, progress: 0 } : a)),
          );
        }
      });
    },
    [session, startPoll],
  );

  const addFiles = useCallback(
    (incoming: File[]) => {
      if (!canUpload) {
        setBannerError("Your role cannot upload files. Ask an editor or administrator.");
        return;
      }
      if (!limits) {
        setBannerError("Attachment limits are still loading. Try again in a moment.");
        return;
      }
      setBannerError(null);
      const folder = incoming.find((f) => (f as File & { webkitRelativePath?: string }).webkitRelativePath);
      if (folder?.webkitRelativePath) {
        setBannerError("Folders cannot be dropped here. Select individual files.");
        return;
      }
      const existingFiles = attachments.map((a) => a.file);
      const next: ChatAttachmentChip[] = [];
      for (const file of incoming) {
        if (existingFiles.length + next.length >= limits.max_files_per_message) {
          setBannerError(`You can attach up to ${limits.max_files_per_message} files per message.`);
          break;
        }
        const err = validateChatFileClient(file, limits, [...existingFiles, ...next.map((n) => n.file)]);
        if (err) {
          setBannerError(err);
          continue;
        }
        const clientId = newUuid();
        next.push({ clientId, file, status: "queued", progress: 0 });
      }
      if (!next.length) return;
      setAttachments((prev) => [...prev, ...next]);
      for (const chip of next) {
        runUpload(chip.clientId, chip.file);
      }
    },
    [attachments, canUpload, limits, runUpload],
  );

  const removeAttachment = useCallback(
    (clientId: string) => {
      const row = attachments.find((a) => a.clientId === clientId);
      stopPoll(clientId);
      setAttachments((prev) => prev.filter((a) => a.clientId !== clientId));
      if (session && row?.documentId) {
        void deleteChatAttachment(session, row.documentId).catch(() => {});
      }
    },
    [attachments, session, stopPoll],
  );

  const retryAttachment = useCallback(
    (clientId: string) => {
      const row = attachments.find((a) => a.clientId === clientId);
      if (!row) return;
      setAttachments((prev) =>
        prev.map((a) => (a.clientId === clientId ? { ...a, status: "queued", error: undefined, progress: 0 } : a)),
      );
      runUpload(clientId, row.file);
    },
    [attachments, runUpload],
  );

  const clearAttachments = useCallback(() => {
    attachments.forEach((a) => stopPoll(a.clientId));
    setAttachments([]);
  }, [attachments, stopPoll]);

  const documentIds = useMemo(
    () => attachments.filter((a) => a.documentId && a.status !== "failed").map((a) => a.documentId!),
    [attachments],
  );

  const sendBlocked = attachments.some((a) => a.status === "uploading" || a.status === "queued");

  return {
    limits,
    attachments,
    bannerError,
    setBannerError,
    addFiles,
    removeAttachment,
    retryAttachment,
    clearAttachments,
    documentIds,
    sendBlocked,
  };
}
