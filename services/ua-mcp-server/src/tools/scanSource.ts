import { scanSource as scanSourceAdapter } from "../adapters/understandAnythingAdapter.js";

export type ScanSourceArgs = {
  sourcePath: string;
  projectRoot: string;
};

export async function scanSource(args: ScanSourceArgs) {
  const result = await scanSourceAdapter(args.sourcePath, args.projectRoot);
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
  };
}
