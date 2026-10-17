import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface Common {
  children: ReactNode;
  primary?: boolean;
  className?: string;
}

type ButtonProps = Common & {
  as?: "button";
  type?: "button" | "submit";
  /** Toggle state, forwarded as aria-pressed. */
  pressed?: boolean;
  disabled?: boolean;
  title?: string;
  "aria-label"?: string;
  onClick?: () => void;
};

type LinkProps = Common & {
  as: "link";
  to: string;
  /** The place the user is on, forwarded as aria-current="page". */
  current?: boolean;
  "aria-label"?: string;
  onClick?: () => void;
};

export type ControlProps = ButtonProps | LinkProps;

/** The `.ctl` control: 44 px, hairline frame, corner brackets. */
export function Control(props: ControlProps) {
  const classes = ["ctl", props.primary ? "primary" : "", props.className ?? ""].filter(Boolean).join(" ");
  if (props.as === "link") {
    return (
      <Link
        to={props.to}
        className={classes}
        aria-current={props.current ? "page" : undefined}
        aria-label={props["aria-label"]}
        onClick={props.onClick}
      >
        {props.children}
      </Link>
    );
  }
  return (
    <button
      type={props.type ?? "button"}
      className={classes}
      aria-pressed={props.pressed}
      aria-label={props["aria-label"]}
      disabled={props.disabled}
      title={props.title}
      onClick={props.onClick}
    >
      {props.children}
    </button>
  );
}
