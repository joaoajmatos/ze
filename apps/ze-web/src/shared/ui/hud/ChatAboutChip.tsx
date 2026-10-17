interface ChatAboutChipProps {
  /** What the chat would be about; it names the control for assistive technology. */
  label: string;
  /** Called with the chip itself, so a caller without a wider element can still point the orb at it. */
  onClick: (chip: Element) => void;
}

/**
 * "Chat about this" on a module or card. Under `(hover: hover)` it is visually hidden until the module is
 * hovered or holds focus, but it stays in the DOM and in the tab order; under `(hover: none)` it is always shown.
 */
export function ChatAboutChip({ label, onClick }: ChatAboutChipProps) {
  return (
    <button type="button" className="chat-about" aria-label={`Chat about ${label}`} aria-keyshortcuts="c" onClick={(e) => onClick(e.currentTarget)}>
      [ chat about this ]
    </button>
  );
}
