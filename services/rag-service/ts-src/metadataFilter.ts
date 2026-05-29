import { canAccess, type AccessResult } from "../../permission-service/ts-src/accessChecker.js";

type Chunk = Record<string, unknown>;

export function filterAllowed(
  chunks: Chunk[],
  scope: Record<string, unknown>,
): [Chunk[], Chunk[]] {
  const allowed: Chunk[] = [];
  const denied: Chunk[] = [];

  for (const chunk of chunks) {
    const [ok, reason] = canAccess(chunk, scope);
    if (ok) {
      allowed.push(chunk);
    } else {
      denied.push({
        chunk_id: chunk.chunk_id,
        doc_id: chunk.doc_id,
        reason,
      });
    }
  }

  return [allowed, denied];
}

export { canAccess };
export type { AccessResult };
