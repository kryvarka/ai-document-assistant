import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import type { Document } from "../types";
import { useDocuments } from "./useDocuments";

function doc(overrides: Partial<Document> = {}): Document {
  return {
    id: "d1",
    filename: "notes.md",
    file_type: ".md",
    chunk_count: 0,
    status: "processing",
    created_at: new Date().toISOString(),
    file_size_bytes: 100,
    ...overrides,
  };
}

describe("useDocuments", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("polls while a document is still indexing and stops once it settles", async () => {
    const list = vi
      .spyOn(client, "listDocuments")
      .mockResolvedValueOnce({ documents: [doc()], total: 1 })
      .mockResolvedValue({
        documents: [doc({ status: "ready", chunk_count: 7 })],
        total: 1,
      });

    const { result } = renderHook(() => useDocuments(true));

    await waitFor(() => expect(result.current.documents[0].status).toBe("processing"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });

    await waitFor(() => expect(result.current.documents[0].status).toBe("ready"));

    const callsAfterSettling = list.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(list.mock.calls.length).toBe(callsAfterSettling);
  });

  it("reports the document that finished indexing", async () => {
    vi.spyOn(client, "listDocuments")
      .mockResolvedValueOnce({ documents: [doc()], total: 1 })
      .mockResolvedValue({
        documents: [doc({ status: "ready", chunk_count: 7 })],
        total: 1,
      });

    const { result } = renderHook(() => useDocuments(true));

    await waitFor(() => expect(result.current.documents[0].status).toBe("processing"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });

    await waitFor(() => expect(result.current.justSettled?.status).toBe("ready"));
    expect(result.current.justSettled?.chunk_count).toBe(7);

    act(() => result.current.acknowledgeSettled());
    expect(result.current.justSettled).toBeNull();
  });

  it("reports a failed ingestion with its reason", async () => {
    vi.spyOn(client, "listDocuments")
      .mockResolvedValueOnce({ documents: [doc()], total: 1 })
      .mockResolvedValue({
        documents: [doc({ status: "failed", error_message: "No extractable text" })],
        total: 1,
      });

    const { result } = renderHook(() => useDocuments(true));

    await waitFor(() => expect(result.current.documents[0].status).toBe("processing"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });

    await waitFor(() => expect(result.current.justSettled?.status).toBe("failed"));
    expect(result.current.justSettled?.error_message).toBe("No extractable text");
  });

  it("does not fetch anything while signed out", async () => {
    const list = vi.spyOn(client, "listDocuments");

    const { result } = renderHook(() => useDocuments(false));

    await waitFor(() => expect(result.current.documents).toEqual([]));
    expect(list).not.toHaveBeenCalled();
  });

  it("surfaces an upload failure through error state", async () => {
    vi.spyOn(client, "listDocuments").mockResolvedValue({ documents: [], total: 0 });
    vi.spyOn(client, "uploadDocument").mockRejectedValue(new Error("File too large"));

    const { result } = renderHook(() => useDocuments(true));
    await waitFor(() => expect(result.current.documents).toEqual([]));

    let thrown: unknown;
    await act(async () => {
      try {
        await result.current.upload(new File(["x"], "big.pdf"));
      } catch (err) {
        thrown = err;
      }
    });

    expect((thrown as Error).message).toBe("File too large");
    expect(result.current.error).toBe("File too large");

    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
  });
});
