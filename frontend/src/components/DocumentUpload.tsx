import { Loader2, UploadCloud } from "lucide-react";
import { useCallback, useRef, useState } from "react";

interface DocumentUploadProps {
  onUpload: (file: File) => Promise<unknown>;
  isUploading: boolean;
}

export function DocumentUpload({ onUpload, isUploading }: DocumentUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      onUpload(file);
    },
    [onUpload],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      if (inputRef.current) inputRef.current.value = "";
    },
    [handleFile],
  );

  return (
    <div
      className={`upload-zone ${isDragOver ? "drag-over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.docx,.md"
        onChange={handleChange}
        style={{ display: "none" }}
      />
      {isUploading ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
          <Loader2 className="upload-zone-icon-spinner" size={28} />
          <div className="upload-zone-text">Uploading…</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px" }}>
          <UploadCloud size={30} style={{ color: "var(--color-accent)", opacity: 0.9 }} />
          <div className="upload-zone-text">
            <strong>Drop a file</strong> or click to upload
          </div>
          <div className="upload-zone-formats">PDF, TXT, DOCX, MD — up to 20MB</div>
        </div>
      )}
    </div>
  );
}
