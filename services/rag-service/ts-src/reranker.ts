function isNumeric(v: unknown): v is number | boolean {
  return typeof v === "number" || typeof v === "boolean";
}

function compareDesc(a: unknown, b: unknown): number {
  if (a === null) throw new TypeError("Cannot compare null score");
  if (b === null) throw new TypeError("Cannot compare null score");

  const aNum = isNumeric(a);
  const bNum = isNumeric(b);

  if (aNum && bNum) {
    const aVal = Number(a);
    const bVal = Number(b);
    // NaN: Python Timsort treats all NaN comparisons as False →
    // NaN stays in original input position (stable sort preserves it)
    if (Number.isNaN(aVal) || Number.isNaN(bVal)) return 0;
    // Normal numeric descending
    if (aVal < bVal) return 1;
    if (aVal > bVal) return -1;
    return 0;
  }

  if (typeof a === "string" && typeof b === "string") {
    if (a < b) return 1;
    if (a > b) return -1;
    return 0;
  }

  throw new TypeError("Cannot compare scores of different types");
}

class KeyError extends Error {
  constructor(msg: string) {
    super(msg);
    this.name = "KeyError";
  }
}

function extractScore(item: Record<string, unknown>): unknown {
  if (!("score" in item)) {
    throw new KeyError("'score'");
  }
  const val = item.score;
  if (val === null) {
    throw new TypeError("Cannot compare null score");
  }
  if (val === undefined) {
    throw new TypeError("Cannot compare undefined score");
  }
  return val;
}

export function rerank(
  scored: Record<string, unknown>[],
  limit: number = 5,
): Record<string, unknown>[] {
  const sorted = [...scored].sort((a, b) => {
    const scoreA = extractScore(a);
    const scoreB = extractScore(b);
    return compareDesc(scoreA, scoreB);
  });
  return sorted.slice(0, limit);
}
