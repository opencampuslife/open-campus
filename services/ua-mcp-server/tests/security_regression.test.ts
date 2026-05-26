import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { Sandbox } from "../src/sandbox.js";
import { buildGraph } from "../src/adapters/understandAnythingAdapter.js";

const ALLOWED_KEYS = new Set(["nodes", "edges", "layers", "warnings"]);

function tmpProject(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "mcp-sec-"));
  fs.mkdirSync(path.join(dir, "knowledge_vault", "docs"), { recursive: true });
  fs.mkdirSync(path.join(dir, "data", "ingestion"), { recursive: true });
  return dir;
}

describe("MCP Security Regression", () => {
  describe("Sandbox path validation", () => {
    it("rejects path traversal with ../..", () => {
      expect(Sandbox.validate("../../etc/passwd", "/tmp/project")).toBe(false);
    });

    it("rejects absolute /etc/passwd", () => {
      expect(Sandbox.validate("/etc/passwd", "/tmp/project")).toBe(false);
    });

    it("rejects ~/.ssh path", () => {
      expect(Sandbox.validate("~/.ssh", "/tmp/project")).toBe(false);
    });

    it("rejects .env file path", () => {
      expect(Sandbox.validate("/path/to/.env", "/tmp/project")).toBe(false);
    });

    it("rejects root parent traversal", () => {
      expect(Sandbox.validate("..", "/tmp/project")).toBe(false);
    });

    it("accepts path under knowledge_vault", () => {
      expect(Sandbox.validate("knowledge_vault/public", "/tmp/project")).toBe(true);
    });

    it("accepts exact knowledge_vault", () => {
      expect(Sandbox.validate("knowledge_vault", "/tmp/project")).toBe(true);
    });

    it("accepts nested path under knowledge_vault", () => {
      expect(Sandbox.validate("knowledge_vault/public/campus/file.md", "/tmp/project")).toBe(true);
    });

    it("accepts path under data/ingestion", () => {
      expect(Sandbox.validate("data/ingestion/incoming", "/tmp/project")).toBe(true);
    });

    it("accepts exact data/ingestion", () => {
      expect(Sandbox.validate("data/ingestion", "/tmp/project")).toBe(true);
    });
  });

  describe("buildGraph output shape", () => {
    it("does not expose permission-overriding fields at top level", async () => {
      const projectRoot = tmpProject();
      const docPath = path.join(projectRoot, "knowledge_vault", "docs", "test_permissions.md");
      fs.writeFileSync(
        docPath,
        [
          "---",
          "title: Permission Test",
          "doc_id: perm_test_001",
          "visibility: internal",
          "allowed_roles:",
          "  - sales",
          "  - admin",
          "data_level: L3",
          "data_level_int: 3",
          "business_tags:",
          "  - test",
          "  - pricing",
          "---",
          "# Permission Test",
          "Content with internal data.",
        ].join("\n"),
      );

      const result = await buildGraph("knowledge_vault/docs", projectRoot);

      const topKeys = new Set(Object.keys(result));
      for (const key of topKeys) {
        expect(ALLOWED_KEYS.has(key)).toBe(true);
      }
      expect(topKeys).toEqual(ALLOWED_KEYS);

      expect(Array.isArray(result.nodes)).toBe(true);
      expect(Array.isArray(result.edges)).toBe(true);
      expect(Array.isArray(result.layers)).toBe(true);
      expect(Array.isArray(result.warnings)).toBe(true);

      expect((result as Record<string, unknown>).visibility).toBeUndefined();
      expect((result as Record<string, unknown>).allowed_roles).toBeUndefined();
      expect((result as Record<string, unknown>).data_level).toBeUndefined();
      expect((result as Record<string, unknown>).data_level_int).toBeUndefined();
      expect((result as Record<string, unknown>).permissions).toBeUndefined();
      expect((result as Record<string, unknown>).metadata).toBeUndefined();

      fs.rmSync(projectRoot, { recursive: true, force: true });
    });

    it("node metadata copies frontmatter but result shape is safe", async () => {
      const projectRoot = tmpProject();
      const docPath = path.join(projectRoot, "knowledge_vault", "docs", "doc_meta.md");
      fs.writeFileSync(
        docPath,
        [
          "---",
          "title: Metadata Doc",
          "doc_id: meta_doc",
          "visibility: internal",
          "allowed_roles:",
          "  - sales",
          "data_level: L3",
          "data_level_int: 3",
          "business_tags:",
          "  - pricing",
          "review_status: approved",
          "---",
          "# Metadata Doc",
          "Content.",
        ].join("\n"),
      );

      const result = await buildGraph("knowledge_vault/docs", projectRoot);

      for (const node of result.nodes) {
        if (node.type === "document") {
          expect(typeof node.metadata).toBe("object");
          expect(node.metadata).not.toBeNull();
        }
      }

      expect(result.nodes.length).toBeGreaterThanOrEqual(1);
      expect(Object.keys(result)).toEqual(["nodes", "edges", "layers", "warnings"]);

      fs.rmSync(projectRoot, { recursive: true, force: true });
    });
  });
});
