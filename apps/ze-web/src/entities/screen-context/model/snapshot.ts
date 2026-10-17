import type { WsCanvasRef, WsScreenContext, WsScreenRef } from "@myguyze/ze-client";
import { placeOf } from "@/shared/config";
import { useScreenContextStore } from "./store";

const CAPS = { subject: 3, selection: 20, visible: 30, canvas: 12 } as const;

function capRef(ref: WsScreenRef): WsScreenRef {
  const out: WsScreenRef = { kind: ref.kind.slice(0, 64), id: ref.id.slice(0, 64) };
  if (ref.label) out.label = ref.label.slice(0, 120);
  if (ref.component) out.component = ref.component.slice(0, 40);
  if (ref.parent_id) out.parent_id = ref.parent_id.slice(0, 64);
  if (ref.as_of) out.as_of = ref.as_of;
  return out;
}

function merge<T>(lists: (T[] | undefined)[], cap: number): T[] {
  return lists.flatMap((l) => l ?? []).slice(0, cap);
}

/**
 * What the person can see right now: the publications in mount order, capped like the engine caps them.
 * `route` is the path alone (no query string). A snapshot carries `captured_at`, which marks it finished.
 */
export function screenSnapshot(pathname: string = window.location.pathname, now: Date = new Date()): WsScreenContext {
  const pubs = [...useScreenContextStore.getState().publications.values()];
  const place = placeOf(pathname);
  const context: WsScreenContext = { route: pathname.slice(0, 200), captured_at: now.toISOString() };
  if (place) context.place = place.id;

  const subject = merge(pubs.map((p) => p.subject), CAPS.subject).map(capRef);
  const selection = merge(pubs.map((p) => p.selection), CAPS.selection).map(capRef);
  const visible = merge(pubs.map((p) => p.visible), CAPS.visible).map(capRef);
  const canvas: WsCanvasRef[] = merge(pubs.map((p) => p.canvas), CAPS.canvas).map((c) => ({
    index: c.index,
    type: c.type.slice(0, 40),
    ...(c.ref ? { ref: capRef(c.ref) } : {}),
  }));
  if (subject.length) context.subject = subject;
  if (selection.length) context.selection = selection;
  if (visible.length) context.visible = visible;
  if (canvas.length) context.canvas = canvas;
  const focused = pubs.map((p) => p.focused_module).filter(Boolean).at(-1);
  if (focused) context.focused_module = focused.slice(0, 80);
  return context;
}
