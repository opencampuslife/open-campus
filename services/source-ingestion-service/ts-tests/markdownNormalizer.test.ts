import { describe, it, expect } from "vitest";
import { writeFileSync, unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";
import { normalizeMarkdown } from "../ts-src/markdownNormalizer.js";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

interface FixtureCase {
  input: string;
  output: string;
}

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..", "..");
const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "markdown_normalizer.json");

const fixtures: FixtureCase[] = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
) as FixtureCase[];

function runPythonNormalizer(text: string): string {
  const tmpScript = resolve(tmpdir(), `parity_${randomUUID()}.py`);
  const script = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(resolve(REPO_ROOT, "services", "source-ingestion-service", "src"))})`,
    "from markdown_normalizer import normalize_markdown",
    `result = normalize_markdown(${JSON.stringify(text)})`,
    "print(json.dumps(result))",
  ].join("\n");
  writeFileSync(tmpScript, script, "utf-8");
  try {
    const result = execSync(`python3 ${JSON.stringify(tmpScript)}`, {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      timeout: 10_000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return JSON.parse(result.trim()) as string;
  } finally {
    try { unlinkSync(tmpScript); } catch { /* ignore */ }
  }
}

describe("markdownNormalizer parity tests", () => {
  it("has at least 8 fixture cases", () => {
    expect(fixtures.length).toBeGreaterThanOrEqual(8);
  });

  it("matches golden baseline for all fixtures", () => {
    for (let i = 0; i < fixtures.length; i++) {
      const c = fixtures[i]!;
      const tsOutput = normalizeMarkdown(c.input);
      expect(tsOutput).toBe(c.output);
    }
  });

  it("produces identical output to Python for each fixture", () => {
    for (const c of fixtures) {
      const tsOutput = normalizeMarkdown(c.input);
      const pyOutput = runPythonNormalizer(c.input);
      expect(tsOutput).toBe(pyOutput);
    }
  });

  it("normalizes Windows line endings", () => {
    expect(normalizeMarkdown("A\r\nB\r\nC")).toBe("A\nB\nC\n");
  });

  it("normalizes old Mac line endings", () => {
    expect(normalizeMarkdown("A\rB\rC")).toBe("A\nB\nC\n");
  });

  it("removes BOM", () => {
    expect(normalizeMarkdown("\uFEFF# Title")).toBe("# Title\n");
  });

  it("adds space after heading hashes", () => {
    expect(normalizeMarkdown("#Heading")).toBe("# Heading\n");
    expect(normalizeMarkdown("##Subheading")).toBe("## Subheading\n");
  });

  it("collapses 3+ consecutive newlines", () => {
    expect(normalizeMarkdown("A\n\n\n\nB")).toBe("A\n\nB\n");
  });

  it("strips trailing whitespace per line", () => {
    expect(normalizeMarkdown("hello   \nworld  ")).toBe("hello\nworld\n");
  });

  it("ensures single trailing newline", () => {
    expect(normalizeMarkdown("text")).toBe("text\n");
    expect(normalizeMarkdown("text\n\n\n")).toBe("text\n");
  });

  it("returns single newline for empty input", () => {
    expect(normalizeMarkdown("")).toBe("\n");
  });
});
