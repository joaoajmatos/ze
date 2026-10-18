import type { SessionSchema, SessionSearchResult } from "@myguyze/ze-client";
import { useEffect, useRef, useState } from "react";
import { formatRelative, useSession, useSessionSearchQuery, useSessionsQuery } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { Control, Module } from "@/shared/ui";

const SEARCH_DELAY_MS = 300;

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

const asSession = (r: SessionSearchResult): SessionSchema => ({
  id: r.id, title: r.title, preview: r.preview, title_source: r.title_source, created_at: r.created_at, last_active_at: r.last_active_at,
});

const plain = (snippet: string) => snippet.replace(/<\/?b>/g, "");

interface ItemProps {
  session: SessionSchema;
  active: boolean;
  onSelect: () => void;
  snippet?: string | null;
}

function Item({ session, active, onSelect, snippet }: ItemProps) {
  const label = session.title ?? session.preview ?? "Untitled chat";
  const thinking = useWsStore((s) => s.thinkingThreads[session.id] ?? false);
  const attention = useWsStore((s) => s.attentionThreads[session.id] ?? false);
  const flag = thinking ? `${label} is replying` : attention ? `${label} has a new reply` : null;
  return (
    <div className={`row ${active ? "focused" : ""}`}>
      <button type="button" className="t ctl-text" style={{ minHeight: 44, display: "block" }} onClick={onSelect} aria-current={active ? "true" : undefined}>
        {label}
      </button>
      <span className="ro">
        {flag && (
          <span role="img" aria-label={flag} className={thinking ? "" : "hot"}>
            ●{" "}
          </span>
        )}
        {formatRelative(session.last_active_at)}
      </span>
      {(snippet ?? session.preview) && session.preview !== label && <span className="s">{snippet ? plain(snippet) : session.preview}</span>}
    </div>
  );
}

/** Past conversations: browse or search, pick one, or start a new chat. */
export function SessionsRail() {
  const threadId = useSession((s) => s.threadId);
  const selectSession = useSession((s) => s.selectSession);
  const newSession = useSession((s) => s.newSession);
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query, SEARCH_DELAY_MS);
  const searching = debounced.trim().length >= 2;
  const more = useRef<HTMLDivElement>(null);

  const browse = useSessionsQuery();
  const search = useSessionSearchQuery(debounced);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = browse;

  useEffect(() => {
    const node = more.current;
    if (searching || !node || !hasNextPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isFetchingNextPage) void fetchNextPage();
      },
      { rootMargin: "120px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [searching, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const sessions = browse.data?.pages.flatMap((p) => p.items) ?? [];
  const results = search.data ?? [];
  const loading = searching ? search.isLoading : browse.isLoading;
  const failed = searching ? search.isError : browse.isError;

  return (
    <Module label="Conversations" as="section" className="sessions-rail">
      <Control primary onClick={() => newSession()}>
        New chat
      </Control>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search conversations…"
        aria-label="Search conversations"
        style={{ minHeight: 44, width: "100%", background: "transparent", color: "var(--ink)", border: "1px solid var(--hair)", padding: "0 14px", font: "inherit" }}
      />
      {failed ? (
        <p className="hot" role="alert">
          Couldn't read your conversations.
        </p>
      ) : loading ? (
        <p className="muted">Reading…</p>
      ) : searching ? (
        results.length === 0 ? (
          <p className="muted">No conversations found.</p>
        ) : (
          results.map((r) => (
            <Item key={r.id} session={asSession(r)} active={r.id === threadId} onSelect={() => selectSession(r.id)} snippet={r.snippet} />
          ))
        )
      ) : sessions.length === 0 ? (
        <p className="muted">No past sessions yet.</p>
      ) : (
        sessions.map((s) => <Item key={s.id} session={s} active={s.id === threadId} onSelect={() => selectSession(s.id)} />)
      )}
      {!searching && hasNextPage && (
        <div ref={more} className="muted">
          {isFetchingNextPage ? "Loading more…" : null}
        </div>
      )}
    </Module>
  );
}
