import {
  FolderOpen,
  KeyRound,
  LogOut,
  MessageSquare,
  Plus,
  Sparkles,
  Trash2,
  User as UserIcon,
} from "lucide-react";

import type { Conversation, Document, User } from "../types";
import { DocumentCard } from "./DocumentCard";
import { DocumentUpload } from "./DocumentUpload";

interface SidebarProps {
  activeUser: User | null;
  onOpenAuthModal: () => void;
  onLogout: () => void;
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onDeleteConversation: (id: string) => void;
  documents: Document[];
  isUploading: boolean;
  onUpload: (file: File) => Promise<unknown>;
  onDeleteDocument: (id: string) => void;
}

export function Sidebar({
  activeUser,
  onOpenAuthModal,
  onLogout,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  documents,
  isUploading,
  onUpload,
  onDeleteDocument,
}: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <Sparkles size={18} color="#ffffff" />
          </div>
          <div>
            <div className="sidebar-logo-text">DocQA</div>
          </div>
          <span className="sidebar-logo-badge">RAG</span>
        </div>

        <div className="user-profile-bar">
          <div
            className="user-profile-clickable"
            onClick={onOpenAuthModal}
            title={activeUser ? "Account details" : "Click to Sign In or Register"}
          >
            <div className="user-avatar-badge">
              <UserIcon size={14} />
            </div>
            <div className="user-profile-details">
              <div className="user-profile-name">
                {activeUser ? activeUser.name : "Guest User"}
              </div>
              <div className="user-profile-role">
                {activeUser ? activeUser.role : "Sign In / Register"}
              </div>
            </div>
          </div>

          {activeUser ? (
            <button
              type="button"
              className="user-logout-btn"
              onClick={onLogout}
              title="Sign Out"
            >
              <LogOut size={13} />
            </button>
          ) : (
            <button
              type="button"
              className="user-auth-pill"
              onClick={onOpenAuthModal}
              title="Sign In or Register"
            >
              <KeyRound size={12} />
              <span>Sign In</span>
            </button>
          )}
        </div>

        <button type="button" className="new-chat-btn" onClick={onNewChat}>
          <Plus size={16} />
          <span>New Conversation</span>
        </button>

        <div style={{ marginTop: "12px" }}>
          <DocumentUpload onUpload={onUpload} isUploading={isUploading} />
        </div>
      </div>

      <div className="sidebar-content">
        {conversations.length > 0 && (
          <div className="sidebar-section">
            <div className="sidebar-section-title">
              Chat Threads ({conversations.length})
            </div>
            <div className="conversation-list">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`conversation-item ${conv.id === activeConversationId ? "active" : ""}`}
                  onClick={() => onSelectConversation(conv.id)}
                >
                  <MessageSquare size={14} className="conversation-icon" />
                  <span className="conversation-title" title={conv.title}>
                    {conv.title}
                  </span>
                  <button
                    type="button"
                    className="conversation-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(conv.id);
                    }}
                    title="Delete thread"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="sidebar-section" style={{ marginTop: "16px" }}>
          <div className="sidebar-section-title">
            Documents ({documents.length})
          </div>
          {documents.length > 0 ? (
            <div className="documents-list">
              {documents.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  onDelete={onDeleteDocument}
                />
              ))}
            </div>
          ) : (
            !isUploading && (
              <div className="empty-docs-box">
                <FolderOpen size={24} style={{ opacity: 0.4 }} />
                <div>No documents indexed yet.</div>
                <div style={{ fontSize: "11px" }}>
                  {activeUser
                    ? "Upload PDF, TXT, DOCX, or MD above."
                    : "Sign in to upload and manage documents."}
                </div>
              </div>
            )
          )}
        </div>
      </div>
    </aside>
  );
}
