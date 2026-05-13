import { useState, useRef, useEffect } from "react";
import { ArrowUp } from "lucide-react";

interface Props {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export default function InputBox({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  };

  return (
    <div className="border-t border-border bg-bg/95 backdrop-blur">
      <div className="max-w-3xl mx-auto px-4 py-4">
        <div className="relative flex items-end bg-bg-card border border-border rounded-2xl shadow-lg focus-within:border-ink-muted transition-colors">
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask anything about the indexed documentation..."
            className="flex-1 bg-transparent resize-none px-4 py-3.5 outline-none placeholder:text-ink-dim text-[15px]"
            disabled={disabled}
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="m-2 w-8 h-8 rounded-full bg-ink text-bg flex items-center justify-center disabled:bg-bg-card disabled:text-ink-dim transition-colors hover:bg-ink/90"
            aria-label="Send"
          >
            <ArrowUp size={16} />
          </button>
        </div>
        <p className="text-center text-xs text-ink-dim mt-2">
          <span className="text-accent">k</span>gent grounds answers in the indexed documentation. Verify important details.
        </p>
      </div>
    </div>
  );
}
