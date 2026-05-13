import { useEffect, useState } from "react";
import { X, Eye, EyeOff } from "lucide-react";
import { getKeys, saveKeys, type ApiKeys } from "../lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

interface Field {
  key: keyof ApiKeys;
  label: string;
  placeholder: string;
  type: "secret" | "url";
}

const FIELDS: Field[] = [
  { key: "ANTHROPIC_API_KEY", label: "Anthropic API key", placeholder: "sk-ant-...", type: "secret" },
  { key: "OPENAI_API_KEY", label: "OpenAI API key", placeholder: "sk-...", type: "secret" },
  { key: "GROQ_API_KEY", label: "Groq API key", placeholder: "gsk_...", type: "secret" },
  { key: "OLLAMA_BASE_URL", label: "Ollama base URL", placeholder: "http://localhost:11434", type: "url" },
];

export default function SettingsModal({ open, onClose, onSaved }: Props) {
  const [values, setValues] = useState<ApiKeys>({});
  const [shown, setShown] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (open) {
      setValues(getKeys());
      setShown({});
    }
  }, [open]);

  if (!open) return null;

  const update = (k: keyof ApiKeys, v: string) =>
    setValues((prev) => ({ ...prev, [k]: v }));

  const handleSave = () => {
    const cleaned: ApiKeys = {};
    for (const [k, v] of Object.entries(values)) {
      if (v && v.trim()) cleaned[k as keyof ApiKeys] = v.trim();
    }
    saveKeys(cleaned);
    onSaved();
    onClose();
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-bg-card border border-border rounded-xl w-full max-w-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-base font-medium">Settings</h2>
          <button
            onClick={onClose}
            className="text-ink-muted hover:text-ink transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <p className="text-xs text-ink-dim">
            Keys are stored locally in your browser. They are sent to the <span className="text-accent">k</span>gent
            server only with each request and never persisted server-side.
          </p>
          {FIELDS.map((field) => (
            <div key={field.key}>
              <label className="block text-xs text-ink-muted mb-1.5">
                {field.label}
              </label>
              <div className="relative">
                <input
                  type={
                    field.type === "secret" && !shown[field.key] ? "password" : "text"
                  }
                  value={values[field.key] ?? ""}
                  onChange={(e) => update(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  autoComplete="off"
                  className="w-full bg-bg-soft border border-border rounded-md px-3 py-2 text-sm pr-9 outline-none focus:border-ink-dim transition-colors"
                />
                {field.type === "secret" && (
                  <button
                    type="button"
                    onClick={() =>
                      setShown((s) => ({ ...s, [field.key]: !s[field.key] }))
                    }
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-dim hover:text-ink-muted"
                    aria-label="Toggle visibility"
                  >
                    {shown[field.key] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-border flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-ink-muted hover:text-ink transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-1.5 text-sm bg-accent text-white rounded-md hover:bg-accent-hover transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
