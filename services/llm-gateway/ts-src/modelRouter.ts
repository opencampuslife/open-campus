import { deepseekModel } from "./config.js";

export function routeModel(
  task: string,
  scope: Record<string, unknown>,
): Record<string, string | null> {
  return {
    provider: "deepseek",
    model: deepseekModel(),
    task: task,
    role: "role" in scope ? (scope["role"] as string | null) : "unknown",
  };
}
