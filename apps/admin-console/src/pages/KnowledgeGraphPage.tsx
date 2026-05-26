import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { getAdminHeaders } from "../dataProvider";
import {
  Filter,
  X,
  Maximize2,
  Minimize2,
  Bug,
  Terminal,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from "lucide-react";

type FlowNodeData = {
  label: string;
  nodeType: string;
  subtitle?: string;
  properties?: Record<string, unknown>;
};

type PositionedNode = {
  id: string;
  x: number;
  y: number;
  data: FlowNodeData;
};

type PositionedEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
  relation?: string;
};

type GraphNodeData = {
  id: string;
  type: string;
  label: string;
  subtitle?: string;
  properties?: Record<string, unknown>;
};

type GraphEdgeData = {
  source: string;
  target: string;
  label?: string;
  relation?: string;
};

type GraphApiResponse = Record<string, unknown> & {
  graph_run_id?: string;
  nodes?: unknown[];
  edges?: unknown[];
};

type LayoutResult = {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  width: number;
  height: number;
};

const NODE_WIDTH = 176;
const NODE_HEIGHT = 72;
const H_GAP = 56;
const V_GAP = 120;
const CANVAS_PADDING = 48;

const nodeColors: Record<string, string> = {
  document: "#3b82f6",
  topic: "#22c55e",
  risk_flag: "#ef4444",
  concept: "#a855f7",
  default: "#737373",
};

const nodeBgColors: Record<string, string> = {
  document: "#1e3a5f",
  topic: "#14532d",
  risk_flag: "#7f1d1d",
  concept: "#3b0764",
  default: "#262626",
};

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asRecordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Record<string, unknown> =>
      !!item && typeof item === "object" && !Array.isArray(item)
  );
}

function normalizeGraphData(
  raw: Record<string, unknown> | undefined
): { nodes: GraphNodeData[]; edges: GraphEdgeData[] } | null {
  if (!raw) return null;
  const apiNodes = asRecordArray(raw.nodes || raw.node_list || []);
  const apiEdges = asRecordArray(raw.edges || raw.edge_list || []);

  if (!apiNodes.length && !apiEdges.length) return null;

  const nodeMap = new Map<string, GraphNodeData>();
  for (const rawNode of apiNodes) {
    const id = asString(rawNode.id || rawNode.node_id);
    if (!id || nodeMap.has(id)) continue;
    const subtitle = asString(rawNode.subtitle);
    nodeMap.set(id, {
      id,
      type: asString(rawNode.type || rawNode.node_type, "default"),
      label: asString(rawNode.label || rawNode.title, id),
      subtitle: subtitle || undefined,
      properties: asRecord(rawNode.properties || rawNode.metadata),
    });
  }

  const nodeIds = new Set(nodeMap.keys());
  const edges: GraphEdgeData[] = [];
  for (const rawEdge of apiEdges) {
    const source = asString(rawEdge.source || rawEdge.source_node_id);
    const target = asString(rawEdge.target || rawEdge.target_node_id);
    if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target)) continue;
    const label = asString(rawEdge.label || rawEdge.edge_type || rawEdge.relation);
    const relation = asString(rawEdge.relation || rawEdge.edge_type);
    edges.push({
      source,
      target,
      label: label || undefined,
      relation: relation || undefined,
    });
  }

  return { nodes: [...nodeMap.values()], edges };
}

function simpleLayout(nodes: GraphNodeData[], edges: GraphEdgeData[]): LayoutResult {
  const validNodes = nodes.filter((n) => n.id && typeof n.id === "string");
  const nodeIds = new Set(validNodes.map((n) => n.id));
  const validEdges = edges.filter(
    (e) =>
      e.source &&
      typeof e.source === "string" &&
      e.target &&
      typeof e.target === "string" &&
      nodeIds.has(e.source) &&
      nodeIds.has(e.target)
  );

  if (validNodes.length === 0) {
    return {
      nodes: [],
      edges: [],
      width: NODE_WIDTH + CANVAS_PADDING * 2,
      height: NODE_HEIGHT + CANVAS_PADDING * 2,
    };
  }

  const levelMap = new Map<string, number>();
  const childrenMap = new Map<string, string[]>();
  const parentsMap = new Map<string, string[]>();

  for (const node of validNodes) {
    levelMap.set(node.id, 0);
    childrenMap.set(node.id, []);
    parentsMap.set(node.id, []);
  }

  for (const edge of validEdges) {
    const children = childrenMap.get(edge.source) || [];
    children.push(edge.target);
    childrenMap.set(edge.source, children);

    const parents = parentsMap.get(edge.target) || [];
    parents.push(edge.source);
    parentsMap.set(edge.target, parents);
  }

  const rootNodes = validNodes.filter((n) => (parentsMap.get(n.id) || []).length === 0);
  const queue = rootNodes.map((n) => n.id);
  const visited = new Set<string>(queue);

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentLevel = levelMap.get(current) || 0;
    for (const child of childrenMap.get(current) || []) {
      if (!visited.has(child)) {
        levelMap.set(child, Math.max(levelMap.get(child) || 0, currentLevel + 1));
        visited.add(child);
        queue.push(child);
      }
    }
  }

  const levelGroups = new Map<number, GraphNodeData[]>();
  for (const node of validNodes) {
    const level = levelMap.get(node.id) || 0;
    const group = levelGroups.get(level) || [];
    group.push(node);
    levelGroups.set(level, group);
  }

  const levels = [...levelGroups.keys()].sort((a, b) => a - b);
  const maxColumns = Math.max(...levels.map((level) => levelGroups.get(level)?.length || 0), 1);
  const width = maxColumns * NODE_WIDTH + Math.max(maxColumns - 1, 0) * H_GAP + CANVAS_PADDING * 2;
  const height = levels.length * NODE_HEIGHT + Math.max(levels.length - 1, 0) * V_GAP + CANVAS_PADDING * 2;

  const positionedNodes: PositionedNode[] = [];
  for (const level of levels) {
    const group = levelGroups.get(level) || [];
    const rowWidth = group.length * NODE_WIDTH + Math.max(group.length - 1, 0) * H_GAP;
    const startX = CANVAS_PADDING + Math.max((width - CANVAS_PADDING * 2 - rowWidth) / 2, 0);

    group.forEach((node, index) => {
      positionedNodes.push({
        id: node.id,
        x: startX + index * (NODE_WIDTH + H_GAP),
        y: CANVAS_PADDING + level * (NODE_HEIGHT + V_GAP),
        data: {
          label: node.label,
          nodeType: node.type,
          subtitle: node.subtitle,
          properties: node.properties,
        },
      });
    });
  }

  const positionedEdges: PositionedEdge[] = validEdges.map((edge, index) => ({
    id: `e-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.label || edge.relation,
    relation: edge.relation,
  }));

  return { nodes: positionedNodes, edges: positionedEdges, width, height };
}

function edgePath(source: PositionedNode, target: PositionedNode): string {
  const startX = source.x + NODE_WIDTH / 2;
  const startY = source.y + NODE_HEIGHT;
  const endX = target.x + NODE_WIDTH / 2;
  const endY = target.y;
  const deltaY = Math.max((endY - startY) / 2, 36);
  return `M ${startX} ${startY} C ${startX} ${startY + deltaY}, ${endX} ${endY - deltaY}, ${endX} ${endY}`;
}

function StaticGraphCanvas({
  layout,
  selectedNodeId,
  onSelectNode,
}: {
  layout: LayoutResult;
  selectedNodeId: string | null;
  onSelectNode: (node: PositionedNode) => void;
}) {
  const nodeMap = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node])),
    [layout.nodes]
  );

  return (
    <div className="w-full h-full overflow-auto">
      <div
        className="relative min-w-full min-h-full"
        style={{
          width: `${Math.max(layout.width, 640)}px`,
          height: `${Math.max(layout.height, 420)}px`,
        }}
      >
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox={`0 0 ${Math.max(layout.width, 640)} ${Math.max(layout.height, 420)}`}
          preserveAspectRatio="xMinYMin meet"
        >
          {layout.edges.map((edge) => {
            const source = nodeMap.get(edge.source);
            const target = nodeMap.get(edge.target);
            if (!source || !target) return null;
            const midX = (source.x + target.x + NODE_WIDTH) / 2;
            const midY = (source.y + target.y + NODE_HEIGHT) / 2;
            return (
              <g key={edge.id}>
                <path
                  d={edgePath(source, target)}
                  fill="none"
                  stroke="#525252"
                  strokeWidth="2"
                />
                <circle cx={midX} cy={midY} r="3" fill="#78716c" />
                {edge.label ? (
                  <text
                    x={midX + 8}
                    y={midY - 6}
                    fill="#a8a29e"
                    fontSize="11"
                    fontFamily="system-ui, sans-serif"
                  >
                    {edge.label}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>

        {layout.nodes.map((node) => {
          const nodeType = node.data.nodeType || "default";
          const borderColor = nodeColors[nodeType] || nodeColors.default;
          const active = selectedNodeId === node.id;
          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelectNode(node)}
              className="absolute rounded-lg border-2 px-3 py-2 text-left shadow-lg transition-transform hover:scale-[1.02]"
              style={{
                left: `${node.x}px`,
                top: `${node.y}px`,
                width: `${NODE_WIDTH}px`,
                minHeight: `${NODE_HEIGHT}px`,
                borderColor,
                backgroundColor: nodeBgColors[nodeType] || nodeBgColors.default,
                color: "#e5e5e5",
                boxShadow: active ? `0 0 0 2px ${borderColor}` : "0 10px 20px rgba(0, 0, 0, 0.25)",
              }}
            >
              <div className="flex items-center gap-2">
                <div
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: borderColor }}
                />
                <span className="truncate text-sm font-medium">{node.data.label}</span>
              </div>
              {node.data.subtitle ? (
                <div className="mt-1 truncate text-[11px] text-stone-400">
                  {node.data.subtitle}
                </div>
              ) : null}
              <div className="mt-2 text-[10px] uppercase tracking-wide text-stone-500">
                {nodeType}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

async function fetchLatestGraph(signal?: AbortSignal): Promise<GraphApiResponse> {
  const response = await fetch("/api/admin/graph/latest", {
    method: "GET",
    headers: getAdminHeaders(),
    signal,
  });

  const payload = (await response.json()) as GraphApiResponse;
  if (!response.ok) {
    throw new Error(asString(payload.error || payload.message, `Graph API failed (${response.status})`));
  }

  return payload;
}

export function KnowledgeGraphPage() {
  const [rawApi, setRawApi] = useState<GraphApiResponse | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<PositionedNode | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);
  const graphRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    fetchLatestGraph(controller.signal)
      .then((payload) => {
        setRawApi(payload);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [reloadToken]);

  const rawGraph = useMemo(() => normalizeGraphData(rawApi), [rawApi]);

  const filteredGraph = useMemo(() => {
    if (!rawGraph) return { nodes: [], edges: [] };
    const nodes = rawGraph.nodes.filter((node) => {
      const typeMatch = filterType === "all" || node.type === filterType;
      const searchMatch =
        !searchQuery ||
        node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        node.id.toLowerCase().includes(searchQuery.toLowerCase());
      return typeMatch && searchMatch;
    });
    const nodeIds = new Set(nodes.map((node) => node.id));
    const edges = rawGraph.edges.filter(
      (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)
    );
    return { nodes, edges };
  }, [rawGraph, filterType, searchQuery]);

  const layout = useMemo(
    () => simpleLayout(filteredGraph.nodes, filteredGraph.edges),
    [filteredGraph]
  );

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const node of rawGraph?.nodes || []) {
      counts[node.type] = (counts[node.type] || 0) + 1;
    }
    return counts;
  }, [rawGraph]);

  useEffect(() => {
    if (!selectedNode) return;
    const nextSelected = layout.nodes.find((node) => node.id === selectedNode.id) || null;
    setSelectedNode(nextSelected);
  }, [layout.nodes, selectedNode]);

  const handleSelectNode = useCallback((node: PositionedNode) => {
    setSelectedNode(node);
  }, []);

  return (
    <div className={`space-y-4 ${fullscreen ? "fixed inset-0 z-50 bg-[#0a0a0a] p-4" : ""}`}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-100">Knowledge Graph</h1>
          <p className="mt-1 text-sm text-stone-500">
            Visual exploration of knowledge entities and relationships
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDebugOpen((open) => !open)}
            title="Debug Console"
          >
            <Bug className="h-4 w-4 text-amber-500" />
            {debugOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setFullscreen((value) => !value)}>
            {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setReloadToken((value) => value + 1)}>
            <RefreshCw className="mr-1 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          Graph API error: {error}
        </div>
      ) : null}

      {debugOpen && (
        <div className="space-y-3 rounded-lg border border-stone-700 bg-stone-900 p-4 text-xs font-mono">
          <div className="flex items-center gap-2 text-stone-400">
            <Terminal className="h-3.5 w-3.5" />
            <span className="font-semibold">Debug Console</span>
            <span className="text-stone-600">- Graph Data Inspector</span>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div className="rounded border border-stone-800 bg-stone-950 p-2">
              <div className="mb-1 text-stone-500">API Response</div>
              <div className="text-stone-200">
                status: {rawApi ? "loaded" : isLoading ? "loading..." : "empty"}
                {rawApi && <> · run_id: {String(rawApi.graph_run_id || "?")}</>}
              </div>
              <div className="mt-1 text-stone-400">{rawApi ? Object.keys(rawApi).join(", ") : "-"}</div>
              <div className="mt-1 text-stone-500">
                api_nodes: {(rawApi?.nodes as unknown[])?.length ?? 0} · api_edges: {(rawApi?.edges as unknown[])?.length ?? 0}
              </div>
            </div>
            <div className="rounded border border-stone-800 bg-stone-950 p-2">
              <div className="mb-1 text-stone-500">Normalized</div>
              <div className="text-stone-200">
                nodes: {rawGraph?.nodes.length ?? 0} · edges: {rawGraph?.edges.length ?? 0}
              </div>
              <div className="mt-1 text-stone-400">
                {rawGraph?.nodes.length ? `first id: ${rawGraph.nodes[0]?.id.slice(0, 24)}` : "no nodes"}
              </div>
              <div className="text-stone-400">
                {rawGraph?.edges.length ? `first src: ${rawGraph.edges[0]?.source.slice(0, 24)}` : "no edges"}
              </div>
            </div>
            <div className="rounded border border-stone-800 bg-stone-950 p-2">
              <div className="mb-1 text-stone-500">Layout</div>
              <div className="text-stone-200">
                rendered nodes: {layout.nodes.length} · rendered edges: {layout.edges.length}
              </div>
              <div className="mt-1 text-stone-400">node types: {JSON.stringify(typeCounts)}</div>
              <div className="text-stone-400">
                canvas: {Math.round(layout.width)} × {Math.round(layout.height)}
              </div>
            </div>
          </div>

          <details className="text-stone-500">
            <summary className="cursor-pointer hover:text-stone-300">Raw API Response</summary>
            <pre className="mt-2 max-h-64 overflow-auto rounded border border-stone-800 bg-stone-950 p-2 whitespace-pre-wrap text-stone-400">
              {rawApi ? JSON.stringify(rawApi, null, 2).slice(0, 4000) : "(empty)"}
            </pre>
          </details>
        </div>
      )}

      <div
        className={`flex gap-4 ${fullscreen ? "h-[calc(100%-4rem)]" : ""}`}
        style={{
          minHeight: fullscreen ? undefined : "calc(100vh - 180px)",
          height: fullscreen ? undefined : "calc(100vh - 180px)",
        }}
      >
        <div
          className="relative flex-1 overflow-hidden rounded-lg border border-stone-800 bg-stone-950"
          ref={graphRef}
        >
          <div className="absolute left-4 top-4 z-10 flex flex-wrap items-center gap-2 rounded-lg border border-stone-800 bg-stone-950/90 p-2">
            <Filter className="h-4 w-4 text-stone-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="rounded border border-stone-700 bg-stone-900 px-2 py-1 text-xs text-stone-200 outline-none focus:border-amber-600"
            >
              <option value="all">All Types</option>
              {Object.entries(typeCounts).map(([type, count]) => (
                <option key={type} value={type}>
                  {type} ({count})
                </option>
              ))}
            </select>
            <div className="h-5 w-px bg-stone-800" />
            <input
              type="text"
              placeholder="Search nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-44 rounded border border-stone-700 bg-stone-900 px-2 py-1 text-xs text-stone-200 outline-none placeholder-stone-600 focus:border-amber-600"
            />
          </div>

          <div className="absolute bottom-4 right-4 z-10 rounded-lg border border-stone-800 bg-stone-950/90 p-2 text-xs">
            {Object.entries(nodeColors).map(([type, color]) => (
              <div key={type} className="flex items-center gap-2">
                <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="capitalize text-stone-400">{type}</span>
              </div>
            ))}
          </div>

          {isLoading ? (
            <div className="flex h-full items-center justify-center text-stone-500">
              Loading graph data...
            </div>
          ) : layout.nodes.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-stone-500">
              <span>No graph data available</span>
              {rawApi && !rawGraph ? (
                <span className="text-xs text-stone-600">API responded but normalization returned empty</span>
              ) : null}
              {rawGraph && rawGraph.nodes.length === 0 ? (
                <span className="text-xs text-stone-600">Normalized nodes: 0 (check field mapping)</span>
              ) : null}
            </div>
          ) : (
            <StaticGraphCanvas
              layout={layout}
              selectedNodeId={selectedNode?.id || null}
              onSelectNode={handleSelectNode}
            />
          )}
        </div>

        {selectedNode ? (
          <div className="w-72 shrink-0">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-sm text-stone-200">Node Detail</CardTitle>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="text-stone-500 hover:text-stone-200"
                >
                  <X className="h-4 w-4" />
                </button>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <span className="text-xs text-stone-500">Label</span>
                  <p className="text-sm text-stone-200">{selectedNode.data.label}</p>
                </div>
                <div>
                  <span className="text-xs text-stone-500">Type</span>
                  <p>
                    <Badge
                      variant={
                        selectedNode.data.nodeType === "risk_flag"
                          ? "error"
                          : selectedNode.data.nodeType === "topic"
                            ? "success"
                            : "info"
                      }
                    >
                      {selectedNode.data.nodeType || "unknown"}
                    </Badge>
                  </p>
                </div>
                {selectedNode.data.subtitle ? (
                  <div>
                    <span className="text-xs text-stone-500">Subtitle</span>
                    <p className="text-sm text-stone-300">{selectedNode.data.subtitle}</p>
                  </div>
                ) : null}
                {selectedNode.data.properties ? (
                  <div>
                    <span className="text-xs text-stone-500">Properties</span>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-stone-900 p-2 text-[10px] text-stone-400">
                      {JSON.stringify(selectedNode.data.properties, null, 2)}
                    </pre>
                  </div>
                ) : null}
                <div>
                  <span className="text-xs text-stone-500">Position</span>
                  <p className="font-mono text-xs text-stone-500">
                    x: {Math.round(selectedNode.x)}, y: {Math.round(selectedNode.y)}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </div>
    </div>
  );
}
