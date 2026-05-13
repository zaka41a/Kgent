interface Props {
  onSuggest: (prompt: string) => void;
}

const SUGGESTIONS = [
  "Where would a new contributor get lost first, and why?",
  "Trace the path of a single user request through the system",
  "Which parts of this codebase are most likely to break under load?",
  "If I had one hour to refactor, what would have the highest payoff?",
];

export default function EmptyState({ onSuggest }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 text-center">
      <img src="/logo.svg" alt="kgent" className="w-14 h-14 mb-5" />
      <h1 className="text-2xl font-semibold mb-2">How can I help?</h1>
      <p className="text-ink-muted mb-8 max-w-md">
        Ask anything about the documentation indexed by <span className="text-accent">k</span>gent.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="text-left text-sm px-4 py-3 rounded-xl border border-border bg-bg-soft hover:bg-bg-card hover:border-ink-dim transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
