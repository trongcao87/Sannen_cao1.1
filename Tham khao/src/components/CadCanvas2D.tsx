import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Crosshair,
  Hand,
  Maximize2,
  Merge,
  Minus,
  MousePointerClick,
  Plus,
  Scissors,
} from 'lucide-react';
import {
  Breakline,
  CanvasToolMode,
  ContourPolyline,
  CrossSectionDef,
  DesignSurfaceSpec,
  GridCalculationResult,
  LayerVisibility,
  Point2D,
  PolygonZone,
  SurveyPoint,
  TaluyCalculationResult,
  TinSurface,
} from '../types/snvn';
import { evaluateDesignElevation, interpolateTinZ } from '../engine/tin';

interface CadCanvas2DProps {
  mhtn: TinSurface;
  designSpec: DesignSurfaceSpec;
  customDesignTin?: TinSurface | null;
  points: SurveyPoint[];
  breaklines: Breakline[];
  boundary: PolygonZone;
  exclusions: PolygonZone[];
  gridResult: GridCalculationResult;
  contours: ContourPolyline[];
  taluyResult: TaluyCalculationResult;
  sections: CrossSectionDef[];
  activeSectionId: string;
  layers: LayerVisibility;
  toolMode: CanvasToolMode;
  onToolModeChange: (mode: CanvasToolMode) => void;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  selectedCellId: string | null;
  onSelectCell: (cellId: string | null) => void;
  pendingMergeCellId: string | null;
  onMergeCellClick: (cellId: string) => void;
  onCreateSection: (start: Point2D, end: Point2D) => void;
}

interface ViewportTransform {
  cx: number; // world X at canvas center
  cy: number; // world Y at canvas center
  scale: number; // pixels per meter
}

function elevationColor(t: number): string {
  // Smooth muted hypsometric ramp suitable for dark CAD canvas
  const clamped = Math.max(0, Math.min(1, t));
  if (clamped < 0.33) {
    const k = clamped / 0.33;
    const r = Math.round(18 + k * 14);
    const g = Math.round(58 + k * 48);
    const b = Math.round(82 - k * 18);
    return `rgba(${r},${g},${b},0.34)`;
  }
  if (clamped < 0.66) {
    const k = (clamped - 0.33) / 0.33;
    const r = Math.round(32 + k * 78);
    const g = Math.round(106 + k * 8);
    const b = Math.round(64 - k * 24);
    return `rgba(${r},${g},${b},0.34)`;
  }
  const k = (clamped - 0.66) / 0.34;
  const r = Math.round(110 + k * 45);
  const g = Math.round(114 - k * 34);
  const b = Math.round(40 - k * 8);
  return `rgba(${r},${g},${b},0.36)`;
}

export const CadCanvas2D: React.FC<CadCanvas2DProps> = ({
  mhtn,
  designSpec,
  customDesignTin,
  points,
  breaklines,
  boundary,
  exclusions,
  gridResult,
  contours,
  taluyResult,
  sections,
  activeSectionId,
  layers,
  toolMode,
  onToolModeChange,
  selectedNodeId,
  onSelectNode,
  selectedCellId,
  onSelectCell,
  pendingMergeCellId,
  onMergeCellClick,
  onCreateSection,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 960, height: 640 });
  const [view, setView] = useState<ViewportTransform>({ cx: 120, cy: 95, scale: 2.8 });
  const [hoverInfo, setHoverInfo] = useState<{
    x: number;
    y: number;
    hTN: number;
    hTK: number;
    dh: number;
  } | null>(null);
  const [sectionDraftStart, setSectionDraftStart] = useState<Point2D | null>(null);
  const [sectionDraftCurr, setSectionDraftCurr] = useState<Point2D | null>(null);

  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0, cx: 0, cy: 0 });
  const hasAutoFitRef = useRef(false);

  // Compute combined world bounding box
  const worldBounds = useMemo(() => {
    const b = mhtn.bounds;
    return {
      minX: Number.isFinite(b.minX) ? b.minX : 0,
      maxX: Number.isFinite(b.maxX) ? b.maxX : 250,
      minY: Number.isFinite(b.minY) ? b.minY : 0,
      maxY: Number.isFinite(b.maxY) ? b.maxY : 200,
    };
  }, [mhtn]);

  const zoomExtents = () => {
    const spanX = Math.max(worldBounds.maxX - worldBounds.minX, 40);
    const spanY = Math.max(worldBounds.maxY - worldBounds.minY, 40);
    const padFactor = 0.82;
    const scale = Math.min((size.width * padFactor) / spanX, (size.height * padFactor) / spanY);
    setView({
      cx: (worldBounds.minX + worldBounds.maxX) / 2,
      cy: (worldBounds.minY + worldBounds.maxY) / 2,
      scale: Math.max(0.4, Math.min(25, scale)),
    });
  };

  // Observe container resize
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = Math.max(300, Math.floor(entry.contentRect.width));
        const h = Math.max(260, Math.floor(entry.contentRect.height));
        setSize({ width: w, height: h });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Auto-fit when dataset changes or on first mount
  useEffect(() => {
    if (size.width > 300 && size.height > 260) {
      zoomExtents();
      hasAutoFitRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mhtn.bounds.minX, mhtn.bounds.maxX, mhtn.bounds.minY, mhtn.bounds.maxY, size.width > 300 && !hasAutoFitRef.current]);

  const worldToScreen = (wx: number, wy: number) => ({
    sx: size.width / 2 + (wx - view.cx) * view.scale,
    sy: size.height / 2 - (wy - view.cy) * view.scale,
  });

  const screenToWorld = (sx: number, sy: number): Point2D => ({
    x: view.cx + (sx - size.width / 2) / view.scale,
    y: view.cy - (sy - size.height / 2) / view.scale,
  });

  // Main 2D CAD vector rendering pass
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size.width * dpr;
    canvas.height = size.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // 1. Model Space background
    ctx.fillStyle = '#0B0F17';
    ctx.fillRect(0, 0, size.width, size.height);

    // Subtle CAD drafting coordinate grid
    const gridStepWorld = view.scale > 4 ? 10 : view.scale > 1.8 ? 20 : 50;
    const topLeft = screenToWorld(0, 0);
    const botRight = screenToWorld(size.width, size.height);
    const startX = Math.floor(topLeft.x / gridStepWorld) * gridStepWorld;
    const endX = Math.ceil(botRight.x / gridStepWorld) * gridStepWorld;
    const startY = Math.floor(botRight.y / gridStepWorld) * gridStepWorld;
    const endY = Math.ceil(topLeft.y / gridStepWorld) * gridStepWorld;

    ctx.strokeStyle = 'rgba(148, 163, 184, 0.06)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = startX; x <= endX; x += gridStepWorld) {
      const { sx } = worldToScreen(x, 0);
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, size.height);
    }
    for (let y = startY; y <= endY; y += gridStepWorld) {
      const { sy } = worldToScreen(0, y);
      ctx.moveTo(0, sy);
      ctx.lineTo(size.width, sy);
    }
    ctx.stroke();

    // 2. Elevation Heatmap on TIN triangles
    if (layers.heatmap && mhtn.triangles.length > 0) {
      const zRange = Math.max(0.5, mhtn.bounds.maxZ - mhtn.bounds.minZ);
      for (const tri of mhtn.triangles) {
        const va = mhtn.vertices[tri.a];
        const vb = mhtn.vertices[tri.b];
        const vc = mhtn.vertices[tri.c];
        const avgZ = (va.z + vb.z + vc.z) / 3;
        const t = (avgZ - mhtn.bounds.minZ) / zRange;
        const pA = worldToScreen(va.x, va.y);
        const pB = worldToScreen(vb.x, vb.y);
        const pC = worldToScreen(vc.x, vc.y);
        ctx.fillStyle = elevationColor(t);
        ctx.beginPath();
        ctx.moveTo(pA.sx, pA.sy);
        ctx.lineTo(pB.sx, pB.sy);
        ctx.lineTo(pC.sx, pC.sy);
        ctx.closePath();
        ctx.fill();
      }
    }

    // 3. TIN Wireframe (MHTN)
    if (layers.tinMhtn && mhtn.triangles.length > 0) {
      ctx.strokeStyle = 'rgba(34, 197, 94, 0.24)';
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      for (const tri of mhtn.triangles) {
        const va = worldToScreen(mhtn.vertices[tri.a].x, mhtn.vertices[tri.a].y);
        const vb = worldToScreen(mhtn.vertices[tri.b].x, mhtn.vertices[tri.b].y);
        const vc = worldToScreen(mhtn.vertices[tri.c].x, mhtn.vertices[tri.c].y);
        ctx.moveTo(va.sx, va.sy);
        ctx.lineTo(vb.sx, vb.sy);
        ctx.lineTo(vc.sx, vc.sy);
        ctx.lineTo(va.sx, va.sy);
      }
      ctx.stroke();
    }

    // 4. Contours (Đường đồng mức MHTN & MHTK)
    for (const c of contours) {
      if (c.surface === 'mhtn' && !layers.contoursMhtn) continue;
      if (c.surface === 'mhtk' && !layers.contoursMhtk) continue;
      if (c.points.length < 2) continue;

      if (c.surface === 'mhtn') {
        ctx.strokeStyle = c.isMajor ? 'rgba(217, 155, 78, 0.82)' : 'rgba(148, 163, 184, 0.38)';
        ctx.lineWidth = c.isMajor ? 1.5 : 0.8;
        ctx.setLineDash([]);
      } else {
        ctx.strokeStyle = c.isMajor ? 'rgba(56, 189, 248, 0.78)' : 'rgba(56, 189, 248, 0.35)';
        ctx.lineWidth = c.isMajor ? 1.3 : 0.75;
        ctx.setLineDash([5, 3]);
      }

      ctx.beginPath();
      c.points.forEach((pt, idx) => {
        const { sx, sy } = worldToScreen(pt.x, pt.y);
        if (idx === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      if (c.labelPoint && view.scale >= 1.5) {
        const { sx, sy } = worldToScreen(c.labelPoint.x, c.labelPoint.y);
        ctx.save();
        ctx.translate(sx, sy);
        ctx.rotate(-c.labelPoint.angleRad);
        ctx.font = '500 10px "JetBrains Mono", monospace';
        const txt = c.elevation.toFixed(1);
        const tw = ctx.measureText(txt).width;
        ctx.fillStyle = '#0B0F17';
        ctx.fillRect(-tw / 2 - 2, -6, tw + 4, 12);
        ctx.fillStyle = c.surface === 'mhtn' ? '#F5B971' : '#7DD3FC';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(txt, 0, 0);
        ctx.restore();
      }
    }

    // 5. Cut / Fill shaded polygons inside grid cells
    if (layers.cellVolumes) {
      for (const cell of gridResult.cells) {
        if (!cell.active) continue;
        for (const sub of cell.subPolygons) {
          if (sub.polygon.length < 3) continue;
          ctx.fillStyle =
            sub.type === 'fill' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(234, 179, 8, 0.12)';
          ctx.beginPath();
          sub.polygon.forEach((pt, idx) => {
            const { sx, sy } = worldToScreen(pt.x, pt.y);
            if (idx === 0) ctx.moveTo(sx, sy);
            else ctx.lineTo(sx, sy);
          });
          ctx.closePath();
          ctx.fill();
        }
      }
    }

    // 6. Grid Lines & Selected Cell Highlight
    if (layers.gridLines) {
      for (const cell of gridResult.cells) {
        if (!cell.active) continue;
        const isSelected = cell.id === selectedCellId || cell.id === pendingMergeCellId;
        ctx.strokeStyle = isSelected ? '#38BDF8' : 'rgba(148, 163, 184, 0.42)';
        ctx.lineWidth = isSelected ? 2 : 0.9;
        ctx.beginPath();
        cell.corners.forEach((pt, idx) => {
          const { sx, sy } = worldToScreen(pt.x, pt.y);
          if (idx === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.stroke();
        if (isSelected) {
          ctx.fillStyle = 'rgba(56, 189, 248, 0.12)';
          ctx.fill();
        }
      }
    }

    // 7. Boundary & Exclusion Polygons
    if (layers.boundary) {
      if (boundary.vertices.length >= 3) {
        ctx.strokeStyle = '#60A5FA';
        ctx.lineWidth = 2;
        ctx.beginPath();
        boundary.vertices.forEach((pt, idx) => {
          const { sx, sy } = worldToScreen(pt.x, pt.y);
          if (idx === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.stroke();
      }
      for (const ex of exclusions) {
        if (ex.vertices.length < 3) continue;
        ctx.fillStyle = 'rgba(15, 23, 42, 0.78)';
        ctx.strokeStyle = '#94A3B8';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ex.vertices.forEach((pt, idx) => {
          const { sx, sy } = worldToScreen(pt.x, pt.y);
          if (idx === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);

        // Label exclusion zone
        const avgX = ex.vertices.reduce((s, p) => s + p.x, 0) / ex.vertices.length;
        const avgY = ex.vertices.reduce((s, p) => s + p.y, 0) / ex.vertices.length;
        const sc = worldToScreen(avgX, avgY);
        ctx.font = '500 11px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = '#94A3B8';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Vùng bỏ qua', sc.sx, sc.sy);
      }
    }

    // 8. Breaklines (3D Polyline — Magenta)
    if (layers.breaklines) {
      ctx.strokeStyle = '#D946EF';
      ctx.lineWidth = 1.8;
      for (const bl of breaklines) {
        if (bl.vertices.length < 2) continue;
        ctx.beginPath();
        bl.vertices.forEach((v, idx) => {
          const { sx, sy } = worldToScreen(v.x, v.y);
          if (idx === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.stroke();
      }
    }

    // 9. Taluy 2D Ticks (vạch dài, vạch ngắn — SNVN Chapter V.4)
    if (layers.taluy && taluyResult.segments.length > 0) {
      for (const seg of taluyResult.segments) {
        if (seg.toeLine.length < 2) continue;
        ctx.strokeStyle = seg.type === 'fill' ? 'rgba(239, 68, 68, 0.78)' : 'rgba(234, 179, 8, 0.78)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        seg.toeLine.forEach((p, idx) => {
          const { sx, sy } = worldToScreen(p.x, p.y);
          if (idx === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        });
        ctx.stroke();
      }
      for (const tk of taluyResult.ticks2D) {
        const a = worldToScreen(tk.p1.x, tk.p1.y);
        const b = worldToScreen(tk.p2.x, tk.p2.y);
        ctx.strokeStyle = tk.type === 'fill' ? '#EF4444' : '#EAB308';
        ctx.lineWidth = tk.isLong ? 1.2 : 0.85;
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();
      }
    }

    // 10. Zero-Line (Ranh giới đào đắp ΔH = 0)
    if (layers.zeroLine && gridResult.zeroLines.length > 0) {
      ctx.strokeStyle = '#38BDF8';
      ctx.lineWidth = 2.1;
      ctx.beginPath();
      for (const seg of gridResult.zeroLines) {
        const a = worldToScreen(seg.p1.x, seg.p1.y);
        const b = worldToScreen(seg.p2.x, seg.p2.y);
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
      }
      ctx.stroke();
    }

    // 11. SNVN Volume Circle Symbols (Area | Avg ΔH / Volume)
    if (layers.cellVolumes && view.scale >= 1.45) {
      const drawCircleBadge = (
        wx: number,
        wy: number,
        type: 'cut' | 'fill',
        area: number,
        avgH: number,
        vol: number,
        merged = false
      ) => {
        const { sx, sy } = worldToScreen(wx, wy);
        const r = Math.min(28, Math.max(11, view.scale * (merged ? 4.8 : 3.5)));
        const strokeCol = type === 'fill' ? '#F87171' : '#FACC15';

        ctx.fillStyle = 'rgba(11, 15, 23, 0.86)';
        ctx.strokeStyle = strokeCol;
        ctx.lineWidth = merged ? 1.8 : 1.1;
        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Horizontal divider & top vertical divider (Authentic SNVN Circle Symbol p.35)
        ctx.beginPath();
        ctx.moveTo(sx - r, sy);
        ctx.lineTo(sx + r, sy);
        ctx.moveTo(sx, sy - r);
        ctx.lineTo(sx, sy);
        ctx.stroke();

        if (r >= 15) {
          const fs = Math.min(10, Math.max(7.5, r * 0.36));
          ctx.font = `500 ${fs}px "JetBrains Mono", monospace`;
          ctx.fillStyle = strokeCol;
          ctx.textBaseline = 'middle';
          ctx.textAlign = 'right';
          ctx.fillText(area.toFixed(0), sx - 2, sy - r * 0.36);
          ctx.textAlign = 'left';
          ctx.fillText(avgH.toFixed(2), sx + 2, sy - r * 0.36);
          ctx.textAlign = 'center';
          ctx.font = `600 ${fs + 0.5}px "JetBrains Mono", monospace`;
          ctx.fillText(vol.toFixed(1), sx, sy + r * 0.44);
        }
      };

      const mergedIds = new Set(gridResult.mergedGroups.flatMap((g) => g.cellIds));
      for (const cell of gridResult.cells) {
        if (!cell.active || mergedIds.has(cell.id)) continue;
        for (const sub of cell.subPolygons) {
          if (sub.area < 8) continue;
          drawCircleBadge(sub.centroid.x, sub.centroid.y, sub.type, sub.area, sub.avgDeltaH, sub.volume);
        }
      }
      for (const grp of gridResult.mergedGroups) {
        drawCircleBadge(grp.centroid.x, grp.centroid.y, grp.type, grp.area, grp.avgH, grp.volume, true);
      }
    }

    // 12. SNVN 4-Quadrant Grid Node Elevations (H_TN green, H_TK red, ΔH yellow, Row-Col blue)
    if (layers.nodeLabels) {
      const showNodeText = view.scale >= 2.2;
      for (const row of gridResult.nodes) {
        for (const n of row) {
          if (!n.insideBoundary) continue;
          const { sx, sy } = worldToScreen(n.x, n.y);
          const isSelected = n.id === selectedNodeId;

          if (isSelected || n.isCustomHTK) {
            ctx.strokeStyle = isSelected ? '#38BDF8' : '#F472B6';
            ctx.lineWidth = isSelected ? 2 : 1.4;
            ctx.beginPath();
            ctx.arc(sx, sy, isSelected ? 7 : 4.5, 0, Math.PI * 2);
            ctx.stroke();
          }

          ctx.fillStyle = isSelected ? '#38BDF8' : '#CBD5E1';
          ctx.fillRect(sx - 1.5, sy - 1.5, 3, 3);

          if (showNodeText) {
            const fs = Math.min(10.5, Math.max(8, view.scale * 2.2));
            ctx.font = `500 ${fs}px "JetBrains Mono", monospace`;
            const off = 3;

            // Top-Left: CĐTN (Green)
            ctx.fillStyle = '#4ADE80';
            ctx.textAlign = 'right';
            ctx.textBaseline = 'bottom';
            ctx.fillText(n.hTN.toFixed(2), sx - off, sy - off);

            // Top-Right: CĐTK (Red)
            ctx.fillStyle = '#F87171';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'bottom';
            ctx.fillText(n.hTK.toFixed(2), sx + off, sy - off);

            // Bottom-Left: Chênh cao ΔH (Yellow)
            ctx.fillStyle = '#FACC15';
            ctx.textAlign = 'right';
            ctx.textBaseline = 'top';
            ctx.fillText(Math.abs(n.deltaH).toFixed(2), sx - off, sy + off);

            // Bottom-Right: Chỉ số hàng-cột (Blue)
            ctx.fillStyle = '#93C5FD';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'top';
            ctx.fillText(n.id, sx + off, sy + off);
          }
        }
      }
    }

    // 13. Survey Points (optional crosshair dots)
    if (layers.points) {
      ctx.fillStyle = 'rgba(148, 163, 184, 0.65)';
      for (const p of points) {
        const { sx, sy } = worldToScreen(p.x, p.y);
        ctx.fillRect(sx - 1.5, sy - 1.5, 3, 3);
      }
    }

    // 14. Axis Totals (Lập trục — SNVN Chapter VII.2)
    if (layers.axisTotals && gridResult.nodes.length > 1) {
      const topRowIdx = gridResult.nodes.length - 1;
      const rightColIdx = gridResult.nodes[0].length - 1;

      ctx.font = '600 9.5px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      // Top column summary bubbles
      for (let c = 0; c < gridResult.colSummaries.length; c++) {
        const cs = gridResult.colSummaries[c];
        if (cs.cutVolume + cs.fillVolume < 1) continue;
        const nL = gridResult.nodes[topRowIdx][c];
        const nR = gridResult.nodes[topRowIdx][c + 1];
        const midX = (nL.x + nR.x) / 2;
        const midY = (nL.y + nR.y) / 2 + 10;
        const { sx, sy } = worldToScreen(midX, midY);

        ctx.fillStyle = '#141B29';
        ctx.strokeStyle = '#475569';
        ctx.lineWidth = 1;
        ctx.fillRect(sx - 24, sy - 13, 48, 26);
        ctx.strokeRect(sx - 24, sy - 13, 48, 26);

        ctx.fillStyle = '#FACC15';
        ctx.fillText(`Đ:${Math.round(cs.cutVolume)}`, sx, sy - 5);
        ctx.fillStyle = '#F87171';
        ctx.fillText(`L:${Math.round(cs.fillVolume)}`, sx, sy + 6);
      }

      // Right row summary bubbles
      for (let r = 0; r < gridResult.rowSummaries.length; r++) {
        const rs = gridResult.rowSummaries[r];
        if (rs.cutVolume + rs.fillVolume < 1) continue;
        const nB = gridResult.nodes[r][rightColIdx];
        const nT = gridResult.nodes[r + 1][rightColIdx];
        const midX = (nB.x + nT.x) / 2 + 12;
        const midY = (nB.y + nT.y) / 2;
        const { sx, sy } = worldToScreen(midX, midY);

        ctx.fillStyle = '#141B29';
        ctx.strokeStyle = '#475569';
        ctx.lineWidth = 1;
        ctx.fillRect(sx - 24, sy - 13, 48, 26);
        ctx.strokeRect(sx - 24, sy - 13, 48, 26);

        ctx.fillStyle = '#FACC15';
        ctx.fillText(`Đ:${Math.round(rs.cutVolume)}`, sx, sy - 5);
        ctx.fillStyle = '#F87171';
        ctx.fillText(`L:${Math.round(rs.fillVolume)}`, sx, sy + 6);
      }
    }

    // 15. Cross-Section Cut Lines (Tuyến mặt cắt ngang TCVN)
    if (layers.crossSections) {
      for (const sec of sections) {
        const isActive = sec.id === activeSectionId;
        const a = worldToScreen(sec.start.x, sec.start.y);
        const b = worldToScreen(sec.end.x, sec.end.y);

        ctx.strokeStyle = isActive ? '#38BDF8' : 'rgba(56, 189, 248, 0.55)';
        ctx.lineWidth = isActive ? 2.2 : 1.4;
        ctx.setLineDash([10, 4, 2, 4]);
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();
        ctx.setLineDash([]);

        // End markers
        [a, b].forEach((pt) => {
          ctx.fillStyle = isActive ? '#38BDF8' : '#0284C7';
          ctx.beginPath();
          ctx.arc(pt.sx, pt.sy, 4.5, 0, Math.PI * 2);
          ctx.fill();
        });

        ctx.font = '600 11px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = '#E0F2FE';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'bottom';
        ctx.fillText(sec.name, a.sx + 8, a.sy - 6);
      }
    }

    // Draft cross-section preview line
    if (sectionDraftStart && sectionDraftCurr) {
      const a = worldToScreen(sectionDraftStart.x, sectionDraftStart.y);
      const b = worldToScreen(sectionDraftCurr.x, sectionDraftCurr.y);
      ctx.strokeStyle = '#38BDF8';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(a.sx, a.sy);
      ctx.lineTo(b.sx, b.sy);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [
    size,
    view,
    mhtn,
    points,
    breaklines,
    boundary,
    exclusions,
    gridResult,
    contours,
    taluyResult,
    sections,
    activeSectionId,
    layers,
    selectedNodeId,
    selectedCellId,
    pendingMergeCellId,
    sectionDraftStart,
    sectionDraftCurr,
  ]);

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const before = screenToWorld(mx, my);
    const factor = e.deltaY < 0 ? 1.14 : 1 / 1.14;
    const nextScale = Math.max(0.35, Math.min(35, view.scale * factor));
    const nextCx = before.x - (mx - size.width / 2) / nextScale;
    const nextCy = before.y + (my - size.height / 2) / nextScale;
    setView({ cx: nextCx, cy: nextCy, scale: nextScale });
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const worldPt = screenToWorld(mx, my);

    // Middle/Right button always pans
    if (e.button === 1 || e.button === 2 || toolMode === 'pan') {
      isDraggingRef.current = true;
      dragStartRef.current = { x: e.clientX, y: e.clientY, cx: view.cx, cy: view.cy };
      return;
    }

    if (toolMode === 'edit_node') {
      // Find nearest active grid node within 18px
      let nearestId: string | null = null;
      let minPx = 20;
      for (const row of gridResult.nodes) {
        for (const n of row) {
          if (!n.insideBoundary) continue;
          const sc = worldToScreen(n.x, n.y);
          const d = Math.hypot(sc.sx - mx, sc.sy - my);
          if (d < minPx) {
            minPx = d;
            nearestId = n.id;
          }
        }
      }
      if (nearestId) {
        onSelectNode(nearestId);
        onSelectCell(null);
      } else {
        // Check if clicked inside a cell
        const clickedCell = findCellAt(worldPt);
        onSelectCell(clickedCell ? clickedCell.id : null);
        onSelectNode(null);
      }
      return;
    }

    if (toolMode === 'merge_cell') {
      const clickedCell = findCellAt(worldPt);
      if (clickedCell) {
        onMergeCellClick(clickedCell.id);
      }
      return;
    }

    if (toolMode === 'draw_section') {
      if (!sectionDraftStart) {
        setSectionDraftStart(worldPt);
        setSectionDraftCurr(worldPt);
      } else {
        if (Math.hypot(worldPt.x - sectionDraftStart.x, worldPt.y - sectionDraftStart.y) > 5) {
          onCreateSection(sectionDraftStart, worldPt);
        }
        setSectionDraftStart(null);
        setSectionDraftCurr(null);
      }
    }
  };

  const findCellAt = (pt: Point2D) => {
    for (const cell of gridResult.cells) {
      if (!cell.active) continue;
      const xs = cell.corners.map((c) => c.x);
      const ys = cell.corners.map((c) => c.y);
      if (
        pt.x >= Math.min(...xs) &&
        pt.x <= Math.max(...xs) &&
        pt.y >= Math.min(...ys) &&
        pt.y <= Math.max(...ys)
      ) {
        return cell;
      }
    }
    return null;
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (isDraggingRef.current) {
      const dx = e.clientX - dragStartRef.current.x;
      const dy = e.clientY - dragStartRef.current.y;
      setView((prev) => ({
        ...prev,
        cx: dragStartRef.current.cx - dx / prev.scale,
        cy: dragStartRef.current.cy + dy / prev.scale,
      }));
      return;
    }

    const wPt = screenToWorld(mx, my);
    if (sectionDraftStart) {
      setSectionDraftCurr(wPt);
    }
    const hTN = interpolateTinZ(mhtn, wPt.x, wPt.y);
    const hTK = evaluateDesignElevation(designSpec, wPt.x, wPt.y, customDesignTin);
    setHoverInfo({ x: wPt.x, y: wPt.y, hTN, hTK, dh: hTK - hTN });
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const cursorClass =
    toolMode === 'pan'
      ? 'cursor-grab active:cursor-grabbing'
      : toolMode === 'draw_section'
      ? 'cursor-crosshair'
      : 'cursor-pointer';

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden bg-[#0B0F17] select-none">
      <canvas
        ref={canvasRef}
        style={{ width: size.width, height: size.height }}
        className={`block ${cursorClass}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          isDraggingRef.current = false;
          setHoverInfo(null);
        }}
        onContextMenu={(e) => e.preventDefault()}
      />

      {/* Top-Left Compact Drafting Toolbar */}
      <div className="absolute left-3 top-3 z-10 flex items-center gap-1 rounded-lg border border-[#263248] bg-[#141B29]/95 p-1">
        <button
          type="button"
          onClick={() => {
            onToolModeChange('pan');
            setSectionDraftStart(null);
          }}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
            toolMode === 'pan'
              ? 'bg-sky-500/20 text-sky-300'
              : 'text-slate-400 hover:bg-[#1C2538] hover:text-slate-100'
          }`}
          title="Di chuyển bản vẽ (Pan)"
        >
          <Hand className="h-3.5 w-3.5" />
          Di chuyển
        </button>
        <button
          type="button"
          onClick={() => {
            onToolModeChange('edit_node');
            setSectionDraftStart(null);
          }}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
            toolMode === 'edit_node'
              ? 'bg-sky-500/20 text-sky-300'
              : 'text-slate-400 hover:bg-[#1C2538] hover:text-slate-100'
          }`}
          title="Click chọn nút lưới để hiệu chỉnh cao độ CĐTK hoặc xem ô lưới"
        >
          <MousePointerClick className="h-3.5 w-3.5" />
          Chọn / Sửa nút
        </button>
        <button
          type="button"
          onClick={() => {
            onToolModeChange('merge_cell');
            setSectionDraftStart(null);
          }}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
            toolMode === 'merge_cell'
              ? 'bg-sky-500/20 text-sky-300'
              : 'text-slate-400 hover:bg-[#1C2538] hover:text-slate-100'
          }`}
          title="Lệnh DD_MC: Click lần lượt 2 ô cùng loại (đào hoặc đắp) để cộng gộp khối lượng"
        >
          <Merge className="h-3.5 w-3.5" />
          Cộng ô
        </button>
        <button
          type="button"
          onClick={() => {
            onToolModeChange('draw_section');
            setSectionDraftStart(null);
          }}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
            toolMode === 'draw_section'
              ? 'bg-sky-500/20 text-sky-300'
              : 'text-slate-400 hover:bg-[#1C2538] hover:text-slate-100'
          }`}
          title="Click 2 điểm trên mặt bằng để kẻ tuyến mặt cắt ngang TCVN"
        >
          <Scissors className="h-3.5 w-3.5" />
          Kẻ mặt cắt
        </button>
      </div>

      {/* Top-Right Zoom Controls */}
      <div className="absolute right-3 top-3 z-10 flex items-center gap-1 rounded-lg border border-[#263248] bg-[#141B29]/95 p-1">
        <button
          type="button"
          onClick={() => setView((v) => ({ ...v, scale: Math.min(35, v.scale * 1.25) }))}
          className="rounded-md p-1.5 text-slate-300 hover:bg-[#1C2538] hover:text-white"
          title="Phóng to"
        >
          <Plus className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setView((v) => ({ ...v, scale: Math.max(0.35, v.scale / 1.25) }))}
          className="rounded-md p-1.5 text-slate-300 hover:bg-[#1C2538] hover:text-white"
          title="Thu nhỏ"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={zoomExtents}
          className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-slate-300 hover:bg-[#1C2538] hover:text-white whitespace-nowrap shrink-0"
          title="Zoom toàn bản vẽ (Zoom Extents)"
        >
          <Maximize2 className="h-3.5 w-3.5" />
          Toàn cảnh
        </button>
      </div>

      {/* Contextual Action Hint when in Merge or Section Drawing Mode */}
      {(toolMode === 'merge_cell' || toolMode === 'draw_section' || toolMode === 'edit_node') && (
        <div className="pointer-events-none absolute left-3 top-14 z-10 rounded-md border border-[#263248] bg-[#141B29]/90 px-3 py-1.5 text-xs text-slate-300">
          {toolMode === 'edit_node' &&
            'Nhấn vào giao điểm lưới để chỉnh cao độ thiết kế (CĐTK) hoặc nhấn vào giữa ô để xem chi tiết.'}
          {toolMode === 'merge_cell' &&
            (pendingMergeCellId
              ? `Đã chọn ô ${pendingMergeCellId}. Nhấn tiếp vào ô thứ hai cùng tính chất (đào/đắp) để gộp.`
              : 'Chế độ Cộng ô (DD_MC): Nhấn chọn ô thứ nhất cần gộp khối lượng.')}
          {toolMode === 'draw_section' &&
            (sectionDraftStart
              ? 'Nhấn chọn điểm cuối tuyến cắt để hoàn tất mặt cắt ngang TCVN.'
              : 'Nhấn chọn điểm đầu tuyến cắt trên bản vẽ mặt bằng.')}
        </div>
      )}

      {/* Bottom Live Surveying Coordinates & SNVN Legend Strip */}
      <div className="absolute bottom-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#263248] bg-[#141B29]/95 px-3.5 py-2 text-xs">
        <div className="flex items-center gap-4 font-mono tabular-nums text-slate-300">
          <span className="flex items-center gap-1.5 text-slate-400">
            <Crosshair className="h-3.5 w-3.5 text-sky-400" />
            {hoverInfo ? (
              <>
                <span>X: {hoverInfo.x.toFixed(2)}</span>
                <span className="text-slate-600">·</span>
                <span>Y: {hoverInfo.y.toFixed(2)}</span>
                <span className="text-slate-600">·</span>
                <span className="text-emerald-400">TN: {hoverInfo.hTN.toFixed(2)}m</span>
                <span className="text-slate-600">·</span>
                <span className="text-red-400">TK: {hoverInfo.hTK.toFixed(2)}m</span>
                <span className="text-slate-600">·</span>
                <span className={hoverInfo.dh >= 0 ? 'text-red-300' : 'text-amber-300'}>
                  ΔH: {hoverInfo.dh >= 0 ? '+' : ''}
                  {hoverInfo.dh.toFixed(2)}m ({hoverInfo.dh >= 0 ? 'Đắp' : 'Đào'})
                </span>
              </>
            ) : (
              <span>Di chuột trên mặt bằng để đọc cao độ nội suy TIN</span>
            )}
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="text-emerald-400">CĐTN</span>
          <span aria-hidden="true">·</span>
          <span className="text-red-400">CĐTK / Đắp</span>
          <span aria-hidden="true">·</span>
          <span className="text-amber-400">Đào / ΔH</span>
          <span aria-hidden="true">·</span>
          <span className="text-sky-400">Ranh giới 0</span>
          <span aria-hidden="true">·</span>
          <span className="text-fuchsia-400">Đứt gãy 3D</span>
        </div>
      </div>
    </div>
  );
};
