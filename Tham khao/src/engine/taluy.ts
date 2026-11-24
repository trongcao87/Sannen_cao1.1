import {
  DesignSurfaceSpec,
  Point2D,
  Point3D,
  PolygonZone,
  TaluyCalculationResult,
  TaluyConfig,
  TaluySegmentResult,
  TaluyTick2D,
  TinSurface,
} from '../types/snvn';
import { ensureCCW } from './grid';
import { evaluateDesignElevation, interpolateTinZ } from './tin';

interface TaluyProfileSample {
  top: Point3D;
  toe: Point3D;
  area: number; // cross-section area S_i (m2)
  height: number; // |hTK - hTN|
  runDist: number; // horizontal toe offset (m)
}

/**
 * Trace a single Taluy cross-section outward along unit normal (nx, ny)
 * from boundary point (bx, by, hTK) with SNVN berm (Bgc, Hgc, igc) & optional retaining wall
 * until intersecting the natural terrain TIN surface (MHTN).
 */
function traceTaluyCrossSection(
  bx: number,
  by: number,
  hTK: number,
  nx: number,
  ny: number,
  type: 'cut' | 'fill',
  mhtn: TinSurface,
  cfg: TaluyConfig
): TaluyProfileSample {
  const slopeN = Math.max(0.25, type === 'cut' ? cfg.cutSlopeN : cfg.fillSlopeN);
  const sign = type === 'fill' ? -1 : 1; // Fill slopes downward (-Z), Cut slopes upward (+Z)
  const hTN0 = interpolateTinZ(mhtn, bx, by);
  const initDiff = Math.abs(hTK - hTN0);

  if (initDiff < 0.05) {
    return {
      top: { x: bx, y: by, z: hTK },
      toe: { x: bx, y: by, z: hTN0 },
      area: 0,
      height: 0,
      runDist: 0,
    };
  }

  // Optional retaining wall for fill slopes: drops vertically by retainingWallHeight first
  let startZ = hTK;
  let wallArea = 0;
  if (type === 'fill' && cfg.retainingWall && cfg.retainingWallHeight > 0) {
    const drop = Math.min(cfg.retainingWallHeight, initDiff);
    startZ = hTK - drop;
    // Small base width for retaining wall cross-section
    wallArea = drop * 0.4;
    if (initDiff <= cfg.retainingWallHeight + 0.05) {
      return {
        top: { x: bx, y: by, z: hTK },
        toe: { x: bx + nx * 0.4, y: by + ny * 0.4, z: hTN0 },
        area: wallArea,
        height: initDiff,
        runDist: 0.4,
      };
    }
  }

  // March outward in 0.4m horizontal increments until slope crosses MHTN
  const ds = 0.4;
  const maxDist = 45;
  let dist = 0;
  let currZ = startZ;
  let verticalSinceBerm = 0;
  let inBermRemaining = 0;
  let area = wallArea;
  let prevDiff = sign === -1 ? currZ - hTN0 : hTN0 - currZ;

  while (dist < maxDist) {
    const nextDist = dist + ds;
    let nextZ = currZ;

    if (inBermRemaining > 0) {
      const stepB = Math.min(ds, inBermRemaining);
      nextZ = currZ + sign * stepB * (cfg.bermSlopePct / 100);
      inBermRemaining -= stepB;
    } else {
      const dz = ds / slopeN;
      nextZ = currZ + sign * dz;
      verticalSinceBerm += dz;
      if (cfg.bermHeight > 0.5 && cfg.bermWidth > 0.1 && verticalSinceBerm >= cfg.bermHeight) {
        verticalSinceBerm = 0;
        inBermRemaining = cfg.bermWidth;
      }
    }

    const px = bx + nx * nextDist;
    const py = by + ny * nextDist;
    const groundZ = interpolateTinZ(mhtn, px, py);
    const currDiff = sign === -1 ? nextZ - groundZ : groundZ - nextZ;

    if (currDiff <= 0) {
      // Exact linear interpolation of daylight toe intersection
      const frac = prevDiff > 1e-6 ? prevDiff / (prevDiff - currDiff) : 0.5;
      const finalDist = dist + ds * frac;
      const finalX = bx + nx * finalDist;
      const finalY = by + ny * finalDist;
      const finalZ = interpolateTinZ(mhtn, finalX, finalY);
      area += 0.5 * Math.max(0, prevDiff) * (ds * frac);

      return {
        top: { x: bx, y: by, z: hTK },
        toe: { x: finalX, y: finalY, z: finalZ },
        area,
        height: initDiff,
        runDist: finalDist,
      };
    }

    area += 0.5 * (Math.max(0, prevDiff) + Math.max(0, currDiff)) * ds;
    dist = nextDist;
    currZ = nextZ;
    prevDiff = currDiff;
  }

  const endX = bx + nx * dist;
  const endY = by + ny * dist;
  return {
    top: { x: bx, y: by, z: hTK },
    toe: { x: endX, y: endY, z: interpolateTinZ(mhtn, endX, endY) },
    area,
    height: initDiff,
    runDist: dist,
  };
}

/**
 * SNVN Chapter V: Taluy Design & Volume Calculation (Sides C1..Cn + Convex Corners G1..Gn)
 * Volume formula: V = sum( (S_i + S_{i+1}) / 2 * L^{i,i+1} )
 */
export function computeSnvnTaluy(
  mhtn: TinSurface,
  designSpec: DesignSurfaceSpec,
  boundary: PolygonZone,
  cfg: TaluyConfig,
  customDesignTin?: TinSurface | null
): TaluyCalculationResult {
  if (!cfg.enabled || boundary.vertices.length < 3) {
    return {
      segments: [],
      ticks2D: [],
      totalCutArea: 0,
      totalFillArea: 0,
      totalCutVolume: 0,
      totalFillVolume: 0,
    };
  }

  const poly = ensureCCW(boundary.vertices);
  const n = poly.length;
  const step = Math.max(1.5, Math.min(20, cfg.stepLength));
  const tickStep = Math.max(1.5, Math.min(20, cfg.tickSpacing));

  const segments: TaluySegmentResult[] = [];
  const ticks2D: TaluyTick2D[] = [];

  // Outward unit normal for each CCW edge i -> (i+1): (dy/L, -dx/L)
  const edgeNormals: Point2D[] = [];
  for (let i = 0; i < n; i++) {
    const p1 = poly[i];
    const p2 = poly[(i + 1) % n];
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const len = Math.hypot(dx, dy) || 1;
    edgeNormals.push({ x: dy / len, y: -dx / len });
  }

  let edgeIdx = 1;
  let cornerIdx = 1;

  for (let i = 0; i < n; i++) {
    const p1 = poly[i];
    const p2 = poly[(i + 1) % n];
    const edgeLen = Math.hypot(p2.x - p1.x, p2.y - p1.y);
    if (edgeLen < 1) continue;

    const normal = edgeNormals[i];
    const numSteps = Math.max(2, Math.ceil(edgeLen / step));

    // Split edge into sub-runs of consistent Cut or Fill sign (V.2.1 Ranh giới taluy)
    interface RawRun {
      type: 'cut' | 'fill';
      samples: { s: number; sample: TaluyProfileSample }[];
    }
    const runs: RawRun[] = [];

    for (let k = 0; k <= numSteps; k++) {
      const t = k / numSteps;
      const x = p1.x + (p2.x - p1.x) * t;
      const y = p1.y + (p2.y - p1.y) * t;
      const hTN = interpolateTinZ(mhtn, x, y);
      const hTK = evaluateDesignElevation(designSpec, x, y, customDesignTin);
      const type: 'cut' | 'fill' = hTK >= hTN ? 'fill' : 'cut';
      const sample = traceTaluyCrossSection(x, y, hTK, normal.x, normal.y, type, mhtn, cfg);
      const sDist = t * edgeLen;

      if (runs.length === 0 || runs[runs.length - 1].type !== type) {
        runs.push({ type, samples: [{ s: sDist, sample }] });
      } else {
        runs[runs.length - 1].samples.push({ s: sDist, sample });
      }
    }

    for (const run of runs) {
      if (run.samples.length < 2) continue;
      let vol = 0;
      let surfArea = 0;
      let sumH = 0;
      const topLine: Point3D[] = [];
      const toeLine: Point3D[] = [];
      const meshTriangles: [Point3D, Point3D, Point3D][] = [];

      for (let k = 0; k < run.samples.length; k++) {
        const cur = run.samples[k];
        topLine.push(cur.sample.top);
        toeLine.push(cur.sample.toe);
        sumH += cur.sample.height;

        if (k > 0) {
          const prev = run.samples[k - 1];
          const L = cur.s - prev.s;
          // SNVN Equation V.1: V = ((S_i + S_{i+1}) / 2) * L
          vol += ((prev.sample.area + cur.sample.area) / 2) * L;
          surfArea += ((prev.sample.runDist + cur.sample.runDist) / 2) * L;

          meshTriangles.push([prev.sample.top, cur.sample.top, cur.sample.toe]);
          meshTriangles.push([prev.sample.top, cur.sample.toe, prev.sample.toe]);
        }
      }

      if (vol < 0.5 && surfArea < 0.5) continue;

      const runLen = run.samples[run.samples.length - 1].s - run.samples[0].s;
      segments.push({
        id: `C${edgeIdx++}`,
        kind: 'edge',
        type: run.type,
        length: runLen,
        area: surfArea,
        volume: vol,
        avgHeight: sumH / run.samples.length,
        sectionCount: run.samples.length,
        topLine,
        toeLine,
        meshTriangles,
      });

      // Generate SNVN V.4 2D Taluy ticks (vạch dài / vạch ngắn)
      const subStep = tickStep / (cfg.shortTicksPerLong + 1);
      const nTicks = Math.floor(runLen / subStep);
      for (let tk = 0; tk <= nTicks; tk++) {
        const targetS = run.samples[0].s + tk * subStep;
        // Locate enclosing samples
        let idxS = 0;
        while (idxS < run.samples.length - 2 && run.samples[idxS + 1].s < targetS) idxS++;
        const a = run.samples[idxS];
        const b = run.samples[Math.min(idxS + 1, run.samples.length - 1)];
        const frac = b.s > a.s ? (targetS - a.s) / (b.s - a.s) : 0;
        const tx = a.sample.top.x + (b.sample.top.x - a.sample.top.x) * frac;
        const ty = a.sample.top.y + (b.sample.top.y - a.sample.top.y) * frac;
        const ex = a.sample.toe.x + (b.sample.toe.x - a.sample.toe.x) * frac;
        const ey = a.sample.toe.y + (b.sample.toe.y - a.sample.toe.y) * frac;

        const isLong = tk % (cfg.shortTicksPerLong + 1) === 0;
        const factor = isLong ? 0.92 : 0.45;
        ticks2D.push({
          p1: { x: tx, y: ty },
          p2: { x: tx + (ex - tx) * factor, y: ty + (ey - ty) * factor },
          isLong,
          type: run.type,
        });
      }
    }

    // Convex corner fan G_k at vertex p1 (between previous edge normal and current edge normal)
    const prevIdx = (i - 1 + n) % n;
    const prevPt = poly[prevIdx];
    const cross = (p1.x - prevPt.x) * (p2.y - p1.y) - (p1.y - prevPt.y) * (p2.x - p1.x);
    if (cross > 1e-4) {
      const nA = edgeNormals[prevIdx];
      const nB = normal;
      let a1 = Math.atan2(nA.y, nA.x);
      let a2 = Math.atan2(nB.y, nB.x);
      let dAng = a2 - a1;
      while (dAng < 0) dAng += Math.PI * 2;
      if (dAng > Math.PI) dAng = Math.PI * 2 - dAng;

      const hTN = interpolateTinZ(mhtn, p1.x, p1.y);
      const hTK = evaluateDesignElevation(designSpec, p1.x, p1.y, customDesignTin);
      const cType: 'cut' | 'fill' = hTK >= hTN ? 'fill' : 'cut';
      const fanSteps = 6;
      const fanSamples: { ang: number; sample: TaluyProfileSample }[] = [];

      for (let f = 0; f <= fanSteps; f++) {
        const ang = a1 + (dAng * f) / fanSteps;
        const sample = traceTaluyCrossSection(
          p1.x,
          p1.y,
          hTK,
          Math.cos(ang),
          Math.sin(ang),
          cType,
          mhtn,
          cfg
        );
        fanSamples.push({ ang, sample });
      }

      let cArea = 0;
      let cVol = 0;
      const topLine: Point3D[] = [];
      const toeLine: Point3D[] = [];
      const meshTriangles: [Point3D, Point3D, Point3D][] = [];

      for (let f = 0; f < fanSamples.length; f++) {
        topLine.push(fanSamples[f].sample.top);
        toeLine.push(fanSamples[f].sample.toe);
        if (f > 0) {
          const prevF = fanSamples[f - 1].sample;
          const curF = fanSamples[f].sample;
          const dTheta = dAng / fanSteps;
          const rAvg = (prevF.runDist + curF.runDist) / 2;
          // Cone sector surface area & volume
          cArea += 0.5 * rAvg * rAvg * dTheta;
          // Centroid of triangular cross-section sits at ~r/3 from top edge
          const arcCentroid = (rAvg / 3) * dTheta;
          cVol += ((prevF.area + curF.area) / 2) * arcCentroid;

          meshTriangles.push([prevF.top, curF.toe, prevF.toe]);

          if (f % 2 === 0) {
            ticks2D.push({
              p1: { x: curF.top.x, y: curF.top.y },
              p2: {
                x: curF.top.x + (curF.toe.x - curF.top.x) * 0.85,
                y: curF.top.y + (curF.toe.y - curF.top.y) * 0.85,
              },
              isLong: true,
              type: cType,
            });
          }
        }
      }

      if (cVol > 0.2 || cArea > 0.2) {
        segments.push({
          id: `G${cornerIdx++}`,
          kind: 'corner',
          type: cType,
          length: 0,
          area: cArea,
          volume: cVol,
          avgHeight: Math.abs(hTK - hTN),
          sectionCount: fanSamples.length,
          topLine,
          toeLine,
          meshTriangles,
        });
      }
    }
  }

  let totalCutArea = 0;
  let totalFillArea = 0;
  let totalCutVolume = 0;
  let totalFillVolume = 0;

  for (const seg of segments) {
    if (seg.type === 'cut') {
      totalCutArea += seg.area;
      totalCutVolume += seg.volume;
    } else {
      totalFillArea += seg.area;
      totalFillVolume += seg.volume;
    }
  }

  return {
    segments,
    ticks2D,
    totalCutArea,
    totalFillArea,
    totalCutVolume,
    totalFillVolume,
  };
}
