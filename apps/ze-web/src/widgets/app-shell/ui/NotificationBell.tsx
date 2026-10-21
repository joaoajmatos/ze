import type { NotificationItem } from "@myguyze/ze-client";
import { Bell, CheckCheck, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMarkAllReadMutation,
  useMarkReadMutation,
  useNotificationsQuery,
  useUnreadCountQuery,
} from "@/entities/notification";
import { useSession } from "@/entities/session";
import { cn } from "@/shared/lib/cn";
import { notificationHref } from "@/shared/lib/notification-href";
import { EmptyState } from "@/shared/ui";
import { relativeTime } from "../lib/notification-format";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data: unreadCount } = useUnreadCountQuery();
  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useNotificationsQuery({ markRead: open });
  const markRead = useMarkReadMutation();
  const markAllRead = useMarkAllReadMutation();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const items = data?.pages.flatMap((p) => p.items ?? []) ?? [];

  const selectSession = useSession((s) => s.selectSession);

  function handleItemClick(item: NotificationItem) {
    if (!item.read) void markRead.mutate(item.id);
    if (item.target_type === "chat_thread" && item.target_id) selectSession(item.target_id);
    const href = notificationHref(item);
    if (href) {
      setOpen(false);
      navigate(href);
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="ctl bell"
        aria-label="Notifications"
      >
        <Bell className="w-[18px] h-[18px]" />
        {!!unreadCount && unreadCount > 0 && (
          <span className="count">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 w-96 max-h-[28rem] flex flex-col rounded-2xl border border-foreground/10 bg-background shadow-xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-foreground/[0.08]">
            <span className="text-sm font-semibold text-foreground">Notifications</span>
            <button
              onClick={() => markAllRead.mutate()}
              disabled={!unreadCount}
              className="flex items-center gap-1 text-xs text-smoke hover:text-foreground transition-colors disabled:opacity-40 disabled:hover:text-smoke"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              Mark all read
            </button>
          </div>

          <div className="overflow-y-auto flex-1">
            {isLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="size-4 animate-spin text-smoke" />
              </div>
            ) : isError ? (
              <p role="alert" className="px-4 py-10 text-center text-sm text-smoke">
                Couldn't load notifications.
              </p>
            ) : items.length === 0 ? (
              <EmptyState icon={Bell} message="You're all caught up." />
            ) : (
              <ul>
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => handleItemClick(item)}
                      className={cn(
                        "w-full text-left px-4 py-3 border-b border-foreground/[0.04] hover:bg-foreground/[0.03] transition-colors",
                        !item.read && "bg-plum-voltage/[0.06]",
                      )}
                    >
                      <div className="flex items-start gap-2">
                        {!item.read && (
                          <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-plum-voltage shrink-0" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-foreground truncate">{item.title}</p>
                          {item.delivery === "held" && (
                            <p className="text-[11px] text-smoke/70 mt-0.5">
                              Held for quiet hours
                            </p>
                          )}
                          {item.delivery === "suppressed" && (
                            <p className="text-[11px] text-smoke/70 mt-0.5">
                              Not pushed: daily limit
                            </p>
                          )}
                          <p className="text-xs text-smoke line-clamp-2 mt-0.5">{item.body}</p>
                          <p className="text-[11px] text-smoke/60 mt-1">
                            {relativeTime(item.created_at)} · {item.source}
                          </p>
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {hasNextPage && (
              <button
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
                className="w-full py-2.5 text-xs text-smoke hover:text-foreground transition-colors"
              >
                {isFetchingNextPage ? "Loading…" : "Load more"}
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              navigate("/");
            }}
            className="w-full py-2.5 text-xs text-smoke hover:text-foreground transition-colors border-t border-foreground/[0.08]"
          >
            While you were away
          </button>
        </div>
      )}
    </div>
  );
}
