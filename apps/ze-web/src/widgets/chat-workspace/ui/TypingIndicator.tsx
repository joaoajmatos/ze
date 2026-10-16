export function TypingIndicator({ text }: { text?: string | null }) {
  return (
    <div className="flex items-start gap-2">
      <div className="w-6 h-6 rounded-full bg-plum-voltage/20 flex items-center justify-center flex-shrink-0">
        <span className="font-display text-[10px] text-plum-voltage font-semibold">Z</span>
      </div>
      <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-[20px] border border-border text-sm text-smoke">
        <span className="relative inline-flex w-2 h-2 flex-shrink-0" aria-hidden="true">
          <span className="absolute inset-0 rounded-full bg-plum-voltage shadow-[0_0_8px_1px_rgba(128,82,255,0.8)] motion-safe:animate-[pulse-core_1.8s_ease-in-out_infinite]" />
          <span className="absolute -inset-1.5 rounded-full border border-plum-voltage/35 motion-safe:animate-[pulse-ring_1.8s_ease-out_infinite]" />
        </span>
        <span>{text ?? "Thinking…"}</span>
      </div>
    </div>
  );
}
