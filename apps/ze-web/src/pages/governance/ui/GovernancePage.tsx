import { useState, type FocusEvent } from "react";
import { Attention } from "@/widgets/attention";
import { Connections } from "@/widgets/connections";
import { Data } from "@/widgets/data";
import { Files } from "@/widgets/files";
import { PluginModuleSlot } from "@/widgets/plugin-module";
import { Spend } from "@/widgets/spend";
import { useScreenPublisher } from "@/entities/screen-context";

/** Governance: is Ze behaving? DOM order is the phone order; the desktop grid places each slot by area. */
export function GovernancePage() {
  const [focused, setFocused] = useState<string | null>(null);
  useScreenPublisher(focused ? { focused_module: focused } : null);

  function onFocus(e: FocusEvent<HTMLElement>) {
    const slot = (e.target as HTMLElement).closest("[data-module]");
    const name = slot?.getAttribute("data-module");
    if (name) setFocused(name);
  }

  return (
    <div className="gov" onFocusCapture={onFocus}>
      <div className="gov-attention" data-module="Attention">
        <Attention />
      </div>
      <div className="gov-spend" data-module="Spend">
        <Spend />
      </div>
      <div className="gov-connections" data-module="Connections">
        <Connections extra={<PluginModuleSlot slot="governance.connections" subject={{ kind: "none" }} />} />
      </div>
      <div className="gov-data" data-module="Data">
        <Data />
      </div>
      <div className="gov-files" data-module="Files">
        <Files />
      </div>
    </div>
  );
}
