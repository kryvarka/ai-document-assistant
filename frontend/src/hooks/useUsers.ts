import { useCallback, useEffect, useState } from "react";

import { getCurrentUser, getAuthToken, setAuthToken } from "../api/client";
import type { User } from "../types";

export function useUsers() {
  const [activeUser, setActiveUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkCurrentUser = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setActiveUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const me = await getCurrentUser();
      setActiveUser(me);
    } catch {
      setAuthToken(null);
      setActiveUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const selectUser = useCallback((user: User | null) => {
    setActiveUser(user);
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setActiveUser(null);
  }, []);

  useEffect(() => {
    checkCurrentUser();
  }, [checkCurrentUser]);

  return {
    activeUser,
    isAuthenticated: !!activeUser,
    isLoading,
    selectUser,
    logout,
    checkCurrentUser,
  };
}
