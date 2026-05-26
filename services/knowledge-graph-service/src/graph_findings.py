from __future__ import annotations

from collections import Counter
from typing import Any

from graph_store import GraphStore


def analyze_graph(graph_run_id: str, store: GraphStore) -> dict:
    nodes = store.get_nodes(graph_run_id)
    edges = store.get_edges(graph_run_id)

    node_ids = {n["node_id"] for n in nodes}
    edge_node_ids: set[str] = set()
    adjacency: dict[str, set[str]] = {}
    for n in nodes:
        adjacency[n["node_id"]] = set()

    for e in edges:
        sn = e["source_node_id"]
        tn = e["target_node_id"]
        if sn in adjacency:
            adjacency[sn].add(tn)
        if tn in adjacency:
            adjacency[tn].add(sn)
        edge_node_ids.add(sn)
        edge_node_ids.add(tn)

    node_types = Counter(n["node_type"] for n in nodes)
    isolated_nodes = [n for n in nodes if n["node_id"] not in edge_node_ids]

    visited: set[str] = set()
    components: list[list[str]] = []
    for n in nodes:
        nid = n["node_id"]
        if nid in visited:
            continue
        stack = [nid]
        comp: list[str] = []
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(cur)
            for neighbor in adjacency.get(cur, set()):
                if neighbor not in visited:
                    stack.append(neighbor)
        if comp:
            components.append(comp)

    topics_found = [
        n for n in nodes if n["node_type"] in ("topic", "business_tag")
    ]
    risk_nodes = [n for n in nodes if n["node_type"] == "risk"]

    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "connected_components": len(components),
        "component_sizes": [len(c) for c in components],
    }

    return {
        "graph_run_id": graph_run_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": dict(node_types),
        "isolated_nodes": isolated_nodes,
        "connected_components": components,
        "topics_found": topics_found,
        "risk_nodes": risk_nodes,
        "summary": summary,
    }


def find_connected_docs(
    graph_run_id: str, doc_id: str, store: GraphStore
) -> list[dict]:
    nodes = store.get_nodes(graph_run_id)
    edges = store.get_edges(graph_run_id)

    doc_node = None
    for n in nodes:
        if n.get("source_doc_id") == doc_id or n["node_id"] == doc_id:
            doc_node = n
            break
    if doc_node is None:
        return []

    doc_node_id = doc_node["node_id"]

    topic_ids: set[str] = set()
    for e in edges:
        if e["source_node_id"] == doc_node_id and e["edge_type"] == "has_topic":
            topic_ids.add(e["target_node_id"])
        if e["target_node_id"] == doc_node_id and e["edge_type"] == "has_topic":
            topic_ids.add(e["source_node_id"])

    connected: dict[str, dict] = {}
    for e in edges:
        if e["edge_type"] != "has_topic":
            continue
        other = None
        if e["source_node_id"] in topic_ids and e["target_node_id"] != doc_node_id:
            other = e["target_node_id"]
        elif e["target_node_id"] in topic_ids and e["source_node_id"] != doc_node_id:
            other = e["source_node_id"]
        if other is None:
            continue
        for n in nodes:
            if n["node_id"] == other and n["node_type"] == "document":
                key = n["node_id"]
                if key not in connected:
                    connected[key] = {
                        "doc_node_id": n["node_id"],
                        "doc_label": n["label"],
                        "source_doc_id": n.get("source_doc_id", ""),
                        "shared_topics": [],
                    }
                for t_node in nodes:
                    if t_node["node_id"] in topic_ids and t_node["node_id"] in (
                        e["source_node_id"],
                        e["target_node_id"],
                    ):
                        connected[key]["shared_topics"].append(t_node["label"])

    for v in connected.values():
        v["shared_topics"] = list(set(v["shared_topics"]))

    return list(connected.values())
