import {
  Plus,
  FileText,
  Database,
  Cpu,
  Settings as SettingsIcon,
  FolderPlus,
  FolderGit2,
} from "lucide-react";
import type { StoreInfo } from "../lib/api";
import ConversationList from "./ConversationList";

interface Props {
  info: StoreInfo | null;
  activeConvId: string | null;
  conversationsRefresh: number;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
  onOpenIngest: () => void;
  onError: (msg: string) => void;
}

export default function Sidebar({
  info,
  activeConvId,
  conversationsRefresh,
  onSelectConversation,
  onNewChat,
  onOpenSettings,
  onOpenIngest,
  onError,
}: Props) {
  const repoLabel = info?.active_repo
    ? info.active_repo.split("/").slice(-2).join("/")
    : "no repository indexed";

  return (
    <aside className="hidden md:flex md:w-72 flex-col bg-bg-soft border-r border-border">
      <div className="p-3 border-b border-border space-y-2">
        <div className="flex items-center gap-2 px-1 pb-2">
          <img src="/logo.svg" alt="kgent" className="w-7 h-7" />
          <span className="font-semibold text-ink">
            <span className="text-accent">k</span>gent
          </span>
        </div>
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 rounded-md border border-border bg-bg-card px-3 py-2 text-sm hover:bg-bg-card/80 transition-colors"
        >
          <Plus size={16} />
          <span>New chat</span>
        </button>
        <button
          onClick={onOpenIngest}
          className="w-full flex items-center gap-2 rounded-md border border-accent/40 bg-accent/10 text-accent px-3 py-2 text-sm hover:bg-accent/20 transition-colors"
        >
          <FolderPlus size={16} />
          <span>Add repository</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-3">
          <div className="text-xs uppercase tracking-wider text-ink-dim mb-2 px-2">
            Conversations
          </div>
          <ConversationList
            activeId={activeConvId}
            onSelect={onSelectConversation}
            refreshKey={conversationsRefresh}
            onError={onError}
          />
        </div>

        <div className="border-t border-border p-3 text-sm text-ink-muted">
          <div className="mb-3">
            <div className="text-xs uppercase tracking-wider text-ink-dim mb-2">
              Active repository
            </div>
            <div className="flex items-start gap-2 mb-1">
              <FolderGit2 size={14} className="mt-0.5 flex-shrink-0" />
              <span className="break-all text-ink/90" title={info?.active_repo ?? ""}>
                {repoLabel}
              </span>
            </div>
            {info?.document_count ? (
              <div className="text-xs text-ink-dim ml-6">
                {info.document_count} documents
              </div>
            ) : null}
          </div>

          <div className="mb-3">
            <div className="text-xs uppercase tracking-wider text-ink-dim mb-2">
              Index
            </div>
            <div className="flex items-center gap-2 mb-1">
              <FileText size={14} />
              <span>{info ? `${info.count} chunks` : "Loading..."}</span>
              {info?.has_graph && (
                <span className="text-xs text-accent ml-1">+ graph</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-ink-dim truncate">
              <Database size={12} />
              <span className="truncate">{info?.store_kind ?? ""}</span>
            </div>
          </div>

          <div>
            <div className="text-xs uppercase tracking-wider text-ink-dim mb-2">
              Default model
            </div>
            <div className="flex items-center gap-2">
              <Cpu size={14} />
              <span>{info?.default_model || "..."}</span>
            </div>
            <div className="text-xs text-ink-dim mt-1 ml-6">
              via {info?.default_provider ?? ""}
            </div>
          </div>
        </div>
      </div>

      <div className="p-3 border-t border-border flex items-center justify-between text-xs text-ink-dim">
        <span><span className="text-accent">k</span>gent v0.1.0</span>
        <button
          onClick={onOpenSettings}
          className="flex items-center gap-1 hover:text-ink-muted transition-colors"
        >
          <SettingsIcon size={12} />
          Settings
        </button>
      </div>
    </aside>
  );
}
