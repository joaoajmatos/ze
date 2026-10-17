import { useWsStore } from "@/shared/api";

export function ConnectionDot() {
  const connected = useWsStore((s) => s.isConnected);
  const name = connected ? "Connected" : "Offline";
  return (
    <span className="conn" role="img" aria-label={name} title={name}>
      <i className={`pulse ${connected ? "" : "off"}`} aria-hidden="true" />
      <span className="lbl only-wide" aria-hidden="true">
        {name}
      </span>
    </span>
  );
}
