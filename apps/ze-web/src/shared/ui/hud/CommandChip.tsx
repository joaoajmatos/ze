import type { ButtonHTMLAttributes, ReactNode } from "react";

interface CommandChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Leading marker: a number or an arrow. */
  index: string;
  /** Key that triggers the chip; shown as a hint. */
  keyHint?: string;
  pressed?: boolean;
  children: ReactNode;
}

/** A suggested question or command: index, label, key hint. */
export function CommandChip({ index, keyHint, pressed, children, className = "", type = "button", ...rest }: CommandChipProps) {
  return (
    <button type={type} className={`ctl cmd ${className}`.trim()} aria-pressed={pressed} {...rest}>
      <span className="cmd-i">{index}</span>
      <span className="cmd-q">{children}</span>
      {keyHint && (
        <span className="cmd-k" aria-hidden="true">
          {keyHint}
        </span>
      )}
    </button>
  );
}
