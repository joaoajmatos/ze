import type { GoalListItem, WsScreenContext } from "@myguyze/ze-client";
import { useEffect } from "react";
import { useAskOverlay } from "@/features/ask-bar";
import { useGoalsQuery } from "@/entities/goal";
import type { UiContribution } from "@/entities/ui-manifest";
import { CommandChip } from "@/shared/ui";

interface Props {
  /** The page wires this to the send path; the chips pass the preset's context. */
  onSend: (text: string, context: WsScreenContext) => boolean;
  disabled?: boolean;
  /** Plugin presets from the manifest; the first two follow the core chips. */
  presets?: UiContribution[];
}

const MAX_PRESETS = 2;

interface Chip {
  id: string;
  text: string;
  context: WsScreenContext;
}

const touched = (g: GoalListItem) => Date.parse(g.last_progress_at ?? g.created_at);

function activeGoal(goals: GoalListItem[]): GoalListItem | null {
  return goals.filter((g) => g.status === "active").reduce<GoalListItem | null>((best, g) => (best && touched(best) >= touched(g) ? best : g), null);
}

const dialogOpen = () => document.querySelector('[role="dialog"], [aria-modal="true"], dialog[open]') !== null;

const typing = (el: Element | null) =>
  el instanceof HTMLElement && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);

/** Suggested questions, plus up to two from plugins. Keys 1-9 send them while the Ask bar is empty and unfocused. */
export function TryChips({ onSend, disabled = false, presets = [] }: Props) {
  const barEmpty = useAskOverlay((s) => s.draft.trim() === "");
  const { data: goals = [] } = useGoalsQuery();
  const goal = activeGoal(goals);

  const chips: Chip[] = [
    { id: "core.slipping", text: "What's slipping?", context: { origin: "preset", compose: "slipping" } },
    { id: "core.decisions", text: "What should I decide today?", context: { origin: "preset", compose: "decisions" } },
    ...(goal ? [{ id: "core.goal", text: `How is ${goal.title} going?`, context: { origin: "preset", topic: goal.title } satisfies WsScreenContext }] : []),
    ...presets.slice(0, MAX_PRESETS).map((p): Chip => ({ id: p.id, text: p.prompt ?? p.label, context: { origin: "preset" } })),
  ];

  useEffect(() => {
    if (disabled || !barEmpty) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented || typing(document.activeElement) || dialogOpen()) return;
      const chip = chips[Number(e.key) - 1];
      if (!chip) return;
      e.preventDefault();
      onSend(chip.text, chip.context);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="chips" role="group" aria-label="Try asking">
      {chips.map((chip, i) => (
        <CommandChip key={chip.id} index={String(i + 1)} keyHint={String(i + 1)} disabled={disabled} onClick={() => onSend(chip.text, chip.context)}>
          {chip.text}
        </CommandChip>
      ))}
    </div>
  );
}
