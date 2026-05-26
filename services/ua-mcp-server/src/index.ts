import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { scanSource } from "./tools/scanSource.js";
import { buildGraph } from "./tools/buildGraph.js";
import { reviewGraph } from "./tools/reviewGraph.js";

const server = new Server(
  { name: "ua-mcp-server", version: "0.1.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "ua.scan_source",
      description: "Scans a directory/file for Understand-Anything analysis. Returns file listing with extension categorization.",
      inputSchema: {
        type: "object",
        properties: {
          sourcePath: { type: "string", description: "Path to the source directory or file to scan (relative to projectRoot)" },
          projectRoot: { type: "string", description: "Absolute path to the project root" },
        },
        required: ["sourcePath", "projectRoot"],
      },
    },
    {
      name: "ua.build_graph",
      description: "Builds a knowledge graph from markdown files in the given source path. Parses frontmatter to extract topics, relationships, and risk flags.",
      inputSchema: {
        type: "object",
        properties: {
          sourcePath: { type: "string", description: "Path to scan for markdown files (relative to projectRoot)" },
          projectRoot: { type: "string", description: "Absolute path to the project root" },
        },
        required: ["sourcePath", "projectRoot"],
      },
    },
    {
      name: "ua.review_graph",
      description: "Reviews an existing graph run for isolated nodes, risk flags, coverage analysis, and provides suggestions.",
      inputSchema: {
        type: "object",
        properties: {
          graphRunId: { type: "string", description: "ID of the graph run to review" },
          projectRoot: { type: "string", description: "Absolute path to the project root" },
        },
        required: ["graphRunId", "projectRoot"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (!args) {
    throw new McpError(ErrorCode.InvalidParams, "No arguments provided");
  }

  try {
    switch (name) {
      case "ua.scan_source": {
        const { sourcePath, projectRoot } = args as { sourcePath: string; projectRoot: string };
        return await scanSource({ sourcePath, projectRoot });
      }

      case "ua.build_graph": {
        const { sourcePath, projectRoot } = args as { sourcePath: string; projectRoot: string };
        return await buildGraph({ sourcePath, projectRoot });
      }

      case "ua.review_graph": {
        const { graphRunId, projectRoot } = args as { graphRunId: string; projectRoot: string };
        return await reviewGraph({ graphRunId, projectRoot });
      }

      default:
        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
    }
  } catch (error) {
    if (error instanceof McpError) {
      throw error;
    }
    return {
      content: [{ type: "text", text: error instanceof Error ? error.message : String(error) }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
