import { useFrame } from "@/shared/api";
import { useTraceStore } from "./useTraceStore";

export function useTraceSocket() {
  const mergePartialTrace = useTraceStore((s) => s.mergePartialTrace);
  const commitPendingTrace = useTraceStore((s) => s.commitPendingTrace);

  useFrame("trace_update", (frame) => {
    if (!frame.thread_id) return;
    if (frame.partial) {
      mergePartialTrace(frame);
    } else {
      commitPendingTrace(frame);
    }
  });
}
