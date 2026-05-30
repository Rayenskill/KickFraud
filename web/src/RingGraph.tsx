import { useEffect, useState, useRef } from "react";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import { fetchGraph } from "./api";
import type { Graph, GraphNode } from "./types";

interface RingGraphProps {
  onNodeClick: (id: string, type: string) => void;
}

export function RingGraph({ onNodeClick }: RingGraphProps) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods>();

  useEffect(() => {
    fetchGraph().then(setGraph).catch(console.error);
  }, []);

  useEffect(() => {
    if (containerRef.current) {
      const { clientWidth, clientHeight } = containerRef.current;
      setDimensions({ width: clientWidth, height: clientHeight });
    }

    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [graph]);

  // Spread out the simulation once loaded
  useEffect(() => {
    if (fgRef.current && graph) {
      const fg = fgRef.current;
      // Stronger charge repulsion to spread nodes apart
      fg.d3Force("charge")?.strength(-120);
      // Longer link distance so clusters breathe
      fg.d3Force("link")?.distance(60);
      // Re-heat the simulation so the new forces take effect
      fg.d3ReheatSimulation();
    }
  }, [graph]);

  if (!graph) return <div style={{ padding: 16 }}>Loading graph...</div>;

  const fraudNodes = graph.nodes.filter(
    (n: GraphNode) => (n.flag_count ?? 0) > 0 || n.suspicious
  ).length;

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%" }}>
      <div className="graph-overlay">
        <h3 style={{ fontSize: "0.95rem", marginBottom: 4, fontWeight: 600 }}>
          Network Map
        </h3>
        <p
          style={{
            fontSize: "0.75rem",
            color: "var(--text-muted)",
            lineHeight: 1.4,
          }}
        >
          {graph.nodes.length} entities &middot; {fraudNodes} flagged
          <br />
          Click a node to filter queue
        </p>
      </div>
      {dimensions.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={{ nodes: graph.nodes, links: graph.edges as any }}
          /* -------- Node rendering -------- */
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const n = node as GraphNode;
            const isHovered = hoveredNode === n.id;
            const isFlagged = (n.flag_count ?? 0) > 0;
            const isMerchant = n.type === "merchant";

            // Size: merchants slightly bigger, cards small
            let radius = isMerchant ? 3 : 1.8;
            if (isFlagged) radius += 0.6;
            if (isHovered) radius += 1;

            // Color by role
            let fill: string;
            if (isMerchant && n.suspicious) fill = "#ef4444"; // red
            else if (isMerchant) fill = "#6366f1"; // indigo
            else if (isFlagged) fill = "#f59e0b"; // amber
            else fill = "#334155"; // slate-700, very subtle for normal cards

            const alpha = isFlagged || isMerchant ? 1 : 0.45;

            ctx.beginPath();
            ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI);
            ctx.fillStyle = fill;
            ctx.globalAlpha = alpha;
            ctx.fill();
            ctx.globalAlpha = 1;

            // Draw a glow ring around flagged nodes
            if (isFlagged || (isMerchant && n.suspicious)) {
              ctx.beginPath();
              ctx.arc(node.x!, node.y!, radius + 1.5, 0, 2 * Math.PI);
              ctx.strokeStyle = fill;
              ctx.globalAlpha = 0.25;
              ctx.lineWidth = 1;
              ctx.stroke();
              ctx.globalAlpha = 1;
            }

            // Label only on hover or for flagged merchants
            if (isHovered || (isMerchant && n.suspicious)) {
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
          /* -------- Link rendering -------- */
          linkColor={(link: any) => {
            if (link.type === "co_burst") return "rgba(239, 68, 68, 0.35)";
            if (link.type === "shared_ip") return "rgba(245, 158, 11, 0.25)";
            if (link.type === "shared_device")
              return "rgba(139, 92, 246, 0.25)";
            return "rgba(148, 163, 184, 0.06)"; // transaction links: nearly invisible
          }}
          linkWidth={(link: any) => {
            if (link.type === "co_burst")
              return Math.max(0.5, (link.weight || 1) * 0.3);
            if (link.type === "shared_ip" || link.type === "shared_device")
              return 0.5;
            return 0.15; // transaction links: hairline
          }}
          /* -------- Interactions -------- */
          onNodeHover={(node: any) => setHoveredNode(node?.id ?? null)}
          onNodeClick={(node: any) => {
            onNodeClick(node.id, node.type);
            if (fgRef.current) {
              fgRef.current.centerAt(node.x, node.y, 800);
              fgRef.current.zoom(6, 1200);
            }
          }}
          backgroundColor="transparent"
          cooldownTicks={120}
          enableNodeDrag={true}
        />
      )}
    </div>
  );
}
