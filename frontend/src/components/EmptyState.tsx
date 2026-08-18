import { BookOpen, MessageSquareText, Sparkles } from "lucide-react";

interface EmptyStateProps {
  hasDocuments: boolean;
  onSuggestionClick: (question: string) => void;
}

const SUGGESTIONS = [
  "What are the main topics covered in my documents?",
  "Summarize the key points from the uploaded files",
  "What conclusions or recommendations are mentioned?",
  "Are there any action items or next steps?",
];

export function EmptyState({ hasDocuments, onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon-wrapper">
        {hasDocuments ? (
          <MessageSquareText size={48} color="var(--color-accent)" />
        ) : (
          <BookOpen size={48} color="var(--color-accent)" />
        )}
      </div>
      <div className="empty-state-title">
        {hasDocuments ? "Ask about your documents" : "Upload documents to begin"}
      </div>
      <div className="empty-state-subtitle">
        {hasDocuments
          ? "Your documents are indexed and ready. Ask any question to get precise answers with source citations."
          : "Upload PDF, TXT, DOCX, or Markdown files using the sidebar. The system will index and embed them for AI search."}
      </div>
      {hasDocuments && (
        <div className="empty-state-hints">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="empty-state-hint"
              onClick={() => onSuggestionClick(s)}
            >
              <Sparkles size={12} style={{ marginRight: 6, display: "inline-block", verticalAlign: "middle" }} />
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
