import {
  Breakline,
  CrossSectionDef,
  CrossSectionResult,
  CrossSectionStation,
  DesignSurfaceSpec,
  Point2D,
  TinSurface,
} from '../types/snvn';
import { evaluateDesignElevation, interpolateTinZ } from './tin';

function segmentIntersectionT(
  a: Point2D,
  b: Point2D,
  c: Point2D,
  d: Point2D
): number | null {
  const dx1 = b.x - a.x;
  const dy1 = b.y - a.y;
  const dx2 = d.x - c.x;
  const dy2 = d.y - c.y;
  const denom = dx1 * dy2 - dy1 * dx2;
  if (Math.abs(denom) < 1e-9) return null;
  const t = ((c.x - a.x) * dy2 - (c.y - a.y) * dx2) / denom;
  const u = ((c.x - a.x) * dy1 - (c.y - a.y) * dx1) / denom;
  if (t >= 0 && t <= 1 && u >= 0 && u <= 1) return t;
  return null;
}

/**
 * Sample a TCVN standard cross-section (Mặt cắt ngang) along a user-defined cutting line:
 * - Samples evenly every ~15–20m AND at exact breakline intersections AND exact cut/fill zero-crossings.
 * - Computes Cut Area (F_đào) and Fill Area (F_đắp) in m².
 */
export function computeCrossSection(
  def: CrossSectionDef,
  mhtn: TinSurface,
  designSpec: DesignSurfaceSpec,
  breaklines: Breakline[],
  customDesignTin?: TinSurface | null
): CrossSectionResult {
  const totalLength = Math.hypot(def.end.x - def.start.x, def.end.y - def.start.y);
  if (totalLength < 1) {
    return {
      def,
      totalLength: 0,
      datumElevation: 0,
      minElevation: 0,
      maxElevation: 10,
      cutArea: 0,
      fillArea: 0,
      stations: [],
    };
  }

  const tSamples: { t: number; note?: string }[] = [];
  const nominalStep = Math.max(10, Math.min(25, Math.round(totalLength / 14 / 5) * 5 || 15));

  for (let d = 0; d < totalLength; d += nominalStep) {
    tSamples.push({ t: d / totalLength, note: d === 0 ? 'Đầu tuyến' : undefined });
  }
  tSamples.push({ t: 1, note: 'Cuối tuyến' });

  // Intersect with breaklines so terrain ridges/ditches are captured accurately
  for (const bl of breaklines) {
    for (let i = 0; i < bl.vertices.length - 1; i++) {
      const t = segmentIntersectionT(def.start, def.end, bl.vertices[i], bl.vertices[i + 1]);
      if (t !== null && t > 0.01 && t < 0.99) {
        tSamples.push({ t, note: 'Đứt gãy' });
      }
    }
  }

  tSamples.sort((a, b) => a.t - b.t);

  // Deduplicate very close stations (< 1.5m)
  const mergedT: { t: number; note?: string }[] = [];
  for (const item of tSamples) {
    if (
      mergedT.length === 0 ||
      (item.t - mergedT[mergedT.length - 1].t) * totalLength > 1.8
    ) {
      mergedT.push(item);
    } else if (item.note && !mergedT[mergedT.length - 1].note) {
      mergedT[mergedT.length - 1].note = item.note;
    }
  }

  const evalAtT = (t: number, note?: string) => {
    const x = def.start.x + (def.end.x - def.start.x) * t;
    const y = def.start.y + (def.end.y - def.start.y) * t;
    const hTN = interpolateTinZ(mhtn, x, y);
    const hTK = evaluateDesignElevation(designSpec, x, y, customDesignTin);
    return {
      dist: t * totalLength,
      x,
      y,
      hTN,
      hTK,
      deltaH: hTK - hTN,
      note,
    };
  };

  // Build preliminary list and insert exact Cut/Fill zero-crossing stations (ΔH = 0)
  const rawPoints = mergedT.map((m) => evalAtT(m.t, m.note));
  const finalPoints: typeof rawPoints = [];

  for (let i = 0; i < rawPoints.length; i++) {
    const curr = rawPoints[i];
    if (i > 0) {
      const prev = rawPoints[i - 1];
      if ((prev.deltaH > 0.01 && curr.deltaH < -0.01) || (prev.deltaH < -0.01 && curr.deltaH > 0.01)) {
        const frac = prev.deltaH / (prev.deltaH - curr.deltaH);
        const zeroDist = prev.dist + (curr.dist - prev.dist) * frac;
        const zeroT = zeroDist / totalLength;
        const zPt = evalAtT(zeroT, 'Điểm 0');
        zPt.deltaH = 0;
        finalPoints.push(zPt);
      }
    }
    finalPoints.push(curr);
  }

  let cutArea = 0;
  let fillArea = 0;
  let minE = Infinity;
  let maxE = -Infinity;

  const stations: CrossSectionStation[] = finalPoints.map((pt, idx) => {
    const segDist = idx === 0 ? 0 : pt.dist - finalPoints[idx - 1].dist;
    if (pt.hTN < minE) minE = pt.hTN;
    if (pt.hTK < minE) minE = pt.hTK;
    if (pt.hTN > maxE) maxE = pt.hTN;
    if (pt.hTK > maxE) maxE = pt.hTK;

    if (idx > 0) {
      const prev = finalPoints[idx - 1];
      const avgDh = (prev.deltaH + pt.deltaH) / 2;
      if (avgDh >= 0) fillArea += avgDh * segDist;
      else cutArea += Math.abs(avgDh) * segDist;
    }

    return {
      ...pt,
      segDist,
    };
  });

  // Datum elevation (Mức so sánh) rounded down to clean 2m below minimum elevation
  const datumElevation = Math.floor((minE - 1.8) / 2) * 2;

  return {
    def,
    totalLength,
    datumElevation,
    minElevation: minE,
    maxElevation: maxE,
    cutArea,
    fillArea,
    stations,
  };
}
