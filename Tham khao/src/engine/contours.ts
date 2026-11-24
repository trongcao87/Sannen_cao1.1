import { ContourConfig, ContourPolyline, Point2D, TinSurface } from '../types/snvn';

interface RawSeg {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

function ptKey(x: number, y: number): string {
  return `${Math.round(x * 100)},${Math.round(y * 100)}`;
}

/** Stitch unordered triangle contour segments into continuous polylines */
function stitchSegments(segments: RawSeg[]): Point2D[][] {
  if (segments.length === 0) return [];

  const adj = new Map<string, number[]>();
  const addAdj = (k: string, idx: number) => {
    const arr = adj.get(k);
    if (arr) arr.push(idx);
    else adj.set(k, [idx]);
  };

  segments.forEach((s, i) => {
    addAdj(ptKey(s.x1, s.y1), i);
    addAdj(ptKey(s.x2, s.y2), i);
  });

  const used = new Uint8Array(segments.length);
  const polylines: Point2D[][] = [];

  for (let i = 0; i < segments.length; i++) {
    if (used[i]) continue;
    used[i] = 1;
    const s = segments[i];
    const chain: Point2D[] = [
      { x: s.x1, y: s.y1 },
      { x: s.x2, y: s.y2 },
    ];

    // Extend forward
    while (true) {
      const tail = chain[chain.length - 1];
      const candidates = adj.get(ptKey(tail.x, tail.y));
      if (!candidates) break;
      let extended = false;
      for (const nextIdx of candidates) {
        if (used[nextIdx]) continue;
        used[nextIdx] = 1;
        const ns = segments[nextIdx];
        if (Math.hypot(ns.x1 - tail.x, ns.y1 - tail.y) < 0.05) {
          chain.push({ x: ns.x2, y: ns.y2 });
        } else {
          chain.push({ x: ns.x1, y: ns.y1 });
        }
        extended = true;
        break;
      }
      if (!extended) break;
    }

    // Extend backward
    while (true) {
      const head = chain[0];
      const candidates = adj.get(ptKey(head.x, head.y));
      if (!candidates) break;
      let extended = false;
      for (const prevIdx of candidates) {
        if (used[prevIdx]) continue;
        used[prevIdx] = 1;
        const ps = segments[prevIdx];
        if (Math.hypot(ps.x1 - head.x, ps.y1 - head.y) < 0.05) {
          chain.unshift({ x: ps.x2, y: ps.y2 });
        } else {
          chain.unshift({ x: ps.x1, y: ps.y1 });
        }
        extended = true;
        break;
      }
      if (!extended) break;
    }

    polylines.push(chain);
  }

  return polylines;
}

/** Chaikin corner-cutting smoothing preserving endpoints */
function smoothPolyline(pts: Point2D[], iterations: number): Point2D[] {
  if (pts.length < 3 || iterations <= 0) return pts;
  let curr = pts;
  const closed = Math.hypot(pts[0].x - pts[pts.length - 1].x, pts[0].y - pts[pts.length - 1].y) < 0.05;

  for (let it = 0; it < iterations; it++) {
    const next: Point2D[] = [];
    if (!closed) next.push(curr[0]);
    for (let i = 0; i < curr.length - 1; i++) {
      const p0 = curr[i];
      const p1 = curr[i + 1];
      next.push({ x: 0.75 * p0.x + 0.25 * p1.x, y: 0.75 * p0.y + 0.25 * p1.y });
      next.push({ x: 0.25 * p0.x + 0.75 * p1.x, y: 0.25 * p0.y + 0.75 * p1.y });
    }
    if (!closed) next.push(curr[curr.length - 1]);
    else if (next.length > 0) next.push(next[0]);
    curr = next;
  }
  return curr;
}

/**
 * Generate smooth contour lines (đường đồng mức) on a TIN surface via Marching Triangles.
 */
export function generateTinContours(
  tin: TinSurface,
  surface: 'mhtn' | 'mhtk',
  config: ContourConfig
): ContourPolyline[] {
  if (tin.triangles.length === 0) return [];
  const minor = Math.max(0.1, Math.min(20, config.minorInterval));
  const major = Math.max(minor, config.majorInterval);

  const startZ = Math.ceil(tin.bounds.minZ / minor) * minor;
  const endZ = Math.floor(tin.bounds.maxZ / minor) * minor;

  const result: ContourPolyline[] = [];
  const { vertices, triangles } = tin;

  // Limit total contour levels to avoid memory blowup on bad data
  const levels: number[] = [];
  for (let z = startZ; z <= endZ + 1e-6 && levels.length < 120; z += minor) {
    levels.push(Number(z.toFixed(3)));
  }

  for (const level of levels) {
    const segs: RawSeg[] = [];

    for (let i = 0; i < triangles.length; i++) {
      const tri = triangles[i];
      const pA = vertices[tri.a];
      const pB = vertices[tri.b];
      const pC = vertices[tri.c];

      // Avoid exact vertex equality degeneracies with tiny epsilon
      const dA = pA.z - level === 0 ? 1e-6 : pA.z - level;
      const dB = pB.z - level === 0 ? 1e-6 : pB.z - level;
      const dC = pC.z - level === 0 ? 1e-6 : pC.z - level;

      const pts: Point2D[] = [];
      const checkEdge = (p1: { x: number; y: number }, d1: number, p2: { x: number; y: number }, d2: number) => {
        if ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) {
          const t = d1 / (d1 - d2);
          pts.push({ x: p1.x + t * (p2.x - p1.x), y: p1.y + t * (p2.y - p1.y) });
        }
      };

      checkEdge(pA, dA, pB, dB);
      checkEdge(pB, dB, pC, dC);
      checkEdge(pC, dC, pA, dA);

      if (pts.length === 2) {
        segs.push({ x1: pts[0].x, y1: pts[0].y, x2: pts[1].x, y2: pts[1].y });
      }
    }

    const chains = stitchSegments(segs);
    const ratio = level / major;
    const isMajor = Math.abs(ratio - Math.round(ratio)) < 0.02;

    for (const rawChain of chains) {
      if (rawChain.length < 2) continue;
      const smoothed = smoothPolyline(rawChain, config.smoothIterations);

      // Compute total length & midpoint label orientation
      let totalLen = 0;
      for (let k = 1; k < smoothed.length; k++) {
        totalLen += Math.hypot(smoothed[k].x - smoothed[k - 1].x, smoothed[k].y - smoothed[k - 1].y);
      }

      let labelPoint: { x: number; y: number; angleRad: number } | undefined;
      if (totalLen > 24 && (isMajor || totalLen > 75)) {
        const halfLen = totalLen * 0.5;
        let acc = 0;
        for (let k = 1; k < smoothed.length; k++) {
          const segL = Math.hypot(smoothed[k].x - smoothed[k - 1].x, smoothed[k].y - smoothed[k - 1].y);
          if (acc + segL >= halfLen && segL > 1e-4) {
            const frac = (halfLen - acc) / segL;
            const lx = smoothed[k - 1].x + (smoothed[k].x - smoothed[k - 1].x) * frac;
            const ly = smoothed[k - 1].y + (smoothed[k].y - smoothed[k - 1].y) * frac;
            let ang = Math.atan2(smoothed[k].y - smoothed[k - 1].y, smoothed[k].x - smoothed[k - 1].x);
            if (ang > Math.PI / 2) ang -= Math.PI;
            if (ang < -Math.PI / 2) ang += Math.PI;
            labelPoint = { x: lx, y: ly, angleRad: ang };
            break;
          }
          acc += segL;
        }
      }

      result.push({
        elevation: level,
        isMajor,
        surface,
        points: smoothed,
        labelPoint,
      });
    }
  }

  return result;
}
