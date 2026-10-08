import { ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { NavLink, useLocation } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/shared/lib/cn";
import { motion } from "@/shared/lib/motion";
import { useMediaQuery } from "@/shared/lib/use-media-query";

interface NavGroupProps {
  icon: LucideIcon;
  label: string;
  children: React.ReactNode;
  /** If set, the label area is a NavLink to this path */
  href?: string;
  hrefIndex?: boolean;
  /** Route paths (without leading slash) that auto-open this group when active */
  childPaths?: string[];
  defaultOpen?: boolean;
  /** Aggregate child status shown as an indicator when the group is collapsed */
  status?: "thinking" | "attention" | null;
}

const FLYOUT_GAP = 8;
const FLYOUT_MARGIN = 16;

function StatusDot({ status }: { status: NavGroupProps["status"] }) {
  if (status === "thinking") {
    return (
      <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full border border-plum-voltage/60 border-t-plum-voltage animate-spin" />
    );
  }
  if (status === "attention") {
    return (
      <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-plum-voltage animate-pulse" />
    );
  }
  return null;
}

export function NavGroup(props: NavGroupProps) {
  const isWide = useMediaQuery("(min-width: 1024px)");
  return isWide ? <AccordionGroup {...props} /> : <FlyoutGroup {...props} />;
}

function useChildActive(childPaths: string[]) {
  const { pathname } = useLocation();
  return childPaths.some((p) => {
    const abs = p === "/" ? "/" : `/${p}`;
    return pathname === abs || pathname.startsWith(`${abs}/`);
  });
}

/** md width: the sidebar is icons only, so children open in a click flyout. */
function FlyoutGroup({ icon: Icon, label, children, href, hrefIndex, childPaths = [], status }: NavGroupProps) {
  const { pathname } = useLocation();
  const isChildActive = useChildActive(childPaths);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const open = pos !== null;

  const isHrefActive =
    href !== undefined &&
    (hrefIndex ? pathname === href : pathname === href || pathname.startsWith(`${href}/`));
  const isActive = isChildActive || isHrefActive;

  function toggle() {
    if (open) {
      setPos(null);
      return;
    }
    const rect = buttonRef.current?.getBoundingClientRect();
    setPos({ top: rect?.top ?? 0, left: (rect?.right ?? 0) + FLYOUT_GAP });
  }

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setPos(null);
        buttonRef.current?.focus();
      }
    }
    function onPointerDown(e: PointerEvent | MouseEvent) {
      const target = e.target as Node;
      if (panelRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      setPos(null);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open]);

  return (
    <div>
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        aria-label={label}
        title={label}
        aria-haspopup="true"
        aria-expanded={open}
        className={cn(
          "w-full flex items-center justify-center px-3 py-2 rounded-pill text-sm",
          motion.colors,
          isActive || open
            ? "bg-plum-voltage/15 text-foreground"
            : "text-smoke hover:text-foreground hover:bg-foreground/5",
        )}
      >
        <span className="relative flex-shrink-0">
          <Icon className="w-4 h-4" />
          {!open && <StatusDot status={status} />}
        </span>
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            role="group"
            aria-label={label}
            style={{
              top: pos.top,
              left: pos.left,
              maxHeight: `calc(100vh - ${pos.top}px - ${FLYOUT_MARGIN}px)`,
            }}
            className="fixed z-50 w-56 overflow-y-auto rounded-xl border border-border bg-background p-2 shadow-2xl shadow-black/60"
            onClick={(e) => {
              if ((e.target as HTMLElement).closest("a, button")) setPos(null);
            }}
          >
            <p className="px-3 pb-1 pt-0.5 text-[11px] font-medium uppercase tracking-widest text-smoke">
              {label}
            </p>
            {href && (
              <NavLink
                to={href}
                end={hrefIndex}
                className={({ isActive: active }) =>
                  cn(
                    "mb-0.5 flex w-full items-center gap-2.5 rounded-pill px-3 py-1.5 text-xs",
                    motion.colors,
                    active
                      ? "bg-plum-voltage/15 text-foreground"
                      : "text-smoke hover:text-foreground hover:bg-secondary",
                  )
                }
              >
                <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{label}</span>
              </NavLink>
            )}
            <div className="space-y-0.5">{children}</div>
          </div>,
          document.body,
        )}
    </div>
  );
}

/** lg width and up: label visible, children in an inline accordion. */
function AccordionGroup({
  icon: Icon,
  label,
  children,
  href,
  hrefIndex,
  childPaths = [],
  defaultOpen = false,
}: NavGroupProps) {
  const isChildActive = useChildActive(childPaths);
  const [open, setOpen] = useState(defaultOpen || isChildActive);

  useEffect(() => {
    if (isChildActive) setOpen(true);
  }, [isChildActive]);

  const toggle = () => setOpen((o) => !o);

  const sharedLabelClass = cn(
    "flex-1 flex items-center gap-3 px-3 py-2 rounded-pill text-sm min-w-0",
    motion.colors,
  );

  return (
    <div>
      <div className="flex items-center gap-0.5">
        {href ? (
          <NavLink
            to={href}
            end={hrefIndex}
            aria-label={label}
            title={label}
            className={({ isActive }) =>
              cn(
                sharedLabelClass,
                isActive
                  ? "bg-plum-voltage/15 text-foreground"
                  : "text-smoke hover:text-foreground hover:bg-foreground/5",
              )
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1 truncate">{label}</span>
          </NavLink>
        ) : (
          <button
            type="button"
            onClick={toggle}
            aria-label={label}
            title={label}
            aria-expanded={open}
            className={cn(
              sharedLabelClass,
              isChildActive
                ? "text-foreground"
                : "text-smoke hover:text-foreground hover:bg-foreground/5",
            )}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1 truncate text-left">{label}</span>
          </button>
        )}

        <button
          type="button"
          onClick={toggle}
          aria-label={open ? `Collapse ${label}` : `Expand ${label}`}
          aria-expanded={open}
          className={cn(
            "flex w-7 h-7 items-center justify-center rounded text-foreground/40 hover:text-foreground flex-shrink-0",
            motion.colors,
          )}
        >
          <ChevronRight className={cn("w-4 h-4", motion.rotate, open && "rotate-90")} />
        </button>
      </div>

      <div
        className={cn(
          "grid",
          motion.accordion,
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        )}
      >
        <div className="overflow-hidden">
          <div className="pl-3 pt-0.5 pb-1 space-y-0.5">{children}</div>
        </div>
      </div>
    </div>
  );
}
