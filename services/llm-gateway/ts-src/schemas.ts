import { z } from "zod";

// --- str() helper matching Python's str() for None handling ---
function pyStr(v: unknown): string {
  if (v === null) return "None";
  return String(v);
}

// Matches Python's `list(chunk.get(key, default))`
function listFromChunk(
  chunk: Record<string, unknown>,
  key: string,
  defaultVal: string[],
): string[] {
  if (!(key in chunk)) return defaultVal;
  const val = chunk[key];
  if (val === null) throw new TypeError("'NoneType' object is not iterable");
  if (Array.isArray(val)) return val.map(pyStr);
  return [pyStr(val)];
}

// Matches Python's `str(chunk.get(key, default))`
function strFromChunk(
  chunk: Record<string, unknown>,
  key: string,
  defaultVal: string,
): string {
  if (!(key in chunk)) return defaultVal;
  return pyStr(chunk[key]);
}

// --- EvidenceChunk ---

export const EvidenceChunkSchema = z.object({
  chunk_id: z.string(),
  doc_id: z.string(),
  title: z.string(),
  content: z.string(),
  visibility: z.string(),
  data_level: z.string(),
  allowed_roles: z.array(z.string()),
  source_uri: z.string(),
}).strict();

export type EvidenceChunk = z.infer<typeof EvidenceChunkSchema>;

export function evidenceChunkFromChunk(
  chunk: Record<string, unknown>,
): EvidenceChunk {
  function require(key: string): unknown {
    if (!(key in chunk)) throw new Error(`KeyError: '${key}'`);
    return chunk[key];
  }
  return EvidenceChunkSchema.parse({
    chunk_id: pyStr(require("chunk_id")),
    doc_id: pyStr(require("doc_id")),
    title: pyStr(require("title")),
    content: pyStr(require("content")),
    visibility: pyStr(require("visibility")),
    data_level: pyStr(require("data_level")),
    allowed_roles: listFromChunk(chunk, "allowed_roles", []),
    source_uri: strFromChunk(chunk, "source_uri", ""),
  });
}

// --- LLMRequest ---

export const LLMRequestSchema = z.object({
  user_role: z.string(),
  intent: z.string(),
  user_query: z.string(),
  allowed_evidence: z.array(EvidenceChunkSchema),
  answer_policy: z.record(z.string(), z.unknown()).default({}),
  output_format: z.string().default("plain_text_with_sources"),
  risk_level: z.string().default("low"),
  session_id: z.string().default(""),
  campus: z.string().default("all"),
}).strict();

export type LLMRequest = z.infer<typeof LLMRequestSchema>;

export function llmRequestToPolicyDict(
  req: LLMRequest,
): Record<string, unknown> {
  return {
    task: "admissions_answer",
    message: req.user_query,
    intent: req.intent,
    scope: {
      role: req.user_role,
      campus: req.campus,
    },
    risk_level: req.risk_level,
    session_id: req.session_id,
    answer_policy: req.answer_policy,
    output_format: req.output_format,
    evidence: req.allowed_evidence,
  };
}
