import { useEffect, useState, useRef } from "react";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import { fetchGraph } from "./api";
import type { Graph, GraphNode } from "./types";

interface RingGraphProps {
  onNodeClick?: (id: string, type: "card" | "merchant") => void;
  refreshTrigger?: number;
}

export function RingGraph({ onNodeClick, refreshTrigger = 0 }: RingGraphProps) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods>();

  useEffect(() => {
    fetchGraph().then(setGraph).catch(console.error);
  }, [refreshTrigger]);

  useEffect(() => {
    if (!containerRef.current) return;
    let timeoutId: number;
    const observer = new ResizeObserver((entries) => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => {
          if (fgRef.current) {
            fgRef.current.zoomToFit(400, 50);
          }
        }, 150);
      }
    });
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      window.clearTimeout(timeoutId);
    };
  }, [graph]);

  useEffect(() => {
    if (fgRef.current && graph) {
      const fg = fgRef.current;
      fg.d3Force("charge")?.strength(-120);
      fg.d3Force("link")?.distance(60);
      fg.d3ReheatSimulation();
    }
  }, [graph]);

  if (!graph) return <div style={{ padding: 16 }}>Loading graph...</div>;

  const fraudNodes = graph.nodes.filter(
    (n: GraphNode) => (n.flag_count ?? 0) > 0 || n.suspicious
  ).length;

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      <div className="graph-overlay glass-panel">
        <h3 style={{ fontSize: "1rem", marginBottom: 4, fontWeight: 700, color: "var(--accent-blue)" }}>
          Network Map
        </h3>
        <p style={{ fontSize: "0.8rem", color: "var(--text-main)", lineHeight: 1.4, fontWeight: 600 }}>
          {graph.nodes.length} entities &middot; {fraudNodes} flagged
        </p>
        <div className="graph-context-panel">
          Visualizes connections between cards and merchants. Clusters of nodes sharing IPs or Devices indicate likely coordinated fraud rings. Click a node to filter the review queue.
        </div>
      </div>

      {dimensions.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={{ nodes: graph.nodes, links: graph.edges as any }}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const n = node as GraphNode;
            const isFlagged = (n.flag_count ?? 0) > 0;
            const isMerchant = n.type === "merchant";

            let radius = isMerchant ? 3 : 1.8;
            if (isFlagged) radius += 0.6;

            let fill: string;
            if (isMerchant && n.suspicious) fill = "#ef4444";
            else if (isMerchant) fill = "#6366f1";
            else if (isFlagged) fill = "#f59e0b";
            else fill = "#334155";

            const alpha = isFlagged || isMerchant ? 1 : 0.45;

            ctx.beginPath();
            ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI);
            ctx.fillStyle = fill;
            ctx.globalAlpha = alpha;
            ctx.fill();
            ctx.globalAlpha = 1;

            if (isFlagged || (isMerchant && n.suspicious)) {
              ctx.beginPath();
              ctx.arc(node.x!, node.y!, radius + 1.5, 0, 2 * Math.PI);
              ctx.strokeStyle = fill;
              ctx.globalAlpha = 0.25;
              ctx.lineWidth = 1;
              ctx.stroke();
              ctx.globalAlpha = 1;
            }

            if (isMerchant && n.suspicious) {
              const label = n.id;
              const fontSize = Math.max(10 / globalScale, 2.5);
              ctx.font = `${fontSize}px Inter, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "rgba(248,250,252,0.9)";
              ctx.fillText(label, node.x!, node.y! + radius + 2);
            }
          }}
          nodePointerAreaPaint={(node: any, color, ctx) => {
            const r = node.type === "merchant" ? 5 : 3;
            ctx.beginPath();
            ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
          linkColor={(link: any) => {
            if (link.type === "co_burst") return "rgba(239, 68, 68, 0.35)";
            if (link.type === "shared_ip") return "rgba(245, 158, 11, 0.25)";
            if (link.type === "shared_device") return "rgba(139, 92, 246, 0.25)";
            return "rgba(148, 163, 184, 0.06)";
          }}
          linkWidth={(link: any) => {
            if (link.type === "co_burst") return Math.max(0.5, (link.weight || 1) * 0.3);
            if (link.type === "shared_ip" || link.type === "shared_device") return 0.5;
            return 0.15;
          }}
          onNodeClick={(node: any) => {
            if (onNodeClick) {
              onNodeClick(node.id, node.type);
            }
          }}
          backgroundColor="transparent"
          warmupTicks={100}
          cooldownTicks={0}
          enableNodeDrag={false}
          enableZoomInteraction={true}
          enablePanInteraction={true}
        />
      )}
    </div>
  );
}
