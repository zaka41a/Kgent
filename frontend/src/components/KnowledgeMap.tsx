import { useEffect, useRef } from "react";
import type { GraphEdge, GraphNode } from "../lib/api";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlight?: string[];
  className?: string;
}

interface SimNode {
  id: string;
  label: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  deg: number;
}

interface Palette {
  ink: string;
  muted: string;
  dim: string;
  accent: string;
  bg: string;
}

interface Sim {
  setHighlight: (ids: string[]) => void;
  destroy: () => void;
}

function readPalette(el: Element): Palette {
  const cs = getComputedStyle(el);
  const c = (name: string) => `rgb(${cs.getPropertyValue(name).trim()})`;
  return {
    ink: c("--ink"),
    muted: c("--ink-muted"),
    dim: c("--ink-dim"),
    accent: c("--accent"),
    bg: c("--bg-card"),
  };
}

function createSim(
  canvas: HTMLCanvasElement,
  rawNodes: GraphNode[],
  rawEdges: GraphEdge[],
  initialHighlight: string[],
): Sim {
  const ctx = canvas.getContext("2d");
  if (!ctx) return { setHighlight: () => {}, destroy: () => {} };

  const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let pal = readPalette(canvas);
  let highlight = new Set(initialHighlight);
  let width = 0;
  let height = 0;

  const nodes: SimNode[] = rawNodes.map((n, i) => {
    const a = (i / Math.max(1, rawNodes.length)) * Math.PI * 2;
    return {
      id: n.id,
      label: n.label,
      x: 0.5 + Math.cos(a) * 0.28 + (Math.random() - 0.5) * 0.06,
      y: 0.5 + Math.sin(a) * 0.28 + (Math.random() - 0.5) * 0.06,
      vx: 0,
      vy: 0,
      deg: 1,
    };
  });
  const byId = new Map<string, SimNode>();
  nodes.forEach((n) => byId.set(n.id, n));
  const edges = rawEdges.filter((e) => byId.has(e.src) && byId.has(e.dst));
  edges.forEach((e) => {
    byId.get(e.src)!.deg += 1;
    byId.get(e.dst)!.deg += 1;
  });

  const mouse = { x: -999, y: -999, active: false };

  function resize() {
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function step() {
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.0008;
        const f = 0.00028 / d2;
        const d = Math.sqrt(d2);
        const ux = dx / d;
        const uy = dy / d;
        a.vx += ux * f;
        a.vy += uy * f;
        b.vx -= ux * f;
        b.vy -= uy * f;
      }
    }
    edges.forEach((e) => {
      const a = byId.get(e.src)!;
      const b = byId.get(e.dst)!;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.0001;
      const f = (d - 0.2) * 0.01;
      const ux = dx / d;
      const uy = dy / d;
      a.vx += ux * f;
      a.vy += uy * f;
      b.vx -= ux * f;
      b.vy -= uy * f;
    });
    nodes.forEach((n) => {
      n.vx += (0.5 - n.x) * 0.004;
      n.vy += (0.5 - n.y) * 0.004;
      if (mouse.active) {
        const dx = n.x - mouse.x;
        const dy = n.y - mouse.y;
        const d2 = dx * dx + dy * dy + 0.001;
        if (d2 < 0.05) {
          const f = 0.00035 / d2;
          const d = Math.sqrt(d2);
          n.vx += (dx / d) * f;
          n.vy += (dy / d) * f;
        }
      }
      n.vx *= 0.86;
      n.vy *= 0.86;
      n.x = Math.max(0.06, Math.min(0.94, n.x + n.vx));
      n.y = Math.max(0.08, Math.min(0.92, n.y + n.vy));
    });
  }

  function draw() {
    ctx!.clearRect(0, 0, width, height);
    edges.forEach((e) => {
      const a = byId.get(e.src)!;
      const b = byId.get(e.dst)!;
      const hot = highlight.has(a.id) || highlight.has(b.id);
      ctx!.beginPath();
      ctx!.moveTo(a.x * width, a.y * height);
      ctx!.lineTo(b.x * width, b.y * height);
      ctx!.strokeStyle = hot ? pal.accent : pal.dim;
      ctx!.globalAlpha = hot ? 0.85 : 0.3;
      ctx!.lineWidth = hot ? 1.6 : 0.9;
      ctx!.stroke();
    });
    ctx!.globalAlpha = 1;

    // Only the cited nodes and the one under the cursor get a label; showing
    // every hub at once turns a large graph into an unreadable pile of text.
    let hoverId: string | null = null;
    if (mouse.active) {
      let best = Infinity;
      for (const n of nodes) {
        const dx = n.x * width - mouse.x * width;
        const dy = n.y * height - mouse.y * height;
        const d = dx * dx + dy * dy;
        if (d < best) {
          best = d;
          hoverId = n.id;
        }
      }
      if (best > 24 * 24) hoverId = null;
    }

    nodes.forEach((n) => {
      const x = n.x * width;
      const y = n.y * height;
      const on = highlight.has(n.id);
      const r = 3.4 + Math.min(4, n.deg * 0.9) + (on ? 2.2 : 0);
      if (on) {
        ctx!.beginPath();
        ctx!.arc(x, y, r + 7, 0, Math.PI * 2);
        ctx!.fillStyle = pal.accent;
        ctx!.globalAlpha = 0.18;
        ctx!.fill();
        ctx!.globalAlpha = 1;
      }
      ctx!.beginPath();
      ctx!.arc(x, y, r, 0, Math.PI * 2);
      ctx!.fillStyle = on ? pal.accent : pal.dim;
      ctx!.fill();
      ctx!.lineWidth = 1.4;
      ctx!.strokeStyle = pal.bg;
      ctx!.stroke();
      if (on || n.id === hoverId) {
        ctx!.font = `${on ? "600 " : "500 "}11px ui-monospace, Menlo, monospace`;
        ctx!.fillStyle = pal.ink;
        ctx!.textAlign = "center";
        ctx!.fillText(n.label, x, y - r - 6);
      }
    });
  }

  let raf: number | null = null;
  let settle = 0;
  function loop() {
    step();
    draw();
    if (!reduced) {
      raf = requestAnimationFrame(loop);
    } else if (settle++ < 260) {
      raf = requestAnimationFrame(loop);
    }
  }

  const onMove = (ev: MouseEvent) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = (ev.clientX - rect.left) / rect.width;
    mouse.y = (ev.clientY - rect.top) / rect.height;
    mouse.active = true;
  };
  const onLeave = () => {
    mouse.active = false;
    mouse.x = -999;
    mouse.y = -999;
  };
  canvas.addEventListener("mousemove", onMove);
  canvas.addEventListener("mouseleave", onLeave);

  const ro = new ResizeObserver(() => {
    resize();
    if (reduced) draw();
  });
  ro.observe(canvas);

  // Recolor when the app toggles its theme (html gains/loses the theme class).
  const mo = new MutationObserver(() => {
    pal = readPalette(canvas);
    if (reduced) draw();
  });
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

  resize();
  for (let s = 0; s < 90; s++) step();
  loop();

  return {
    setHighlight(ids: string[]) {
      highlight = new Set(ids);
      if (reduced) {
        settle = 0;
        if (raf === null) loop();
        else draw();
      }
    },
    destroy() {
      if (raf !== null) cancelAnimationFrame(raf);
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mouseleave", onLeave);
      ro.disconnect();
      mo.disconnect();
    },
  };
}

export default function KnowledgeMap({ nodes, edges, highlight = [], className }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const simRef = useRef<Sim | null>(null);
  const highlightRef = useRef(highlight);
  highlightRef.current = highlight;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const sim = createSim(canvas, nodes, edges, highlightRef.current);
    simRef.current = sim;
    return () => {
      sim.destroy();
      simRef.current = null;
    };
  }, [nodes, edges]);

  useEffect(() => {
    simRef.current?.setHighlight(highlight);
  }, [highlight]);

  return <canvas ref={canvasRef} className={className} />;
}
