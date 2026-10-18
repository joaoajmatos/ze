import type { SourceTraceResponse } from "@myguyze/ze-client";
import { sourceHostname } from "../../../lib/source-host";
import { TraceRow } from "./TraceRow";

export function SourcesRow({ sources }: { sources: SourceTraceResponse[] }) {
  if (sources.length === 0) return null;
  return (
    <TraceRow title="Sources" count={sources.length}>
      <ul className="tr-list" data-testid="message-sources">
        {sources.map((source) => {
          const host = sourceHostname(source.url);
          return (
            <li key={source.url}>
              <a href={source.url} target="_blank" rel="noopener noreferrer">
                {source.title?.trim() || host}
              </a>
              {source.title?.trim() && <span className="ro muted">{host}</span>}
            </li>
          );
        })}
      </ul>
    </TraceRow>
  );
}
