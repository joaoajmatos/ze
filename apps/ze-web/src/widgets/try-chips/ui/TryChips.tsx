import type { GoalListItem, WsScreenContext } from "@myguyze/ze-client";
import { useEffect } from "react";
import { useAskOverlay } from "@/features/ask-bar";
import { useGoalsQuery } from "@/entities/goal";
import { CommandChip } from "@/shared/ui";

interface Props {
  /** The page wires this to the send path; the chips pass the preset's context. */
  onSend: (text: string, context: WsScreenContext) => boolean;
  disabled?: boolean;
}

interface Chip {
  text: string;
  context: WsScreenContext;
}

const touched = (g: GoalListItem) => Date.parse(g.last_progress_at ?? g.created_at);

function activeGoal(goals: GoalListItem[]): GoalListItem | null {
  return goals.filter((g) => g.status === "active").reduce<GoalListItem | null>((best, g) => (best && touched(best) >= touched(g) ? best : g), null);
}

const typing = (el: Element | null) =>
  el instanceof HTMLElement && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);

/** Three suggested questions. Keys 1-3 send them while the Ask bar is empty and unfocused. */
export function TryChips({ onSend, disabled = false }: Props) {
  const barEmpty = useAskOverlay((s) => s.draft.trim() === "");
  const { data: goals = [] } = useGoalsQuery();
  const goal = activeGoal(goals);

  const chips: Chip[] = [
    { text: "What's slipping?", context: { origin: "preset", compose: "slipping" } },
    { text: "What should I decide today?", context: { origin: "preset", compose: "decisions" } },
    ...(goal ? [{ text: `How is ${goal.title} going?`, context: { origin: "preset", topic: goal.title } satisfies WsScreenContext }] : []),
  ];

  useEffect(() => {
    if (disabled || !barEmpty) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented || typing(document.activeElement)) return;
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
        <CommandChip key={chip.text} index={String(i + 1)} keyHint={String(i + 1)} disabled={disabled} onClick={() => onSend(chip.text, chip.context)}>
          {chip.text}
        </CommandChip>
      ))}
    </div>
  );
}
