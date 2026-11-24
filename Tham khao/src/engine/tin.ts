import {
  BoundingBox,
  Breakline,
  DesignSurfaceSpec,
  Point2D,
  Point3D,
  SurveyPoint,
  TinSurface,
  TinTriangle,
} from '../types/snvn';

const EPS = 1e-9;

interface RawTri {
  a: number;
  b: number;
  c: number;
}

function orient2D(ax: number, ay: number, bx: number, by: number, cx: number, cy: number): number {
  return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
}

function inCircumcircle(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  cx: number,
  cy: number,
  px: number,
  py: number
): boolean {
  const dx = ax - px;
  const dy = ay - py;
  const ex = bx - px;
  const ey = by - py;
  const fx = cx - px;
  const fy = cy - py;

  const ap = dx * dx + dy * dy;
  const bp = ex * ex + ey * ey;
  const cp = fx * fx + fy * fy;

  const det =
    dx * (ey * cp - bp * fy) -
    dy * (ex * cp - bp * fx) +
    ap * (ex * fy - ey * fx);

  // Ensure CCW orientation check
  const area = orient2D(ax, ay, bx, by, cx, cy);
  return area > 0 ? det > 1e-10 : det < -1e-10;
}

function segmentsProperlyIntersect(a: Point2D, b: Point2D, c: Point2D, d: Point2D): boolean {
  const o1 = orient2D(a.x, a.y, b.x, b.y, c.x, c.y);
  const o2 = orient2D(a.x, a.y, b.x, b.y, d.x, d.y);
  const o3 = orient2D(c.x, c.y, d.x, d.y, a.x, a.y);
  const o4 = orient2D(c.x, c.y, d.x, d.y, b.x, b.y);
  return ((o1 > EPS && o2 < -EPS) || (o1 < -EPS && o2 > EPS)) &&
    ((o3 > EPS && o4 < -EPS) || (o3 < -EPS && o4 > EPS));
}

function edgeKey(u: number, v: number): string {
  return u < v ? `${u}:${v}` : `${v}:${u}`;
}

function hasEdge(tri: RawTri, u: number, v: number): boolean {
  return (
    (tri.a === u && tri.b === v) ||
    (tri.b === u && tri.a === v) ||
    (tri.b === u && tri.c === v) ||
    (tri.c === u && tri.b === v) ||
    (tri.c === u && tri.a === v) ||
    (tri.a === u && tri.c === v)
  );
}

function oppositeVertex(tri: RawTri, u: number, v: number): number {
  if (tri.a !== u && tri.a !== v) return tri.a;
  if (tri.b !== u && tri.b !== v) return tri.b;
  return tri.c;
}

function makeCCW(verts: Point3D[], a: number, b: number, c: number): RawTri {
  const area = orient2D(verts[a].x, verts[a].y, verts[b].x, verts[b].y, verts[c].x, verts[c].y);
  return area >= 0 ? { a, b, c } : { a, b: c, c: b };
}

/**
 * Constrained Delaunay Triangulation (CDT):
 * 1. Deduplicate survey points + breakline vertices (breaklines take priority on identical XY).
 * 2. Run Bowyer-Watson Delaunay triangulation.
 * 3. Enforce every breakline segment via iterative diagonal edge flipping (Sloan's CDT algorithm)
 *    so that no TIN edge ever crosses a terrain breakline (per SNVN Chapter III).
 */
export function buildConstrainedTin(
  name: string,
  points: SurveyPoint[],
  breaklines: Breakline[] = []
): TinSurface {
  const vertices: Point3D[] = [];
  const constrainedEdges: [number, number][] = [];

  const findOrAddVertex = (p: Point3D, tolerance = 0.05): number => {
    const tolSq = tolerance * tolerance;
    for (let i = 0; i < vertices.length; i++) {
      const dx = vertices[i].x - p.x;
      const dy = vertices[i].y - p.y;
      if (dx * dx + dy * dy <= tolSq) {
        return i;
      }
    }
    vertices.push({ x: p.x, y: p.y, z: p.z });
    return vertices.length - 1;
  };

  // Insert breakline vertices first so their exact Z controls the terrain discontinuity
  for (const bl of breaklines) {
    if (bl.vertices.length < 2) continue;
    const blIndices: number[] = [];
    for (const v of bl.vertices) {
      blIndices.push(findOrAddVertex(v, 0.05));
    }
    for (let i = 0; i < blIndices.length - 1; i++) {
      const u = blIndices[i];
      const v = blIndices[i + 1];
      if (u !== v) {
        constrainedEdges.push([u, v]);
      }
    }
  }

  for (const pt of points) {
    findOrAddVertex(pt, 0.08);
  }

  if (vertices.length < 3) {
    return {
      name,
      vertices,
      triangles: [],
      constrainedEdges,
      bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0, minZ: 0, maxZ: 0 },
    };
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;

  for (const v of vertices) {
    if (v.x < minX) minX = v.x;
    if (v.x > maxX) maxX = v.x;
    if (v.y < minY) minY = v.y;
    if (v.y > maxY) maxY = v.y;
    if (v.z < minZ) minZ = v.z;
    if (v.z > maxZ) maxZ = v.z;
  }

  const dx = Math.max(maxX - minX, 1);
  const dy = Math.max(maxY - minY, 1);
  const dmax = Math.max(dx, dy);
  const midX = (minX + maxX) / 2;
  const midY = (minY + maxY) / 2;

  // Append 3 super-triangle vertices temporarily
  const nReal = vertices.length;
  const allVerts: Point3D[] = [
    ...vertices,
    { x: midX - 20 * dmax, y: midY - dmax, z: 0 },
    { x: midX, y: midY + 20 * dmax, z: 0 },
    { x: midX + 20 * dmax, y: midY - dmax, z: 0 },
  ];

  let tris: RawTri[] = [makeCCW(allVerts, nReal, nReal + 1, nReal + 2)];

  // Bowyer-Watson incremental insertion
  for (let i = 0; i < nReal; i++) {
    const p = allVerts[i];
    const badIndices: number[] = [];

    for (let t = 0; t < tris.length; t++) {
      const tri = tris[t];
      const va = allVerts[tri.a];
      const vb = allVerts[tri.b];
      const vc = allVerts[tri.c];
      if (inCircumcircle(va.x, va.y, vb.x, vb.y, vc.x, vc.y, p.x, p.y)) {
        badIndices.push(t);
      }
    }

    const edgeCount = new Map<string, { u: number; v: number; count: number }>();
    const badSet = new Set(badIndices);

    for (const idx of badIndices) {
      const tri = tris[idx];
      const triEdges: [number, number][] = [
        [tri.a, tri.b],
        [tri.b, tri.c],
        [tri.c, tri.a],
      ];
      for (const [u, v] of triEdges) {
        const k = edgeKey(u, v);
        const existing = edgeCount.get(k);
        if (existing) {
          existing.count += 1;
        } else {
          edgeCount.set(k, { u, v, count: 1 });
        }
      }
    }

    const nextTris: RawTri[] = [];
    for (let t = 0; t < tris.length; t++) {
      if (!badSet.has(t)) nextTris.push(tris[t]);
    }

    for (const edge of edgeCount.values()) {
      if (edge.count === 1) {
        nextTris.push(makeCCW(allVerts, edge.u, edge.v, i));
      }
    }
    tris = nextTris;
  }

  // Remove triangles touching super-triangle vertices
  tris = tris.filter((t) => t.a < nReal && t.b < nReal && t.c < nReal);

  // Enforce breakline constraints via Sloan diagonal edge-flipping
  if (constrainedEdges.length > 0) {
    const constrainedSet = new Set(constrainedEdges.map(([u, v]) => edgeKey(u, v)));

    for (const [cu, cv] of constrainedEdges) {
      const targetKey = edgeKey(cu, cv);
      const existsAlready = tris.some((t) => hasEdge(t, cu, cv));
      if (existsAlready) continue;

      const pU = vertices[cu];
      const pV = vertices[cv];

      // Find all existing mesh edges that strictly cross (cu, cv)
      const crossingQueue: [number, number][] = [];
      const seenCross = new Set<string>();

      for (const t of tris) {
        const edges: [number, number][] = [
          [t.a, t.b],
          [t.b, t.c],
          [t.c, t.a],
        ];
        for (const [u, v] of edges) {
          if (u === cu || u === cv || v === cu || v === cv) continue;
          const k = edgeKey(u, v);
          if (seenCross.has(k) || constrainedSet.has(k)) continue;
          if (segmentsProperlyIntersect(pU, pV, vertices[u], vertices[v])) {
            seenCross.add(k);
            crossingQueue.push([u, v]);
          }
        }
      }

      let guard = 0;
      const maxIter = crossingQueue.length * 10 + 40;
      while (crossingQueue.length > 0 && guard < maxIter) {
        guard++;
        const [eu, ev] = crossingQueue.shift()!;

        // Find the two adjacent triangles sharing (eu, ev)
        const adjIdx: number[] = [];
        for (let t = 0; t < tris.length; t++) {
          if (hasEdge(tris[t], eu, ev)) {
            adjIdx.push(t);
            if (adjIdx.length === 2) break;
          }
        }
        if (adjIdx.length !== 2) continue;

        const t1 = tris[adjIdx[0]];
        const t2 = tris[adjIdx[1]];
        const o1 = oppositeVertex(t1, eu, ev);
        const o2 = oppositeVertex(t2, eu, ev);
        if (o1 === o2) continue;

        // Check strict convexity of quad (eu, o1, ev, o2)
        const c1 = orient2D(vertices[o1].x, vertices[o1].y, vertices[o2].x, vertices[o2].y, vertices[eu].x, vertices[eu].y);
        const c2 = orient2D(vertices[o1].x, vertices[o1].y, vertices[o2].x, vertices[o2].y, vertices[ev].x, vertices[ev].y);
        const c3 = orient2D(vertices[eu].x, vertices[eu].y, vertices[ev].x, vertices[ev].y, vertices[o1].x, vertices[o1].y);
        const c4 = orient2D(vertices[eu].x, vertices[eu].y, vertices[ev].x, vertices[ev].y, vertices[o2].x, vertices[o2].y);

        const isConvex = c1 * c2 < -EPS && c3 * c4 < -EPS;
        if (!isConvex) {
          // Defer and retry after adjacent flips make this quad convex
          crossingQueue.push([eu, ev]);
          continue;
        }

        // Perform diagonal flip: replace (eu, ev) with (o1, o2)
        tris[adjIdx[0]] = makeCCW(vertices, o1, o2, eu);
        tris[adjIdx[1]] = makeCCW(vertices, o1, o2, ev);

        // If the new diagonal still crosses (cu, cv), push it back to queue
        if (
          edgeKey(o1, o2) !== targetKey &&
          o1 !== cu &&
          o1 !== cv &&
          o2 !== cu &&
          o2 !== cv &&
          segmentsProperlyIntersect(pU, pV, vertices[o1], vertices[o2])
        ) {
          crossingQueue.push([o1, o2]);
        }
      }
    }
  }

  const finalTris: TinTriangle[] = tris
    .filter((t) => {
      const area = Math.abs(
        orient2D(
          vertices[t.a].x,
          vertices[t.a].y,
          vertices[t.b].x,
          vertices[t.b].y,
          vertices[t.c].x,
          vertices[t.c].y
        )
      );
      return area > 1e-6;
    })
    .map((t) => {
      const va = vertices[t.a];
      const vb = vertices[t.b];
      const vc = vertices[t.c];
      return {
        a: t.a,
        b: t.b,
        c: t.c,
        minX: Math.min(va.x, vb.x, vc.x),
        maxX: Math.max(va.x, vb.x, vc.x),
        minY: Math.min(va.y, vb.y, vc.y),
        maxY: Math.max(va.y, vb.y, vc.y),
      };
    });

  return {
    name,
    vertices,
    triangles: finalTris,
    constrainedEdges,
    bounds: { minX, maxX, minY, maxY, minZ, maxZ },
  };
}

/**
 * Exact barycentric elevation interpolation on a TIN surface.
 * Falls back to nearest triangle/vertex IDW if (x, y) is slightly outside the convex hull.
 */
export function interpolateTinZ(tin: TinSurface, x: number, y: number): number {
  const { vertices, triangles } = tin;
  if (vertices.length === 0) return 0;

  for (let i = 0; i < triangles.length; i++) {
    const tri = triangles[i];
    if (x < tri.minX - 1e-6 || x > tri.maxX + 1e-6 || y < tri.minY - 1e-6 || y > tri.maxY + 1e-6) {
      continue;
    }
    const va = vertices[tri.a];
    const vb = vertices[tri.b];
    const vc = vertices[tri.c];

    const denom = (vb.y - vc.y) * (va.x - vc.x) + (vc.x - vb.x) * (va.y - vc.y);
    if (Math.abs(denom) < 1e-12) continue;

    const w1 = ((vb.y - vc.y) * (x - vc.x) + (vc.x - vb.x) * (y - vc.y)) / denom;
    const w2 = ((vc.y - va.y) * (x - vc.x) + (va.x - vc.x) * (y - vc.y)) / denom;
    const w3 = 1 - w1 - w2;

    if (w1 >= -1e-5 && w2 >= -1e-5 && w3 >= -1e-5) {
      return w1 * va.z + w2 * vb.z + w3 * vc.z;
    }
  }

  // Fallback: inverse-distance weighted average of 3 nearest TIN vertices
  let d1 = Infinity,
    d2 = Infinity,
    d3 = Infinity;
  let z1 = 0,
    z2 = 0,
    z3 = 0;
  for (let i = 0; i < vertices.length; i++) {
    const v = vertices[i];
    const dSq = (v.x - x) ** 2 + (v.y - y) ** 2;
    if (dSq < 1e-9) return v.z;
    if (dSq < d1) {
      d3 = d2;
      z3 = z2;
      d2 = d1;
      z2 = z1;
      d1 = dSq;
      z1 = v.z;
    } else if (dSq < d2) {
      d3 = d2;
      z3 = z2;
      d2 = dSq;
      z2 = v.z;
    } else if (dSq < d3) {
      d3 = dSq;
      z3 = v.z;
    }
  }
  const w1 = 1 / Math.sqrt(d1);
  const w2 = d2 < Infinity ? 1 / Math.sqrt(d2) : 0;
  const w3 = d3 < Infinity ? 1 / Math.sqrt(d3) : 0;
  return (w1 * z1 + w2 * z2 + w3 * z3) / (w1 + w2 + w3);
}

/**
 * Evaluate analytical or custom TIN Design Surface (MHTK) elevation at (x, y)
 * matching SNVN Chapter III.4 (Flat, Simple Offset-3D Slope, Ridge/Transverse Slope, Custom TIN).
 */
export function evaluateDesignElevation(
  spec: DesignSurfaceSpec,
  x: number,
  y: number,
  customDesignTin?: TinSurface | null
): number {
  if (spec.mode === 'custom_tin' && customDesignTin && customDesignTin.vertices.length >= 3) {
    return interpolateTinZ(customDesignTin, x, y) + spec.elevationShift;
  }

  const base = spec.baseElevation + spec.elevationShift;

  if (spec.mode === 'flat') {
    return base;
  }

  const rad = (spec.slopeAngleDeg * Math.PI) / 180;
  const dirX = Math.cos(rad);
  const dirY = Math.sin(rad);
  const perpX = -dirY;
  const perpY = dirX;

  const dx = x - spec.refPoint.x;
  const dy = y - spec.refPoint.y;

  // Projection along main slope direction (positive = downslope)
  const along = dx * dirX + dy * dirY;
  const across = Math.abs(dx * perpX + dy * perpY);

  if (spec.mode === 'single_slope') {
    // SNVN III.4.1: slopes down along slopeAngleDeg at longitudinalSlopePct %
    return base - along * (spec.longitudinalSlopePct / 100);
  }

  // SNVN III.4.2: ridge_slope — slopes down along main ridge AND away on both sides
  return (
    base -
    along * (spec.longitudinalSlopePct / 100) -
    across * (spec.transverseSlopePct / 100)
  );
}

/**
 * Build a TIN representation of MHTK over the project bounds so it can be contoured & rendered in 3D WebGL.
 */
export function buildDesignTin(
  spec: DesignSurfaceSpec,
  bounds: BoundingBox,
  customDesignTin?: TinSurface | null
): TinSurface {
  if (spec.mode === 'custom_tin' && customDesignTin && customDesignTin.vertices.length >= 3) {
    if (Math.abs(spec.elevationShift) < 1e-9) return customDesignTin;
    return {
      ...customDesignTin,
      vertices: customDesignTin.vertices.map((v) => ({
        ...v,
        z: v.z + spec.elevationShift,
      })),
      bounds: {
        ...customDesignTin.bounds,
        minZ: customDesignTin.bounds.minZ + spec.elevationShift,
        maxZ: customDesignTin.bounds.maxZ + spec.elevationShift,
      },
    };
  }

  const pad = 15;
  const minX = bounds.minX - pad;
  const maxX = bounds.maxX + pad;
  const minY = bounds.minY - pad;
  const maxY = bounds.maxY + pad;

  const cols = 14;
  const rows = 14;
  const pts: SurveyPoint[] = [];
  let id = 1;
  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c <= cols; c++) {
      const x = minX + ((maxX - minX) * c) / cols;
      const y = minY + ((maxY - minY) * r) / rows;
      const z = evaluateDesignElevation(spec, x, y, customDesignTin);
      pts.push({
        id: `TK-${id++}`,
        x,
        y,
        z,
        source: 'PRESET',
        layer: 'MHTK',
      });
    }
  }

  // If ridge_slope, include the ridge axis as a 3D breakline so the ridge crest is razor sharp!
  const breaklines: Breakline[] = [];
  if (spec.mode === 'ridge_slope') {
    const rad = (spec.slopeAngleDeg * Math.PI) / 180;
    const dx = Math.cos(rad);
    const dy = Math.sin(rad);
    const span = Math.hypot(maxX - minX, maxY - minY) * 0.7;
    const ridgeVerts: Point3D[] = [];
    for (let i = -4; i <= 4; i++) {
      const t = (i / 4) * span;
      const x = spec.refPoint.x + dx * t;
      const y = spec.refPoint.y + dy * t;
      if (x >= minX && x <= maxX && y >= minY && y <= maxY) {
        ridgeVerts.push({ x, y, z: evaluateDesignElevation(spec, x, y) });
      }
    }
    if (ridgeVerts.length >= 2) {
      breaklines.push({
        id: 'MHTK-RIDGE',
        name: 'Tuyến sống lưng MHTK',
        vertices: ridgeVerts,
        is3D: true,
        layer: 'MHTK_RIDGE',
      });
    }
  }

  return buildConstrainedTin('MHTK', pts, breaklines);
}
