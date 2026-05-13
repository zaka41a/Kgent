import { useState } from "react";
import { X, FolderPlus, Loader2 } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  onIngested: (result: IngestResult) => void;
  onError: (message: string) => void;
}

export interface IngestResult {
  documents: number;
  chunks_added: number;
  total_chunks: number;
  repo_path: string;
}

export default function IngestModal({ open, onClose, onIngested, onError }: Props) {
  const [path, setPath] = useState("");
  const [replace, setReplace] = useState(true);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const submit = async () => {
    const trimmed = path.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: trimmed, replace }),
      });
      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          detail = JSON.parse(text).detail ?? text;
        } catch {
          /* keep raw */
        }
        onError(detail);
        return;
      }
      const data = (await res.json()) as IngestResult;
      onIngested(data);
      setPath("");
      onClose();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={() => !busy && onClose()}
    >
      <div
        className="bg-bg-card border border-border rounded-xl w-full max-w-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-base font-medium flex items-center gap-2">
            <FolderPlus size={18} />
            Add repository
          </h2>
          <button
            onClick={onClose}
            disabled={busy}
            className="text-ink-muted hover:text-ink transition-colors disabled:opacity-40"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <p className="text-xs text-ink-dim">
            Provide an absolute path to any directory containing documentation,
            source code, or notes. <span className="text-accent">k</span>gent will extract supported files (md, rst,
            py, ts, java, go, yaml, etc.), chunk them, and index them.
          </p>

          <div>
            <label className="block text-xs text-ink-muted mb-1.5">
              Repository path
            </label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/Users/me/projects/my-repo"
              autoFocus
              autoComplete="off"
              spellCheck={false}
              className="w-full bg-bg-soft border border-border rounded-md px-3 py-2 text-sm font-mono outline-none focus:border-ink-dim transition-colors"
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-muted cursor-pointer">
            <input
              type="checkbox"
              checked={replace}
              onChange={(e) => setReplace(e.target.checked)}
              className="accent-accent"
            />
            <span>Replace the current index</span>
          </label>
        </div>

        <div className="px-5 py-3 border-t border-border flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            disabled={busy}
            className="px-3 py-1.5 text-sm text-ink-muted hover:text-ink transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy || !path.trim()}
            className="px-4 py-1.5 text-sm bg-accent text-white rounded-md hover:bg-accent-hover transition-colors disabled:opacity-40 flex items-center gap-2"
          >
            {busy && <Loader2 size={14} className="animate-spin" />}
            {busy ? "Ingesting..." : "Ingest"}
          </button>
        </div>
      </div>
    </div>
  );
}
