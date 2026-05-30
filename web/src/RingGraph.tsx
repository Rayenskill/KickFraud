// Force-directed fraud-ring graph (signature feature).
// TODO (H10-H14): render with react-force-graph-2d; node-click filters the queue.
import { useEffect, useState } from "react";
import { fetchGraph } from "./api";
import type { Graph } from "./types";

export function RingGraph() {
  const [graph, setGraph] = useState<Graph | null>(null);

  useEffect(() => {
    fetchGraph().then(setGraph).catch(() => setGraph(null));
  }, []);

  if (!graph) return <p>Ring graph — waiting for /graph…</p>;
  return (
    <p>
      Ring graph stub: {graph.nodes.length} nodes, {graph.edges.length} edges.
    </p>
  );
}
