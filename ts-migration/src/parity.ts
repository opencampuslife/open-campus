import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";

export interface ParityCase<T> {
  name: string;
  input: unknown;
  pythonResult: T;
  tsResult: T;
}

export interface ParityReport {
  total: number;
  passed: number;
  failed: number;
  failures: Array<{ name: string; python: unknown; ts: unknown; diff: string }>;
}

export function loadFixture<T>(fixturePath: string): Array<{ input: unknown; output: T }> {
  const raw = readFileSync(fixturePath, "utf-8");
  return JSON.parse(raw) as Array<{ input: unknown; output: T }>;
}

export function runPythonModule(
  modulePath: string,
  funcName: string,
  args: unknown[],
  repoRoot: string,
): string {
  const argsJson = JSON.stringify(args);
  const script = `
import json, sys
sys.path.insert(0, ${JSON.stringify(repoRoot)})
exec(open(${JSON.stringify(modulePath)}).read())
result = ${funcName}(*json.loads(${JSON.stringify(argsJson)}))
print(json.dumps(result, ensure_ascii=False, default=str))
`;
  const output = execSync("python3 -c " + JSON.stringify(script), {
    cwd: repoRoot,
    encoding: "utf-8",
    timeout: 30_000,
  });
  return output.trim();
}

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (typeof a !== "object" || typeof b !== "object") return false;

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

export function runParityTests<T>(
  moduleName: string,
  pythonFunc: string,
  pythonFile: string,
  tsFunc: (input: unknown) => T,
  repoRoot: string,
): ParityReport {
  const fixtureFile = resolve(repoRoot, "ts-migration", "fixtures", `${moduleName}.json`);
  const cases = loadFixture<T>(fixtureFile);
  const report: ParityReport = { total: cases.length, passed: 0, failed: 0, failures: [] };

  for (const c of cases) {
    const tsResult = tsFunc(c.input);
    const pythonResult = c.output;

    if (deepEqual(tsResult, pythonResult as unknown)) {
      report.passed++;
    } else {
      report.failed++;
      report.failures.push({
        name: `case ${cases.indexOf(c)}`,
        python: pythonResult,
        ts: tsResult,
        diff: JSON.stringify({ python: pythonResult, typescript: tsResult }, null, 2),
      });
    }
  }

  return report;
}
