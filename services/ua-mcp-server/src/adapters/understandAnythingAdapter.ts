import fs from "node:fs";
import path from "node:path";
import { Sandbox } from "../sandbox.js";

export type ScanResult = {
  files: string[];
  summary: string;
  warnings: string[];
};

export type GraphNode = {
  id: string;
  type: string;
  label: string;
  metadata: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
};

export type GraphResult = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  layers: string[];
  warnings: string[];
};

export type Finding = {
  type: string;
  severity: "low" | "medium" | "high";
  message: string;
};

export type ReviewResult = {
  findings: Finding[];
  summary: string;
  suggestions: string[];
};

type Frontmatter = Record<string, unknown>;

function parseFrontmatter(content: string): { frontmatter: Frontmatter; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) {
    return { frontmatter: {}, body: content };
  }
  const yamlBlock = match[1];
  const body = match[2];
  const frontmatter: Frontmatter = {};
  const lines = yamlBlock.split("\n");
  let currentKey: string | null = null;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("- ") && currentKey) {
      const item = trimmed.slice(2).trim();
      if (item) {
        const existing = frontmatter[currentKey];
        if (Array.isArray(existing)) {
          (existing as string[]).push(item);
        } else {
          frontmatter[currentKey] = [item];
        }
      }
      continue;
    }

    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) {
      continue;
    }

    currentKey = line.slice(0, colonIdx).trim();
    let value: unknown = line.slice(colonIdx + 1).trim();
    if (value === "") {
      frontmatter[currentKey] = [];
      continue;
    }

    if (typeof value === "string" && value.startsWith("[")) {
      const strVal = value;
      try {
        value = JSON.parse(strVal);
      } catch {
        value = strVal.replace(/[[\]]/g, "").split(",").map((s: string) => s.trim()).filter(Boolean);
      }
    }

    frontmatter[currentKey] = value;
  }

  return { frontmatter, body };
}

function readdirRecursive(dir: string, basePath: string): string[] {
  const results: string[] = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relativePath = path.relative(basePath, fullPath);
      if (entry.isDirectory()) {
        results.push(...readdirRecursive(fullPath, basePath));
      } else {
        results.push(relativePath);
      }
    }
  } catch {
    // skip unreadable directories
  }
  return results;
}

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  const timeout = Number(process.env.UA_TIMEOUT_MS) || ms;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        controller.signal.addEventListener("abort", () => reject(new Error(`Operation timed out after ${timeout}ms`)));
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

export function validateSandboxPath(requestedPath: string, projectRoot: string): boolean {
  const resolved = path.resolve(projectRoot, requestedPath);

  if (!resolved.startsWith(path.resolve(projectRoot))) {
    return false;
  }

  return Sandbox.validate(requestedPath, projectRoot);
}

export async function scanSource(sourcePath: string, projectRoot: string): Promise<ScanResult> {
  return withTimeout(scanSourceImpl(sourcePath, projectRoot), 30_000);
}

async function scanSourceImpl(sourcePath: string, projectRoot: string): Promise<ScanResult> {
  if (!validateSandboxPath(sourcePath, projectRoot)) {
    throw new Error(`Path "${sourcePath}" is outside the allowed sandbox`);
  }

  const resolvedPath = path.resolve(projectRoot, sourcePath);

  if (!fs.existsSync(resolvedPath)) {
    return { files: [], summary: "Path does not exist", warnings: [`Path not found: ${resolvedPath}`] };
  }

  const stats = fs.statSync(resolvedPath);
  const files: string[] = [];

  if (stats.isDirectory()) {
    files.push(...readdirRecursive(resolvedPath, resolvedPath));
  } else {
    files.push(path.relative(projectRoot, resolvedPath));
  }

  const extensionMap = new Map<string, number>();
  const warnings: string[] = [];

  for (const file of files) {
    const ext = path.extname(file).toLowerCase() || "(no extension)";
    extensionMap.set(ext, (extensionMap.get(ext) || 0) + 1);
  }

  const extSummary = Array.from(extensionMap.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([ext, count]) => `${ext}: ${count}`)
    .join(", ");

  if (files.length === 0) {
    warnings.push("No files found in the specified path");
  }

  return {
    files,
    summary: `Found ${files.length} file(s). Extensions: ${extSummary || "none"}`,
    warnings,
  };
}

export async function buildGraph(sourcePath: string, projectRoot: string): Promise<GraphResult> {
  return withTimeout(buildGraphImpl(sourcePath, projectRoot), 30_000);
}

async function buildGraphImpl(sourcePath: string, projectRoot: string): Promise<GraphResult> {
  if (!validateSandboxPath(sourcePath, projectRoot)) {
    throw new Error(`Path "${sourcePath}" is outside the allowed sandbox`);
  }

  const resolvedPath = path.resolve(projectRoot, sourcePath);

  if (!fs.existsSync(resolvedPath)) {
    return { nodes: [], edges: [], layers: [], warnings: [`Path not found: ${resolvedPath}`] };
  }

  const files = readdirRecursive(resolvedPath, resolvedPath).filter(f => f.endsWith(".md"));
  const warnings: string[] = [];
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const topicToDocs = new Map<string, Set<string>>();
  const docIds: string[] = [];

  for (const file of files) {
    const fullPath = path.join(resolvedPath, file);
    let content: string;
    try {
      content = fs.readFileSync(fullPath, "utf-8");
    } catch {
      warnings.push(`Could not read file: ${file}`);
      continue;
    }

    const { frontmatter } = parseFrontmatter(content);
    const docId = (frontmatter.doc_id as string) || `doc_${docIds.length}`;
    const title = (frontmatter.title as string) || file;
    docIds.push(docId);

    nodes.push({
      id: docId,
      type: "document",
      label: title,
      metadata: {
        file,
        visibility: frontmatter.visibility,
        data_level: frontmatter.data_level,
        source_type: frontmatter.source_type,
        review_status: frontmatter.review_status,
      },
    });

    const tags: string[] = [];
    const rawTags = frontmatter.business_tags;
    if (Array.isArray(rawTags)) {
      tags.push(...rawTags.map(t => String(t)));
    } else if (typeof rawTags === "string") {
      tags.push(rawTags);
    }

    for (const tag of tags) {
      if (!topicToDocs.has(tag)) {
        topicToDocs.set(tag, new Set());
      }
      topicToDocs.get(tag)!.add(docId);

      if (!nodes.find(n => n.id === `topic:${tag}`)) {
        nodes.push({
          id: `topic:${tag}`,
          type: "topic",
          label: tag,
          metadata: {},
        });
      }

      edges.push({
        id: `${docId}_contains_${tag}`,
        source: docId,
        target: `topic:${tag}`,
        type: "contains",
      });
    }

    if (rawTags === undefined || (Array.isArray(rawTags) && rawTags.length === 0)) {
      warnings.push(`Document "${title}" has no business_tags`);
    }

    const body = content.replace(/^---[\s\S]*?---\n/, "");
    const riskKeywords = ["风险", "警告", "违规", "danger", "warning", "risk", "compliance", "违规"];
    const lowerBody = body.toLowerCase();
    const foundRisks = riskKeywords.filter(kw => {
      try {
        return lowerBody.includes(kw.toLowerCase());
      } catch {
        return false;
      }
    });
    if (foundRisks.length > 0) {
      const riskId = `risk:${docId}`;
      nodes.push({
        id: riskId,
        type: "risk_flag",
        label: `Risk flags in ${title}`,
        metadata: { keywords: foundRisks },
      });
      edges.push({
        id: `${docId}_flagged`,
        source: docId,
        target: riskId,
        type: "has_risk",
      });
    }
  }

  const topicEntries = Array.from(topicToDocs.entries());
  const seenEdges = new Set<string>();
  for (let i = 0; i < topicEntries.length; i++) {
    const [, docsA] = topicEntries[i];
    const docArrayA = Array.from(docsA);
    for (let j = i + 1; j < topicEntries.length; j++) {
      const [, docsB] = topicEntries[j];
      for (const docA of docArrayA) {
        if (docsB.has(docA)) {
          for (const docB of Array.from(docsB)) {
            if (docA !== docB) {
              const edgeKey = docA < docB ? `${docA}:${docB}` : `${docB}:${docA}`;
              if (!seenEdges.has(edgeKey)) {
                seenEdges.add(edgeKey);
                edges.push({
                  id: `related:${edgeKey}`,
                  source: docA < docB ? docA : docB,
                  target: docA < docB ? docB : docA,
                  type: "related_to",
                });
              }
            }
          }
        }
      }
    }
  }

  const layers = ["documents", "topics", "risks"];

  return { nodes, edges, layers, warnings };
}

export async function reviewGraph(graphRunId: string, projectRoot: string): Promise<ReviewResult> {
  return withTimeout(reviewGraphImpl(graphRunId, projectRoot), 30_000);
}

async function reviewGraphImpl(graphRunId: string, projectRoot: string): Promise<ReviewResult> {
  const findings: Finding[] = [];
  const suggestions: string[] = [];

  const graphRunPath = path.resolve(projectRoot, ".ua-mcp", "runs", graphRunId, "graph.json");

  let graphData: { nodes: GraphNode[]; edges: GraphEdge[] } | null = null;

  if (fs.existsSync(graphRunPath)) {
    try {
      graphData = JSON.parse(fs.readFileSync(graphRunPath, "utf-8"));
    } catch {
      findings.push({
        type: "load_error",
        severity: "high",
        message: `Could not parse graph run data at ${graphRunPath}`,
      });
    }
  } else {
    findings.push({
      type: "run_not_found",
      severity: "high",
      message: `Graph run "${graphRunId}" not found. No persisted graph data available.`,
    });
    suggestions.push("Run ua.build_graph first to generate graph data.");
  }

  if (!graphData) {
    return {
      findings,
      summary: "Review could not be completed because no graph data was found.",
      suggestions,
    };
  }

  const { nodes: graphNodes, edges: graphEdges } = graphData;

  const nodeIds = new Set(graphNodes.map(n => n.id));
  const edgeSourceTargets = new Set<string>();

  for (const edge of graphEdges) {
    edgeSourceTargets.add(edge.source);
    edgeSourceTargets.add(edge.target);
  }

  const isolatedNodes = graphNodes.filter(n => !edgeSourceTargets.has(n.id));
  if (isolatedNodes.length > 0) {
    findings.push({
      type: "isolated_nodes",
      severity: "medium",
      message: `Found ${isolatedNodes.length} isolated node(s) with no edges connecting them: ${isolatedNodes.map(n => n.label).join(", ")}`,
    });
    suggestions.push("Add more relationships or tags to connect isolated nodes to the rest of the graph.");
  }

  const riskFlags = graphNodes.filter(n => n.type === "risk_flag");
  if (riskFlags.length > 0) {
    findings.push({
      type: "risk_flags",
      severity: riskFlags.length > 5 ? "high" : "medium",
      message: `Found ${riskFlags.length} risk flag(s) in the graph.`,
    });
    suggestions.push("Review documents with risk flags for compliance issues.");
  }

  const docNodes = graphNodes.filter(n => n.type === "document");
  const docsWithTags = docNodes.filter(n => {
    const edges = graphEdges.filter(e => e.source === n.id && e.type === "contains");
    return edges.length > 0;
  });

  const coverage = docNodes.length > 0 ? (docsWithTags.length / docNodes.length) * 100 : 0;
  findings.push({
    type: "coverage",
    severity: coverage < 50 ? "high" : coverage < 80 ? "medium" : "low",
    message: `Tag coverage: ${coverage.toFixed(1)}% (${docsWithTags.length}/${docNodes.length} documents have topic tags)`,
  });

  if (coverage < 100) {
    suggestions.push("Add business_tags to documents missing them to improve graph connectivity and searchability.");
  }

  const topicNodes = graphNodes.filter(n => n.type === "topic");
  if (topicNodes.length === 0) {
    findings.push({
      type: "no_topics",
      severity: "medium",
      message: "No topic nodes found in the graph.",
    });
    suggestions.push("Ensure documents have business_tags in their frontmatter to create topic nodes.");
  }

  const summary = `Reviewed graph run "${graphRunId}": ${graphNodes.length} nodes, ${graphEdges.length} edges, ${docNodes.length} documents, ${topicNodes.length} topics, ${riskFlags.length} risk flags. Coverage: ${coverage.toFixed(1)}%.`;

  return { findings, summary, suggestions };
}
