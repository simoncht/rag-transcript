"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Controls,
  type Node,
  type Edge,
  useEdgesState,
  useNodesState,
} from "reactflow";

import type { InsightGraph } from "@/lib/types";
import { TopicNode } from "@/components/insights/TopicNode";
import { RootNode } from "@/components/insights/RootNode";
import { TopicDetailPanel } from "@/components/insights/TopicDetailPanel";

type Props = {
  conversationId: string;
  graphData: InsightGraph;
};

const DEFAULT_COLLAPSE_DEPTH = 2;

function mindMapLayout(
  rootId: string,
  childrenByNodeId: Map<string, string[]>,
  {
    xSpacing,
    ySpacing,
  }: {
    xSpacing: number;
    ySpacing: number;
  }
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const visited = new Set<string>();
  let nextY = 0;

  const dfs = (nodeId: string, depth: number): number => {
    if (visited.has(nodeId)) {
      return positions.get(nodeId)?.y ?? 0;
    }
    visited.add(nodeId);

    const kids = childrenByNodeId.get(nodeId) ?? [];
    let y = 0;

    if (kids.length === 0) {
      y = nextY;
      nextY += ySpacing;
    } else {
      const childYs = kids.map((childId) => dfs(childId, depth + 1));
      y = childYs.reduce((sum, val) => sum + val, 0) / childYs.length;
    }

    positions.set(nodeId, { x: depth * xSpacing, y });
    return y;
  };

  dfs(rootId, 0);

  const ys = Array.from(positions.values()).map((pos) => pos.y);
  if (ys.length) {
    const mid = (Math.min(...ys) + Math.max(...ys)) / 2;
    positions.forEach((pos, id) => {
      positions.set(id, { x: pos.x, y: pos.y - mid });
    });
  }

  return positions;
}

function buildChildrenMap(edges: Edge[]): Map<string, string[]> {
  const childrenById = new Map<string, string[]>();
  for (const edge of edges) {
    if (!edge.source || !edge.target) continue;
    const list = childrenById.get(edge.source) ?? [];
    list.push(edge.target);
    childrenById.set(edge.source, list);
  }
  return childrenById;
}

function computeDepthByNodeId(
  rootId: string,
  childrenByNodeId: Map<string, string[]>
): Map<string, number> {
  const depthById = new Map<string, number>([[rootId, 0]]);
  const queue: string[] = [rootId];

  while (queue.length) {
    const current = queue.shift();
    if (!current) break;
    const depth = depthById.get(current) ?? 0;
    for (const childId of childrenByNodeId.get(current) ?? []) {
      if (depthById.has(childId)) continue;
      depthById.set(childId, depth + 1);
      queue.push(childId);
    }
  }

  return depthById;
}

function computeDefaultCollapsedNodeIds(
  nodes: Node[],
  edges: Edge[],
  collapseFromDepth: number
): Set<string> {
  const rootId = nodes.find((node) => node.type === "root")?.id;
  if (!rootId) return new Set();

  const childrenByNodeId = buildChildrenMap(edges);
  const depthByNodeId = computeDepthByNodeId(rootId, childrenByNodeId);

  const collapsed = new Set<string>();
  depthByNodeId.forEach((depth, nodeId) => {
    if (depth < collapseFromDepth) return;
    if ((childrenByNodeId.get(nodeId)?.length ?? 0) === 0) return;
    collapsed.add(nodeId);
  });

  return collapsed;
}

export function ConversationInsightMap({ conversationId, graphData }: Props) {
  const initialNodes = useMemo(() => graphData.nodes as unknown as Node[], [graphData.nodes]);
  const initialEdges = useMemo(() => graphData.edges as unknown as Edge[], [graphData.edges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [collapsedNodeIds, setCollapsedNodeIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    setSelectedNodeId(null);
    setCollapsedNodeIds(
      computeDefaultCollapsedNodeIds(initialNodes, initialEdges, DEFAULT_COLLAPSE_DEPTH)
    );
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const rootNodeId = useMemo(() => {
    const root = nodes.find((node) => node.type === "root")?.id;
    return root ?? nodes[0]?.id ?? null;
  }, [nodes]);

  const childrenByNodeId = useMemo(() => buildChildrenMap(edges), [edges]);

  const depthByNodeId = useMemo(() => {
    if (!rootNodeId) return new Map<string, number>();
    return computeDepthByNodeId(rootNodeId, childrenByNodeId);
  }, [rootNodeId, childrenByNodeId]);

  const parentByNodeId = useMemo(() => {
    const parentMap = new Map<string, string>();
    for (const edge of edges) {
      if (edge.source && edge.target) {
        parentMap.set(edge.target, edge.source);
      }
    }
    return parentMap;
  }, [edges]);

  const toggleCollapse = useCallback((nodeId: string) => {
    setCollapsedNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const visibleNodeIds = useMemo(() => {
    if (!rootNodeId) return new Set(nodes.map((node) => node.id));

    const visible = new Set<string>();
    const stack: string[] = [rootNodeId];

    while (stack.length) {
      const current = stack.pop();
      if (!current) break;
      if (visible.has(current)) continue;
      visible.add(current);

      if (collapsedNodeIds.has(current)) continue;
      for (const childId of childrenByNodeId.get(current) ?? []) {
        stack.push(childId);
      }
    }

    return visible;
  }, [rootNodeId, nodes, childrenByNodeId, collapsedNodeIds]);

  useEffect(() => {
    if (selectedNodeId && !visibleNodeIds.has(selectedNodeId)) {
      setSelectedNodeId(null);
    }
  }, [selectedNodeId, visibleNodeIds]);

  const visibleNodes = useMemo(
    () => nodes.filter((node) => visibleNodeIds.has(node.id)),
    [nodes, visibleNodeIds]
  );

  const visibleEdges = useMemo(
    () =>
      edges.filter(
        (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
      ),
    [edges, visibleNodeIds]
  );

  const layoutPositions = useMemo(() => {
    if (!rootNodeId) return new Map<string, { x: number; y: number }>();
    const visibleChildrenByNodeId = buildChildrenMap(visibleEdges);
    return mindMapLayout(rootNodeId, visibleChildrenByNodeId, {
      xSpacing: 360,
      ySpacing: 110,
    });
  }, [rootNodeId, visibleEdges]);

  const highlightedNodeIds = useMemo(() => {
    if (!selectedNodeId) return null;
    const ids = new Set<string>();
    ids.add(selectedNodeId);

    // Walk ancestors (selected -> root).
    let current = selectedNodeId;
    while (parentByNodeId.has(current)) {
      const parent = parentByNodeId.get(current)!;
      ids.add(parent);
      current = parent;
    }

    // Add children of the selected node.
    for (const edge of edges) {
      if (edge.source === selectedNodeId) {
        ids.add(edge.target);
      }
    }

    return ids;
  }, [selectedNodeId, edges, parentByNodeId]);

  const highlightedEdgeIds = useMemo(() => {
    if (!selectedNodeId) return null;
    const byKey = new Map<string, string>();
    for (const edge of edges) {
      byKey.set(`${edge.source}->${edge.target}`, edge.id);
    }

    const ids = new Set<string>();

    // Ancestor chain edges.
    let current = selectedNodeId;
    while (parentByNodeId.has(current)) {
      const parent = parentByNodeId.get(current)!;
      const edgeId = byKey.get(`${parent}->${current}`);
      if (edgeId) ids.add(edgeId);
      current = parent;
    }

    // Direct children edges.
    for (const edge of edges) {
      if (edge.source === selectedNodeId) {
        ids.add(edge.id);
      }
    }

    return ids;
  }, [selectedNodeId, edges, parentByNodeId]);

  const baseNodes = useMemo(() => {
    return visibleNodes.map((node) => {
      const depth = depthByNodeId.get(node.id) ?? 0;
      const hasChildren = (childrenByNodeId.get(node.id)?.length ?? 0) > 0;
      const position = layoutPositions.get(node.id) ?? node.position;

      return {
        ...node,
        position,
        data: {
          ...(node.data ?? {}),
          depth,
          hasChildren,
          isCollapsed: collapsedNodeIds.has(node.id),
          onToggleCollapse: toggleCollapse,
        },
      };
    });
  }, [
    visibleNodes,
    depthByNodeId,
    childrenByNodeId,
    layoutPositions,
    collapsedNodeIds,
    toggleCollapse,
  ]);

  const displayNodes = useMemo(() => {
    if (!selectedNodeId || !highlightedNodeIds) return baseNodes;
    return baseNodes.map((node) => ({
      ...node,
      data: {
        ...(node.data ?? {}),
        isHighlighted: highlightedNodeIds.has(node.id),
        isDimmed: !highlightedNodeIds.has(node.id),
      },
    }));
  }, [baseNodes, selectedNodeId, highlightedNodeIds]);

  const baseEdges = useMemo(() => {
    return visibleEdges.map((edge) => ({
      ...edge,
      type: "bezier",
      style: {
        ...(edge.style ?? {}),
        stroke: "#a5b4fc",
        strokeWidth: 2,
        strokeOpacity: 0.7,
      },
    }));
  }, [visibleEdges]);

  const displayEdges = useMemo(() => {
    if (!selectedNodeId || !highlightedEdgeIds) return baseEdges;
    return baseEdges.map((edge) => {
      const isActive = highlightedEdgeIds.has(edge.id);
      return {
        ...edge,
        animated: isActive,
        style: {
          ...(edge.style ?? {}),
          strokeOpacity: isActive ? 1 : 0.12,
          strokeWidth: isActive ? 2 : 1,
        },
      };
    });
  }, [baseEdges, selectedNodeId, highlightedEdgeIds]);

  const handleNodeClick = useCallback((_event: any, node: Node) => {
    if (
      node.type === "topic" ||
      node.type === "subtopic" ||
      node.type === "point" ||
      node.type === "moment"
    ) {
      setSelectedNodeId(node.id);
      return;
    }
    setSelectedNodeId(null);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  return (
    <div className="flex h-full w-full gap-4">
      <div className="flex-1 overflow-hidden rounded-lg border border-border bg-background">
        <ReactFlow
          className="insight-flow"
          nodes={displayNodes}
          edges={displayEdges}
          nodeTypes={{
            root: RootNode,
            topic: TopicNode,
            subtopic: TopicNode,
            point: TopicNode,
            moment: TopicNode,
          }}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          nodesDraggable={false}
          nodesConnectable={false}
          fitView
          fitViewOptions={{ padding: 0.25, minZoom: 0.82, maxZoom: 1.1 }}
          defaultEdgeOptions={{
            type: "bezier",
            style: { stroke: "#a5b4fc", strokeWidth: 2 },
          }}
        >
          <Controls />
        </ReactFlow>
      </div>

      {selectedNodeId ? (
        <TopicDetailPanel
          conversationId={conversationId}
          topicId={selectedNodeId}
          onClose={() => setSelectedNodeId(null)}
        />
      ) : null}
    </div>
  );
}
