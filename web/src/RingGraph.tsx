import { useEffect, useState, useCallback, useRef } from "react";
import ForceGraph2D, { ForceGraphMethods } from "react-force-graph-2d";
import { fetchGraph } from "./api";
import type { Graph, GraphNode } from "./types";

interface RingGraphProps {
  onNodeClick: (id: string, type: string) => void;
}

export function RingGraph({ onNodeClick }: RingGraphProps) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
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
          height: containerRef.current.clientHeight
        });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [graph]); // Re-measure when graph loads

  if (!graph) return <div style={{padding: 16}}>Loading graph...</div>;

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <div className="graph-overlay">
        <h3 style={{fontSize: '1rem', marginBottom: 4}}>Fraud Rings</h3>
        <p style={{fontSize: '0.8rem', color: 'var(--text-muted)'}}>
          {graph.nodes.length} nodes · {graph.edges.length} edges
        </p>
      </div>
      {dimensions.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graph}
          nodeLabel="id"
          nodeColor={(node: any) => {
            const n = node as GraphNode;
            if (n.type === 'merchant') return 'var(--danger)';
            if (n.flag_count && n.flag_count > 0) return 'var(--warning)';
            return 'var(--accent-blue)';
          }}
          nodeVal={(node: any) => {
            const n = node as GraphNode;
            if (n.type === 'merchant') return 8;
            return 3;
          }}
          linkColor={(link: any) => {
            if (link.type === 'co_burst') return 'rgba(239, 68, 68, 0.4)';
            return 'rgba(148, 163, 184, 0.2)';
          }}
          linkWidth={(link: any) => {
            if (link.type === 'co_burst') return Math.max(1, (link.weight || 1) / 2);
            return 1;
          }}
          onNodeClick={(node: any) => {
            onNodeClick(node.id, node.type);
            
            // Center camera on node
            if (fgRef.current) {
              fgRef.current.centerAt(node.x, node.y, 1000);
              fgRef.current.zoom(8, 2000);
            }
          }}
          backgroundColor="transparent"
        />
      )}
    </div>
  );
}
