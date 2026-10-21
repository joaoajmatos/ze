import { useEffect, useRef, useState } from "react";
import { ConnectedPrimitiveTree } from "@/features/primitive-tree";
import { modulesForSlot, useUiManifestQuery, useUiModuleQuery } from "@/entities/ui-manifest";
import type { ModuleSlot, ModuleSubject, UiContribution } from "@/entities/ui-manifest";
import { Module } from "@/shared/ui/hud";

interface PluginModuleSlotProps {
  slot: ModuleSlot;
  subject: ModuleSubject;
}

const POLL_MS = 60_000;

/** True while `ref` is on screen; false until the first observation. */
function useVisible(ref: React.RefObject<Element | null>): boolean {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      const last = entries.at(-1);
      if (last) setVisible(last.isIntersecting);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return visible;
}

function SlotModule({ entry, subject }: { entry: UiContribution; subject: ModuleSubject }) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useVisible(ref);
  const { data, isLoading, isError, error } = useUiModuleQuery(entry.id, subject, { refetchInterval: visible ? POLL_MS : false });

  if (data && !data.applies) return null;

  return (
    <div ref={ref}>
      <Module label={entry.label}>
        {isLoading && <p role="status" className="note">Loading {entry.label}…</p>}
        {isError && <p className="note">{error instanceof Error ? error.message : "This module could not load."}</p>}
        {data?.applies && <ConnectedPrimitiveTree components={data.components} uiVersion={data.ui_version} />}
      </Module>
    </div>
  );
}

/** The modules plugins contribute to `slot`. A module never delays its place: each loads and fails on its own. */
export function PluginModuleSlot({ slot, subject }: PluginModuleSlotProps) {
  const { data: manifest } = useUiManifestQuery();
  const modules = modulesForSlot(manifest, slot);
  if (modules.length === 0) return null;
  return (
    <>
      {modules.map((entry) => (
        <SlotModule key={entry.id} entry={entry} subject={subject} />
      ))}
    </>
  );
}
