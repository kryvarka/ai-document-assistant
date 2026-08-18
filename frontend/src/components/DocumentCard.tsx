import {
  AlertTriangle,
  File,
  FileCode,
  FileSpreadsheet,
  FileText,
  Loader2,
  Trash2,
} from "lucide-react";

import type { Document } from "../types";

interface DocumentCardProps {
  document: Document;
  onDelete: (id: string) => void;
}

function getFileIcon(fileType: string) {
  switch (fileType) {
    case ".pdf":
      return <FileText size={18} color="#ef4444" />;
    case ".docx":
      return <FileSpreadsheet size={18} color="#3b82f6" />;
    case ".md":
      return <FileCode size={18} color="#8b5cf6" />;
    case ".txt":
    default:
      return <File size={18} color="#10b981" />;
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentCard({ document, onDelete }: DocumentCardProps) {
  const typeClass = document.file_type.replace(".", "");
  const isProcessing = document.status === "processing";
  const hasFailed = document.status === "failed";

  return (
    <div className={`document-card ${document.status}`}>
      <div className="document-card-main">
        <div className={`document-card-icon ${typeClass}`}>
          {getFileIcon(document.file_type)}
        </div>
        <div className="document-card-info">
          <div className="document-card-name" title={document.filename}>
            {document.filename}
          </div>
          <div className="document-card-meta">
            <span>{formatFileSize(document.file_size_bytes)}</span>
            <span>·</span>
            {isProcessing ? (
              <span className="document-card-status processing">
                <Loader2 size={11} className="spin" />
                Indexing…
              </span>
            ) : hasFailed ? (
              <span
                className="document-card-status failed"
                title={document.error_message ?? "Indexing failed"}
              >
                <AlertTriangle size={11} />
                Failed
              </span>
            ) : (
              <span>{document.chunk_count} chunks</span>
            )}
          </div>
        </div>
      </div>
      <button
        type="button"
        className="document-card-delete"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(document.id);
        }}
        title="Delete document"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}
