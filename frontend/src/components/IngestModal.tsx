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

interface IngestJob {
  state: string;
  phase: string;
  processed: number;
  total: number;
  documents: number;
  chunks: number;
  indexed: number;
  index_total: number;
  total_chunks: number;
  error: string | null;
  repo_path: string;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const PHASE_LABELS: Record<string, string> = {
  queued: "Queued",
  scanning: "Scanning files",
  reading: "Reading documents",
  indexing: "Building the index",
  done: "Done",
  error: "Failed",
};

function jobPercent(job: IngestJob): number {
  if (job.phase === "reading" && job.total > 0) {
    return Math.round((job.processed / job.total) * 100);
  }
  if (job.phase === "indexing" && job.index_total > 0) {
    return Math.round((job.indexed / job.index_total) * 100);
  }
  return job.phase === "done" ? 100 : 0;
}

export default function IngestModal({ open, onClose, onIngested, onError }: Props) {
  const [path, setPath] = useState("");
  const [replace, setReplace] = useState(true);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<IngestJob | null>(null);

  if (!open) return null;

  const submit = async () => {
    const trimmed = path.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setJob(null);
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
      const { job_id } = (await res.json()) as { job_id: string };

      // The server runs the ingestion in the background. Poll its status
      // until the job reports that it completed or failed.
      let finished = false;
      while (!finished) {
        await sleep(600);
        const statusRes = await fetch(`/api/ingest/status/${job_id}`);
        if (!statusRes.ok) {
          onError("Lost track of the ingestion job.");
          return;
        }
        const current = (await statusRes.json()) as IngestJob;
        setJob(current);
        if (current.state === "completed") {
          onIngested({
            documents: current.documents,
            chunks_added: current.chunks,
            total_chunks: current.total_chunks,
            repo_path: current.repo_path,
          });
          setPath("");
          onClose();
          finished = true;
        } else if (current.state === "failed") {
          onError(current.error || "Ingestion failed.");
          finished = true;
        }
      }
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setJob(null);
    }
  };

  const buttonLabel = busy
    ? job
      ? PHASE_LABELS[job.phase] ?? "Ingesting..."
      : "Ingesting..."
    : "Ingest";

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
              disabled={busy}
              className="w-full bg-bg-soft border border-border rounded-md px-3 py-2 text-sm font-mono outline-none focus:border-ink-dim transition-colors disabled:opacity-50"
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-ink-muted cursor-pointer">
            <input
              type="checkbox"
              checked={replace}
              onChange={(e) => setReplace(e.target.checked)}
              disabled={busy}
              className="accent-accent"
            />
            <span>Replace the current index</span>
          </label>

          {busy && job && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-ink-muted">
                <span>{PHASE_LABELS[job.phase] ?? job.phase}</span>
                <span>{jobPercent(job)}%</span>
              </div>
              <div className="h-1.5 w-full bg-bg-soft rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent transition-all duration-300"
                  style={{ width: `${jobPercent(job)}%` }}
                />
              </div>
              <p className="text-xs text-ink-dim">
                {job.documents} documents, {job.chunks} chunks
              </p>
            </div>
          )}
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
            {buttonLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
