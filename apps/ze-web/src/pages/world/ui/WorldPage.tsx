import type { WsScreenContext } from "@myguyze/ze-client";
import { useEffect, useState, type FocusEvent } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import { Away } from "@/widgets/away";
import { DoingNow } from "@/widgets/doing-now";
import { LoopsRail } from "@/widgets/loops-rail";
import { NeedsYou } from "@/widgets/needs-you";
import { Touched } from "@/widgets/touched";
import { WorldField } from "@/widgets/world-field";
import { useAskOverlay, useChatAbout } from "@/features/ask-bar";
import { useLoopTransitionMutation } from "@/entities/loop";
import { presenceActions } from "@/entities/presence";
import { screenSnapshot, useScreenPublisher } from "@/entities/screen-context";
import { useWsStore } from "@/shared/api";
import { useNarrow, useRailSlot, useReducedMotion, useSendNotice } from "@/shared/lib";
import { Corners, CommandChip, LeaderLine } from "@/shared/ui";
import { parseFocus } from "../lib/focus";
import { useWorld } from "../model/useWorld";

const FIELD_KINDS = new Set(["loop", "goal", "hypothesis", "reminder"]);

const MODULE_OF: [string, string][] = [
  [".world-needs", "needs-you"],
  [".world-doing", "doing-now"],
  [".world-loops", "loops-rail"],
  [".world-touched", "touched"],
  [".world-away", "away"],
  [".world-hero", "world-field"],
];

export function WorldPage() {
  const world = useWorld();
  const narrow = useNarrow();
  const reducedMotion = useReducedMotion();
  const chatAbout = useChatAbout();
  const offline = !useWsStore((s) => s.isConnected);
  const railSlot = useRailSlot((s) => s.element);
  const transition = useLoopTransitionMutation();
  const [params] = useSearchParams();
  const focus = parseFocus(params.get("focus"));
  const focusKey = focus && FIELD_KINDS.has(focus.kind) ? `${focus.kind}:${focus.id}` : null;
  // A manual pick belongs to the focus link it was made under; a new link selects its own item.
  const rawFocus = params.get("focus");
  const [pick, setPick] = useState<{ under: string | null; key: string | null } | null>(null);
  const picked = pick && pick.under === rawFocus ? pick.key : undefined;
  const setPicked = (key: string | null) => setPick({ under: rawFocus, key });
  const [focusedModule, setFocusedModule] = useState("world-field");

  const concerns = world.field.data;
  const selected = picked !== undefined ? picked : focusKey && concerns.some((c) => c.key === focusKey) ? focusKey : null;
  const slipped = world.counts.slipped;
  const attention = !world.loading && (slipped > 0 || world.failedRun);

  // The orb holds attention while something has slipped, shows work while a run is going, and drains back otherwise.
  const signal = world.loading ? null : attention ? "attention" : world.running ? "acting" : null;
  useEffect(() => {
    presenceActions.setWorldSignal(signal);
    return () => presenceActions.setWorldSignal(null);
  }, [signal]);

  // The mark's CSS pulse and the orb's heartbeat share one absolute clock (2.2 s period).
  useEffect(() => {
    if (attention) document.documentElement.style.setProperty("--beat-offset", `${-((performance.now() / 1000) % 2.2)}s`);
  }, [attention]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPicked(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useScreenPublisher({ focused_module: focusedModule });

  const leaderOn = attention && concerns.some((c) => c.slipped) && !narrow && !reducedMotion;

  function onFocusCapture(e: FocusEvent) {
    const target = e.target as Element;
    const hit = MODULE_OF.find(([selector]) => target.closest(selector));
    if (hit) setFocusedModule(hit[1]);
  }

  function askSlipping() {
    const context = { ...screenSnapshot(window.location.pathname), origin: "preset", compose: "slipping" } as WsScreenContext;
    if (!useAskOverlay.getState().submit("What's slipping?", context)) {
      useSendNotice.getState().showNotice("Ze has not sent your last message yet. Wait for it, then send this one.");
    }
  }

  const failedNames = world.sourcesFailed;

  const rail = (
    <>
      <NeedsYou decisions={world.decisions.data} loading={world.decisions.loading} error={world.decisions.error} now={world.now} offline={offline} focus={focus} onChatAbout={chatAbout} />
      <DoingNow goals={world.doing.data.goals} workflows={world.doing.data.workflows} executions={world.doing.data.executions} loading={world.doing.loading} error={world.doing.error} now={world.now} />
    </>
  );

  return (
    <div className="world" onFocusCapture={onFocusCapture}>
      {railSlot ? createPortal(rail, railSlot) : rail}

      <section className={`hero world-hero ${attention ? "attn" : ""}`} aria-label="World-state viewport">
        {leaderOn && <LeaderLine from=".presence-orb canvas" to=".pt.lead rect" reducedMotion={reducedMotion} />}
        <Corners />
        <div className="hero-head">
          <span className="lbl on">{narrow ? `World · ${concerns.length}` : `Time left × how sure · ${concerns.length} concerns`}</span>
          <span className="lbl">
            {offline ? (
              <span className="hot">Ze is offline</span>
            ) : failedNames.length ? (
              <span className="hot">
                {failedNames.length} source{failedNames.length > 1 ? "s" : ""} down: {failedNames.join(", ")}
              </span>
            ) : slipped ? (
              <span className="hot">{slipped} slipping</span>
            ) : (
              "steady"
            )}
          </span>
        </div>
        <WorldField
          concerns={concerns}
          now={world.now}
          loading={world.field.loading}
          error={world.field.error}
          recordsFailed={world.recordsFailed}
          narrow={narrow}
          offline={offline}
          selected={selected}
          onSelect={setPicked}
          onChatAbout={chatAbout}
        />
        <div className="hero-foot">
          <p className="sentence">{world.field.loading ? "Reading the world-state…" : world.field.error ? "I could not read the world-state." : world.sentence}</p>
          <CommandChip index="→" onClick={askSlipping} disabled={offline}>
            What's slipping?
          </CommandChip>
        </div>
      </section>

      <aside className="rail world-right" aria-label="Feeds">
        <LoopsRail
          loops={world.loops.data}
          loading={world.loops.loading}
          error={world.loops.error}
          now={world.now}
          offline={offline}
          selected={selected}
          onSelect={setPicked}
          onTransition={(loopId, kind) => transition.mutate({ loopId, kind })}
          busyId={transition.isPending ? (transition.variables?.loopId ?? null) : null}
          onChatAbout={chatAbout}
        />
        <Touched loops={world.touched.data.loops} closedLoops={world.touched.data.closedLoops} goals={world.touched.data.goals} workflows={world.touched.data.workflows} loading={world.touched.loading} error={world.touched.error} now={world.now} />
        <Away notifications={world.away.data.notifications} jobRuns={world.away.data.jobRuns} budget={world.away.data.budget} loading={world.away.loading} error={world.away.error} now={world.now} onChatAbout={chatAbout} />
      </aside>
    </div>
  );
}
