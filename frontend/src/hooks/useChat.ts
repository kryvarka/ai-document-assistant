import { useCallback, useState } from "react";

import { getConversation, streamChat } from "../api/client";
import type { Message, SourceChunk } from "../types";

let messageCounter = 0;

function generateId(): string {
  return `msg_${Date.now()}_${++messageCounter}`;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadConversationMessages = useCallback(async (conversationId: string) => {
    try {
      setIsLoading(true);
      const detail = await getConversation(conversationId);
      setMessages(detail.messages || []);
    } catch {
      setMessages([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback(
    async (
      question: string,
      options: {
        conversationId?: string;
        documentIds?: string[];
        onConversationCreated?: (id: string) => void;
      } = {},
    ) => {
      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content: question,
      };

      const assistantId = generateId();
      const assistantMessage: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsLoading(true);

      let sources: SourceChunk[] = [];

      await streamChat(
        question,
        {
          conversationId: options.conversationId,
          documentIds: options.documentIds,
        },
        {
          onMeta: (meta: { conversation_id: string; sources: SourceChunk[] }) => {
            if (meta.conversation_id && options.onConversationCreated) {
              options.onConversationCreated(meta.conversation_id);
            }
          },
          onSources: (s: SourceChunk[]) => {
            sources = s;
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, sources: s } : m)),
            );
          },
          onToken: (token: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + token } : m,
              ),
            );
          },
          onDone: () => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, isStreaming: false, sources }
                  : m,
              ),
            );
            setIsLoading(false);
          },
          onError: (error: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: `Error: ${error}`,
                      isStreaming: false,
                    }
                  : m,
              ),
            );
            setIsLoading(false);
          },
        },
      );
    },
    [],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isLoading,
    sendMessage,
    clearMessages,
    loadConversationMessages,
    setMessages,
  };
}
