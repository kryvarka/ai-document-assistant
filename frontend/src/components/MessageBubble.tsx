import { Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Message } from "../types";
import { SourceCard } from "./SourceCard";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className="message">
      <div className={`message-avatar ${message.role}`}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className="message-content">
        <div className="message-role">{isUser ? "You" : "DocQA"}</div>
        <div className="message-text">
          {message.content ? (
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : message.isStreaming ? (
            <TypingIndicator />
          ) : null}
        </div>
        {message.sources && message.sources.length > 0 && !message.isStreaming && (
          <div className="message-sources">
            {message.sources.map((source, idx) => (
              <SourceCard
                key={`${source.document_name}-${source.chunk_index}-${idx}`}
                source={source}
                index={idx + 1}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <span />
      <span />
      <span />
    </div>
  );
}
