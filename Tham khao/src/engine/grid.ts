import {
  ColumnSummary,
  DesignSurfaceSpec,
  GridCalculationResult,
  GridCell,
  GridConfig,
  GridNode,
  MergedCellGroup,
  Point2D,
  PolygonZone,
  RowSummary,
  SubPolygonVolume,
  TinSurface,
  ZeroLineSegment,
} from '../types/snvn';
import { evaluateDesignElevation, interpolateTinZ } from './tin';

interface PointWithDelta extends Point2D {
  dh: number; // hTK - hTN (+ fill, - cut)
}

/** Parse SNVN grid spec like "5x20,5x15,5x20" or "12x20.0" into array of dimensions */
export function parseGridSpec(spec: string, fallbackStep = 20): number[] {
  const parts = spec
    .split(/[,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  const dims: number[] = [];
  for (const part of parts) {
    const match = part.match(/^(\d+)\s*[xX*]\s*(\d+(?:\.\d+)?)$/);
    if (match) {
      const count = Math.min(Math.max(parseInt(match[1], 10), 1), 60);
      const size = Math.min(Math.max(parseFloat(match[2]), 2), 200);
      for (let i = 0; i < count; i++) dims.push(size);
    } else {
      const num = parseFloat(part);
      if (!Number.isNaN(num) && num >= 2 && num <= 200) {
        dims.push(num);
      }
    }
  }
  if (dims.length === 0) {
    for (let i = 0; i < 10; i++) dims.push(fallbackStep);
  }
  return dims.slice(0, 60);
}

/** Format an array of widths/heights back into compact SNVN syntax e.g. "5x20,2x15" */
export function formatGridSpec(dims: number[]): string {
  if (dims.length === 0) return '10x20';
  const groups: string[] = [];
  let current = dims[0];
  let count = 1;
  for (let i = 1; i < dims.length; i++) {
    if (Math.abs(dims[i] - current) < 1e-3) {
      count++;
    } else {
      groups.push(`${count}x${Number(current.toFixed(1))}`);
      current = dims[i];
      count = 1;
    }
  }
  groups.push(`${count}x${Number(current.toFixed(1))}`);
  return groups.join(',');
}

/** Auto-fit SNVN grid origin, colSpec, rowSpec to tightly enclose boundary polygon */
export function autoFitGridToBoundary(
  boundary: Point2D[],
  stepX = 20,
  stepY = 20,
  angleDeg = 0
): { originX: number; originY: number; colSpec: string; rowSpec: string; width: number; height: number } {
  if (boundary.length < 3) {
    return { originX: 0, originY: 0, colSpec: '10x20', rowSpec: '10x20', width: 200, height: 200 };
  }
  const rad = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);

  // Project boundary onto rotated grid axes
  let minU = Infinity,
    maxU = -Infinity,
    minV = Infinity,
    maxV = -Infinity;
  for (const p of boundary) {
    const u = p.x * cos + p.y * sin;
    const v = -p.x * sin + p.y * cos;
    if (u < minU) minU = u;
    if (u > maxU) maxU = u;
    if (v < minV) minV = v;
    if (v > maxV) maxV = v;
  }

  const pad = 4;
  minU -= pad;
  minV -= pad;
  maxU += pad;
  maxV += pad;

  const width = maxU - minU;
  const height = maxV - minV;
  const nCols = Math.max(1, Math.min(45, Math.ceil(width / stepX)));
  const nRows = Math.max(1, Math.min(45, Math.ceil(height / stepY)));

  // Convert (minU, minV) back to world coordinates
  const originX = Number((minU * cos - minV * sin).toFixed(2));
  const originY = Number((minU * sin + minV * cos).toFixed(2));

  return {
    originX,
    originY,
    colSpec: `${nCols}x${stepX}`,
    rowSpec: `${nRows}x${stepY}`,
    width: Number(width.toFixed(1)),
    height: Number(height.toFixed(1)),
  };
}

export function polygonSignedArea(poly: Point2D[]): number {
  let area = 0;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i];
    const b = poly[(i + 1) % poly.length];
    area += a.x * b.y - b.x * a.y;
  }
  return area * 0.5;
}

export function ensureCCW(poly: Point2D[]): Point2D[] {
  return polygonSignedArea(poly) < 0 ? [...poly].reverse() : [...poly];
}

export function polygonAreaAndCentroid(poly: Point2D[]): { area: number; centroid: Point2D } {
  if (poly.length < 3) {
    return { area: 0, centroid: poly[0] ?? { x: 0, y: 0 } };
  }
  let a2 = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < poly.length; i++) {
    const p0 = poly[i];
    const p1 = poly[(i + 1) % poly.length];
    const cross = p0.x * p1.y - p1.x * p0.y;
    a2 += cross;
    cx += (p0.x + p1.x) * cross;
    cy += (p0.y + p1.y) * cross;
  }
  const area = Math.abs(a2) * 0.5;
  if (area < 1e-8) {
    const sx = poly.reduce((s, p) => s + p.x, 0) / poly.length;
    const sy = poly.reduce((s, p) => s + p.y, 0) / poly.length;
    return { area: 0, centroid: { x: sx, y: sy } };
  }
  return {
    area,
    centroid: { x: cx / (3 * a2), y: cy / (3 * a2) },
  };
}

export function pointInPolygon(pt: Point2D, poly: Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x,
      yi = poly[i].y;
    const xj = poly[j].x,
      yj = poly[j].y;
    const intersect =
      yi > pt.y !== yj > pt.y &&
      pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi + 1e-15) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/** Sutherland-Hodgman polygon clipping against a convex CCW clip polygon */
export function clipPolygonConvex(subject: Point2D[], clipCCW: Point2D[]): Point2D[] {
  let output = [...subject];
  if (output.length < 3 || clipCCW.length < 3) return [];

  for (let i = 0; i < clipCCW.length; i++) {
    const a = clipCCW[i];
    const b = clipCCW[(i + 1) % clipCCW.length];
    const input = output;
    output = [];
    if (input.length === 0) break;

    const isInside = (p: Point2D) => (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x) >= -1e-7;

    const intersect = (p1: Point2D, p2: Point2D): Point2D => {
      const dx1 = p2.x - p1.x;
      const dy1 = p2.y - p1.y;
      const dx2 = b.x - a.x;
      const dy2 = b.y - a.y;
      const denom = dx1 * dy2 - dy1 * dx2;
      if (Math.abs(denom) < 1e-12) return p2;
      const t = ((a.x - p1.x) * dy2 - (a.y - p1.y) * dx2) / denom;
      return { x: p1.x + t * dx1, y: p1.y + t * dy1 };
    };

    let s = input[input.length - 1];
    for (const e of input) {
      if (isInside(e)) {
        if (!isInside(s)) {
          output.push(intersect(s, e));
        }
        output.push(e);
      } else if (isInside(s)) {
        output.push(intersect(s, e));
      }
      s = e;
    }
  }
  return output;
}

/**
 * Subtract a convex exclusion polygon (like a substation/pond hole) from a convex cell polygon
 * by slicing the cell along the 4 half-planes outside the exclusion edges.
 */
function subtractConvexExclusion(subject: Point2D[], exclusionCCW: Point2D[]): Point2D[][] {
  if (subject.length < 3 || exclusionCCW.length < 3) return [subject];
  const overlap = clipPolygonConvex(subject, exclusionCCW);
  if (overlap.length < 3 || Math.abs(polygonSignedArea(overlap)) < 1e-4) {
    return [subject];
  }

  const pieces: Point2D[][] = [];
  let remaining = [...subject];

  for (let i = 0; i < exclusionCCW.length; i++) {
    if (remaining.length < 3) break;
    const a = exclusionCCW[i];
    const b = exclusionCCW[(i + 1) % exclusionCCW.length];

    // Half-plane OUTSIDE edge (a -> b) has cross < 0; INSIDE has cross >= 0
    const outside: Point2D[] = [];
    const inside: Point2D[] = [];

    const cross = (p: Point2D) => (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
    const intersect = (p1: Point2D, p2: Point2D): Point2D => {
      const c1 = cross(p1);
      const c2 = cross(p2);
      const t = c1 / (c1 - c2 + 1e-15);
      return { x: p1.x + t * (p2.x - p1.x), y: p1.y + t * (p2.y - p1.y) };
    };

    let prev = remaining[remaining.length - 1];
    let prevIn = cross(prev) >= 0;
    for (const curr of remaining) {
      const currIn = cross(curr) >= 0;
      if (currIn) {
        if (!prevIn) {
          const inter = intersect(prev, curr);
          inside.push(inter);
          outside.push(inter);
        }
        inside.push(curr);
      } else {
        if (prevIn) {
          const inter = intersect(prev, curr);
          inside.push(inter);
          outside.push(inter);
        }
        outside.push(curr);
      }
      prev = curr;
      prevIn = currIn;
    }

    if (outside.length >= 3 && Math.abs(polygonSignedArea(outside)) > 1e-4) {
      pieces.push(outside);
    }
    remaining = inside;
  }

  return pieces;
}

/**
 * Split a polygon with per-vertex deltaH into Cut (dh < 0) and Fill (dh > 0) sub-polygons
 * along the exact dh = 0 zero-crossing line!
 */
function splitPolygonByZeroDeltaH(poly: PointWithDelta[]): {
  fillPoly: PointWithDelta[];
  cutPoly: PointWithDelta[];
  zeroSeg: ZeroLineSegment | null;
} {
  const fillPoly: PointWithDelta[] = [];
  const cutPoly: PointWithDelta[] = [];
  const crossings: Point2D[] = [];

  for (let i = 0; i < poly.length; i++) {
    const p1 = poly[i];
    const p2 = poly[(i + 1) % poly.length];

    const p1Fill = p1.dh >= 0;
    const p2Fill = p2.dh >= 0;

    if (p1Fill) fillPoly.push(p1);
    else cutPoly.push(p1);

    if (p1Fill !== p2Fill) {
      const denom = p1.dh - p2.dh;
      const t = Math.abs(denom) > 1e-12 ? p1.dh / denom : 0.5;
      const zeroPt: PointWithDelta = {
        x: p1.x + t * (p2.x - p1.x),
        y: p1.y + t * (p2.y - p1.y),
        dh: 0,
      };
      fillPoly.push(zeroPt);
      cutPoly.push(zeroPt);
      crossings.push({ x: zeroPt.x, y: zeroPt.y });
    }
  }

  const zeroSeg: ZeroLineSegment | null =
    crossings.length >= 2 ? { p1: crossings[0], p2: crossings[1] } : null;

  return { fillPoly, cutPoly, zeroSeg };
}

/**
 * Evaluate bilinear deltaH inside a cell given its 4 corners (00, 10, 11, 01) and local (u,v) in [0,1].
 */
function bilinearValue(
  u: number,
  v: number,
  v00: number,
  v10: number,
  v11: number,
  v01: number
): number {
  const uC = Math.max(0, Math.min(1, u));
  const vC = Math.max(0, Math.min(1, v));
  return (
    (1 - uC) * (1 - vC) * v00 +
    uC * (1 - vC) * v10 +
    uC * vC * v11 +
    (1 - uC) * vC * v01
  );
}

/**
 * Full SNVN Chapter IV Rectangular Grid Earthwork Computation
 */
export function computeSnvnGrid(
  mhtn: TinSurface,
  designSpec: DesignSurfaceSpec,
  gridConfig: GridConfig,
  boundary: PolygonZone,
  exclusions: PolygonZone[],
  nodeOverrides: Record<string, number>,
  mergedPairs: [string, string][],
  customDesignTin?: TinSurface | null
): GridCalculationResult {
  const colWidths = parseGridSpec(gridConfig.colSpec, 20);
  const rowHeights = parseGridSpec(gridConfig.rowSpec, 20);

  const nCols = colWidths.length;
  const nRows = rowHeights.length;

  const rad = (gridConfig.angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);

  const cumX: number[] = [0];
  for (let c = 0; c < nCols; c++) cumX.push(cumX[c] + colWidths[c]);

  const cumY: number[] = [0];
  for (let r = 0; r < nRows; r++) cumY.push(cumY[r] + rowHeights[r]);

  const boundaryCCW = ensureCCW(boundary.vertices);
  const exclusionsCCW = exclusions
    .filter((e) => e.vertices.length >= 3)
    .map((e) => ensureCCW(e.vertices));

  const isInsideZone = (pt: Point2D): boolean => {
    if (!pointInPolygon(pt, boundaryCCW)) return false;
    for (const ex of exclusionsCCW) {
      if (pointInPolygon(pt, ex)) return false;
    }
    return true;
  };

  // Build (nRows + 1) x (nCols + 1) nodes
  const nodes: GridNode[][] = [];
  for (let r = 0; r <= nRows; r++) {
    const rowNodes: GridNode[] = [];
    for (let c = 0; c <= nCols; c++) {
      const lx = cumX[c];
      const ly = cumY[r];
      const x = gridConfig.originX + lx * cos - ly * sin;
      const y = gridConfig.originY + lx * sin + ly * cos;
      const id = `${r + 1}-${c + 1}`;
      const hTN = interpolateTinZ(mhtn, x, y);
      const hasOverride = Object.prototype.hasOwnProperty.call(nodeOverrides, id);
      const hTK = hasOverride
        ? nodeOverrides[id]
        : evaluateDesignElevation(designSpec, x, y, customDesignTin);

      rowNodes.push({
        id,
        row: r,
        col: c,
        x,
        y,
        hTN,
        hTK,
        deltaH: hTK - hTN,
        isCustomHTK: hasOverride,
        insideBoundary: isInsideZone({ x, y }),
      });
    }
    nodes.push(rowNodes);
  }

  const cells: GridCell[] = [];
  const zeroLines: ZeroLineSegment[] = [];

  const colSummaries: ColumnSummary[] = colWidths.map((_, c) => ({
    col: c,
    label: `Cột ${c + 1}`,
    cutArea: 0,
    fillArea: 0,
    cutVolume: 0,
    fillVolume: 0,
  }));

  const rowSummaries: RowSummary[] = rowHeights.map((_, r) => ({
    row: r,
    label: `Hàng ${r + 1}`,
    cutArea: 0,
    fillArea: 0,
    cutVolume: 0,
    fillVolume: 0,
  }));

  for (let r = 0; r < nRows; r++) {
    for (let c = 0; c < nCols; c++) {
      const n00 = nodes[r][c];
      const n10 = nodes[r][c + 1];
      const n11 = nodes[r + 1][c + 1];
      const n01 = nodes[r + 1][c];

      const corners: Point2D[] = [
        { x: n00.x, y: n00.y },
        { x: n10.x, y: n10.y },
        { x: n11.x, y: n11.y },
        { x: n01.x, y: n01.y },
      ];

      // Clip cell against boundary polygon
      const clipped = clipPolygonConvex(corners, boundaryCCW);
      if (clipped.length < 3 || Math.abs(polygonSignedArea(clipped)) < 0.05) {
        cells.push({
          id: `${r + 1}-${c + 1}`,
          row: r,
          col: c,
          corners,
          clippedPolygon: [],
          active: false,
          totalArea: 0,
          cutArea: 0,
          fillArea: 0,
          cutAvgH: 0,
          fillAvgH: 0,
          cutVolume: 0,
          fillVolume: 0,
          subPolygons: [],
        });
        continue;
      }

      // Subtract exclusion zones (holes)
      let fragments: Point2D[][] = [clipped];
      for (const ex of exclusionsCCW) {
        const nextFrags: Point2D[][] = [];
        for (const frag of fragments) {
          nextFrags.push(...subtractConvexExclusion(frag, ex));
        }
        fragments = nextFrags;
      }

      const cellW = colWidths[c];
      const cellH = rowHeights[r];

      // Transform a world point back to local (u, v) in [0, 1] inside this cell
      const evalLocalDeltaH = (pt: Point2D): number => {
        const dx = pt.x - n00.x;
        const dy = pt.y - n00.y;
        const u = (dx * cos + dy * sin) / cellW;
        const v = (-dx * sin + dy * cos) / cellH;
        return bilinearValue(u, v, n00.deltaH, n10.deltaH, n11.deltaH, n01.deltaH);
      };

      const subPolygons: SubPolygonVolume[] = [];
      let cellCutArea = 0;
      let cellFillArea = 0;
      let cellCutVol = 0;
      let cellFillVol = 0;

      for (const frag of fragments) {
        if (frag.length < 3) continue;
        const withDh: PointWithDelta[] = frag.map((p) => ({
          x: p.x,
          y: p.y,
          dh: evalLocalDeltaH(p),
        }));

        const { fillPoly, cutPoly, zeroSeg } = splitPolygonByZeroDeltaH(withDh);
        if (zeroSeg) {
          zeroLines.push(zeroSeg);
        }

        if (fillPoly.length >= 3) {
          const { area, centroid } = polygonAreaAndCentroid(fillPoly);
          if (area > 0.05) {
            // SNVN Formula: Average elevation diff across polygon vertices (positive for fill)
            const avgH =
              fillPoly.reduce((acc, p) => acc + Math.max(0, p.dh), 0) / fillPoly.length;
            const vol = avgH * area;
            cellFillArea += area;
            cellFillVol += vol;
            subPolygons.push({
              type: 'fill',
              polygon: fillPoly.map(({ x, y }) => ({ x, y })),
              area,
              avgDeltaH: avgH,
              volume: vol,
              centroid,
            });
          }
        }

        if (cutPoly.length >= 3) {
          const { area, centroid } = polygonAreaAndCentroid(cutPoly);
          if (area > 0.05) {
            const avgH =
              cutPoly.reduce((acc, p) => acc + Math.max(0, -p.dh), 0) / cutPoly.length;
            const vol = avgH * area;
            cellCutArea += area;
            cellCutVol += vol;
            subPolygons.push({
              type: 'cut',
              polygon: cutPoly.map(({ x, y }) => ({ x, y })),
              area,
              avgDeltaH: avgH,
              volume: vol,
              centroid,
            });
          }
        }
      }

      const totalArea = cellCutArea + cellFillArea;
      const active = totalArea > 0.05;

      if (active) {
        // Mark the 4 corner nodes as active for display
        n00.insideBoundary = true;
        n10.insideBoundary = true;
        n11.insideBoundary = true;
        n01.insideBoundary = true;

        colSummaries[c].cutArea += cellCutArea;
        colSummaries[c].fillArea += cellFillArea;
        colSummaries[c].cutVolume += cellCutVol;
        colSummaries[c].fillVolume += cellFillVol;

        rowSummaries[r].cutArea += cellCutArea;
        rowSummaries[r].fillArea += cellFillArea;
        rowSummaries[r].cutVolume += cellCutVol;
        rowSummaries[r].fillVolume += cellFillVol;
      }

      cells.push({
        id: `${r + 1}-${c + 1}`,
        row: r,
        col: c,
        corners,
        clippedPolygon: fragments[0] ?? [],
        active,
        totalArea,
        cutArea: cellCutArea,
        fillArea: cellFillArea,
        cutAvgH: cellCutArea > 1e-6 ? cellCutVol / cellCutArea : 0,
        fillAvgH: cellFillArea > 1e-6 ? cellFillVol / cellFillArea : 0,
        cutVolume: cellCutVol,
        fillVolume: cellFillVol,
        subPolygons,
      });
    }
  }

  // Handle SNVN Chapter VII.1 Merged Cells (Cộng ô - DD_MC)
  const cellMap = new Map<string, GridCell>();
  for (const cell of cells) cellMap.set(cell.id, cell);

  const mergedGroups: MergedCellGroup[] = [];
  const usedMerged = new Set<string>();
  mergedPairs.forEach(([idA, idB], idx) => {
    if (usedMerged.has(idA) || usedMerged.has(idB)) return;
    const ca = cellMap.get(idA);
    const cb = cellMap.get(idB);
    if (!ca || !cb || !ca.active || !cb.active) return;

    // Only merge pure same-type cells (cut+cut or fill+fill)
    const aPureFill = ca.fillArea > 0 && ca.cutArea < 0.05;
    const bPureFill = cb.fillArea > 0 && cb.cutArea < 0.05;
    const aPureCut = ca.cutArea > 0 && ca.fillArea < 0.05;
    const bPureCut = cb.cutArea > 0 && cb.fillArea < 0.05;

    if ((aPureFill && bPureFill) || (aPureCut && bPureCut)) {
      const type: 'cut' | 'fill' = aPureFill ? 'fill' : 'cut';
      const area = type === 'fill' ? ca.fillArea + cb.fillArea : ca.cutArea + cb.cutArea;
      const volume = type === 'fill' ? ca.fillVolume + cb.fillVolume : ca.cutVolume + cb.cutVolume;
      const centA = ca.subPolygons[0]?.centroid ?? ca.corners[0];
      const centB = cb.subPolygons[0]?.centroid ?? cb.corners[0];
      const gid = `MERGE-${idx + 1}`;
      ca.mergedGroupId = gid;
      cb.mergedGroupId = gid;
      usedMerged.add(idA);
      usedMerged.add(idB);
      mergedGroups.push({
        id: gid,
        cellIds: [idA, idB],
        type,
        area,
        avgH: area > 1e-6 ? volume / area : 0,
        volume,
        centroid: { x: (centA.x + centB.x) / 2, y: (centA.y + centB.y) / 2 },
      });
    }
  });

  const totalCutArea = colSummaries.reduce((s, c) => s + c.cutArea, 0);
  const totalFillArea = colSummaries.reduce((s, c) => s + c.fillArea, 0);
  const totalCutVolume = colSummaries.reduce((s, c) => s + c.cutVolume, 0);
  const totalFillVolume = colSummaries.reduce((s, c) => s + c.fillVolume, 0);
  const effectiveFillVolume = totalFillVolume * gridConfig.compactionFactor;

  return {
    colWidths,
    rowHeights,
    nodes,
    cells,
    mergedGroups,
    zeroLines,
    colSummaries,
    rowSummaries,
    totalLandArea: totalCutArea + totalFillArea,
    totalCutArea,
    totalFillArea,
    totalCutVolume,
    totalFillVolume,
    effectiveFillVolume,
    netVolume: effectiveFillVolume - totalCutVolume,
  };
}

/**
 * Automatic Cut-Fill Balance Optimizer (Cân bằng đào đắp tự động):
 * Binary search over elevationShift so that (Fill * compactionFactor) == Cut.
 */
export function optimizeBalanceElevationShift(
  mhtn: TinSurface,
  designSpec: DesignSurfaceSpec,
  gridConfig: GridConfig,
  boundary: PolygonZone,
  exclusions: PolygonZone[],
  customDesignTin?: TinSurface | null
): { optimalShift: number; cutVolume: number; fillVolume: number } {
  let lo = -18;
  let hi = 18;
  let bestShift = designSpec.elevationShift;
  let bestCut = 0;
  let bestFill = 0;

  for (let iter = 0; iter < 18; iter++) {
    const mid = (lo + hi) / 2;
    const testSpec: DesignSurfaceSpec = { ...designSpec, elevationShift: mid };
    const res = computeSnvnGrid(
      mhtn,
      testSpec,
      gridConfig,
      boundary,
      exclusions,
      {},
      [],
      customDesignTin
    );
    bestShift = mid;
    bestCut = res.totalCutVolume;
    bestFill = res.effectiveFillVolume;
    const diff = res.effectiveFillVolume - res.totalCutVolume;
    if (Math.abs(diff) < 5) break;
    if (diff > 0) {
      // Too much fill -> lower design surface
      hi = mid;
    } else {
      // Too much cut -> raise design surface
      lo = mid;
    }
  }

  return {
    optimalShift: Number(bestShift.toFixed(3)),
    cutVolume: bestCut,
    fillVolume: bestFill,
  };
}

/** Generate data points for Cut/Fill Balance Curve chart across deltaZ shifts */
export function computeBalanceCurve(
  mhtn: TinSurface,
  designSpec: DesignSurfaceSpec,
  gridConfig: GridConfig,
  boundary: PolygonZone,
  exclusions: PolygonZone[],
  customDesignTin?: TinSurface | null
): { shift: number; label: string; cutVol: number; fillVol: number; netVol: number }[] {
  const offsets = [-3.0, -2.0, -1.0, -0.5, 0, 0.5, 1.0, 2.0, 3.0];
  return offsets.map((delta) => {
    const testShift = Number((designSpec.elevationShift + delta).toFixed(2));
    const res = computeSnvnGrid(
      mhtn,
      { ...designSpec, elevationShift: testShift },
      gridConfig,
      boundary,
      exclusions,
      {},
      [],
      customDesignTin
    );
    return {
      shift: testShift,
      label: `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}m`,
      cutVol: Math.round(res.totalCutVolume),
      fillVol: Math.round(res.effectiveFillVolume),
      netVol: Math.round(res.effectiveFillVolume - res.totalCutVolume),
    };
  });
}
