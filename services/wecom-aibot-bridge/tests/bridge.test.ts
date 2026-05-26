import { describe, expect, it, vi } from "vitest";
import {
  forwardTextToGateway,
  sessionIdForMessage,
  textContent,
  userIdForMessage,
  type BridgeConfig,
  type TextMessageBody,
} from "../src/bridge.js";

const body: TextMessageBody = {
  chatid: "group-001",
  from: { userid: "teacher-001" },
  text: { content: "学校报名流程是什么？" },
};

const config: BridgeConfig = {
  apiUrl: "http://api.local/api/gaokao/chat",
  trustedProxyToken: "trusted-token",
  campus: "school_demo",
};

describe("wecom aibot bridge", () => {
  it("extracts text and generates stable opaque identifiers", () => {
    expect(textContent(body)).toBe("学校报名流程是什么？");
    expect(sessionIdForMessage(body)).toMatch(/^wecom_[a-f0-9]{20}$/);
    expect(userIdForMessage(body)).toMatch(/^wecom_user_[a-f0-9]{20}$/);
    expect(sessionIdForMessage(body)).not.toContain("group-001");
  });

  it("forwards a customer identity to the public chat gateway", async () => {
    const fetchFn = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: "请按公开流程办理。" }),
    });

    const answer = await forwardTextToGateway(body, textContent(body), config, fetchFn as unknown as typeof fetch);
    const [, request] = fetchFn.mock.calls[0];
    const headers = request.headers as Record<string, string>;
    const payload = JSON.parse(String(request.body));

    expect(answer).toBe("请按公开流程办理。");
    expect(headers["x-gaokao-role"]).toBe("customer");
    expect(headers["x-gaokao-trusted-proxy"]).toBe("trusted-token");
    expect(payload.message).toBe("学校报名流程是什么？");
    expect(payload).not.toHaveProperty("role");
  });

  it("returns a public-safe response when retrieval produces no answer", async () => {
    const fetchFn = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: "", recommended_actions: ["人工跟进"] }),
    });

    const answer = await forwardTextToGateway(body, textContent(body), config, fetchFn as unknown as typeof fetch);

    expect(answer).toContain("暂未找到可直接答复的公开信息");
  });
});
