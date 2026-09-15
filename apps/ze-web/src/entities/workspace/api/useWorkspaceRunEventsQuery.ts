import { useEffect, useState } from "react";
import { getConfig } from "@/shared/config";

export type WorkspaceRunEventsStatus = "streaming" | "closed" | "unavailable";

export interface WorkspaceRunEventsState {
  lines: string;
  lastSeq: number | null;
  status: WorkspaceRunEventsStatus;
  exitCode: number | null;
  looksBinary: boolean;
}

interface JournalEventLine {
  seq: number;
  type: "stdout" | "stderr" | "exit";
  data: string;
  exit_code?: number | null;
  timed_out?: boolean | null;
}

// A handful of decode-replacement chars is normal near a UTF-8 boundary split
// across chunks; a run of them signals genuinely non-text output (research.md R4).
const BINARY_REPLACEMENT_THRESHOLD = 3;

function initialState(): WorkspaceRunEventsState {
  return { lines: "", lastSeq: null, status: "streaming", exitCode: null, looksBinary: false };
}

/**
 * Opens GET /api/v0/workspace/runs/{runId}/events (Phase 129's existing NDJSON
 * watch stream) and accumulates it into a growing preview (Phase 131 FR-001/002).
 * Reused as-is by both the chat still-running chip and the workspace page banner
 * (FR-003 — one truth, two places). Does nothing when runId is null.
 */
export function useWorkspaceRunEventsQuery(runId: string | null): WorkspaceRunEventsState {
  const [state, setState] = useState<WorkspaceRunEventsState>(initialState);
  // Reset state during render when runId changes, rather than in the effect
  // body, per React's guidance for "adjusting state when a prop changes".
  const [trackedRunId, setTrackedRunId] = useState(runId);
  if (runId !== trackedRunId) {
    setTrackedRunId(runId);
    setState(initialState());
  }

  useEffect(() => {
    if (!runId) return;

    let cancelled = false;

    async function stream() {
      const cfg = getConfig();
      if (!cfg) {
        if (!cancelled) setState((s) => ({ ...s, status: "unavailable" }));
        return;
      }

      let sawExit = false;
      try {
        const res = await fetch(
          `${cfg.serverUrl.replace(/\/$/, "")}/api/v0/workspace/runs/${runId}/events`,
          { headers: { Authorization: `Bearer ${cfg.apiKey}` } },
        );
        if (!res.ok || !res.body) {
          if (!cancelled) setState((s) => ({ ...s, status: "unavailable" }));
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            if (!part.trim()) continue;
            let evt: JournalEventLine;
            try {
              evt = JSON.parse(part);
            } catch {
              continue;
            }

            if (evt.type === "exit") {
              sawExit = true;
            }

            setState((s) => {
              // Defends against an out-of-order or duplicate line; a single
              // open connection is already ordered, so this only guards
              // against a pathological re-emit rather than normal operation.
              if (s.lastSeq !== null && evt.seq <= s.lastSeq) return s;
              if (evt.type === "exit") {
                return {
                  ...s,
                  lastSeq: evt.seq,
                  status: "closed",
                  exitCode: evt.exit_code ?? null,
                };
              }
              const replacementCount = (evt.data.match(/�/g) ?? []).length;
              return {
                ...s,
                lines: s.lines + evt.data,
                lastSeq: evt.seq,
                looksBinary: s.looksBinary || replacementCount > BINARY_REPLACEMENT_THRESHOLD,
              };
            });
          }
        }
      } catch {
        if (!cancelled) setState((s) => ({ ...s, status: "unavailable" }));
        return;
      }

      if (!cancelled && !sawExit) {
        // Stream ended without an exit event — stay honest, do not invent
        // output (FR-010).
        setState((s) => (s.status === "closed" ? s : { ...s, status: "unavailable" }));
      }
    }

    stream();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  return state;
}
