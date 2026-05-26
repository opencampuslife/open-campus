import { createHash } from "node:crypto";

export type TextMessageBody = {
  chatid?: string;
  chattype?: "single" | "group";
  from?: { userid?: string };
  text?: { content?: string };
};

export type BridgeConfig = {
  apiUrl: string;
  trustedProxyToken: string;
  campus: string;
};

type ChatResponse = {
  answer?: string;
  recommended_actions?: string[];
};

const NO_PUBLIC_ANSWER =
  "暂未找到可直接答复的公开信息。请补充您想了解的具体事项，或联系学校工作人员协助处理。";

function stableId(value: string): string {
  return createHash("sha256").update(value).digest("hex").slice(0, 20);
}

export function textContent(body: TextMessageBody | undefined): string {
  return String(body?.text?.content || "").trim();
}

export function sessionIdForMessage(body: TextMessageBody): string {
  const source = body.chatid || body.from?.userid || "anonymous";
  return `wecom_${stableId(source)}`;
}

export function userIdForMessage(body: TextMessageBody): string {
  return `wecom_user_${stableId(body.from?.userid || "anonymous")}`;
}

export async function forwardTextToGateway(
  body: TextMessageBody,
  content: string,
  config: BridgeConfig,
  fetchFn: typeof fetch = fetch,
): Promise<string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "x-gaokao-user-id": userIdForMessage(body),
    "x-gaokao-role": "customer",
    "x-gaokao-campus": config.campus,
    "x-gaokao-auth-level": "wecom_aibot",
  };
  if (config.trustedProxyToken) {
    headers["x-gaokao-trusted-proxy"] = config.trustedProxyToken;
  }

  const response = await fetchFn(config.apiUrl, {
    method: "POST",
    headers,
    body: JSON.stringify({
      session_id: sessionIdForMessage(body),
      message: content,
    }),
  });

  const result = (await response.json()) as ChatResponse & { error?: string };
  if (!response.ok) {
    throw new Error(result.error || `Gateway request failed (${response.status})`);
  }
  return result.answer?.trim() || NO_PUBLIC_ANSWER;
}
