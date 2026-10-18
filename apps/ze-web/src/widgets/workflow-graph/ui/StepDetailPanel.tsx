import ReactMarkdown from "react-markdown";
import { formatDurationMs, type WorkflowGraphNode } from "@/entities/workflow";
import { STEP_STATE_WORD } from "./StepNode";

const markdownComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => <p className="md-head">{children}</p>,
  h2: ({ children }: { children?: React.ReactNode }) => <p className="md-head">{children}</p>,
  h3: ({ children }: { children?: React.ReactNode }) => <p className="md-head">{children}</p>,
  p: ({ children }: { children?: React.ReactNode }) => <p>{children}</p>,
  code: ({ children }: { children?: React.ReactNode }) => <code>{children}</code>,
};

interface Props {
  node: WorkflowGraphNode;
  executionError: string | null;
  onClose: () => void;
}

/** A step's details. The step's own error is program output, so it sits in the verbatim mono box. */
export function StepDetailPanel({ node, executionError, onClose }: Props) {
  const { step, state, result } = node;
  const showInferred = state === "failed-inferred" && executionError && !result?.error;
  const failed = state === "completed-fail" || state === "failed-inferred";
  const verbatim = result?.error ?? (showInferred ? executionError : null);

  return (
    <aside className={`step-detail ${failed ? "hot" : ""}`} aria-label="Step details">
      <header className="step-detail-head">
        <div>
          <p className="t">{step.task}</p>
          <p className="s">
            {STEP_STATE_WORD[state]}
            {result && ` · ${formatDurationMs(result.duration_ms)}`}
            {result?.attempt_count != null && result.attempt_count > 1 && ` · ${result.attempt_count} attempts`}
            {result?.no_results && " · nothing new"}
          </p>
        </div>
        <button type="button" className="ctl" onClick={onClose} aria-label="Close step details">
          Close
        </button>
      </header>
      {step.agent_hint && (
        <section>
          <h3 className="lbl">Agent</h3>
          <p>{step.agent_hint}</p>
        </section>
      )}
      {step.verify && (
        <section>
          <h3 className="lbl">Check</h3>
          <p className="run-command">{step.verify}</p>
        </section>
      )}
      {result?.output && (
        <section>
          <h3 className="lbl">Output</h3>
          <div className="step-output">
            <ReactMarkdown components={markdownComponents}>{result.output}</ReactMarkdown>
          </div>
        </section>
      )}
      {failed && (
        <section>
          <h3 className="lbl">What went wrong</h3>
          <p className="hot">This step failed.</p>
          {verbatim && <pre className="run-output">{verbatim}</pre>}
        </section>
      )}
      {!step.agent_hint && !step.verify && !result?.output && !failed && <p className="muted">No details for this step yet.</p>}
    </aside>
  );
}
