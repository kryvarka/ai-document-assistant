import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Message } from "../types";
import { MessageBubble } from "./MessageBubble";

function message(overrides: Partial<Message> = {}): Message {
  return { id: "m1", role: "assistant", content: "", ...overrides };
}

describe("MessageBubble", () => {
  it("renders markdown structure rather than raw syntax", () => {
    render(
      <MessageBubble
        message={message({
          content: "Findings:\n\n- **First** item\n- Second item\n\n`code()`",
        })}
      />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("First").tagName).toBe("STRONG");
    expect(screen.getByText("code()").tagName).toBe("CODE");
  });

  it("renders GFM tables", () => {
    render(
      <MessageBubble
        message={message({
          content: "| Metric | Value |\n| --- | --- |\n| TTFT | 185ms |",
        })}
      />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "185ms" })).toBeInTheDocument();
  });

  it("does not execute HTML embedded in model output", () => {
    const { container } = render(
      <MessageBubble
        message={message({
          content: '<img src=x onerror="alert(1)"><script>alert(2)</script> safe text',
        })}
      />,
    );

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("safe text");
  });

  it("shows a typing indicator while streaming with no content yet", () => {
    const { container } = render(
      <MessageBubble message={message({ content: "", isStreaming: true })} />,
    );

    expect(container.querySelector(".typing-indicator")).not.toBeNull();
  });

  it("numbers sources so citations in the answer can be matched to cards", () => {
    const sources = [
      { content: "first", document_name: "spec.pdf", chunk_index: 4, relevance_score: 0.66 },
      { content: "second", document_name: "spec.pdf", chunk_index: 7, relevance_score: 0.65 },
      { content: "third", document_name: "spec.pdf", chunk_index: 9, relevance_score: 0.61 },
    ];

    render(
      <MessageBubble
        message={message({ content: "See [Source 2].", isStreaming: false, sources })}
      />,
    );

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("chunk 4")).toBeInTheDocument();
    expect(screen.getByText("chunk 7")).toBeInTheDocument();
    expect(screen.getByText("chunk 9")).toBeInTheDocument();
    expect(screen.getAllByText("spec.pdf")).toHaveLength(3);
  });

  it("expands a source to reveal its chunk text", async () => {
    const user = userEvent.setup();
    const sources = [
      { content: "the underlying chunk text", document_name: "spec.pdf", chunk_index: 4, relevance_score: 0.66 },
    ];

    render(<MessageBubble message={message({ content: "answer", sources })} />);

    expect(screen.queryByText("the underlying chunk text")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /spec\.pdf/ }));
    expect(screen.getByText("the underlying chunk text")).toBeInTheDocument();
  });

  it("hides sources until the stream finishes", () => {
    const sources = [
      { content: "c", document_name: "spec.pdf", chunk_index: 0, relevance_score: 0.91 },
    ];

    const { rerender, container } = render(
      <MessageBubble message={message({ content: "partial", isStreaming: true, sources })} />,
    );
    expect(container.querySelector(".message-sources")).toBeNull();

    rerender(
      <MessageBubble message={message({ content: "complete", isStreaming: false, sources })} />,
    );
    expect(screen.getByText("spec.pdf")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
  });

  it("labels user and assistant turns distinctly", () => {
    const { rerender } = render(<MessageBubble message={message({ role: "user", content: "hi" })} />);
    expect(screen.getByText("You")).toBeInTheDocument();

    rerender(<MessageBubble message={message({ role: "assistant", content: "hello" })} />);
    expect(screen.getByText("DocQA")).toBeInTheDocument();
  });
});
