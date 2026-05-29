import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { buildCitations } from "../ts-src/citationBuilder.js";
import type { CitationChunk } from "../ts-src/citationBuilder.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "citation_builder.json");

interface FixtureCase {
  input: CitationChunk[];
  output: { doc_id: string; title: string; source_uri: string }[];
}

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runPythonBuilder(chunks: CitationChunk[]): unknown {
  const tmpScript = resolve(tmpdir(), `parity_cite_${randomUUID()}.py`);
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "rag-service", "src"))})`,
    "from citation_builder import build_citations",
    `result = build_citations(json.loads(${JSON.stringify(JSON.stringify(chunks))}))`,
    "print(json.dumps(result, ensure_ascii=False))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const output = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 10_000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return JSON.parse(output.trim()) as unknown;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

describe("citationBuilder parity tests", () => {
  it("has 5 golden fixture cases", () => {
    expect(fixtures.length).toBe(5);
  });

  it("matches golden baseline for all fixtures", () => {
    for (const c of fixtures) {
      expect(buildCitations(c.input)).toEqual(c.output);
    }
  });

  it("produces identical output to Python for all fixtures", () => {
    for (const c of fixtures) {
      const tsOutput = buildCitations(c.input);
      const pyOutput = runPythonBuilder(c.input);
      expect(tsOutput).toEqual(pyOutput);
    }
  });

  it("returns empty array for empty input", () => {
    expect(buildCitations([])).toEqual([]);
  });

  it("deduplicates by doc_id keeping first occurrence", () => {
    const chunks: CitationChunk[] = [
      { doc_id: "a", title: "First A", source_uri: "u1" },
      { doc_id: "b", title: "B", source_uri: "u2" },
      { doc_id: "a", title: "Second A", source_uri: "u3" },
    ];
    expect(buildCitations(chunks)).toEqual([
      { doc_id: "a", title: "First A", source_uri: "u1" },
      { doc_id: "b", title: "B", source_uri: "u2" },
    ]);
  });

  it("preserves input order of first occurrence", () => {
    const chunks: CitationChunk[] = [
      { doc_id: "z", title: "Z", source_uri: "u3" },
      { doc_id: "a", title: "A", source_uri: "u1" },
      { doc_id: "m", title: "M", source_uri: "u2" },
      { doc_id: "a", title: "A again", source_uri: "u4" },
    ];
    expect(buildCitations(chunks)).toEqual([
      { doc_id: "z", title: "Z", source_uri: "u3" },
      { doc_id: "a", title: "A", source_uri: "u1" },
      { doc_id: "m", title: "M", source_uri: "u2" },
    ]);
  });

  it("handles single item", () => {
    const chunks: CitationChunk[] = [
      { doc_id: "single", title: "Only", source_uri: "http://x" },
    ];
    expect(buildCitations(chunks)).toEqual([
      { doc_id: "single", title: "Only", source_uri: "http://x" },
    ]);
  });

  it("handles all duplicates", () => {
    const chunks: CitationChunk[] = [
      { doc_id: "x", title: "X", source_uri: "u" },
      { doc_id: "x", title: "X", source_uri: "u" },
      { doc_id: "x", title: "X", source_uri: "u" },
    ];
    const result = buildCitations(chunks);
    expect(result.length).toBe(1);
    expect(result[0]).toEqual({ doc_id: "x", title: "X", source_uri: "u" });
  });

  it("handles Chinese titles", () => {
    const chunks: CitationChunk[] = [
      { doc_id: "c1", title: "高考志愿填报指南", source_uri: "https://edu.cn/1" },
      { doc_id: "c2", title: "2026年招生简章", source_uri: "https://edu.cn/2" },
    ];
    expect(buildCitations(chunks)).toEqual([
      { doc_id: "c1", title: "高考志愿填报指南", source_uri: "https://edu.cn/1" },
      { doc_id: "c2", title: "2026年招生简章", source_uri: "https://edu.cn/2" },
    ]);
  });

  it("is not affected by extra fields in chunk", () => {
    const chunks = [
      { doc_id: "d1", title: "T", source_uri: "u", chunk_id: "c1", extra_field: 42 },
      { doc_id: "d2", title: "T2", source_uri: "u2", chunk_id: "c2", score: 0.95 },
    ] as unknown as CitationChunk[];
    expect(buildCitations(chunks)).toEqual([
      { doc_id: "d1", title: "T", source_uri: "u" },
      { doc_id: "d2", title: "T2", source_uri: "u2" },
    ]);
  });

  it("strips chunk_id from output", () => {
    const chunks: CitationChunk[] = [
      { doc_id: "d1", title: "T", source_uri: "u", chunk_id: "c999" },
    ];
    const result = buildCitations(chunks);
    expect(result[0]).not.toHaveProperty("chunk_id");
  });
});
