import { runPythonModule } from "./parity.js";
import { runShadow } from "./shadow.js";
import type { ShadowConfig } from "./shadow.js";

// ── Mode ────────────────────────────────────────────────────────────────────

export type CutoverMode = "python" | "typescript" | "shadow";

// ── Module route definition ─────────────────────────────────────────────────

export interface ModuleRoute {
  module: string;
  mode: CutoverMode;
  pythonFile: string;
  pythonFunc: string;
  tsFunc: (input: unknown) => unknown;
  repoRoot: string;
}

// ── Cutover config ──────────────────────────────────────────────────────────

export interface CutoverConfig {
  routes: Record<string, ModuleRoute>;
  shadow?: ShadowConfig;
}

// ── Route result ────────────────────────────────────────────────────────────

export interface CutoverResult {
  module: string;
  mode: CutoverMode;
  result: unknown;
}

// ── Router ──────────────────────────────────────────────────────────────────

export function routeCutover(config: CutoverConfig, moduleName: string, input: unknown): CutoverResult {
  const route = config.routes[moduleName];
  if (!route) {
    throw new Error(`Unknown cutover module: ${moduleName}`);
  }

  const mode = route.mode;

  switch (mode) {
    case "python": {
      const raw = runPythonModule(route.pythonFile, route.pythonFunc, [input], route.repoRoot);
      const result = JSON.parse(raw);
      return { module: moduleName, mode, result };
    }

    case "typescript": {
      const result = route.tsFunc(input);
      return { module: moduleName, mode, result };
    }

    case "shadow": {
      const raw = runPythonModule(route.pythonFile, route.pythonFunc, [input], route.repoRoot);
      const pythonResult = JSON.parse(raw);

      if (config.shadow) {
        runShadow(config.shadow, moduleName, input);
      }

      return { module: moduleName, mode, result: pythonResult };
    }
  }
}

export function setCutoverMode(config: CutoverConfig, moduleName: string, mode: CutoverMode): CutoverConfig {
  return {
    ...config,
    routes: {
      ...config.routes,
      [moduleName]: { ...config.routes[moduleName]!, mode },
    },
  };
}
