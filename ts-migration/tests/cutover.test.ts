import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { readFileSync, rmSync, mkdirSync, readdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import {
  routeCutover,
  setCutoverMode,
} from "../src/cutover.js";
import type { CutoverConfig } from "../src/cutover.js";
import { normalizeMarkdown } from "../../services/source-ingestion-service/ts-src/index.js";

const REPO_ROOT = resolve(import.meta.dirname!, "..", "..");

const DEFAULT_CUTOVER_CONFIG: CutoverConfig = {
  routes: {
    markdown_normalizer: {
      module: "markdown_normalizer",
      mode: "python",
      pythonFile: resolve(REPO_ROOT, "services", "source-ingestion-service", "src", "markdown_normalizer.py"),
      pythonFunc: "normalize_markdown",
      tsFunc: (input: unknown) => normalizeMarkdown(input as string),
      repoRoot: REPO_ROOT,
    },
  },
};

const FIXTURE_PATH = resolve(REPO_ROOT, "ts-migration", "fixtures", "markdown_normalizer.json");
const FIXTURES: Array<{ input: string; output: string }> = JSON.parse(readFileSync(FIXTURE_PATH, "utf-8"));

describe("setCutoverMode", () => {
  it("defaults to python mode", () => {
    expect(DEFAULT_CUTOVER_CONFIG.routes.markdown_normalizer?.mode).toBe("python");
  });

  it("returns new config with updated mode", () => {
    const updated = setCutoverMode(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", "typescript");
    expect(updated.routes.markdown_normalizer?.mode).toBe("typescript");
    expect(DEFAULT_CUTOVER_CONFIG.routes.markdown_normalizer?.mode).toBe("python");
  });
});

describe("routeCutover", () => {
  it("returns python result in python mode", () => {
    const result = routeCutover(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", "Hello\nWorld");
    expect(result.mode).toBe("python");
    expect(result.module).toBe("markdown_normalizer");
    expect(typeof result.result).toBe("string");
    expect((result.result as string).trim()).toBe("Hello\nWorld");
  });

  it("returns typescript result in typescript mode", () => {
    const config = setCutoverMode(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", "typescript");
    const result = routeCutover(config, "markdown_normalizer", "Hello\nWorld");
    expect(result.mode).toBe("typescript");
    expect(typeof result.result).toBe("string");
    expect((result.result as string).trim()).toBe("Hello\nWorld");
  });

  it("python and typescript modes produce same result for all fixtures", () => {
    const tsConfig = setCutoverMode(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", "typescript");

    for (const c of FIXTURES) {
      const pyResult = routeCutover(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", c.input);
      const tsResult = routeCutover(tsConfig, "markdown_normalizer", c.input);
      expect(pyResult.result).toEqual(tsResult.result);
    }
  });

  it("shadow mode returns python result", () => {
    const config = setCutoverMode(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", "shadow");
    const result = routeCutover(config, "markdown_normalizer", "Hello\nWorld");
    expect(result.mode).toBe("shadow");
    expect(typeof result.result).toBe("string");
  });

  it("shadow mode writes shadow report when shadow config provided", () => {
    const tmpDir = join(tmpdir(), `cutover_shadow_${randomUUID()}`);
    mkdirSync(tmpDir, { recursive: true });

    const config: CutoverConfig = {
      routes: DEFAULT_CUTOVER_CONFIG.routes,
      shadow: {
        reportsDir: tmpDir,
        modules: {
          markdown_normalizer: {
            enabled: true,
            module: "markdown_normalizer",
            compareFn: (_input: unknown) => {
              return { python: "result", ts: "result" };
            },
          },
        },
      },
    };
    const withMode = setCutoverMode(config, "markdown_normalizer", "shadow");
    routeCutover(withMode, "markdown_normalizer", "test");

    const files = readdirSync(tmpDir);
    expect(files.length).toBeGreaterThanOrEqual(1);
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("shadow mode does not write report when no shadow config", () => {
    const tmpDir = join(tmpdir(), `cutover_no_shadow_${randomUUID()}`);
    mkdirSync(tmpDir, { recursive: true });

    const config = setCutoverMode(DEFAULT_CUTOVER_CONFIG, "markdown_normalizer", "shadow");
    routeCutover(config, "markdown_normalizer", "test");

    const files = readdirSync(tmpDir);
    expect(files.length).toBe(0);
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("throws for unknown module", () => {
    expect(() => routeCutover(DEFAULT_CUTOVER_CONFIG, "nonexistent", "test")).toThrow("Unknown cutover module");
  });

  it("throws for invalid mode at runtime", () => {
    const badConfig: CutoverConfig = {
      routes: {
        bad: {
          module: "bad",
          mode: "invalid" as "python",
          pythonFile: "/dev/null",
          pythonFunc: "f",
          tsFunc: () => null,
          repoRoot: REPO_ROOT,
        },
      },
    };
    expect(() => routeCutover(badConfig, "bad", "x")).toThrow("Invalid cutover mode");
  });
});
