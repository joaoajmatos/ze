import type { MemoryFeedItem } from "@myguyze/ze-client";
import { useMemo, useState } from "react";
import {
  BeliefRow,
  useMemoryFeedQuery,
  useMemoryTimelineBoundsQuery,
  useReviewFactMutation,
} from "@/entities/memory-feed-item";
import { Chip, Control, Module } from "@/shared/ui";

const FILTERS = { type: "all" } as const;
const EMPTY = "I have not learned anything yet. Tell me about yourself or connect Gmail.";

function dateLabel(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function EpisodeRow({ item }: { item: MemoryFeedItem }) {
  return (
    <li className="row episode">
      <span className="t">{item.summary ?? item.prompt_snippet ?? "An earlier conversation"}</span>
      <span className="s">
        <Chip kind="dotted">episode</Chip> {item.agent.replace(/[_-]+/g, " ")} ·{" "}
        {new Date(item.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
      </span>
    </li>
  );
}

export function BeliefsFeed({ onChatAbout }: { onChatAbout?: (element: Element) => void }) {
  const [asOfDate, setAsOfDate] = useState<string | null>(null);
  const asOf = asOfDate ? new Date(`${asOfDate}T23:59:59`).toISOString() : undefined;
  const feed = useMemoryFeedQuery(FILTERS, asOf);
  const bounds = useMemoryTimelineBoundsQuery();
  const review = useReviewFactMutation(FILTERS);

  const items = useMemo(() => feed.data?.pages.flatMap((p) => p.items) ?? [], [feed.data]);
  const totals = feed.data?.pages[0];

  return (
    <Module label="Beliefs" onChatAbout={onChatAbout} chatAboutLabel="my beliefs">
      <div className="belief-asof">
        <label className="lbl" htmlFor="beliefs-as-of">As of</label>
        <input
          id="beliefs-as-of"
          type="date"
          className="text-field"
          value={asOfDate ?? ""}
          min={bounds.data?.earliest?.slice(0, 10)}
          max={bounds.data?.latest.slice(0, 10)}
          onChange={(e) => setAsOfDate(e.target.value || null)}
        />
        {asOfDate && <Control onClick={() => setAsOfDate(null)}>Now</Control>}
        <p className="ro" aria-live="polite">
          {asOfDate ? `As of ${dateLabel(asOfDate)} · kinds and confidence as of now` : "Showing now"}
        </p>
      </div>

      {feed.isLoading && <p role="status" className="note">Reading what I know…</p>}
      {feed.isError && (
        <p className="note">
          Could not load my beliefs. <Control onClick={() => void feed.refetch()}>Retry</Control>
        </p>
      )}
      {!feed.isLoading && !feed.isError && items.length === 0 && <p className="note">{EMPTY}</p>}

      {items.length > 0 && (
        <>
          {totals?.total_facts != null && totals.total_episodes != null && (
            <p className="note">
              <span className="ro">{totals.total_facts}</span> beliefs · <span className="ro">{totals.total_episodes}</span> episodes
            </p>
          )}
          <ul className="belief-list">
            {items.map((item) =>
              item.type === "fact" ? (
                <BeliefRow
                  key={item.id}
                  item={item}
                  busy={review.isPending}
                  onKeep={() => review.mutate({ actions: [{ id: item.id, action: "confirm" }] })}
                  onDrop={() => review.mutate({ actions: [{ id: item.id, action: "reject" }] })}
                  onEdit={(value) => review.mutate({ actions: [{ id: item.id, action: "edit", value }] })}
                />
              ) : (
                <EpisodeRow key={item.id} item={item} />
              ),
            )}
          </ul>
          {feed.hasNextPage && (
            <Control disabled={feed.isFetchingNextPage} onClick={() => void feed.fetchNextPage()}>
              {feed.isFetchingNextPage ? "Loading…" : "Earlier beliefs"}
            </Control>
          )}
        </>
      )}
    </Module>
  );
}
