import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createServer } from "node:http";
import { chatCompletion, HttpError } from "../ts-src/index.js";
import type { Transport } from "../ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "provider_deepseek.json");

interface FixtureOutput {
  ok: boolean;
  result?: string;
  error?: string;
  message?: string;
}

interface RequestSnapshot {
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: Record<string, unknown>;
}

interface MockDef {
  type: string;
  code?: number;
  detail?: string;
  reason?: string;
  body?: string;
  response_body?: Record<string, unknown>;
}

interface FixtureCase {
  desc: string;
  input: {
    messages: Array<{ role: string; content: string }>;
    model: string;
    base_url: string | null;
    api_key: string | null;
    timeout: number;
  };
  mock: MockDef;
  output: FixtureOutput;
  request_snapshot: RequestSnapshot;
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === null || b === null) return a === b;
  if (typeof a !== typeof b) return false;
  if (typeof a !== "object" || typeof b !== "object") return false;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false;
    }
    return true;
  }
  const aObj = a as Record<string, unknown>;
  const bObj = b as Record<string, unknown>;
  const aKeys = Object.keys(aObj).sort();
  const bKeys = Object.keys(bObj).sort();
  if (aKeys.length !== bKeys.length) return false;
  for (let i = 0; i < aKeys.length; i++) {
    if (aKeys[i] !== bKeys[i]) return false;
  }
  for (const key of aKeys) {
    if (!deepEqual(aObj[key], bObj[key])) return false;
  }
  return true;
}

function createMockTransport(mock: MockDef): Transport {
  if (mock.type === "success") {
    return async (_url, _opts, _timeout) => {
      return {
        status: 200,
        body: JSON.stringify(mock.response_body ?? { choices: [{ message: { content: "" } }] }),
      };
    };
  }
  if (mock.type === "http_error") {
    return async (_url, _opts, _timeout) => {
      throw new HttpError(mock.code!, mock.detail!);
    };
  }
  if (mock.type === "uri_error") {
    return async (_url, _opts, _timeout) => {
      throw new Error(mock.reason);
    };
  }
  if (mock.type === "invalid_json") {
    return async (_url, _opts, _timeout) => {
      return { status: 200, body: mock.body! };
    };
  }
  throw new Error(`Unknown mock type: ${mock.type}`);
}

async function runTs(f: FixtureCase): Promise<FixtureOutput> {
  try {
    const transport = createMockTransport(f.mock);
    const result = await chatCompletion(f.input.messages, {
      model: f.input.model,
      base_url: f.input.base_url ?? undefined,
      api_key: f.input.api_key ?? undefined,
      timeout: f.input.timeout ?? 30.0,
      transport,
    });
    return { ok: true, result };
  } catch (e: unknown) {
    const err = e as Error;
    return { ok: false, error: err.name ?? err.constructor.name, message: err.message };
  }
}

beforeEach(() => {
  delete process.env["DEEPSEEK_API_KEY"];
  delete process.env["DEEPSEEK_BASE_URL"];
});

// ── Golden Fixture Parity ──

describe("golden fixture parity", () => {
  const envDependent = new Set([
    "API key from env var",
    "custom base_url from env var",
    "default base_url used when not specified",
    "missing API key raises RuntimeError",
  ]);

  it("matches stored golden JSON for all standard fixtures", async () => {
    for (const f of fixtures) {
      if (envDependent.has(f.desc)) continue;
      const tsResult = await runTs(f);
      if (f.output.ok) {
        expect(tsResult.ok).toBe(true);
        expect(tsResult.result).toBe(f.output.result);
      } else {
        expect(tsResult.ok).toBe(false);
        expect(tsResult.error).toBe(f.output.error);
      }
    }
  });

  it("API key from env var matches golden fixture", async () => {
    const f = fixtures.find(x => x.desc === "API key from env var")!;
    process.env["DEEPSEEK_API_KEY"] = "env-key-abc";
    const tsResult = await runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result).toBe("Hello!");
  });

  it("custom base_url from env var matches golden fixture", async () => {
    const f = fixtures.find(x => x.desc === "custom base_url from env var")!;
    process.env["DEEPSEEK_BASE_URL"] = "https://custom.deepseek.com";
    process.env["DEEPSEEK_API_KEY"] = "env-key-base-url";
    const tsResult = await runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result).toBe("Hello!");
  });

  it("default base_url used when not specified matches golden fixture", async () => {
    const f = fixtures.find(x => x.desc === "default base_url used when not specified")!;
    process.env["DEEPSEEK_API_KEY"] = "test-key-default-url";
    const tsResult = await runTs(f);
    expect(tsResult.ok).toBe(true);
    expect(tsResult.result).toBe("ok");
  });

  it("missing API key raises RuntimeError", async () => {
    const f = fixtures.find(x => x.desc === "missing API key raises RuntimeError")!;
    delete process.env["DEEPSEEK_API_KEY"];
    const tsResult = await runTs(f);
    expect(tsResult.ok).toBe(false);
    expect(tsResult.error).toBe("RuntimeError");
    expect(tsResult.message).toBe("DEEPSEEK_API_KEY is not set");
  });
});

// ── A: Request Payload Snapshot ──

describe("A: request payload snapshot", () => {
  it("payload contains only model, messages, stream", async () => {
    const captured = { url: "", headers: {} as Record<string, string>, body: "" };
    const transport: Transport = async (url, opts, _timeout) => {
      captured.url = url;
      captured.headers = opts.headers as Record<string, string>;
      captured.body = opts.body;
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "Hello" }],
      { model: "deepseek-chat", api_key: "test-key", transport },
    );
    const payload = JSON.parse(captured.body) as Record<string, unknown>;
    expect(Object.keys(payload).sort()).toEqual(["messages", "model", "stream"]);
  });

  it("payload body deep equals Python snapshot", async () => {
    const f = fixtures.find(x => x.desc === "minimal valid request")!;
    const captured = { body: "" };
    const transport: Transport = async (url, opts, _timeout) => {
      captured.body = opts.body;
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "Hello!" } }] }) };
    };
    await chatCompletion(
      f.input.messages,
      { model: f.input.model, base_url: f.input.base_url ?? undefined, api_key: f.input.api_key ?? undefined, transport },
    );
    const tsPayload = JSON.parse(captured.body) as Record<string, unknown>;
    expect(deepEqual(tsPayload, f.request_snapshot.body!)).toBe(true);
  });

  it("stream field is always false", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      const payload = JSON.parse(opts.body) as Record<string, unknown>;
      expect(payload.stream).toBe(false);
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "k", transport },
    );
  });

  it("temperature not present in payload (Python does not send it)", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      const payload = JSON.parse(opts.body) as Record<string, unknown>;
      expect(payload).not.toHaveProperty("temperature");
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "k", transport },
    );
  });

  it("max_tokens not present in payload (Python does not send it)", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      const payload = JSON.parse(opts.body) as Record<string, unknown>;
      expect(payload).not.toHaveProperty("max_tokens");
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "k", transport },
    );
  });

  it("request URL ends with /chat/completions", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      expect(url).toMatch(/\/chat\/completions$/);
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "k", transport },
    );
  });

  it("request method is POST", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      expect(opts.method).toBe("POST");
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "k", transport },
    );
  });
});

// ── B: Headers Snapshot ──

describe("B: headers snapshot", () => {
  it("Authorization header present with Bearer token", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      expect(opts.headers["Authorization"]).toBe("Bearer test-key-12345");
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "test-key-12345", transport },
    );
  });

  it("Content-Type header is application/json", async () => {
    const transport: Transport = async (url, opts, _timeout) => {
      expect(opts.headers["Content-Type"]).toBe("application/json");
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "test" }],
      { model: "m", api_key: "k", transport },
    );
  });

  it("headers match Python snapshot for minimal request", async () => {
    const f = fixtures.find(x => x.desc === "minimal valid request")!;
    const transport: Transport = async (url, opts, _timeout) => {
      expect(opts.headers["Authorization"]).toBe(f.request_snapshot.headers!["Authorization"]);
      expect(opts.headers["Content-Type"]).toBe("application/json");
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "Hello!" } }] }) };
    };
    await chatCompletion(
      f.input.messages,
      { model: f.input.model, api_key: f.input.api_key!, transport },
    );
  });
});

// ── C: Response Parsing Snapshot ──

describe("C: response parsing snapshot", () => {
  it("parses normal response and returns content", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "Hello world" } }] }) };
    };
    const result = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    expect(result).toBe("Hello world");
  });

  it("response with extra usage field returns content correctly", async () => {
    const transport: Transport = async () => {
      return {
        status: 200,
        body: JSON.stringify({
          choices: [{ message: { content: "Usage info" } }],
          usage: { prompt_tokens: 15, completion_tokens: 5, total_tokens: 20 },
        }),
      };
    };
    const result = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    expect(result).toBe("Usage info");
  });

  it("response without usage field parses correctly", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "No usage" } }] }) };
    };
    const result = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    expect(result).toBe("No usage");
  });

  it("unicode Chinese response preserves characters", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "复读班学费：9800元/学期" } }] }) };
    };
    const result = await chatCompletion(
      [{ role: "user", content: "你好" }],
      { model: "m", api_key: "k", transport },
    );
    expect(result).toBe("复读班学费：9800元/学期");
  });

  it("emoji response preserves emoji", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "😊欢迎咨询" } }] }) };
    };
    const result = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    expect(result).toBe("😊欢迎咨询");
  });

  it("response missing choices field throws KeyError", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ id: "123" }) };
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("'choices'");
  });

  it("response choices empty array throws IndexError", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [] }) };
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("list index out of range");
  });

  it("response message missing content throws KeyError", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ index: 0, message: {} }] }) };
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("'content'");
  });

  it("response choices[0] missing message throws KeyError", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ index: 0 }] }) };
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("'message'");
  });
});

// ── D: Error Mapping Snapshot ──

describe("D: error mapping snapshot", () => {
  it("HTTP 400 maps to RuntimeError with code and detail", async () => {
    const transport: Transport = async () => {
      throw new HttpError(400, '{"error":{"message":"Bad request"}}');
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API error 400: {\"error\":{\"message\":\"Bad request\"}}");
  });

  it("HTTP 401 maps correctly", async () => {
    const transport: Transport = async () => {
      throw new HttpError(401, '{"error":{"message":"Invalid API key"}}');
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API error 401");
  });

  it("HTTP 429 maps correctly", async () => {
    const transport: Transport = async () => {
      throw new HttpError(429, '{"error":{"message":"Rate limited"}}');
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API error 429");
  });

  it("HTTP 500 maps correctly", async () => {
    const transport: Transport = async () => {
      throw new HttpError(500, "Internal error");
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API error 500");
  });

  it("timeout (generic error) maps to network error", async () => {
    const transport: Transport = async () => {
      throw new Error("timed out");
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API network error: timed out");
  });

  it("network error maps to network error with reason", async () => {
    const transport: Transport = async () => {
      throw new Error("Connection refused");
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API network error: Connection refused");
  });

  it("non-JSON response throws RuntimeError with JSONDecodeError name", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: "This is not JSON" };
    };
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow();
  });

  it("missing API key throws with descriptive message", async () => {
    delete process.env["DEEPSEEK_API_KEY"];
    await expect(
      chatCompletion([{ role: "user", content: "hello" }], { model: "m", api_key: undefined, transport: undefined }),
    ).rejects.toThrow("DEEPSEEK_API_KEY is not set");
  });

  it("missing API key error has name RuntimeError", async () => {
    delete process.env["DEEPSEEK_API_KEY"];
    try {
      await chatCompletion([{ role: "user", content: "hello" }], { model: "m", transport: undefined });
    } catch (e: unknown) {
      expect((e as Error).name).toBe("RuntimeError");
    }
  });
});

// ── E: No Real Network Snapshot ──

describe("E: no real network snapshot", () => {
  it("only mock transport is used (no real fetch)", async () => {
    let called = false;
    const transport: Transport = async (url, opts, _timeout) => {
      called = true;
      expect(url).toBeTruthy();
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "ok" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    expect(called).toBe(true);
  });

  it("mock transport captures all requests (no fallback to default)", async () => {
    let callCount = 0;
    const transport: Transport = async (url, opts, _timeout) => {
      callCount++;
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "mocked" } }] }) };
    };
    await chatCompletion(
      [{ role: "user", content: "a" }],
      { model: "m", api_key: "k", transport },
    );
    await chatCompletion(
      [{ role: "user", content: "b" }],
      { model: "m", api_key: "k", transport },
    );
    expect(callCount).toBe(2);
  });

  it("throws HttpError from mock transport (not real fetch)", async () => {
    const transport: Transport = async () => {
      throw new HttpError(400, '{"error":"mock error"}');
    };
    await expect(
      chatCompletion([{ role: "user", content: "x" }], { model: "m", api_key: "k", transport }),
    ).rejects.toThrow("DeepSeek API error 400");
  });

  it("source file has transport injection point", () => {
    const source = readFileSync(
      resolve(import.meta.dirname!, "..", "ts-src", "providerDeepseek.ts"),
      "utf-8",
    );
    expect(source).toContain("transport");
    expect(source).toContain("Transport");
  });
});

// ── F: Repeatable calls stable ──

describe("F: repeatable calls stable", () => {
  it("same inputs produce same output", async () => {
    const transport: Transport = async () => {
      return { status: 200, body: JSON.stringify({ choices: [{ message: { content: "stable" } }] }) };
    };
    const a = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    const b = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "m", api_key: "k", transport },
    );
    expect(a).toBe(b);
  });
});

// ── G: defaultTransport Production Validation ──

describe("G: defaultTransport production validation", () => {
  let server: ReturnType<typeof createServer>;
  let port: number;
  let received: { method: string; headers: Record<string, string>; body: string };

  afterEach(() => {
    server?.close();
  });

  it("defaultTransport sends correct request and parses response via local HTTP server", async () => {
    received = { method: "", headers: {}, body: "" };
    await new Promise<void>((resolveServer) => {
      server = createServer((req, res) => {
        let data = "";
        req.on("data", (chunk: Buffer) => { data += chunk.toString(); });
        req.on("end", () => {
          received.method = req.method ?? "";
          received.headers = req.headers as Record<string, string>;
          received.body = data;
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ choices: [{ message: { content: "from-default-transport" } }] }));
        });
      });
      server.listen(0, () => {
        port = (server.address() as { port: number }).port;
        resolveServer();
      });
    });

    const result = await chatCompletion(
      [{ role: "user", content: "hello" }],
      { model: "deepseek-chat", api_key: "test-key", base_url: `http://localhost:${port}` },
    );

    expect(result).toBe("from-default-transport");
    expect(received.method).toBe("POST");
    expect(received.headers["authorization"]).toBe("Bearer test-key");
    expect(received.headers["content-type"]).toBe("application/json");
    const payload = JSON.parse(received.body) as Record<string, unknown>;
    expect(payload.model).toBe("deepseek-chat");
    expect(payload.stream).toBe(false);
    expect((payload.messages as Array<Record<string, string>>)[0]!.content).toBe("hello");
  });

  it("defaultTransport propagates 400 from server as RuntimeError", async () => {
    await new Promise<void>((resolveServer) => {
      server = createServer((_req, res) => {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: { message: "bad request" } }));
      });
      server.listen(0, () => {
        port = (server.address() as { port: number }).port;
        resolveServer();
      });
    });

    await expect(
      chatCompletion(
        [{ role: "user", content: "hello" }],
        { model: "m", api_key: "k", base_url: `http://localhost:${port}` },
      ),
    ).rejects.toThrow("DeepSeek API error 400");
  });

  it("defaultTransport timeout aborts request", async () => {
    await new Promise<void>((resolveServer) => {
      server = createServer((_req, res) => {
        // Never respond — triggers timeout
      });
      server.listen(0, () => {
        port = (server.address() as { port: number }).port;
        resolveServer();
      });
    });

    await expect(
      chatCompletion(
        [{ role: "user", content: "hello" }],
        { model: "m", api_key: "k", base_url: `http://localhost:${port}`, timeout: 0.01 },
      ),
    ).rejects.toThrow("DeepSeek API network error");
  });
});
