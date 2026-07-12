import Logo from "./Logo";

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
      <Logo className="w-12 h-12 text-accent mb-5" />
      <div className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-dim mb-3">
        Knowledge agent · runs locally
      </div>
      <h1 className="text-3xl font-semibold tracking-tight mb-2">
        Navigate what kgent has read.
      </h1>
      <p className="text-ink-muted mb-8 max-w-md">
        Every answer is grounded in real passages, and every citation is a node you can see on the map.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="group flex items-start gap-2.5 text-left text-sm px-4 py-3 rounded-xl border border-border bg-bg-soft hover:bg-bg-card hover:border-accent/50 transition-colors"
          >
            <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-ink-dim group-hover:bg-accent transition-colors flex-none" />
            <span>{s}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
