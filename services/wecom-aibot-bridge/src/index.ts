import AiBot, { generateReqId } from "@wecom/aibot-node-sdk";
import type { WsFrame } from "@wecom/aibot-node-sdk";
import { forwardTextToGateway, textContent, type BridgeConfig, type TextMessageBody } from "./bridge.js";

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function loadConfig(): BridgeConfig & { botId: string; secret: string; wsUrl?: string } {
  return {
    botId: requiredEnv("WECOM_AIBOT_BOT_ID"),
    secret: requiredEnv("WECOM_AIBOT_SECRET"),
    apiUrl: process.env.WECOM_AIBOT_API_URL || "http://127.0.0.1:8787/api/gaokao/chat",
    trustedProxyToken: process.env.WECOM_AIBOT_TRUSTED_PROXY_TOKEN || process.env.TRUSTED_PROXY_TOKEN || "",
    campus: process.env.WECOM_AIBOT_CAMPUS || "all",
    wsUrl: process.env.WECOM_AIBOT_WS_URL || undefined,
  };
}

const config = loadConfig();
const client = new AiBot.WSClient({
  botId: config.botId,
  secret: config.secret,
  wsUrl: config.wsUrl,
  maxReconnectAttempts: -1,
  logger: {
    debug: () => undefined,
    info: (message: string) => console.info(`[wecom-aibot] ${message}`),
    warn: (message: string) => console.warn(`[wecom-aibot] ${message}`),
    error: (message: string) => console.error(`[wecom-aibot] ${message}`),
  },
});

client.on("authenticated", () => {
  console.info("[wecom-aibot] authenticated");
});

client.on("message.text", async (frame: WsFrame) => {
  const body = (frame.body || {}) as TextMessageBody;
  const content = textContent(body);
  if (!content) {
    return;
  }

  const streamId = generateReqId("gaokao");
  try {
    await client.replyStream(frame, streamId, "正在查询公开信息，请稍候...", false);
    const answer = await forwardTextToGateway(body, content, config);
    await client.replyStream(frame, streamId, answer, true);
  } catch (error) {
    console.error("[wecom-aibot] request failed", error instanceof Error ? error.message : String(error));
    await client.replyStream(
      frame,
      streamId,
      "当前服务暂时无法完成查询，请稍后重试或联系工作人员。",
      true,
    );
  }
});

client.on("event.enter_chat", async (frame: WsFrame) => {
  await client.replyWelcome(frame, {
    msgtype: "text",
    text: {
      content: "您好，我可以协助查询学校公开信息与咨询流程。需要办理请假、订餐或报修时，我会引导您进入对应页面。",
    },
  });
});

client.on("error", (error: Error) => {
  console.error("[wecom-aibot] connection error", error.message);
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    client.disconnect();
    process.exit(0);
  });
}

client.connect();

