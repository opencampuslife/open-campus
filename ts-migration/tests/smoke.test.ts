import { describe, it, expect } from "vitest";
import { loadFixture, deepEqual } from "../src/parity.js";

describe("parity test framework smoke test", () => {
  const FIXTURES_DIR = new URL("../fixtures", import.meta.url).pathname;

  it("loadFixture loads markdown_normalizer fixtures", () => {
    const path = `${FIXTURES_DIR}/markdown_normalizer.json`;
    const cases = loadFixture<string>(path);
    expect(cases.length).toBe(10);
    expect(typeof cases[0]!.input).toBe("string");
    expect(typeof cases[0]!.output).toBe("string");
  });

  it("deepEqual compares primitives correctly", () => {
    expect(deepEqual(1, 1)).toBe(true);
    expect(deepEqual(1, 2)).toBe(false);
    expect(deepEqual("hello", "hello")).toBe(true);
    expect(deepEqual(null, null)).toBe(true);
    expect(deepEqual(null, undefined)).toBe(false);
  });

  it("deepEqual compares nested objects", () => {
    expect(deepEqual({ a: 1, b: { c: 2 } }, { a: 1, b: { c: 2 } })).toBe(true);
    expect(deepEqual({ a: 1, b: { c: 2 } }, { a: 1, b: { c: 3 } })).toBe(false);
    expect(deepEqual({ a: 1 }, { a: 1, b: 2 })).toBe(false);
  });

  it("deepEqual compares arrays", () => {
    expect(deepEqual([1, 2, 3], [1, 2, 3])).toBe(true);
    expect(deepEqual([1, 2, 3], [1, 2, 4])).toBe(false);
    expect(deepEqual([1, 2], [1, 2, 3])).toBe(false);
  });

  it("deepEqual handles order-independent key comparison", () => {
    expect(deepEqual({ b: 2, a: 1 }, { a: 1, b: 2 })).toBe(true);
  });

  it("all fixture modules exist and have at least 5 cases", () => {
    const modules = [
      "markdown_normalizer",
      "citation_builder",
      "recommendation_model",
      "compliance_checker",
      "metadata_filter",
      "permission_service",
    ];
    for (const mod of modules) {
      const cases = loadFixture(`${FIXTURES_DIR}/${mod}.json`);
      expect(cases.length).toBeGreaterThanOrEqual(5);
    }
  });
});
