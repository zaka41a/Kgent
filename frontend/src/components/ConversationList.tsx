import { useEffect, useState } from "react";
import { MessageSquare, Trash2, Loader2, Check, X } from "lucide-react";
import {
  deleteConversation,
  listConversations,
  type Conversation,
} from "../lib/api";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  refreshKey: number;
  onError: (message: string) => void;
  onDeleted?: (id: string) => void;
}

export default function ConversationList({
  activeId,
  onSelect,
  refreshKey,
  onError,
  onDeleted,
}: Props) {
  const [items, setItems] = useState<Conversation[] | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  useEffect(() => {
    listConversations()
      .then(setItems)
      .catch((e) => {
        onError(e instanceof Error ? e.message : String(e));
        setItems([]);
      });
  }, [refreshKey, onError]);

  const doDelete = async (id: string) => {
    setConfirmId(null);
    try {
      await deleteConversation(id);
      setItems((curr) => (curr ? curr.filter((c) => c.id !== id) : curr));
      onDeleted?.(id);
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  if (items === null) {
    return (
      <div className="flex items-center gap-2 text-xs text-ink-dim px-2 py-3">
        <Loader2 size={12} className="animate-spin" />
        Loading...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-xs text-ink-dim px-2 py-3">
        No previous conversations.
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      {items.map((conv) => {
        const isActive = conv.id === activeId;
        const confirming = confirmId === conv.id;
        return (
          <div
            key={conv.id}
            className={`group w-full rounded-md text-sm flex items-center transition-colors ${
              isActive
                ? "bg-bg-card text-ink"
                : "text-ink-muted hover:bg-bg-card/60"
            }`}
          >
            <button
              onClick={() => onSelect(conv.id)}
              className="flex-1 min-w-0 text-left pl-2 py-1.5 flex items-center gap-2"
            >
              <MessageSquare size={13} className="flex-shrink-0" />
              <span className="flex-1 truncate">{conv.title}</span>
            </button>
            {confirming ? (
              <div className="flex items-center pr-1">
                <button
                  onClick={() => doDelete(conv.id)}
                  className="p-1 text-red-400 hover:text-red-300 transition-colors"
                  aria-label="Confirm"
                  title="Confirm delete"
                >
                  <Check size={13} />
                </button>
                <button
                  onClick={() => setConfirmId(null)}
                  className="p-1 text-ink-dim hover:text-ink transition-colors"
                  aria-label="Cancel"
                  title="Cancel"
                >
                  <X size={13} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmId(conv.id)}
                className="pr-2 pl-1 py-1.5 opacity-0 group-hover:opacity-100 text-ink-dim hover:text-red-400 transition-opacity"
                aria-label="Delete conversation"
              >
                <Trash2 size={12} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
