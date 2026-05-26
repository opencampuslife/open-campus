import { reviewGraph as reviewGraphAdapter } from "../adapters/understandAnythingAdapter.js";

export type ReviewGraphArgs = {
  graphRunId: string;
  projectRoot: string;
};

export async function reviewGraph(args: ReviewGraphArgs) {
  const result = await reviewGraphAdapter(args.graphRunId, args.projectRoot);
  return {
    content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
  };
}
