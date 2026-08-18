import { Loader2, MessageSquare, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Conversation, Message } from "../types";
import { EmptyState } from "./EmptyState";
import { MessageBubble } from "./MessageBubble";

interface ChatPanelProps {
  activeConversation: Conversation | null;
  messages: Message[];
  isLoading: boolean;
  hasDocuments: boolean;
  onSendMessage: (question: string) => void;
}

export function ChatPanel({
  activeConversation,
  messages,
  isLoading,
  hasDocuments,
  onSendMessage,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || !hasDocuments) return;
    onSendMessage(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, isLoading, hasDocuments, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  const handleSuggestionClick = useCallback(
    (question: string) => {
      onSendMessage(question);
    },
    [onSendMessage],
  );

  return (
    <div className="main-content">
      <div className="chat-header-bar">
        <div className="chat-header-info">
          <MessageSquare size={16} style={{ color: "var(--color-accent)" }} />
          <span className="chat-header-title">
            {activeConversation ? activeConversation.title : "New Session"}
          </span>
        </div>
        <div className="chat-header-badge">
          {hasDocuments ? "Knowledge Base Connected" : "No Docs Uploaded"}
        </div>
      </div>

      <div className="chat-container">
        {messages.length === 0 ? (
          <EmptyState
            hasDocuments={hasDocuments}
            onSuggestionClick={handleSuggestionClick}
          />
        ) : (
          <div className="chat-messages">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <textarea
              ref={textareaRef}
              className="chat-input"
              placeholder={
                hasDocuments
                  ? "Ask a question or follow up on previous answers..."
                  : "Upload a document first to start chatting"
              }
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              disabled={!hasDocuments}
              rows={1}
            />
            <button
              type="button"
              className="chat-send-btn"
              onClick={handleSubmit}
              disabled={!input.trim() || isLoading || !hasDocuments}
              title="Send message"
            >
              {isLoading ? (
                <Loader2 size={16} className="upload-zone-icon-spinner" />
              ) : (
                <Send size={15} />
              )}
            </button>
          </div>
          <div className="chat-input-hint">
            Press Enter to send · Shift+Enter for new line · Multi-turn context enabled
          </div>
        </div>
      </div>
    </div>
  );
}
