import { apiFetch } from "@/lib/api-token";

/** 不经 hey-api 生成. */

export type AgentTokenUsage = {
  input: number;
  cache_read: number;
  cache_write: number;
  output: number;
  requests?: number;
};

export type AgentSseEvent =
  | { type: "text_delta"; text: string; seq?: number }
  | { type: "tool_call"; tool_call_id: string; name: string; args: unknown; seq?: number }
  | { type: "tool_result"; tool_call_id: string; name: string; result: unknown; seq?: number }
  | {
      type: "needs_approval";
      approval_id: string;
      sql: string;
      tool: string;
      entity?: "metadata" | "actor" | null;
      name?: string | null;
      reason?: string;
      seq?: number;
    }
  | {
      type: "done";
      saved_query_ids: number[];
      status: string;
      usage?: AgentTokenUsage;
      seq?: number;
    }
  | { type: "error"; message: string; seq?: number }
  | { type: "cancelled"; seq?: number }
  | { type: "user_message"; text: string; seq?: number }
  | { type: "assistant_message"; text: string; usage?: AgentTokenUsage; seq?: number };

function apiBase(): string {
  return import.meta.env.VITE_API_URL || "";
}

function asSseEvent(value: unknown): AgentSseEvent | null {
  if (value === null || typeof value !== "object" || !("type" in value)) return null;
  const type = (value as { type: unknown }).type;
  if (typeof type !== "string") return null;
  // SSE 行已是服务端 model_dump; 按 type 判别联合
  return value as AgentSseEvent;
}

async function* parseSseStream(body: ReadableStream<Uint8Array>): AsyncGenerator<AgentSseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((l) => l.trim())
        .find((l) => l.startsWith("data:"));
      if (!line) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      try {
        const ev = asSseEvent(JSON.parse(raw));
        if (ev) yield ev;
      } catch {
        // ignore malformed
      }
    }
  }
}

export async function* streamAgentMessage(
  sessionId: number,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentSseEvent> {
  const res = await apiFetch(`${apiBase()}/api/agent/sessions/${sessionId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    yield { type: "error", message: text || `HTTP ${res.status}` };
    return;
  }
  if (!res.body) {
    yield { type: "error", message: "empty stream body" };
    return;
  }
  yield* parseSseStream(res.body);
}

export async function* streamAgentApprove(
  sessionId: number,
  approvalIds: readonly string[],
  slowTimeoutMs = 60_000,
  signal?: AbortSignal,
): AsyncGenerator<AgentSseEvent> {
  const res = await apiFetch(`${apiBase()}/api/agent/sessions/${sessionId}/approve/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ approval_ids: [...approvalIds], slow_timeout_ms: slowTimeoutMs }),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    yield { type: "error", message: text || `HTTP ${res.status}` };
    return;
  }
  if (!res.body) {
    yield { type: "error", message: "empty stream body" };
    return;
  }
  yield* parseSseStream(res.body);
}

export async function* streamAgentReject(
  sessionId: number,
  approvalId: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentSseEvent> {
  const res = await apiFetch(`${apiBase()}/api/agent/sessions/${sessionId}/reject/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ approval_id: approvalId }),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    yield { type: "error", message: text || `HTTP ${res.status}` };
    return;
  }
  if (!res.body) {
    yield { type: "error", message: "empty stream body" };
    return;
  }
  yield* parseSseStream(res.body);
}

/** 刷新/切换页面后续订: GET .../events/stream?after= */
export async function* streamAgentEvents(
  sessionId: number,
  after: number,
  signal?: AbortSignal,
): AsyncGenerator<AgentSseEvent> {
  const res = await apiFetch(
    `${apiBase()}/api/agent/sessions/${sessionId}/events/stream?after=${encodeURIComponent(String(after))}`,
    {
      method: "GET",
      headers: { Accept: "text/event-stream" },
      signal,
    },
  );
  if (!res.ok) {
    const text = await res.text();
    yield { type: "error", message: text || `HTTP ${res.status}` };
    return;
  }
  if (!res.body) {
    yield { type: "error", message: "empty stream body" };
    return;
  }
  yield* parseSseStream(res.body);
}
