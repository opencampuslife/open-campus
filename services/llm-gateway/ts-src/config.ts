const ENV = globalThis.process?.env ?? {};

export function deepseekApiKey(): string | undefined {
  return ENV["DEEPSEEK_API_KEY"];
}

export function deepseekBaseUrl(): string {
  return ENV["DEEPSEEK_BASE_URL"] ?? "https://api.deepseek.com";
}

export function deepseekModel(): string {
  return ENV["DEEPSEEK_MODEL"] ?? "deepseek-v4-flash";
}

export function llmEnabled(): boolean {
  return ENV["DEEPSEEK_ENABLE_LLM"] === "1" && !!ENV["DEEPSEEK_API_KEY"];
}
