import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { validateSandboxPath, scanSource, buildGraph } from "../src/adapters/understandAnythingAdapter.js";
import { Sandbox } from "../src/sandbox.js";

describe("Sandbox", () => {
  it("validates paths within knowledge_vault", () => {
    expect(Sandbox.validate("knowledge_vault/public", "/tmp/project")).toBe(true);
  });

  it("validates exact knowledge_vault path", () => {
    expect(Sandbox.validate("knowledge_vault", "/tmp/project")).toBe(true);
  });

  it("validates nested paths within knowledge_vault", () => {
    expect(Sandbox.validate("knowledge_vault/public/campus/file.md", "/tmp/project")).toBe(true);
  });

  it("rejects paths outside the sandbox", () => {
    expect(Sandbox.validate("../etc/passwd", "/tmp/project")).toBe(false);
  });

  it("rejects paths in /etc", () => {
    expect(Sandbox.validate("/etc/passwd", "/tmp/project")).toBe(false);
  });

  it("rejects paths in project root parent", () => {
    expect(Sandbox.validate("..", "/tmp/project")).toBe(false);
  });

  it("validates paths within data/ingestion", () => {
    expect(Sandbox.validate("data/ingestion/incoming", "/tmp/project")).toBe(true);
  });
});

describe("validateSandboxPath", () => {
  it("returns true for valid sandbox path", () => {
    expect(validateSandboxPath("knowledge_vault/public", "/tmp/project")).toBe(true);
  });

  it("returns false for invalid sandbox path", () => {
    expect(validateSandboxPath("/etc/passwd", "/tmp/project")).toBe(false);
  });

  it("returns false for path traversal", () => {
    expect(validateSandboxPath("../etc/passwd", "/tmp/project")).toBe(false);
  });
});

describe("scanSource", () => {
  it("scans a directory and returns files with summary", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ua-test-"));
    fs.mkdirSync(path.join(tmpDir, "knowledge_vault", "test"), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, "knowledge_vault", "test", "a.md"), "# Hello");
    fs.writeFileSync(path.join(tmpDir, "knowledge_vault", "test", "b.txt"), "Hello");

    const result = await scanSource("knowledge_vault/test", tmpDir);

    expect(result.files).toHaveLength(2);
    expect(result.files).toContain("a.md");
    expect(result.files).toContain("b.txt");
    expect(result.summary).toContain("2 file(s)");
    expect(result.warnings).toEqual([]);

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("returns warning for non-existent path", async () => {
    const result = await scanSource("knowledge_vault/nonexistent", "/tmp/nonexistent_project");
    expect(result.files).toEqual([]);
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it("rejects path outside sandbox", async () => {
    await expect(scanSource("/etc/passwd", "/tmp/project")).rejects.toThrow("outside the allowed sandbox");
  });
});

describe("buildGraph", () => {
  it("builds a graph from markdown files with frontmatter", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ua-test-graph-"));
    const vaultDir = path.join(tmpDir, "knowledge_vault", "docs");
    fs.mkdirSync(vaultDir, { recursive: true });

    fs.writeFileSync(
      path.join(vaultDir, "doc1.md"),
      [
        "---",
        "title: Document 1",
        "doc_id: doc_1",
        "business_tags:",
        "  - 校区介绍",
        "  - 郑州",
        "visibility: public",
        "---",
        "# Document 1",
        "Content about campus",
      ].join("\n"),
    );

    fs.writeFileSync(
      path.join(vaultDir, "doc2.md"),
      [
        "---",
        "title: Document 2",
        "doc_id: doc_2",
        "business_tags:",
        "  - 校区介绍",
        "  - 北京",
        "visibility: public",
        "---",
        "# Document 2",
        "Content about Beijing campus",
      ].join("\n"),
    );

    const result = await buildGraph("knowledge_vault/docs", tmpDir);

    expect(result.nodes.length).toBeGreaterThanOrEqual(4);
    expect(result.edges.length).toBeGreaterThanOrEqual(4);
    expect(result.layers).toEqual(["documents", "topics", "risks"]);

    const docNodes = result.nodes.filter(n => n.type === "document");
    expect(docNodes).toHaveLength(2);

    const topicNodes = result.nodes.filter(n => n.type === "topic");
    expect(topicNodes.length).toBeGreaterThanOrEqual(2);

    const containsEdges = result.edges.filter(e => e.type === "contains");
    expect(containsEdges.length).toBeGreaterThanOrEqual(4);

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("rejects path outside sandbox", async () => {
    await expect(buildGraph("/etc", "/tmp/project")).rejects.toThrow("outside the allowed sandbox");
  });

  it("handles directory with no markdown files", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ua-test-empty-"));
    fs.mkdirSync(path.join(tmpDir, "knowledge_vault", "empty"), { recursive: true });

    const result = await buildGraph("knowledge_vault/empty", tmpDir);
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
    expect(result.warnings).toEqual([]);

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
});
