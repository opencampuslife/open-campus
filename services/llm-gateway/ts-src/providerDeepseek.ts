export type TransportResponse = {
  status: number;
  body: string;
};

export type Transport = (
  url: string,
  options: { method: string; headers: Record<string, string>; body: string },
  timeout: number,
) => Promise<TransportResponse>;

export class HttpError extends Error {
  statusCode: number;
  responseBody: string;
  constructor(statusCode: number, responseBody: string) {
    super(`HTTP ${statusCode}`);
    this.statusCode = statusCode;
    this.responseBody = responseBody;
    this.name = "HttpError";
  }
}

export type ChatCompletionOptions = {
  model: string;
  base_url?: string;
  api_key?: string;
  timeout?: number;
  transport?: Transport;
};

function pyDictGet<T>(d: Record<string, unknown>, key: string): T {
  if (!(key in d)) {
    const err = new Error(`'${key}'`);
    err.name = "KeyError";
    throw err;
  }
  return d[key] as T;
}

function pyListGet<T>(arr: T[], index: number): T {
  if (index >= arr.length) {
    const err = new Error("list index out of range");
    err.name = "IndexError";
    throw err;
  }
  return arr[index] as T;
}

function parseDeepseekJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch (e: unknown) {
    const err = new Error((e as Error).message);
    err.name = "JSONDecodeError";
    throw err;
  }
}

function pyRuntimeError(message: string): Error {
  const err = new Error(message);
  err.name = "RuntimeError";
  return err;
}

async function defaultTransport(
  url: string,
  options: { method: string; headers: Record<string, string>; body: string },
  timeout: number,
): Promise<TransportResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout * 1000);
  try {
    const resp = await fetch(url, { ...options, signal: controller.signal });
    const body = await resp.text();
    if (!resp.ok) {
      throw new HttpError(resp.status, body);
    }
    return { status: resp.status, body };
  } finally {
    clearTimeout(timer);
  }
}

import { deepseekApiKey, deepseekBaseUrl } from "./config.js";

export async function chatCompletion(
  messages: Array<{ role: string; content: string }>,
  options: ChatCompletionOptions,
): Promise<string> {
  const apiKey = options.api_key ?? deepseekApiKey();
  if (!apiKey) {
    throw pyRuntimeError("DEEPSEEK_API_KEY is not set");
  }

  const baseUrl = (options.base_url ?? deepseekBaseUrl()).replace(/\/+$/, "");
  const url = `${baseUrl}/chat/completions`;

  const payload: Record<string, unknown> = {
    model: options.model,
    messages: messages,
    stream: false,
  };
  const body = JSON.stringify(payload);

  const transportFn: Transport = options.transport ?? defaultTransport;

  let raw: string;
  try {
    const response = await transportFn(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body,
    }, options.timeout ?? 30.0);
    raw = response.body;
  } catch (e: unknown) {
    if (e instanceof HttpError) {
      throw pyRuntimeError(`DeepSeek API error ${e.statusCode}: ${e.responseBody}`);
    }
    const msg = e instanceof Error ? e.message : String(e);
    throw pyRuntimeError(`DeepSeek API network error: ${msg}`);
  }

  const data = parseDeepseekJson(raw) as Record<string, unknown>;
  const choices = pyDictGet<Array<Record<string, unknown>>>(data, "choices");
  const first = pyListGet(choices, 0);
  const message = pyDictGet<Record<string, unknown>>(first, "message");
  const content = pyDictGet<string>(message, "content");
  return content;
}
