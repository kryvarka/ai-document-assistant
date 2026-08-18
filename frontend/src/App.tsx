import { AlertCircle, CheckCircle2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { AuthModal } from "./components/AuthModal";
import { ChatPanel } from "./components/ChatPanel";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";
import { useConversations } from "./hooks/useConversations";
import { useDocuments } from "./hooks/useDocuments";
import { useUsers } from "./hooks/useUsers";
import type { User } from "./types";

interface Toast {
  id: number;
  message: string;
  type: "success" | "error";
}

let toastId = 0;

export default function App() {
  const { activeUser, isAuthenticated, selectUser, logout } = useUsers();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const streamingConvIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (window.location.pathname !== "/" && window.location.pathname !== "") {
      window.history.replaceState(null, "", "/");
    }
  }, []);

  const {
    documents,
    isUploading,
    error: docError,
    upload,
    remove,
    clearError,
    fetchDocuments,
    justSettled,
    acknowledgeSettled,
  } = useDocuments(isAuthenticated);

  const {
    conversations,
    activeConversationId,
    setActiveConversationId,
    newChat,
    removeConversation,
    fetchConversations,
  } = useConversations(isAuthenticated);

  const {
    messages,
    isLoading,
    sendMessage,
    loadConversationMessages,
    clearMessages,
  } = useChat();

  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: "success" | "error") => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchDocuments();
      fetchConversations();
    } else {
      clearMessages();
    }
  }, [isAuthenticated, fetchDocuments, fetchConversations, clearMessages]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      setActiveConversationId(id);
      loadConversationMessages(id);
    },
    [setActiveConversationId, loadConversationMessages],
  );

  useEffect(() => {
    if (activeConversationId && isAuthenticated && streamingConvIdRef.current !== activeConversationId) {
      loadConversationMessages(activeConversationId);
    }
  }, [activeConversationId, isAuthenticated, loadConversationMessages]);

  useEffect(() => {
    if (!justSettled) return;
    if (justSettled.status === "ready") {
      showToast(`${justSettled.filename} indexed (${justSettled.chunk_count} chunks)`, "success");
    } else {
      showToast(
        `${justSettled.filename} failed to index: ${justSettled.error_message ?? "unknown error"}`,
        "error",
      );
    }
    acknowledgeSettled();
  }, [justSettled, showToast, acknowledgeSettled]);

  useEffect(() => {
    if (docError) {
      showToast(docError, "error");
      clearError();
    }
  }, [docError, showToast, clearError]);

  const handleUpload = useCallback(
    async (file: File) => {
      if (!isAuthenticated) {
        setIsAuthModalOpen(true);
        showToast("Please sign in or register to upload documents", "error");
        return;
      }
      try {
        await upload(file);
        showToast(`${file.name} uploaded — indexing in background`, "success");
      } catch {
      }
    },
    [isAuthenticated, upload, showToast],
  );

  const handleDeleteDoc = useCallback(
    async (id: string) => {
      if (!isAuthenticated) return;
      await remove(id);
      showToast("Document deleted", "success");
    },
    [isAuthenticated, remove, showToast],
  );

  const handleSendMessage = useCallback(
    async (question: string) => {
      if (!isAuthenticated) {
        setIsAuthModalOpen(true);
        showToast("Please sign in or register to ask questions", "error");
        return;
      }
      await sendMessage(question, {
        conversationId: activeConversationId || undefined,
        onConversationCreated: (newId) => {
          streamingConvIdRef.current = newId;
          setActiveConversationId(newId);
          fetchConversations();
        },
      });
    },
    [isAuthenticated, sendMessage, activeConversationId, setActiveConversationId, fetchConversations, showToast],
  );

  const handleNewChat = useCallback(async () => {
    if (!isAuthenticated) {
      setIsAuthModalOpen(true);
      showToast("Please sign in or register first", "error");
      return;
    }
    const conv = await newChat();
    if (conv) {
      streamingConvIdRef.current = null;
      clearMessages();
      showToast("New conversation started", "success");
    }
  }, [isAuthenticated, newChat, clearMessages, showToast]);

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      if (!isAuthenticated) return;
      await removeConversation(id);
      showToast("Chat thread deleted", "success");
    },
    [isAuthenticated, removeConversation, showToast],
  );

  const handleAuthSuccess = (user: User) => {
    selectUser(user);
    showToast(`Signed in as ${user.name}`, "success");
  };

  const handleLogout = () => {
    logout();
    clearMessages();
    showToast("Signed out", "success");
  };

  const activeConv = conversations.find((c) => c.id === activeConversationId) || null;
  const hasSearchableDocuments = documents.some((doc) => doc.status === "ready");

  return (
    <div className="app-layout">
      <Sidebar
        activeUser={activeUser}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onLogout={handleLogout}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        documents={documents}
        isUploading={isUploading}
        onUpload={handleUpload}
        onDeleteDocument={handleDeleteDoc}
      />
      <ChatPanel
        activeConversation={activeConv}
        messages={messages}
        isLoading={isLoading}
        hasDocuments={hasSearchableDocuments}
        onSendMessage={handleSendMessage}
      />
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        activeUser={activeUser}
        onAuthSuccess={handleAuthSuccess}
        onLogout={handleLogout}
      />
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.type}`}>
          {toast.type === "success" ? (
            <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
          ) : (
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
          )}
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
