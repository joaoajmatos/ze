import { motion } from "framer-motion";
import { ArrowUp, Paperclip, X } from "lucide-react";
import { useRef, type KeyboardEvent } from "react";
import { cn } from "@/shared/lib/cn";

export interface ChatAttachment {
  path: string;
  size: number;
  name: string;
}

interface ChatInputProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
  attachments?: ChatAttachment[];
  onPickFile?: (file: File) => void;
  onRemoveAttachment?: (path: string) => void;
  attaching?: boolean;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
  placeholder,
  attachments = [],
  onPickFile,
  onRemoveAttachment,
  attaching = false,
}: ChatInputProps) {
  const isDisabled = disabled ?? false;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  const canSend = Boolean(value.trim() || attachments.length) && !isDisabled && !attaching;

  return (
    <div className="flex-shrink-0 pt-4">
      {attachments.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((item) => (
            <span
              key={item.path}
              className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/[0.04] px-2 py-1 text-[11px] text-white"
            >
              {item.name}
              {onRemoveAttachment && (
                <button
                  type="button"
                  aria-label={`Remove ${item.name}`}
                  onClick={() => onRemoveAttachment(item.path)}
                  className="text-smoke hover:text-white"
                >
                  <X className="size-3" />
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      <div
        className={cn(
          "flex min-h-9 items-end gap-2 rounded-pill border border-white/15 bg-white/[0.03] px-4 py-2 transition-colors",
          "focus-within:border-plum-voltage/50",
          isDisabled && "opacity-50",
        )}
      >
        {onPickFile && (
          <>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) onPickFile(file);
              }}
            />
            <button
              type="button"
              aria-label="Attach file to workspace"
              disabled={isDisabled || attaching}
              onClick={() => fileRef.current?.click()}
              className="mb-0.5 flex size-8 flex-shrink-0 items-center justify-center rounded-full text-smoke hover:text-white disabled:opacity-40"
            >
              <Paperclip className="size-4" />
            </button>
          </>
        )}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            handleInput();
          }}
          onKeyDown={handleKey}
          disabled={isDisabled}
          placeholder={placeholder ?? (isDisabled ? "Ze is thinking…" : "Message Ze")}
          rows={1}
          className={cn(
            "min-h-[1.5rem] max-h-40 flex-1 resize-none overflow-y-auto bg-transparent text-sm leading-relaxed text-white placeholder:text-smoke focus:outline-none disabled:cursor-not-allowed",
          )}
          style={{ height: "auto" }}
        />
        <motion.button
          type="button"
          onClick={onSend}
          disabled={!canSend}
          aria-label="Send message"
          className="flex size-8 flex-shrink-0 items-center justify-center rounded-full bg-plum-voltage text-white transition-opacity disabled:opacity-40"
          whileTap={{ scale: 0.9 }}
        >
          <ArrowUp className="size-4" />
        </motion.button>
      </div>
    </div>
  );
}
