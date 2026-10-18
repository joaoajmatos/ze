import { useConnectionState } from "@/shared/api";

const NAME = { online: "Connected", displaced: "Open in another window", offline: "Offline" } as const;

export function ConnectionDot() {
  const state = useConnectionState();
  const name = NAME[state];
  return (
    <span className="conn" role="img" aria-label={name} title={name}>
      <i className={`pulse ${state === "online" ? "" : "off"}`} aria-hidden="true" />
      <span className="lbl" aria-hidden="true">
        {name}
      </span>
    </span>
  );
}
