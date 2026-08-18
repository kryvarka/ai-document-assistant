import { beforeEach, describe, expect, it, vi } from "vitest";

import { setAuthToken, streamChat } from "./client";
import type { SourceChunk } from "../types";

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function mockStream(wire: string, sliceSize = 7): void {
  const bytes = new TextEncoder().encode(wire);
  let offset = 0;

  const reader = {
    read: async () => {
      if (offset >= bytes.length) return { done: true, value: undefined };
      const value = bytes.slice(offset, offset + sliceSize);
      offset += sliceSize;
      return { done: false, value };
    },
  };

  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => reader },
    }),
  );
}

function collect() {
  const tokens: string[] = [];
  let sources: SourceChunk[] = [];
  let done = false;
  let error: string | null = null;
  let meta: { conversation_id: string } | null = null;

  return {
    tokens,
    get text() {
      return tokens.join("");
    },
    get sources() {
      return sources;
    },
    get done() {
      return done;
    },
    get error() {
      return error;
    },
    get meta() {
      return meta;
    },
    callbacks: {
      onToken: (t: string) => tokens.push(t),
      onSources: (s: SourceChunk[]) => (sources = s),
      onMeta: (m: { conversation_id: string }) => (meta = m),
      onDone: () => (done = true),
      onError: (e: string) => (error = e),
    },
  };
}

describe("streamChat SSE parsing", () => {
  beforeEach(() => {
    setAuthToken("test-token");
    vi.unstubAllGlobals();
  });

  it("preserves newlines, blank lines and markdown structure", async () => {
    const chunks = [
      "Here are the findings:\n\n",
      "- **First** point\n",
      "- Second point\n\n",
      "```python\nx = 1\n```\n",
      "Done.",
    ];
    mockStream(chunks.map((c) => sse("token", c)).join("") + sse("done", {}));

    const sink = collect();
    await streamChat("q", {}, sink.callbacks);

    expect(sink.text).toBe(chunks.join(""));
    expect(sink.text).toContain("\n\n");
    expect(sink.done).toBe(true);
  });

  it("survives events split across network chunk boundaries", async () => {
    const chunks = ["alpha\n", "beta\n", "gamma"];
    mockStream(chunks.map((c) => sse("token", c)).join("") + sse("done", {}), 1);

    const sink = collect();
    await streamChat("q", {}, sink.callbacks);

    expect(sink.text).toBe("alpha\nbeta\ngamma");
    expect(sink.done).toBe(true);
  });

  it("delivers meta and sources before tokens", async () => {
    const sources: SourceChunk[] = [
      { content: "chunk", document_name: "a.pdf", chunk_index: 0, relevance_score: 0.9 },
    ];
    mockStream(
      sse("meta", { conversation_id: "conv_1", sources }) +
        sse("sources", sources) +
        sse("token", "hi") +
        sse("done", {}),
    );

    const sink = collect();
    await streamChat("q", {}, sink.callbacks);

    expect(sink.meta?.conversation_id).toBe("conv_1");
    expect(sink.sources).toHaveLength(1);
    expect(sink.sources[0].document_name).toBe("a.pdf");
  });

  it("surfaces a server-sent error event", async () => {
    mockStream(sse("error", { detail: "upstream exploded" }));

    const sink = collect();
    await streamChat("q", {}, sink.callbacks);

    expect(sink.error).toBe("upstream exploded");
    expect(sink.done).toBe(false);
  });

  it("reports a failed request without starting a stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Rate limit exceeded. Retry in 30s." }),
      }),
    );

    const sink = collect();
    await streamChat("q", {}, sink.callbacks);

    expect(sink.error).toBe("Rate limit exceeded. Retry in 30s.");
  });

  it("sends the bearer token and conversation id", async () => {
    mockStream(sse("done", {}));

    await streamChat("my question", { conversationId: "conv_9" }, collect().callbacks);

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer test-token");
    expect(JSON.parse(init.body)).toMatchObject({
      question: "my question",
      conversation_id: "conv_9",
    });
  });
});
