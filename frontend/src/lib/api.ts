export interface Chunk {
  doc_path: string;
  index: number;
  text: string;
  kind: string;
}

export interface ProviderInfo {
  name: string;
  available: boolean;
  models: string[];
}

export interface StoreInfo {
  count: number;
  store_path: string;
  store_kind: string;
  default_provider: string;
  default_model: string;
  active_repo?: string | null;
  document_count?: number;
  has_graph?: boolean;
}

export interface ApiKeys {
  OPENAI_API_KEY?: string;
  ANTHROPIC_API_KEY?: string;
  GROQ_API_KEY?: string;
  OLLAMA_BASE_URL?: string;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

const KEYS_HEADER = "X-Kgent-Keys";

function loadKeys(): ApiKeys {
  try {
    return JSON.parse(localStorage.getItem("kgent_keys") || "{}") as ApiKeys;
  } catch {
    return {};
  }
}

export function saveKeys(keys: ApiKeys): void {
  localStorage.setItem("kgent_keys", JSON.stringify(keys));
}

export function getKeys(): ApiKeys {
  return loadKeys();
}

function authHeaders(): HeadersInit {
  const keys = loadKeys();
  if (Object.keys(keys).length === 0) return {};
  return { [KEYS_HEADER]: JSON.stringify(keys) };
}

export async function getStoreInfo(): Promise<StoreInfo> {
  const res = await fetch("/api/store/info", { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getProviders(): Promise<ProviderInfo[]> {
  const res = await fetch("/api/providers", { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.providers;
}

export interface AskParams {
  question: string;
  k?: number;
  provider?: string;
  model?: string;
  history?: ChatHistoryMessage[];
  conversation_id?: string;
}

export interface Conversation {
  id: string;
  title: string;
  repo_path: string | null;
  provider: string | null;
  model: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: {
    id: number;
    position: number;
    role: "user" | "assistant";
    content: string;
    context_json: string | null;
    provider: string | null;
    model: string | null;
    elapsed_ms: number | null;
    created_at: string;
  }[];
}

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch("/api/conversations", { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.conversations;
}

export async function createConversation(payload: {
  title?: string;
  provider?: string;
  model?: string;
}): Promise<Conversation> {
  const res = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(`/api/conversations/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface GraphBuildRequest {
  mode: "cooccurrence" | "entity";
  provider?: string;
  model?: string;
}

export interface GraphJob {
  job_id: string;
  state: "pending" | "running" | "completed" | "failed";
  phase: string;
  mode: string;
  processed: number;
  total: number;
  nodes: number;
  edges: number;
  error: string | null;
}

export async function startGraphBuild(req: GraphBuildRequest): Promise<{ job_id: string }> {
  const res = await fetch("/api/graph/build", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getGraphStatus(jobId: string): Promise<GraphJob> {
  const res = await fetch(`/api/graph/status/${jobId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`/api/conversations/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export interface AskResponse {
  answer: string;
  context: Chunk[];
  provider: string;
  model: string;
  elapsed_ms: number;
}

export async function ask(params: AskParams): Promise<AskResponse> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    throw new Error(await formatErrorBody(res));
  }
  return res.json();
}

async function formatErrorBody(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (!text) return `HTTP ${res.status}`;
  try {
    const parsed = JSON.parse(text);
    const detail = parsed.detail;
    if (detail && typeof detail === "object") {
      const provider = detail.provider ? ` [${detail.provider}` + (detail.model ? `/${detail.model}` : "") + "]" : "";
      const hint = detail.hint ? `\n${detail.hint}` : "";
      return `${detail.error || "Request failed"}${provider}${hint}`;
    }
    return detail || text;
  } catch {
    return text || `HTTP ${res.status}`;
  }
}

export interface StreamHandlers {
  onContext: (context: Chunk[], provider: string, model: string) => void;
  onDelta: (text: string) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

export async function askStream(
  params: AskParams,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(params),
      signal,
    });
  } catch (e) {
    if (isAbortError(e)) {
      handlers.onDone();
      return;
    }
    handlers.onError(e instanceof Error ? e.message : String(e));
    handlers.onDone();
    return;
  }

  if (!res.ok || !res.body) {
    handlers.onError(await formatErrorBody(res));
    handlers.onDone();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const evt of events) {
        const line = evt.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        try {
          const data = JSON.parse(payload);
          if (data.type === "context") {
            handlers.onContext(data.context, data.provider, data.model);
          } else if (data.type === "delta") {
            handlers.onDelta(data.content);
          } else if (data.type === "error") {
            const provider = data.provider ? ` [${data.provider}` + (data.model ? `/${data.model}` : "") + "]" : "";
            const hint = data.hint ? `\n${data.hint}` : "";
            const msg = `${data.error || data.message || "Stream failed"}${provider}${hint}`;
            handlers.onError(msg);
          } else if (data.type === "done") {
            handlers.onDone();
            return;
          }
        } catch {
          /* ignore malformed event */
        }
      }
    }
  } catch (e) {
    if (!isAbortError(e)) {
      handlers.onError(e instanceof Error ? e.message : String(e));
    }
  }
  handlers.onDone();
}
