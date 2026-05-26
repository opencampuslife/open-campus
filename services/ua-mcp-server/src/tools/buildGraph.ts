import { buildGraph as buildGraphAdapter } from "../adapters/understandAnythingAdapter.js";

export type BuildGraphArgs = {
  sourcePath: string;
  projectRoot: string;
};

export async function buildGraph(args: BuildGraphArgs) {
  const result = await buildGraphAdapter(args.sourcePath, args.projectRoot);
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
  };
}
