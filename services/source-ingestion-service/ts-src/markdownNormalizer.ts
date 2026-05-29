const HEADING_PATTERN = /^#{1,6}(?=\S)/gm;
const NEWLINE_COLLAPSE_PATTERN = /\n{3,}/g;

export function normalizeMarkdown(text: string): string {
  text = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  text = text.replace(/\uFEFF/g, "");

  const lines = text.split("\n");
  const cleaned = lines.map((line) => line.replace(/[ \t]+$/, ""));
  text = cleaned.join("\n");

  text = text.replace(NEWLINE_COLLAPSE_PATTERN, "\n\n");
  text = text.replace(HEADING_PATTERN, (match) => match + " ");
  text = text.replace(/\n*$/, "") + "\n";

  return text;
}
