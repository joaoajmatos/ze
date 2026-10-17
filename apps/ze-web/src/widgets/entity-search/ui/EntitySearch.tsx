import type { WsScreenRef } from "@myguyze/ze-client";
import { useEffect, useState } from "react";
import { useSearchEntitiesQuery } from "@/entities/memory-graph";
import { ChatAboutChip, Module } from "@/shared/ui";

interface EntitySearchProps {
  onSelect: (entityId: string) => void;
  onChatAbout?: (ref: WsScreenRef, element: Element) => void;
}

export function EntitySearch({ onSelect, onChatAbout }: EntitySearchProps) {
  const [text, setText] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebounced(text.trim()), 250);
    return () => clearTimeout(id);
  }, [text]);

  const search = useSearchEntitiesQuery(debounced, undefined);
  const results = search.data ?? [];

  return (
    <Module label="Find an entity">
      <input
        type="search"
        className="text-field entity-search-box"
        aria-label="Search entities"
        placeholder="Ada, Lisbon, Project Atlas"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {debounced === "" && <p className="note">Search for a person, place or project to see what I know around it.</p>}
      {debounced !== "" && search.isError && <p className="note">Search failed. Try again.</p>}
      {debounced !== "" && !search.isError && !search.isFetching && results.length === 0 && (
        <p className="note">No entity named {debounced}</p>
      )}
      {results.length > 0 && (
        <ul className="belief-list">
          {results.map((r) => (
            <li key={r.id} className="row">
              <button type="button" className="ctl-text entity-hit" onClick={() => onSelect(r.id)}>
                <span className="t">{r.canonical_name}</span>
                <span className="s">
                  {r.entity_type} · <span className="ro">{r.degree}</span> {r.degree === 1 ? "connection" : "connections"}
                </span>
              </button>
              {onChatAbout && (
                <ChatAboutChip
                  label={r.canonical_name}
                  onClick={(chip) =>
                    onChatAbout({ kind: "entity", id: r.id, label: r.canonical_name, component: "entity_row" }, chip.closest("li") ?? chip)
                  }
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </Module>
  );
}
