import { mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { redactPayload } from "./redactor.js";

export function logLlmCall(
  projectRoot: string,
  event: Record<string, unknown>,
): void {
  const logDir = join(projectRoot, "data", "llm_logs");
  mkdirSync(logDir, { recursive: true });
  const redacted = redactPayload(event) as Record<string, unknown>;
  redacted["created_at"] = timestampUtc();
  appendFileSync(
    join(logDir, "llm_calls.jsonl"),
    JSON.stringify(redacted) + "\n",
    "utf-8",
  );
}

function timestampUtc(): string {
  const d = new Date();
  const y = d.getUTCFullYear();
  const M = String(d.getUTCMonth() + 1).padStart(2, "0");
  const D = String(d.getUTCDate()).padStart(2, "0");
  const h = String(d.getUTCHours()).padStart(2, "0");
  const m = String(d.getUTCMinutes()).padStart(2, "0");
  const s = String(d.getUTCSeconds()).padStart(2, "0");
  const us = String(d.getUTCMilliseconds() * 1000).padStart(6, "0");
  return `${y}-${M}-${D}T${h}:${m}:${s}.${us}+00:00`;
}
