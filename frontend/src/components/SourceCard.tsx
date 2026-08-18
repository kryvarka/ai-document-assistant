import { ChevronDown, ChevronUp, Paperclip } from "lucide-react";
import { useState } from "react";

import type { SourceChunk } from "../types";

interface SourceCardProps {
  source: SourceChunk;
  index: number;
}

export function SourceCard({ source, index }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);
  const scorePercent = Math.round(source.relevance_score * 100);

  return (
    <div className="source-card-wrapper">
      <button
        type="button"
        className="source-card"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        title={`Source ${index} — chunk ${source.chunk_index} of ${source.document_name}`}
      >
        <span className="source-card-index">{index}</span>
        <Paperclip size={13} className="source-card-icon" />
        <span className="source-card-name">{source.document_name}</span>
        <span className="source-card-chunk">chunk {source.chunk_index}</span>
        <span className="source-card-score">{scorePercent}%</span>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {expanded && <div className="source-card-expanded">{source.content}</div>}
    </div>
  );
}
