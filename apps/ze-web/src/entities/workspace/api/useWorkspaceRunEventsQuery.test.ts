import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWorkspaceRunEventsQuery } from "./useWorkspaceRunEventsQuery";

vi.mock("@/shared/config", () => ({
  getConfig: () => ({ serverUrl: "http://localhost:8000", apiKey: "test-key" }),
}));

function ndjsonResponse(lines: string[], opts?: { ok?: boolean; body?: boolean }): Response {
  if (opts?.ok === false) {
    return { ok: false, body: null } as unknown as Response;
  }
  if (opts?.body === false) {
    return { ok: true, body: null } as unknown as Response;
  }
  const text = lines.map((l) => l + "\n").join("");
  const bytes = new TextEncoder().encode(text);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
  return { ok: true, body: stream } as unknown as Response;
}

describe("useWorkspaceRunEventsQuery", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does nothing when runId is null", () => {
    const { result } = renderHook(() => useWorkspaceRunEventsQuery(null));
    expect(result.current).toEqual({
      lines: "",
      lastSeq: null,
      status: "streaming",
      exitCode: null,
      looksBinary: false,
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("accumulates stdout/stderr lines in seq order and closes on exit", async () => {
    vi.mocked(fetch).mockResolvedValue(
      ndjsonResponse([
        JSON.stringify({ seq: 0, type: "stdout", data: "line one\n" }),
        JSON.stringify({ seq: 1, type: "stderr", data: "line two\n" }),
        JSON.stringify({ seq: 2, type: "exit", data: "", exit_code: 0, timed_out: false }),
      ]),
    );

    const { result } = renderHook(() => useWorkspaceRunEventsQuery("run-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("closed");
    });

    expect(result.current.lines).toBe("line one\nline two\n");
    expect(result.current.exitCode).toBe(0);
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v0/workspace/runs/run-1/events",
      { headers: { Authorization: "Bearer test-key" } },
    );
  });

  it("does not stack a duplicate prefix on a fresh mount for the same run", async () => {
    const lines = [
      JSON.stringify({ seq: 0, type: "stdout", data: "hello\n" }),
      JSON.stringify({ seq: 1, type: "exit", data: "", exit_code: 0, timed_out: false }),
    ];
    // A fresh Response/ReadableStream per call — a real fetch() would never
    // hand back an already-consumed stream to a second connection.
    vi.mocked(fetch).mockImplementation(() => Promise.resolve(ndjsonResponse(lines)));

    const first = renderHook(() => useWorkspaceRunEventsQuery("run-1"));
    await waitFor(() => expect(first.result.current.status).toBe("closed"));
    expect(first.result.current.lines).toBe("hello\n");
    first.unmount();

    const second = renderHook(() => useWorkspaceRunEventsQuery("run-1"));
    await waitFor(() => expect(second.result.current.status).toBe("closed"));
    expect(second.result.current.lines).toBe("hello\n");
  });

  it("reports unavailable when the stream ends without an exit event", async () => {
    vi.mocked(fetch).mockResolvedValue(
      ndjsonResponse([JSON.stringify({ seq: 0, type: "stdout", data: "partial\n" })]),
    );

    const { result } = renderHook(() => useWorkspaceRunEventsQuery("run-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("unavailable");
    });
    expect(result.current.lines).toBe("partial\n");
  });

  it("reports unavailable when the fetch itself fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useWorkspaceRunEventsQuery("run-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("unavailable");
    });
  });

  it("reports unavailable when the response has no body", async () => {
    vi.mocked(fetch).mockResolvedValue(ndjsonResponse([], { body: false }));

    const { result } = renderHook(() => useWorkspaceRunEventsQuery("run-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("unavailable");
    });
  });

  it("flags looksBinary when a run of replacement characters appears", async () => {
    vi.mocked(fetch).mockResolvedValue(
      ndjsonResponse([
        JSON.stringify({ seq: 0, type: "stdout", data: "����" }),
        JSON.stringify({ seq: 1, type: "exit", data: "", exit_code: 0, timed_out: false }),
      ]),
    );

    const { result } = renderHook(() => useWorkspaceRunEventsQuery("run-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("closed");
    });
    expect(result.current.looksBinary).toBe(true);
  });
});
