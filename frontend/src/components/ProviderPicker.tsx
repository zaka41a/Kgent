import { useEffect, useRef, useState } from "react";
import { ChevronDown, Check, AlertCircle } from "lucide-react";
import type { ProviderInfo } from "../lib/api";

interface Props {
  providers: ProviderInfo[];
  selectedProvider: string;
  selectedModel: string;
  onChange: (provider: string, model: string) => void;
  onOpenSettings: () => void;
}

const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Ollama",
  openai: "OpenAI",
  anthropic: "Anthropic",
  groq: "Groq",
};

export default function ProviderPicker({
  providers,
  selectedProvider,
  selectedModel,
  onChange,
  onOpenSettings,
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const current = providers.find((p) => p.name === selectedProvider);
  const dotColor = current?.available ? "bg-accent" : "bg-red-500";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border bg-bg-card text-sm hover:border-ink-dim transition-colors"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        <span className="text-ink-muted">
          {PROVIDER_LABELS[selectedProvider] ?? selectedProvider}
        </span>
        <span className="text-ink/90">{selectedModel || "no model"}</span>
        <ChevronDown size={14} className="text-ink-dim" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-bg-card border border-border rounded-lg shadow-2xl overflow-hidden z-20">
          <div className="max-h-96 overflow-y-auto">
            {providers.map((p) => (
              <ProviderRow
                key={p.name}
                provider={p}
                isSelectedProvider={p.name === selectedProvider}
                selectedModel={selectedModel}
                onPick={(model) => {
                  onChange(p.name, model);
                  setOpen(false);
                }}
              />
            ))}
          </div>
          <button
            onClick={() => {
              setOpen(false);
              onOpenSettings();
            }}
            className="w-full px-3 py-2 text-xs text-ink-muted hover:bg-bg-soft border-t border-border text-left"
          >
            Manage API keys
          </button>
        </div>
      )}
    </div>
  );
}

function ProviderRow({
  provider,
  isSelectedProvider,
  selectedModel,
  onPick,
}: {
  provider: ProviderInfo;
  isSelectedProvider: boolean;
  selectedModel: string;
  onPick: (model: string) => void;
}) {
  return (
    <div className="border-b border-border last:border-b-0">
      <div className="px-3 pt-2.5 pb-1 flex items-center justify-between text-xs text-ink-muted">
        <div className="flex items-center gap-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              provider.available ? "bg-accent" : "bg-red-500"
            }`}
          />
          <span className="font-medium">{PROVIDER_LABELS[provider.name] ?? provider.name}</span>
        </div>
        {!provider.available && (
          <span className="flex items-center gap-1 text-red-400">
            <AlertCircle size={11} />
            no key
          </span>
        )}
      </div>
      {provider.models.length === 0 ? (
        <div className="px-3 pb-2 text-xs text-ink-dim">No models found.</div>
      ) : (
        provider.models.map((m) => {
          const isSelected = isSelectedProvider && m === selectedModel;
          return (
            <button
              key={m}
              disabled={!provider.available}
              onClick={() => onPick(m)}
              className={`w-full text-left px-3 py-1.5 text-sm flex items-center justify-between hover:bg-bg-soft disabled:opacity-40 disabled:cursor-not-allowed ${
                isSelected ? "text-ink" : "text-ink-muted"
              }`}
            >
              <span>{m}</span>
              {isSelected && <Check size={14} className="text-accent" />}
            </button>
          );
        })
      )}
    </div>
  );
}
