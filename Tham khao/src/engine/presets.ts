import { ProjectPreset, SurveyPoint, Breakline, Point3D } from '../types/snvn';

/** Deterministic PRNG so presets are 100% reproducible */
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function generateIndustrialParkPreset(): ProjectPreset {
  const rand = mulberry32(202604);
  const points: SurveyPoint[] = [];

  // Terrain formula: undulating hill on NW (+23m) sloping toward SE (+11m) with a natural drainage swale
  const terrainZ = (x: number, y: number): number => {
    const base = 16.8 - 0.022 * (x - 120) + 0.028 * (y - 95);
    const hillNW = 4.6 * Math.exp(-((x - 55) ** 2 + (y - 145) ** 2) / 3600);
    const moundNE = 2.4 * Math.exp(-((x - 195) ** 2 + (y - 150) ** 2) / 2800);
    const valleySE = -3.8 * Math.exp(-((x - 185) ** 2 + (y - 45) ** 2) / 4200);
    // Swale along diagonal breakline y = 0.55*x + 25
    const distSwale = Math.abs(y - (0.55 * x + 22)) / Math.sqrt(1 + 0.55 ** 2);
    const swale = -1.65 * Math.exp(-(distSwale ** 2) / 220);
    const micro = 0.35 * Math.sin(x * 0.045) * Math.cos(y * 0.05);
    return Number((base + hillNW + moundNE + valleySE + swale + micro).toFixed(2));
  };

  // Scatter survey grid + jitter covering [-20..260] x [-20..210]
  let idx = 1;
  for (let gx = -20; gx <= 260; gx += 20) {
    for (let gy = -20; gy <= 210; gy += 20) {
      const x = Number((gx + (rand() - 0.5) * 9).toFixed(2));
      const y = Number((gy + (rand() - 0.5) * 9).toFixed(2));
      const z = terrainZ(x, y);
      points.push({
        id: `PT-${idx++}`,
        x,
        y,
        z,
        source: idx % 5 === 0 ? 'TEXT' : idx % 3 === 0 ? 'BLOCK' : 'POINT',
        layer: idx % 5 === 0 ? 'CAODO_TN' : 'DIEM_DO',
      });
    }
  }

  // Breakline 1: Natural drainage channel centerline (3D Polyline)
  const bl1Verts: Point3D[] = [];
  for (let i = 0; i <= 10; i++) {
    const x = 10 + i * 23;
    const y = Number((0.55 * x + 22 + Math.sin(i * 0.7) * 4).toFixed(2));
    const z = Number((terrainZ(x, y) - 0.45).toFixed(2));
    bl1Verts.push({ x, y, z });
  }

  // Breakline 2: Existing embankment terrace edge (3D Polyline)
  const bl2Verts: Point3D[] = [
    { x: 18, y: 128, z: Number((terrainZ(18, 128) + 0.6).toFixed(2)) },
    { x: 56, y: 136, z: Number((terrainZ(56, 136) + 0.75).toFixed(2)) },
    { x: 96, y: 148, z: Number((terrainZ(96, 148) + 0.55).toFixed(2)) },
    { x: 138, y: 162, z: Number((terrainZ(138, 162) + 0.4).toFixed(2)) },
  ];

  const breaklines: Breakline[] = [
    {
      id: 'BL-1',
      name: 'Tim mương thoát nước tự nhiên (3DPoly)',
      vertices: bl1Verts,
      is3D: true,
      layer: 'DUTGAY_MUONG',
    },
    {
      id: 'BL-2',
      name: 'Mép bờ bậc thềm phía Tây Bắc (3DPoly)',
      vertices: bl2Verts,
      is3D: true,
      layer: 'DUTGAY_TALUY',
    },
  ];

  return {
    id: 'kcn-phumy',
    name: 'KCN Phú Mỹ — Lô CN-04',
    location: 'Bà Rịa – Vũng Tàu · 3.65 ha',
    description:
      'Địa hình đồi thoải kết hợp rãnh thoát nước đứt gãy 3D và 01 khu vực hồ kỹ thuật bỏ qua ở trung tâm (mô phỏng chuẩn bài toán SNVN Chương IV–V).',
    points,
    breaklines,
    boundary: {
      id: 'BND-1',
      name: 'Biên lô đào đắp CN-04',
      type: 'boundary',
      vertices: [
        { x: 15, y: 18 },
        { x: 222, y: 12 },
        { x: 235, y: 92 },
        { x: 218, y: 178 },
        { x: 112, y: 186 },
        { x: 12, y: 162 },
      ],
    },
    exclusions: [
      {
        id: 'EXC-1',
        name: 'Vùng bỏ qua — Trạm biến áp 110kV',
        type: 'exclusion',
        vertices: [
          { x: 94, y: 78 },
          { x: 144, y: 78 },
          { x: 144, y: 118 },
          { x: 94, y: 118 },
        ],
      },
    ],
    defaultDesign: {
      mode: 'single_slope',
      baseElevation: 16.5,
      refPoint: { x: 120, y: 95 },
      slopeAngleDeg: -35,
      longitudinalSlopePct: 0.6,
      transverseSlopePct: 0.4,
      elevationShift: 0,
    },
    defaultGrid: {
      name: 'LUOI_CN04',
      colSpec: '12x20',
      rowSpec: '9x20',
      originX: 5,
      originY: 5,
      angleDeg: 0,
      layer: 'SNVN_LUOI',
      compactionFactor: 1.08,
    },
    defaultSections: [
      {
        id: 'SEC-1',
        name: 'MC 1-1 (Tây – Đông)',
        start: { x: 8, y: 55 },
        end: { x: 238, y: 55 },
        horizontalScale: 500,
        verticalScale: 100,
      },
      {
        id: 'SEC-2',
        name: 'MC 2-2 (Nam – Bắc)',
        start: { x: 70, y: 8 },
        end: { x: 70, y: 190 },
        horizontalScale: 500,
        verticalScale: 100,
      },
    ],
  };
}

function generateHillsideUrbanPreset(): ProjectPreset {
  const rand = mulberry32(88912);
  const points: SurveyPoint[] = [];

  const terrainZ = (x: number, y: number): number => {
    const slope = 28.5 - 0.055 * x + 0.018 * y;
    const ridge = 3.2 * Math.exp(-((y - 80) ** 2) / 1400) * Math.sin((x / 200) * Math.PI);
    const dip = -2.2 * Math.exp(-((x - 140) ** 2 + (y - 30) ** 2) / 2500);
    return Number((slope + ridge + dip + 0.25 * Math.cos(x * 0.06)).toFixed(2));
  };

  let idx = 1;
  for (let gx = -15; gx <= 215; gx += 18) {
    for (let gy = -15; gy <= 175; gy += 18) {
      const x = Number((gx + (rand() - 0.5) * 7).toFixed(2));
      const y = Number((gy + (rand() - 0.5) * 7).toFixed(2));
      points.push({
        id: `DT-${idx++}`,
        x,
        y,
        z: terrainZ(x, y),
        source: 'POINT',
        layer: 'KHAOSAT_TN',
      });
    }
  }

  const ridgeLine: Point3D[] = [];
  for (let i = 0; i <= 8; i++) {
    const x = 10 + i * 23;
    const y = 82 + Math.sin(i * 0.5) * 6;
    ridgeLine.push({ x, y: Number(y.toFixed(2)), z: Number((terrainZ(x, y) + 0.5).toFixed(2)) });
  }

  return {
    id: 'kdt-doithong',
    name: 'KĐT Đồi Thông — Phân khu B',
    location: 'Đà Lạt · 2.58 ha',
    description:
      'Khu đô thị sườn đồi có tuyến sống lưng thoát nước hướng dốc hai mái (i_dọc 2.0%, i_ngang 1.5%) phù hợp bài toán MHTK hướng dốc SNVN mục III.4.2.',
    points,
    breaklines: [
      {
        id: 'BL-RIDGE',
        name: 'Đường phân thủy sườn đồi',
        vertices: ridgeLine,
        is3D: true,
        layer: 'DUTGAY_SONGLUNG',
      },
    ],
    boundary: {
      id: 'BND-DT',
      name: 'Ranh giới Phân khu B',
      type: 'boundary',
      vertices: [
        { x: 12, y: 20 },
        { x: 188, y: 14 },
        { x: 196, y: 148 },
        { x: 18, y: 154 },
      ],
    },
    exclusions: [],
    defaultDesign: {
      mode: 'ridge_slope',
      baseElevation: 26.2,
      refPoint: { x: 100, y: 82 },
      slopeAngleDeg: 0,
      longitudinalSlopePct: 2.0,
      transverseSlopePct: 1.5,
      elevationShift: 0,
    },
    defaultGrid: {
      name: 'LUOI_PHANKHUB',
      colSpec: '4x20,4x15,4x20',
      rowSpec: '8x20',
      originX: 4,
      originY: 4,
      angleDeg: 0,
      layer: 'SNVN_LUOI',
      compactionFactor: 1.1,
    },
    defaultSections: [
      {
        id: 'SEC-DT1',
        name: 'MC A-A (Dọc tuyến chính)',
        start: { x: 8, y: 82 },
        end: { x: 198, y: 82 },
        horizontalScale: 500,
        verticalScale: 100,
      },
      {
        id: 'SEC-DT2',
        name: 'MC B-B (Ngang hai mái dốc)',
        start: { x: 100, y: 10 },
        end: { x: 100, y: 158 },
        horizontalScale: 500,
        verticalScale: 100,
      },
    ],
  };
}

function generateRiverPortPreset(): ProjectPreset {
  const rand = mulberry32(44190);
  const points: SurveyPoint[] = [];

  const terrainZ = (x: number, y: number): number => {
    // Alluvial flat near river bank (y < 60 drops steeply)
    const bankDrop = y < 65 ? -0.075 * (65 - y) : 0.012 * (y - 65);
    const wave = 0.55 * Math.sin(x * 0.03) + 0.4 * Math.cos(y * 0.04);
    const levee = 1.6 * Math.exp(-((y - 72) ** 2) / 260);
    return Number((3.8 + bankDrop + levee + wave).toFixed(2));
  };

  let idx = 1;
  for (let gx = -20; gx <= 280; gx += 22) {
    for (let gy = -15; gy <= 185; gy += 20) {
      const x = Number((gx + (rand() - 0.5) * 8).toFixed(2));
      const y = Number((gy + (rand() - 0.5) * 8).toFixed(2));
      points.push({
        id: `CG-${idx++}`,
        x,
        y,
        z: terrainZ(x, y),
        source: 'BLOCK',
        layer: 'DIAHINH_CANG',
      });
    }
  }

  const bankCrest: Point3D[] = [];
  for (let i = 0; i <= 10; i++) {
    const x = i * 27;
    const y = 66 + Math.sin(i * 0.4) * 4;
    bankCrest.push({ x, y: Number(y.toFixed(2)), z: Number((terrainZ(x, y) + 0.3).toFixed(2)) });
  }

  return {
    id: 'cang-icd',
    name: 'Cảng ICD & Bãi Container — Lô A2',
    location: 'Hải Phòng · 4.10 ha',
    description:
      'Mặt bằng bãi ven sông có đường đứt gãy đỉnh kè hiện trạng, yêu cầu san lấp tôn nền vượt lũ cao độ thiết kế phẳng +5.20m.',
    points,
    breaklines: [
      {
        id: 'BL-KE',
        name: 'Đỉnh bờ kè sông hiện trạng',
        vertices: bankCrest,
        is3D: true,
        layer: 'DUTGAY_BOKE',
      },
    ],
    boundary: {
      id: 'BND-ICD',
      name: 'Biên bãi Container Lô A2',
      type: 'boundary',
      vertices: [
        { x: 14, y: 20 },
        { x: 256, y: 20 },
        { x: 262, y: 168 },
        { x: 14, y: 168 },
      ],
    },
    exclusions: [],
    defaultDesign: {
      mode: 'flat',
      baseElevation: 5.2,
      refPoint: { x: 135, y: 94 },
      slopeAngleDeg: 0,
      longitudinalSlopePct: 0.3,
      transverseSlopePct: 0.3,
      elevationShift: 0,
    },
    defaultGrid: {
      name: 'LUOI_ICD_A2',
      colSpec: '13x20',
      rowSpec: '8x20',
      originX: 8,
      originY: 14,
      angleDeg: 0,
      layer: 'SNVN_LUOI',
      compactionFactor: 1.15,
    },
    defaultSections: [
      {
        id: 'SEC-ICD1',
        name: 'MC 1-1 (Vuông góc bờ sông)',
        start: { x: 135, y: 10 },
        end: { x: 135, y: 176 },
        horizontalScale: 500,
        verticalScale: 50,
      },
    ],
  };
}

export const PROJECT_PRESETS: ProjectPreset[] = [
  generateIndustrialParkPreset(),
  generateHillsideUrbanPreset(),
  generateRiverPortPreset(),
];
