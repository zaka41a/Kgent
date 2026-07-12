import { useState, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { User, FileText, Copy, Check, RefreshCw } from "lucide-react";
import type { Chunk } from "../lib/api";
import { copyText } from "../lib/clipboard";
import Logo from "./Logo";

const REMARK_PLUGINS = [remarkGfm];
const REHYPE_PLUGINS = [rehypeHighlight];

// Parsing and highlighting markdown is the expensive part of a message. Memoizing
// it on `content` means that while an answer streams, only the growing message
// re-parses; every earlier message is skipped instead of re-rendered per token.
const MarkdownBody = memo(function MarkdownBody({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS}>
      {content}
    </ReactMarkdown>
  );
});

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

const META = "font-mono text-[0.62rem] uppercase tracking-[0.12em] text-ink-dim";

export default function Message({ message, onRegenerate, showRegenerate }: Props) {
  const isUser = message.role === "user";
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  const handleCopy = async () => {
    const ok = await copyText(message.content);
    setCopyState(ok ? "copied" : "failed");
    setTimeout(() => setCopyState("idle"), 1500);
  };

  const sources = message.context?.length ?? 0;
  const sourceFiles: [string, number][] = message.context
    ? Array.from(
        message.context.reduce(
          (m, c) => m.set(c.doc_path, (m.get(c.doc_path) ?? 0) + 1),
          new Map<string, number>(),
        ),
      )
    : [];

  return (
    <div className={`py-6 ${isUser ? "" : "bg-bg-soft/40"} animate-fade-in`}>
      <div className="max-w-3xl mx-auto px-4 flex gap-4">
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-bg-card border ${
            isUser ? "border-border text-ink-muted" : "border-accent/40 text-accent"
          }`}
        >
          {isUser ? <User size={15} /> : <Logo className="w-4 h-4" />}
        </div>

        <div className="flex-1 min-w-0">
          <div className={`${META} mb-1.5`}>
            {isUser
              ? "You"
              : `kgent${sources > 0 ? ` · grounded in ${sources} passage${sources === 1 ? "" : "s"}` : ""}`}
          </div>

          <div className="prose-chat">
            {message.pending && !message.content ? (
              <div className="dot-pulse pt-1">
                <span></span>
                <span></span>
                <span></span>
              </div>
            ) : message.error ? (
              <div className="text-red-400 text-sm">{message.content}</div>
            ) : (
              <>
                <MarkdownBody content={message.content} />
                {message.streaming && (
                  <span className="inline-block w-2 h-4 bg-ink/70 ml-0.5 align-middle animate-pulse" />
                )}
              </>
            )}
          </div>

          {!isUser && !message.pending && !message.streaming && message.content && !message.error && (
            <div className="mt-2.5 flex items-center gap-4 font-mono text-[0.7rem] text-ink-dim">
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
              {(message.provider || message.elapsedMs !== undefined) && (
                <span className="ml-auto">
                  {message.provider && message.model && (
                    <>
                      {message.provider}/{message.model}
                    </>
                  )}
                  {message.elapsedMs !== undefined && (
                    <> · {(message.elapsedMs / 1000).toFixed(1)}s</>
                  )}
                </span>
              )}
            </div>
          )}

          {sources > 0 && message.context && (
            <div className="mt-3">
              <div className="flex flex-wrap gap-2">
                {sourceFiles.map(([path, n]) => {
                  const name = path.split("/").pop() || path;
                  return (
                    <span
                      key={path}
                      title={path}
                      className="inline-flex items-center gap-1.5 font-mono text-[0.72rem] text-ink-muted border border-border rounded-full px-2.5 py-1 bg-bg-card"
                    >
                      <i className="w-1.5 h-1.5 rounded-full bg-accent inline-block flex-none" />
                      {name}
                      {n > 1 && <span className="text-ink-dim">×{n}</span>}
                    </span>
                  );
                })}
              </div>

              <details className="mt-2">
                <summary className="cursor-pointer select-none flex items-center gap-1.5 font-mono text-xs text-ink-dim hover:text-ink-muted">
                  <FileText size={12} />
                  <span>
                    {sources} source{sources === 1 ? "" : "s"}
                  </span>
                </summary>
                <div className="mt-2 space-y-2">
                  {message.context.map((c, i) => (
                    <div
                      key={i}
                      className="bg-bg-card border border-border rounded-lg p-3 text-xs"
                    >
                      <div className="text-ink-muted whitespace-pre-wrap line-clamp-6">
                        {c.text.slice(0, 600)}
                        {c.text.length > 600 ? "..." : ""}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
