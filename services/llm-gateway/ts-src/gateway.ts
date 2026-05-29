import { LLMRequestSchema, llmRequestToPolicyDict } from "./schemas.js";
import { validateLlmRequest } from "./promptGuard.js";
import { routeModel } from "./modelRouter.js";
import { chatCompletion } from "./providerDeepseek.js";
import { logLlmCall } from "./llmLogger.js";
import { llmEnabled } from "./config.js";
import type { Transport } from "./providerDeepseek.js";

function pyRepr(val: unknown): string {
  if (val === null) return "None";
  if (typeof val === "string") return `'${val}'`;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (Array.isArray(val)) {
    const items = val.map(v => pyRepr(v));
    return `[${items.join(", ")}]`;
  }
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    const entries = Object.entries(obj);
    const inner = entries.map(([k, v]) => `'${k}': ${pyRepr(v)}`);
    return `{${inner.join(", ")}}`;
  }
  return String(val);
}

function buildMessages(request: Record<string, unknown>): Array<{ role: string; content: string }> {
  const scope = (request["scope"] ?? {}) as Record<string, unknown>;
  const system = "你是复读学校招生问答 Agent。只能使用提供的 allowed evidence 回答。不要编造政策、价格、名额或录取结果。不得承诺固定提分或保证录取。如果角色是 visitor/student/parent，不得输出 internal/L3/L4 内容。如果角色是 sales 且证据含 internal 内容，必须标注\u201c内部参考\u201d，并提醒不要原样对外发送。回答末尾用\u201c来源：\u201d列出证据标题。";
  const role = "role" in scope ? String(scope["role"] ?? "None") : "None";
  const campus = "campus" in scope ? String(scope["campus"] ?? "None") : "None";
  const intent = "intent" in request ? String(request["intent"] ?? "None") : "None";
  const message = "message" in request ? String(request["message"] ?? "None") : "None";
  const evidence = "evidence" in request ? pyRepr(request["evidence"]) : "None";
  const user = `用户角色：${role}\n校区：${campus}\n意图：${intent}\n用户问题：${message}\nallowed evidence：${evidence}\n`;
  return [
    { role: "system", content: system },
    { role: "user", content: user },
  ];
}

export async function generateAdmissionsAnswer(
  projectRoot: string,
  request: Record<string, unknown>,
  transport?: Transport,
): Promise<string | null> {
  if (!llmEnabled() && transport === undefined) {
    return null;
  }

  const parsed = LLMRequestSchema.parse(request);
  const policyRequest = llmRequestToPolicyDict(parsed);
  const { valid, violations } = validateLlmRequest(policyRequest);
  if (!valid) {
    logLlmCall(projectRoot, {
      status: "blocked",
      blocked_by: "prompt_guard",
      violations,
      request: policyRequest,
    });
    return null;
  }

  const route = routeModel("admissions_answer", { role: parsed.user_role });
  const messages = buildMessages(policyRequest);

  let answer: string;
  try {
    answer = await chatCompletion(messages, {
      model: route["model"]!,
      transport,
    });
  } catch (exc: unknown) {
    const errMsg = exc instanceof Error ? exc.message : String(exc);
    logLlmCall(projectRoot, {
      status: "error",
      route,
      error: errMsg,
      request: policyRequest,
    });
    return null;
  }

  logLlmCall(projectRoot, {
    status: "ok",
    route,
    request: policyRequest,
    answer,
  });
  return answer;
}
