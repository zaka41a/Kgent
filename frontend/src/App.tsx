import { useCallback, useEffect, useRef, useState } from "react";
import {
  Settings as SettingsIcon,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  ArrowDown,
} from "lucide-react";

import Sidebar from "./components/Sidebar";
import Message, { ChatMessage } from "./components/Message";
import InputBox from "./components/InputBox";
import EmptyState from "./components/EmptyState";
import ProviderPicker from "./components/ProviderPicker";
import SettingsModal from "./components/SettingsModal";
import ToastContainer, { ToastData } from "./components/Toast";
import IngestModal, { IngestResult } from "./components/IngestModal";

import {
  askStream,
  createConversation,
  getConversation,
  getProviders,
  getStoreInfo,
  type Chunk,
  type ChatHistoryMessage,
  type ProviderInfo,
  type StoreInfo,
} from "./lib/api";
import {
  loadSelection,
  saveSelection,
  loadTheme,
  saveTheme,
  loadSidebarOpen,
  saveSidebarOpen,
  type Theme,
} from "./lib/storage";

export default function App() {
  const [info, setInfo] = useState<StoreInfo | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [provider, setProvider] = useState<string>("ollama");
  const [model, setModel] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [conversationsRefresh, setConversationsRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(loadSidebarOpen);
  const [atBottom, setAtBottom] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);
  const toastSeq = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const atBottomRef = useRef(true);

  const pushToast = useCallback((kind: "success" | "error", message: string) => {
    const id = ++toastSeq.current;
    setToasts((prev) => [...prev, { id, kind, message }]);
  }, []);

  const dismissToast = (id: number) =>
    setToasts((prev) => prev.filter((t) => t.id !== id));

  const refreshProviders = useCallback(async () => {
    try {
      const list = await getProviders();
      setProviders(list);
      const stored = loadSelection();
      if (stored && list.find((p) => p.name === stored.provider)?.available) {
        setProvider(stored.provider);
        setModel(stored.model);
        return;
      }
      const firstAvailable = list.find((p) => p.available && p.models.length > 0);
      if (firstAvailable) {
        setProvider(firstAvailable.name);
        setModel(firstAvailable.models[0]);
      }
    } catch (e) {
      pushToast("error", e instanceof Error ? e.message : String(e));
    }
  }, [pushToast]);

  useEffect(() => {
    getStoreInfo().then(setInfo).catch(() => setInfo(null));
    refreshProviders();
  }, [refreshProviders]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.classList.toggle("light", theme === "light");
    saveTheme(theme);
  }, [theme]);

  const toggleTheme = () =>
    setTheme((t) => (t === "dark" ? "light" : "dark"));

  const toggleSidebar = () =>
    setSidebarOpen((open) => {
      saveSidebarOpen(!open);
      return !open;
    });

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    const el = scroller.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  };

  const handleScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    atBottomRef.current = near;
    setAtBottom(near);
  };

  useEffect(() => {
    if (atBottomRef.current) scrollToBottom();
  }, [messages]);

  const handleProviderChange = (p: string, m: string) => {
    setProvider(p);
    setModel(m);
    saveSelection({ provider: p, model: m });
  };

  const ensureConversation = async (): Promise<string> => {
    if (activeConvId) return activeConvId;
    const conv = await createConversation({ provider, model });
    setActiveConvId(conv.id);
    setConversationsRefresh((n) => n + 1);
    return conv.id;
  };

  const submit = async (text: string, regenerateFromIndex?: number) => {
    let history: ChatHistoryMessage[];
    let working: ChatMessage[];

    if (regenerateFromIndex !== undefined) {
      working = messages.slice(0, regenerateFromIndex);
      history = working
        .filter((m) => !m.pending && !m.error)
        .map((m) => ({ role: m.role, content: m.content }));
    } else {
      const userMsg: ChatMessage = { role: "user", content: text };
      working = [...messages, userMsg];
      history = working
        .filter((m) => !m.pending && !m.error)
        .slice(0, -1)
        .map((m) => ({ role: m.role, content: m.content }));
    }

    let convId: string;
    try {
      convId = await ensureConversation();
    } catch (e) {
      pushToast("error", e instanceof Error ? e.message : String(e));
      return;
    }

    const pendingMsg: ChatMessage = {
      role: "assistant",
      content: "",
      pending: true,
      streaming: true,
    };
    setMessages([...working, pendingMsg]);
    atBottomRef.current = true;
    setAtBottom(true);
    setBusy(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const startTime = performance.now();
    let buffer = "";
    let receivedAny = false;

    await askStream(
      {
        question: text,
        provider,
        model,
        history,
        conversation_id: convId,
      },
      {
        onContext: (context, p, m) => {
          setMessages((curr) => {
            const next = [...curr];
            next[next.length - 1] = {
              ...next[next.length - 1],
              context,
              provider: p,
              model: m,
              pending: false,
            };
            return next;
          });
        },
        onDelta: (delta) => {
          buffer += delta;
          receivedAny = true;
          setMessages((curr) => {
            const next = [...curr];
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: buffer,
              pending: false,
            };
            return next;
          });
        },
        onError: (msg) => {
          setMessages((curr) => {
            const next = [...curr];
            next[next.length - 1] = {
              role: "assistant",
              content: msg,
              error: true,
            };
            return next;
          });
          pushToast("error", msg);
        },
        onDone: () => {
          const elapsed = Math.round(performance.now() - startTime);
          setMessages((curr) => {
            const next = [...curr];
            const last = next[next.length - 1];
            if (last && !last.error) {
              next[next.length - 1] = {
                ...last,
                streaming: false,
                pending: false,
                content: receivedAny ? last.content : last.content || "(no response)",
                elapsedMs: elapsed,
              };
            }
            return next;
          });
          setBusy(false);
          abortRef.current = null;
          setConversationsRefresh((n) => n + 1);
        },
      },
      controller.signal,
    );
  };

  const handleSubmit = (text: string) => submit(text);

  const handleStop = () => abortRef.current?.abort();

  const handleRegenerate = (assistantIndex: number) => {
    const userMsg = messages[assistantIndex - 1];
    if (!userMsg || userMsg.role !== "user") return;
    submit(userMsg.content, assistantIndex);
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveConvId(null);
  };

  const handleConversationDeleted = (id: string) => {
    if (id === activeConvId) {
      setActiveConvId(null);
      setMessages([]);
    }
  };

  const handleSelectConversation = async (id: string) => {
    if (id === activeConvId) return;
    try {
      const detail = await getConversation(id);
      const loaded: ChatMessage[] = detail.messages.map((m) => {
        let context: Chunk[] | undefined = undefined;
        if (m.context_json) {
          try {
            context = JSON.parse(m.context_json);
          } catch {
            /* ignore parse errors */
          }
        }
        return {
          role: m.role,
          content: m.content,
          context,
          provider: m.provider ?? undefined,
          model: m.model ?? undefined,
          elapsedMs: m.elapsed_ms ?? undefined,
        };
      });
      setActiveConvId(id);
      setMessages(loaded);
    } catch (e) {
      pushToast("error", e instanceof Error ? e.message : String(e));
    }
  };

  const handleSettingsSaved = () => {
    pushToast("success", "Settings saved");
    refreshProviders();
  };

  const handleIngested = (result: IngestResult) => {
    pushToast(
      "success",
      `Indexed ${result.documents} documents (${result.total_chunks} chunks)`,
    );
    getStoreInfo().then(setInfo).catch(() => undefined);
    setMessages([]);
    setActiveConvId(null);
  };

  const lastAssistantIndex = messages.reduce(
    (acc, m, i) => (m.role === "assistant" && !m.error ? i : acc),
    -1,
  );

  return (
    <div className="h-full flex bg-bg text-ink">
      {sidebarOpen && (
        <Sidebar
          info={info}
          activeConvId={activeConvId}
          conversationsRefresh={conversationsRefresh}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenIngest={() => setIngestOpen(true)}
          onError={(msg) => pushToast("error", msg)}
          onConversationDeleted={handleConversationDeleted}
          onGraphBuilt={() => {
            getStoreInfo().then(setInfo).catch(() => undefined);
            pushToast("success", "Entity graph rebuilt.");
          }}
          selectedProvider={provider}
          selectedModel={model}
        />
      )}

      <main className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-border px-4 py-2.5 flex items-center justify-between gap-3">
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-md text-ink-muted hover:text-ink hover:bg-bg-card transition-colors"
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen ? (
              <PanelLeftClose size={16} />
            ) : (
              <PanelLeftOpen size={16} />
            )}
          </button>
          <div className="flex items-center gap-3">
            <ProviderPicker
              providers={providers}
              selectedProvider={provider}
              selectedModel={model}
              onChange={handleProviderChange}
              onOpenSettings={() => setSettingsOpen(true)}
            />
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-md text-ink-muted hover:text-ink hover:bg-bg-card transition-colors"
              aria-label="Toggle theme"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-1.5 rounded-md text-ink-muted hover:text-ink hover:bg-bg-card transition-colors"
              aria-label="Settings"
            >
              <SettingsIcon size={16} />
            </button>
          </div>
        </header>

        <div className="flex-1 relative min-h-0">
          <div
            ref={scroller}
            onScroll={handleScroll}
            className="absolute inset-0 overflow-y-auto"
          >
            {messages.length === 0 ? (
              <EmptyState onSuggest={handleSubmit} />
            ) : (
              <div>
                {messages.map((m, i) => (
                  <Message
                    key={i}
                    message={m}
                    showRegenerate={i === lastAssistantIndex && !busy}
                    onRegenerate={() => handleRegenerate(i)}
                  />
                ))}
              </div>
            )}
          </div>
          {!atBottom && messages.length > 0 && (
            <button
              onClick={() => scrollToBottom()}
              className="absolute bottom-4 left-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-bg-card border border-border shadow-lg flex items-center justify-center text-ink-muted hover:text-ink hover:bg-bg-soft transition-colors"
              aria-label="Scroll to latest"
              title="Scroll to latest"
            >
              <ArrowDown size={16} />
            </button>
          )}
        </div>

        <InputBox
          onSubmit={handleSubmit}
          disabled={busy}
          busy={busy}
          onStop={handleStop}
        />
      </main>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={handleSettingsSaved}
      />
      <IngestModal
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
        onIngested={handleIngested}
        onError={(msg) => pushToast("error", msg)}
      />
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
