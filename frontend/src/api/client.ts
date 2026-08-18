import type {
  Conversation,
  ConversationDetail,
  Document,
  DocumentListResponse,
  SourceChunk,
  User,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let currentAuthToken: string | null = localStorage.getItem("docqa_auth_token");

export function setAuthToken(token: string | null): void {
  currentAuthToken = token;
  if (token) {
    localStorage.setItem("docqa_auth_token", token);
  } else {
    localStorage.removeItem("docqa_auth_token");
  }
}

export function getAuthToken(): string | null {
  return currentAuthToken;
}

function getAuthHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...customHeaders };
  if (currentAuthToken) {
    headers["Authorization"] = `Bearer ${currentAuthToken}`;
  }
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail || "Request failed");
  }
  return response.json();
}

export async function loginWithCredentials(
  email: string,
  password: string,
): Promise<{ access_token: string; user: User }> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse<{ access_token: string; token_type: string; user: User }>(response);
  setAuthToken(data.access_token);
  return data;
}

export async function registerAccount(payload: {
  name: string;
  email: string;
  password: string;
  role?: string;
}): Promise<{ access_token: string; user: User }> {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await handleResponse<{ access_token: string; token_type: string; user: User }>(response);
  setAuthToken(data.access_token);
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(),
  });
  return handleResponse<User>(response);
}

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });
  return handleResponse<Document>(response);
}

export async function listDocuments(): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE}/documents`, {
    headers: getAuthHeaders(),
  });
  return handleResponse<DocumentListResponse>(response);
}

export async function deleteDocument(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/documents/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!response.ok && response.status !== 204) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail || "Delete failed");
  }
}

export async function listConversations(): Promise<Conversation[]> {
  const response = await fetch(`${API_BASE}/conversations`, {
    headers: getAuthHeaders(),
  });
  return handleResponse<Conversation[]>(response);
}

export async function createConversation(title: string = "New Conversation"): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ title }),
  });
  return handleResponse<Conversation>(response);
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    headers: getAuthHeaders(),
  });
  return handleResponse<ConversationDetail>(response);
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!response.ok && response.status !== 204) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail || "Delete failed");
  }
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onSources: (sources: SourceChunk[]) => void;
  onMeta?: (meta: { conversation_id: string; sources: SourceChunk[] }) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

export async function streamChat(
  question: string,
  options: {
    conversationId?: string;
    documentIds?: string[];
  },
  callbacks: StreamCallbacks,
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: getAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      question,
      conversation_id: options.conversationId,
      document_ids: options.documentIds,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Chat request failed" }));
    callbacks.onError(body.detail || "Chat request failed");
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const eventBlock of events) {
      if (!eventBlock.trim()) continue;
      const lines = eventBlock.split("\n");
      let eventType = "";
      let rawData = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          rawData = line.slice(6);
        }
      }

      if (eventType && rawData !== "") {
        processSSEEvent(eventType, rawData, callbacks);
      }
    }
  }
}

function processSSEEvent(
  eventType: string,
  rawData: string,
  callbacks: StreamCallbacks,
): void {
  let parsedData: unknown;
  try {
    parsedData = JSON.parse(rawData);
  } catch {
    parsedData = rawData;
  }

  switch (eventType) {
    case "meta":
      if (callbacks.onMeta && typeof parsedData === "object" && parsedData !== null) {
        callbacks.onMeta(parsedData as { conversation_id: string; sources: SourceChunk[] });
      }
      break;
    case "sources":
      if (Array.isArray(parsedData)) {
        callbacks.onSources(parsedData as SourceChunk[]);
      }
      break;
    case "token":
      if (typeof parsedData === "string") {
        callbacks.onToken(parsedData);
      }
      break;
    case "done":
      callbacks.onDone();
      break;
    case "error":
      callbacks.onError(
        typeof parsedData === "object" && parsedData !== null && "detail" in parsedData
          ? String((parsedData as { detail: string }).detail)
          : String(parsedData),
      );
      break;
  }
}
