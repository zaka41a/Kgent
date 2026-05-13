import { useEffect } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";

export interface ToastData {
  id: number;
  kind: "success" | "error";
  message: string;
}

interface Props {
  toasts: ToastData[];
  onDismiss: (id: number) => void;
}

export default function ToastContainer({ toasts, onDismiss }: Props) {
  return (
    <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  );
}

function Toast({ toast, onDismiss }: { toast: ToastData; onDismiss: () => void }) {
  useEffect(() => {
    const id = setTimeout(onDismiss, 4000);
    return () => clearTimeout(id);
  }, [onDismiss]);

  const Icon = toast.kind === "success" ? CheckCircle2 : AlertCircle;
  const color = toast.kind === "success" ? "text-accent" : "text-red-400";

  return (
    <div className="flex items-start gap-3 bg-bg-card border border-border rounded-lg px-4 py-3 shadow-2xl min-w-[280px] max-w-md animate-fade-in">
      <Icon size={16} className={`mt-0.5 ${color} flex-shrink-0`} />
      <div className="flex-1 text-sm">{toast.message}</div>
      <button
        onClick={onDismiss}
        className="text-ink-dim hover:text-ink-muted"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}
