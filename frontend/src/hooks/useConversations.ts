import { useCallback, useEffect, useState } from "react";

import {
  createConversation,
  deleteConversation,
  listConversations,
} from "../api/client";
import type { Conversation } from "../types";

export function useConversations(isAuthenticated: boolean) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchConversations = useCallback(async () => {
    if (!isAuthenticated) {
      setConversations([]);
      setActiveConversationId(null);
      return;
    }
    try {
      setIsLoading(true);
      const list = await listConversations();
      setConversations(list);
      setActiveConversationId((currentId) => {
        if (!currentId && list.length > 0) {
          return list[0].id;
        }
        return currentId;
      });
    } catch {
      setConversations([]);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const newChat = useCallback(async () => {
    try {
      const conv = await createConversation("New Conversation");
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      return conv;
    } catch {
      return null;
    }
  }, []);

  const removeConversation = useCallback(
    async (id: string) => {
      try {
        await deleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        setActiveConversationId((currentId) => {
          if (currentId === id) {
            const remaining = conversations.filter((c) => c.id !== id);
            return remaining.length > 0 ? remaining[0].id : null;
          }
          return currentId;
        });
      } catch {
      }
    },
    [conversations],
  );

  return {
    conversations,
    activeConversationId,
    setActiveConversationId,
    isLoading,
    fetchConversations,
    newChat,
    removeConversation,
  };
}
