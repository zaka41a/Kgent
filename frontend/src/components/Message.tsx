import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { User, Bot, FileText, Copy, Check, RefreshCw } from "lucide-react";
import type { Chunk } from "../lib/api";
import { copyText } from "../lib/clipboard";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  context?: Chunk[];
  pending?: boolean;
  streaming?: boolean;
  error?: boolean;
  provider?: string;
  model?: string;
  elapsedMs?: number;
}

interface Props {
  message: ChatMessage;
  onRegenerate?: () => void;
  showRegenerate?: boolean;
}

export default function Message({ message, onRegenerate, showRegenerate }: Props) {
  const isUser = message.role === "user";
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  const handleCopy = async () => {
    const ok = await copyText(message.content);
    setCopyState(ok ? "copied" : "failed");
    setTimeout(() => setCopyState("idle"), 1500);
  };

  return (
    <div className={`py-6 ${isUser ? "" : "bg-bg-soft/40"} animate-fade-in`}>
      <div className="max-w-3xl mx-auto px-4 flex gap-4">
        <div className="flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center bg-bg-card border border-border">
          {isUser ? <User size={16} /> : <Bot size={16} className="text-accent" />}
        </div>
        <div className="flex-1 min-w-0 prose-chat">
          {message.pending && !message.content ? (
            <div className="dot-pulse pt-2">
              <span></span>
              <span></span>
              <span></span>
            </div>
          ) : message.error ? (
            <div className="text-red-400 text-sm">{message.content}</div>
          ) : (
            <>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
              >
                {message.content}
              </ReactMarkdown>
              {message.streaming && (
                <span className="inline-block w-2 h-4 bg-ink/70 ml-0.5 align-middle animate-pulse" />
              )}
            </>
          )}

          {!isUser && !message.pending && !message.streaming && message.content && !message.error && (
            <div className="mt-2 flex items-center gap-3 text-xs text-ink-dim">
              <button
                onClick={handleCopy}
                className={`flex items-center gap-1 transition-colors ${
                  copyState === "failed" ? "text-red-400" : "hover:text-ink-muted"
                }`}
              >
                {copyState === "copied" ? <Check size={12} /> : <Copy size={12} />}
                {copyState === "copied" ? "Copied" : copyState === "failed" ? "Failed" : "Copy"}
              </button>
              {showRegenerate && onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="flex items-center gap-1 hover:text-ink-muted transition-colors"
                >
                  <RefreshCw size={12} />
                  Regenerate
                </button>
              )}
              {(message.provider || message.elapsedMs) && (
                <span className="ml-auto">
                  {message.provider && message.model && (
                    <>
                      {message.provider}/{message.model}
                    </>
                  )}
                  {message.elapsedMs !== undefined && (
                    <> • {(message.elapsedMs / 1000).toFixed(1)}s</>
                  )}
                </span>
              )}
            </div>
          )}

          {message.context && message.context.length > 0 && (
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-ink-muted hover:text-ink select-none flex items-center gap-1.5">
                <FileText size={13} />
                <span>
                  {message.context.length} source{message.context.length === 1 ? "" : "s"}
                </span>
              </summary>
              <div className="mt-2 space-y-2">
                {message.context.map((c, i) => (
                  <div
                    key={i}
                    className="bg-bg-card border border-border rounded-md p-3 text-xs"
                  >
                    <div className="text-accent font-mono mb-1">
                      {c.doc_path}#{c.index}
                    </div>
                    <div className="text-ink-muted whitespace-pre-wrap line-clamp-6">
                      {c.text.slice(0, 600)}
                      {c.text.length > 600 ? "..." : ""}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
