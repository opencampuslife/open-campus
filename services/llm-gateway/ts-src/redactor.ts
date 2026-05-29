const PHONE_RE = /(?<!\d)1[3-9]\d{9}(?!\d)/g;
const KEY_RE = /sk-[A-Za-z0-9]{8,}/g;

export function redactText(text: string): string {
  text = text.replace(PHONE_RE, "[REDACTED_PHONE]");
  text = text.replace(KEY_RE, "[REDACTED_API_KEY]");
  return text;
}

export function redactPayload(payload: unknown): unknown {
  if (typeof payload === "string") {
    return redactText(payload);
  }
  if (Array.isArray(payload)) {
    return payload.map(redactPayload);
  }
  if (payload !== null && typeof payload === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(
      payload as Record<string, unknown>,
    )) {
      result[key] = redactPayload(value);
    }
    return result;
  }
  return payload;
}
