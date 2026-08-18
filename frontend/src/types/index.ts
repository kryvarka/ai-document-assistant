export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export type DocumentStatus = "processing" | "ready" | "failed";

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  chunk_count: number;
  status: DocumentStatus;
  error_message?: string | null;
  created_at: string;
  file_size_bytes: number;
  user_id?: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface SourceChunk {
  content: string;
  document_name: string;
  chunk_index: number;
  relevance_score: number;
}

export interface Conversation {
  id: string;
  title: string;
  user_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  user_id?: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface ChatRequest {
  question: string;
  conversation_id?: string;
  user_id?: string;
  document_ids?: string[];
}

export interface ChatResponse {
  answer: string;
  sources: SourceChunk[];
  model: string;
  conversation_id?: string;
  message_id?: string;
}

export interface Message {
  id: string;
  conversation_id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  isStreaming?: boolean;
}
