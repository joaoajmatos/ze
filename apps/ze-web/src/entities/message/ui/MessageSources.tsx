import type { SourceTraceResponse } from "@myguyze/ze-client";
import { sourceHostname } from "../lib/format";

export function MessageSources({ sources }: { sources: SourceTraceResponse[] }) {
  if (sources.length === 0) return null;
  return (
    <section
      aria-label="Sources"
      data-testid="message-sources"
      className="mt-2 w-full min-w-0 px-1"
    >
      <h3 className="text-[10px] font-medium uppercase tracking-wide text-smoke">Sources</h3>
      <ul className="m-0 mt-1 flex list-none flex-col gap-1 p-0">
        {sources.map((source) => {
          const host = sourceHostname(source.url);
          return (
            <li key={source.url} className="flex min-w-0 items-baseline gap-2 text-xs">
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-0 truncate text-plum-voltage underline underline-offset-2 hover:text-plum-voltage/80"
              >
                {source.title?.trim() || host}
              </a>
              {source.title?.trim() && (
                <span className="flex-shrink-0 text-[10px] text-smoke">{host}</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
