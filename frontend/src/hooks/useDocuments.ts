import { useCallback, useEffect, useRef, useState } from "react";

import { deleteDocument, listDocuments, uploadDocument } from "../api/client";
import type { Document } from "../types";

const POLL_INTERVAL_MS = 1500;

export function useDocuments(isAuthenticated: boolean) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previousStatuses = useRef<Record<string, string>>({});

  const fetchDocuments = useCallback(async () => {
    if (!isAuthenticated) {
      setDocuments([]);
      return;
    }
    try {
      const response = await listDocuments();
      setDocuments(response.documents);
    } catch {
      setDocuments([]);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const hasProcessing = documents.some((doc) => doc.status === "processing");

  useEffect(() => {
    if (!isAuthenticated || !hasProcessing) return;
    const timer = setInterval(fetchDocuments, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isAuthenticated, hasProcessing, fetchDocuments]);

  const [justSettled, setJustSettled] = useState<Document | null>(null);

  useEffect(() => {
    const settled = documents.find(
      (doc) =>
        doc.status !== "processing" && previousStatuses.current[doc.id] === "processing",
    );
    previousStatuses.current = Object.fromEntries(
      documents.map((doc) => [doc.id, doc.status]),
    );
    if (settled) setJustSettled(settled);
  }, [documents]);

  const acknowledgeSettled = useCallback(() => setJustSettled(null), []);

  const upload = useCallback(async (file: File) => {
    setIsUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file);
      setDocuments((prev) => [doc, ...prev]);
      return doc;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setError(message);
      throw err;
    } finally {
      setIsUploading(false);
    }
  }, []);

  const remove = useCallback(async (id: string) => {
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    documents,
    isUploading,
    error,
    upload,
    remove,
    clearError,
    fetchDocuments,
    justSettled,
    acknowledgeSettled,
  };
}
