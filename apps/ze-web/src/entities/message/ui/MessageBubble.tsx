import type { MessageSchema as Message, WsTraceUpdateFrame } from "@myguyze/ze-client";
import { Info } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { ConnectedPrimitiveTree } from "@/entities/primitive-tree";
import { useTraceStore } from "@/features/trace-state";
import { MessageTracePanel } from "@/widgets/message-trace";

type WorkspaceChipTrace = WsTraceUpdateFrame & {
  workspace?: {
    mode?: string;
    unavailable?: boolean;
    script_ran?: boolean;
    runs?: { command?: string; status?: string }[];
  } | null;
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({
  message,
  highlighted = false,
}: {
  message: Message;
  highlighted?: boolean;
}) {
  const isUser = message.role === "user";
  const [traceOpen, setTraceOpen] = useState(false);
  const workspace = useTraceStore((s) => {
    const match = s.traces.find((t) => t.message_id === message.id) as
      | WorkspaceChipTrace
      | undefined;
    return match?.workspace ?? null;
  });

  return (
    <div className={`flex ${isUser ? "justify-end" : "items-start gap-2"}`}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-plum-voltage/20 flex items-center justify-center flex-shrink-0 mt-1">
          <span className="text-[10px] text-plum-voltage font-semibold">Z</span>
        </div>
      )}

      <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {message.text && (
          <div className="group relative">
            <div
              className={`px-4 py-2.5 rounded-[20px] text-sm leading-relaxed space-y-2 ${
                isUser
                  ? "bg-plum-voltage text-foreground rounded-br-[6px]"
                  : "border border-foreground/[0.08] bg-foreground/[0.04] text-foreground rounded-bl-[6px]"
              } ${highlighted ? "ring-2 ring-amber-spark/70" : ""}`}
            >
              <ReactMarkdown
                components={{
                  p: ({ children }) => <p className="m-0">{children}</p>,
                  strong: ({ children }) => (
                    <strong className="font-semibold">{children}</strong>
                  ),
                  a: ({ children, href }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className={`underline underline-offset-2 ${
                        isUser ? "text-foreground" : "text-plum-voltage hover:text-plum-voltage/80"
                      }`}
                    >
                      {children}
                    </a>
                  ),
                  ul: ({ children }) => (
                    <ul className="m-0 list-disc space-y-1 pl-5">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="m-0 list-decimal space-y-1 pl-5">{children}</ol>
                  ),
                  li: ({ children }) => <li className="m-0">{children}</li>,
                  blockquote: ({ children }) => (
                    <blockquote className="my-1 border-l-2 border-foreground/20 pl-3 text-ash">
                      {children}
                    </blockquote>
                  ),
                  code: ({ children }) => (
                    <code className="bg-foreground/10 rounded px-1 py-0.5 text-xs font-mono">
                      {children}
                    </code>
                  ),
                  pre: ({ children }) => (
                    <pre className="bg-foreground/5 rounded-xl p-3 my-2 overflow-x-auto text-xs font-mono">
                      {children}
                    </pre>
                  ),
                }}
              >
                {message.text}
              </ReactMarkdown>
            </div>

            {!isUser && message.id !== "__streaming__" && (
              <button
                onClick={() => setTraceOpen(!traceOpen)}
                title="Why did Ze say this?"
                className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity w-5 h-5 rounded-full bg-foreground/[0.08] hover:bg-foreground/[0.15] flex items-center justify-center"
              >
                <Info className="w-3 h-3 text-smoke" />
              </button>
            )}
          </div>
        )}

        {!isUser && workspace && (() => {
          const stillRunning = (workspace.runs ?? []).find((r) => r.status === "in_progress");
          if (stillRunning) {
            return (
              <span
                data-testid="workspace-still-running-chip"
                className="mt-1 inline-flex w-fit items-center gap-1 rounded-full border border-amber-spark/40 bg-amber-spark/10 px-2 py-0.5 text-[10px] text-amber-spark"
              >
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-spark" />
                Still running · {stillRunning.command ?? "workspace run"}
              </span>
            );
          }
          return (
            <span
              data-testid="workspace-chip"
              className="mt-1 inline-flex w-fit items-center rounded-full border border-plum-voltage/40 bg-plum-voltage/10 px-2 py-0.5 text-[10px] text-plum-voltage"
            >
              Workspace · {workspace.unavailable ? "unavailable" : workspace.mode ?? "used"}
            </span>
          );
        })()}

        {message.components.length > 0 && (
          <div className="mt-2 flex w-full min-w-0 flex-col gap-2">
            <ConnectedPrimitiveTree components={message.components} />
          </div>
        )}

        {traceOpen && !isUser && message.id !== "__streaming__" && (
          <MessageTracePanel messageId={message.id} />
        )}

        <p className="mt-1 px-1 text-[10px] text-smoke">{formatTime(message.created_at)}</p>
      </div>
    </div>
  );
}
