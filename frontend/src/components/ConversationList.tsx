import { useEffect, useState } from "react";
import { MessageSquare, Trash2, Loader2 } from "lucide-react";
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
}

export default function ConversationList({
  activeId,
  onSelect,
  refreshKey,
  onError,
}: Props) {
  const [items, setItems] = useState<Conversation[] | null>(null);

  useEffect(() => {
    listConversations()
      .then(setItems)
      .catch((e) => {
        onError(e instanceof Error ? e.message : String(e));
        setItems([]);
      });
  }, [refreshKey, onError]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      setItems((curr) => (curr ? curr.filter((c) => c.id !== id) : curr));
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
        return (
          <button
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`group w-full text-left px-2 py-1.5 rounded-md text-sm flex items-start gap-2 transition-colors ${
              isActive
                ? "bg-bg-card text-ink"
                : "text-ink-muted hover:bg-bg-card/60"
            }`}
          >
            <MessageSquare size={13} className="mt-0.5 flex-shrink-0" />
            <span className="flex-1 truncate">{conv.title}</span>
            <button
              onClick={(e) => handleDelete(e, conv.id)}
              className="opacity-0 group-hover:opacity-100 text-ink-dim hover:text-red-400 transition-opacity"
              aria-label="Delete"
            >
              <Trash2 size={12} />
            </button>
          </button>
        );
      })}
    </div>
  );
}
