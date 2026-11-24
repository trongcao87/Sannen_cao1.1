import * as XLSX from 'xlsx';
import {
  Breakline,
  ContourPolyline,
  CrossSectionResult,
  GridCalculationResult,
  Point2D,
  Point3D,
  PolygonZone,
  SurveyPoint,
  TaluyCalculationResult,
} from '../types/snvn';

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Parse uploaded Excel (.xlsx/.xls) or CSV file containing survey coordinates (X, Y, Z, BreaklineID, Layer).
 */
export async function parseSurveyExcelOrCsv(file: File): Promise<{
  points: SurveyPoint[];
  breaklines: Breakline[];
}> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array' });
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: '' });

  const points: SurveyPoint[] = [];
  const blMap = new Map<string, Point3D[]>();

  const findNumeric = (row: Record<string, unknown>, candidates: string[]): number | null => {
    for (const key of Object.keys(row)) {
      const k = key.trim().toLowerCase();
      if (candidates.some((c) => k === c || k.includes(c))) {
        const val = Number(String(row[key]).replace(',', '.'));
        if (!Number.isNaN(val)) return val;
      }
    }
    return null;
  };

  const findText = (row: Record<string, unknown>, candidates: string[]): string => {
    for (const key of Object.keys(row)) {
      const k = key.trim().toLowerCase();
      if (candidates.some((c) => k === c || k.includes(c))) {
        return String(row[key]).trim();
      }
    }
    return '';
  };

  rows.forEach((row, idx) => {
    let x = findNumeric(row, ['x', 'easting', 'toado_x', 'kinh']);
    let y = findNumeric(row, ['y', 'northing', 'toado_y', 'vi']);
    let z = findNumeric(row, ['z', 'elev', 'caodo', 'cao độ', 'h_tn', 'htn']);

    // Fallback: take first 3 numeric columns
    if (x === null || y === null || z === null) {
      const nums = Object.values(row)
        .map((v) => Number(String(v).replace(',', '.')))
        .filter((n) => !Number.isNaN(n));
      if (nums.length >= 3) {
        x = x ?? nums[0];
        y = y ?? nums[1];
        z = z ?? nums[2];
      }
    }

    if (x === null || y === null || z === null) return;

    const blId = findText(row, ['breakline', 'dutgay', 'đứt gãy', 'bl']);
    const layer = findText(row, ['layer', 'lop', 'lớp', 'code', 'mã']) || 'EXCEL_IMPORT';

    if (blId) {
      const arr = blMap.get(blId) ?? [];
      arr.push({ x, y, z });
      blMap.set(blId, arr);
    }

    points.push({
      id: `XL-${idx + 1}`,
      x,
      y,
      z,
      source: 'EXCEL',
      layer,
    });
  });

  const breaklines: Breakline[] = [];
  blMap.forEach((verts, key) => {
    if (verts.length >= 2) {
      breaklines.push({
        id: `BL-${key}`,
        name: `Đứt gãy Excel (${key})`,
        vertices: verts,
        is3D: true,
        layer: 'DUTGAY_EXCEL',
      });
    }
  });

  return { points, breaklines };
}

/**
 * Parse ASCII DXF file supporting all 6 SNVN AutoCAD entity types:
 * POINT, INSERT (Block), TEXT, LINE, LWPOLYLINE (2D with Elevation), POLYLINE/VERTEX (3D Breakline).
 */
export async function parseSurveyDxf(file: File): Promise<{
  points: SurveyPoint[];
  breaklines: Breakline[];
  boundary?: Point2D[];
}> {
  const text = await file.text();
  const rawLines = text.split(/\r?\n/).map((l) => l.trim());
  const pairs: { code: number; value: string }[] = [];
  for (let i = 0; i + 1 < rawLines.length; i += 2) {
    const code = parseInt(rawLines[i], 10);
    if (!Number.isNaN(code)) {
      pairs.push({ code, value: rawLines[i + 1] });
    }
  }

  const points: SurveyPoint[] = [];
  const breaklines: Breakline[] = [];
  let boundary: Point2D[] | undefined;

  let inEntities = false;
  let i = 0;
  let ptIdx = 1;
  let blIdx = 1;

  while (i < pairs.length) {
    const p = pairs[i];
    if (p.code === 2 && p.value === 'ENTITIES') {
      inEntities = true;
      i++;
      continue;
    }
    if (inEntities && p.code === 0 && p.value === 'ENDSEC') {
      break;
    }
    if (!inEntities) {
      i++;
      continue;
    }

    if (p.code === 0) {
      const entityType = p.value.toUpperCase();
      i++;
      let layer = '0';
      let x = 0,
        y = 0,
        z = 0;
      let x2 = 0,
        y2 = 0,
        z2 = 0;
      let elev = 0;
      let textVal = '';
      let closedFlag = 0;
      const lwVerts: Point2D[] = [];
      let curLwX: number | null = null;

      while (i < pairs.length && pairs[i].code !== 0) {
        const { code, value } = pairs[i];
        if (code === 8) layer = value;
        else if (code === 10) {
          if (entityType === 'LWPOLYLINE') {
            curLwX = parseFloat(value);
          } else {
            x = parseFloat(value);
          }
        } else if (code === 20) {
          if (entityType === 'LWPOLYLINE' && curLwX !== null) {
            lwVerts.push({ x: curLwX, y: parseFloat(value) });
            curLwX = null;
          } else {
            y = parseFloat(value);
          }
        } else if (code === 30) z = parseFloat(value);
        else if (code === 11) x2 = parseFloat(value);
        else if (code === 21) y2 = parseFloat(value);
        else if (code === 31) z2 = parseFloat(value);
        else if (code === 38) elev = parseFloat(value);
        else if (code === 1) textVal = value;
        else if (code === 70) closedFlag = parseInt(value, 10);
        i++;
      }

      if (entityType === 'POINT' || entityType === 'INSERT') {
        points.push({
          id: `DXF-${ptIdx++}`,
          x,
          y,
          z,
          source: entityType === 'POINT' ? 'POINT' : 'BLOCK',
          layer,
        });
      } else if (entityType === 'TEXT' || entityType === 'MTEXT') {
        const parsedZ = parseFloat(textVal.replace(',', '.'));
        points.push({
          id: `TXT-${ptIdx++}`,
          x,
          y,
          z: Number.isNaN(parsedZ) ? 0 : parsedZ,
          source: 'TEXT',
          layer,
          label: textVal,
        });
      } else if (entityType === 'LINE') {
        breaklines.push({
          id: `BL-L${blIdx++}`,
          name: `Line (${layer})`,
          vertices: [
            { x, y, z },
            { x: x2, y: y2, z: z2 },
          ],
          is3D: true,
          layer,
        });
      } else if (entityType === 'LWPOLYLINE' && lwVerts.length >= 2) {
        const isBoundaryLayer =
          layer.toUpperCase().includes('BIEN') ||
          layer.toUpperCase().includes('BOUNDARY') ||
          (closedFlag & 1) === 1;
        if (isBoundaryLayer && lwVerts.length >= 3 && !boundary) {
          boundary = lwVerts;
        } else {
          breaklines.push({
            id: `BL-2D${blIdx++}`,
            name: `2DPoly (${layer})`,
            vertices: lwVerts.map((v) => ({ x: v.x, y: v.y, z: elev })),
            is3D: false,
            layer,
          });
        }
      } else if (entityType === 'POLYLINE') {
        // Read following VERTEX entities until SEQEND
        const polyVerts: Point3D[] = [];
        while (i < pairs.length) {
          if (pairs[i].code === 0 && pairs[i].value === 'SEQEND') {
            i++;
            break;
          }
          if (pairs[i].code === 0 && pairs[i].value === 'VERTEX') {
            i++;
            let vx = 0,
              vy = 0,
              vz = 0;
            while (i < pairs.length && pairs[i].code !== 0) {
              if (pairs[i].code === 10) vx = parseFloat(pairs[i].value);
              else if (pairs[i].code === 20) vy = parseFloat(pairs[i].value);
              else if (pairs[i].code === 30) vz = parseFloat(pairs[i].value);
              i++;
            }
            polyVerts.push({ x: vx, y: vy, z: vz });
          } else {
            i++;
          }
        }
        if (polyVerts.length >= 2) {
          breaklines.push({
            id: `BL-3D${blIdx++}`,
            name: `3DPoly (${layer})`,
            vertices: polyVerts,
            is3D: true,
            layer,
          });
        }
      }
      continue;
    }
    i++;
  }

  return { points, breaklines, boundary };
}

/**
 * Export professional 6-sheet Excel (.xlsx) Workbook matching all 5 SNVN Chapter VI Tables
 * + Grid Node Elevation Coordinates.
 */
export function exportSnvnExcelWorkbook(
  projectName: string,
  gridResult: GridCalculationResult,
  taluyResult: TaluyCalculationResult
): void {
  const wb = XLSX.utils.book_new();
  const fmt = (n: number) => Number(n.toFixed(2));

  // Sheet 1: VI.1.1 Bảng khối lượng san nền (by column + total)
  const colHeaders = gridResult.colSummaries.map((c) => c.label);
  const sheet1Data = [
    [`BẢNG KHỐI LƯỢNG SAN NỀN — ${projectName.toUpperCase()}`],
    ['Hạng mục', ...colHeaders, 'Đơn vị', 'Tổng cộng'],
    [
      'Khối lượng đào',
      ...gridResult.colSummaries.map((c) => fmt(c.cutVolume)),
      'm³',
      fmt(gridResult.totalCutVolume),
    ],
    [
      'Khối lượng đắp',
      ...gridResult.colSummaries.map((c) => fmt(c.fillVolume)),
      'm³',
      fmt(gridResult.totalFillVolume),
    ],
    [
      'Diện tích đào',
      ...gridResult.colSummaries.map((c) => fmt(c.cutArea)),
      'm²',
      fmt(gridResult.totalCutArea),
    ],
    [
      'Diện tích đắp',
      ...gridResult.colSummaries.map((c) => fmt(c.fillArea)),
      'm²',
      fmt(gridResult.totalFillArea),
    ],
  ];
  const ws1 = XLSX.utils.aoa_to_sheet(sheet1Data);
  ws1['!cols'] = [{ wch: 20 }, ...colHeaders.map(() => ({ wch: 12 })), { wch: 10 }, { wch: 16 }];
  XLSX.utils.book_append_sheet(wb, ws1, '1_KL_SanNen');

  // Sheet 2: VI.1.2 Bảng tổng hợp đào đắp Taluy (G1..Gn, C1..Cn)
  const segHeaders = taluyResult.segments.map((s) => s.id);
  const sheet2Data = [
    [`BẢNG TỔNG HỢP ĐÀO ĐẮP TALUY — ${projectName.toUpperCase()}`],
    ['Hạng mục', ...segHeaders, 'Đơn vị', 'Khối lượng tổng'],
    [
      'Diện tích đào',
      ...taluyResult.segments.map((s) => (s.type === 'cut' ? fmt(s.area) : 0)),
      'm²',
      fmt(taluyResult.totalCutArea),
    ],
    [
      'Khối lượng đào',
      ...taluyResult.segments.map((s) => (s.type === 'cut' ? fmt(s.volume) : 0)),
      'm³',
      fmt(taluyResult.totalCutVolume),
    ],
    [
      'Diện tích đắp',
      ...taluyResult.segments.map((s) => (s.type === 'fill' ? fmt(s.area) : 0)),
      'm²',
      fmt(taluyResult.totalFillArea),
    ],
    [
      'Khối lượng đắp',
      ...taluyResult.segments.map((s) => (s.type === 'fill' ? fmt(s.volume) : 0)),
      'm³',
      fmt(taluyResult.totalFillVolume),
    ],
  ];
  const ws2 = XLSX.utils.aoa_to_sheet(sheet2Data);
  ws2['!cols'] = [{ wch: 20 }, ...segHeaders.map(() => ({ wch: 11 })), { wch: 10 }, { wch: 16 }];
  XLSX.utils.book_append_sheet(wb, ws2, '2_KL_Taluy');

  // Sheet 3: VI.1.3 Bảng tổng hợp khối lượng san nền
  const sheet3Data = [
    [`BẢNG TỔNG HỢP KHỐI LƯỢNG SAN NỀN — ${projectName.toUpperCase()}`],
    ['STT', 'Hạng mục', 'Đơn vị', 'Khối lượng'],
    [1, 'Diện tích khu đất', 'm²', fmt(gridResult.totalLandArea)],
    [2, 'Diện tích đào (trong lưới)', 'm²', fmt(gridResult.totalCutArea)],
    [3, 'Diện tích đắp (trong lưới)', 'm²', fmt(gridResult.totalFillArea)],
    [4, 'Khối lượng đào (trong lưới)', 'm³', fmt(gridResult.totalCutVolume)],
    [5, 'Khối lượng đắp (trong lưới)', 'm³', fmt(gridResult.totalFillVolume)],
    [6, 'Khối lượng đắp quy đổi (K đầm chặt)', 'm³', fmt(gridResult.effectiveFillVolume)],
    [7, 'Khối lượng đào Taluy', 'm³', fmt(taluyResult.totalCutVolume)],
    [8, 'Khối lượng đắp Taluy', 'm³', fmt(taluyResult.totalFillVolume)],
    [9, 'Tổng khối lượng đào (Lưới + Taluy)', 'm³', fmt(gridResult.totalCutVolume + taluyResult.totalCutVolume)],
    [10, 'Tổng khối lượng đắp (Lưới + Taluy)', 'm³', fmt(gridResult.totalFillVolume + taluyResult.totalFillVolume)],
    [
      11,
      'Chênh lệch cân bằng (Đắp - Đào)',
      'm³',
      fmt(
        gridResult.totalFillVolume +
          taluyResult.totalFillVolume -
          (gridResult.totalCutVolume + taluyResult.totalCutVolume)
      ),
    ],
  ];
  const ws3 = XLSX.utils.aoa_to_sheet(sheet3Data);
  ws3['!cols'] = [{ wch: 6 }, { wch: 38 }, { wch: 10 }, { wch: 18 }];
  XLSX.utils.book_append_sheet(wb, ws3, '3_TongHop');

  // Sheet 4 & 5: VI.1.4 Bảng diện tích & khối lượng từng ô lưới
  const sheet4Data: (string | number)[][] = [
    [`BẢNG DIỆN TÍCH SAN NỀN THEO Ô LƯỚI — ${projectName.toUpperCase()}`],
    ['Mã ô (Hàng-Cột)', 'Hàng', 'Cột', 'Diện tích đào (m²)', 'Diện tích đắp (m²)', 'Tổng diện tích (m²)'],
  ];
  const sheet5Data: (string | number)[][] = [
    [`BẢNG KHỐI LƯỢNG SAN NỀN THEO Ô LƯỚI — ${projectName.toUpperCase()}`],
    [
      'Mã ô (Hàng-Cột)',
      'Hàng',
      'Cột',
      'Chênh cao TB đào (m)',
      'Khối lượng đào (m³)',
      'Chênh cao TB đắp (m)',
      'Khối lượng đắp (m³)',
    ],
  ];

  for (const cell of gridResult.cells) {
    if (!cell.active) continue;
    sheet4Data.push([
      cell.id,
      cell.row + 1,
      cell.col + 1,
      fmt(cell.cutArea),
      fmt(cell.fillArea),
      fmt(cell.totalArea),
    ]);
    sheet5Data.push([
      cell.id,
      cell.row + 1,
      cell.col + 1,
      fmt(cell.cutAvgH),
      fmt(cell.cutVolume),
      fmt(cell.fillAvgH),
      fmt(cell.fillVolume),
    ]);
  }
  const ws4 = XLSX.utils.aoa_to_sheet(sheet4Data);
  ws4['!cols'] = [{ wch: 18 }, { wch: 8 }, { wch: 8 }, { wch: 18 }, { wch: 18 }, { wch: 18 }];
  XLSX.utils.book_append_sheet(wb, ws4, '4_DienTich_TheoO');

  const ws5 = XLSX.utils.aoa_to_sheet(sheet5Data);
  ws5['!cols'] = [
    { wch: 18 },
    { wch: 8 },
    { wch: 8 },
    { wch: 18 },
    { wch: 18 },
    { wch: 18 },
    { wch: 18 },
  ];
  XLSX.utils.book_append_sheet(wb, ws5, '5_KhoiLuong_TheoO');

  // Sheet 6: Tọa độ & cao độ nút lưới
  const sheet6Data: (string | number)[][] = [
    [`BẢNG CAO ĐỘ CÁC NÚT LƯỚI — ${projectName.toUpperCase()}`],
    ['Chỉ số (H-C)', 'Tọa độ X (m)', 'Tọa độ Y (m)', 'Cao độ TN (m)', 'Cao độ TK (m)', 'Chênh cao ΔH (m)', 'Ghi chú'],
  ];
  for (const row of gridResult.nodes) {
    for (const node of row) {
      if (!node.insideBoundary) continue;
      sheet6Data.push([
        node.id,
        fmt(node.x),
        fmt(node.y),
        fmt(node.hTN),
        fmt(node.hTK),
        fmt(node.deltaH),
        node.isCustomHTK ? 'Đã hiệu chỉnh tay' : node.deltaH >= 0 ? 'Đắp' : 'Đào',
      ]);
    }
  }
  const ws6 = XLSX.utils.aoa_to_sheet(sheet6Data);
  ws6['!cols'] = [
    { wch: 14 },
    { wch: 14 },
    { wch: 14 },
    { wch: 14 },
    { wch: 14 },
    { wch: 16 },
    { wch: 20 },
  ];
  XLSX.utils.book_append_sheet(wb, ws6, '6_CaoDo_NutLuoi');

  const out = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
  const blob = new Blob([out], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const safeName = projectName.replace(/[^a-zA-Z0-9_-]/g, '_');
  downloadBlob(blob, `SNVN_BangKhoiLuong_${safeName}.xlsx`);
}

/**
 * Export complete ASCII DXF (compatible with AutoCAD 2022) with separated SNVN layers:
 * SNVN_LUOI, SNVN_NUT_TN, SNVN_NUT_TK, SNVN_NUT_DH, SNVN_DAO, SNVN_DAP, SNVN_RANHGIOI_0,
 * SNVN_DONGMUC_CAI, SNVN_DONGMUC_CON, SNVN_TALUY, SNVN_BIEN.
 */
export function exportSnvnDxf(
  projectName: string,
  boundary: PolygonZone,
  exclusions: PolygonZone[],
  gridResult: GridCalculationResult,
  contours: ContourPolyline[],
  taluyResult: TaluyCalculationResult
): void {
  const lines: string[] = [];
  const push = (code: number, value: string | number) => {
    lines.push(String(code), String(value));
  };

  push(0, 'SECTION');
  push(2, 'HEADER');
  push(9, '$ACADVER');
  push(1, 'AC1015');
  push(0, 'ENDSEC');

  push(0, 'SECTION');
  push(2, 'ENTITIES');

  const addLine = (layer: string, color: number, x1: number, y1: number, x2: number, y2: number) => {
    push(0, 'LINE');
    push(8, layer);
    push(62, color);
    push(10, x1.toFixed(3));
    push(20, y1.toFixed(3));
    push(30, '0.0');
    push(11, x2.toFixed(3));
    push(21, y2.toFixed(3));
    push(31, '0.0');
  };

  const addCircle = (layer: string, color: number, cx: number, cy: number, r: number) => {
    push(0, 'CIRCLE');
    push(8, layer);
    push(62, color);
    push(10, cx.toFixed(3));
    push(20, cy.toFixed(3));
    push(30, '0.0');
    push(40, r.toFixed(3));
  };

  const addText = (
    layer: string,
    color: number,
    x: number,
    y: number,
    height: number,
    txt: string,
    rotDeg = 0
  ) => {
    push(0, 'TEXT');
    push(8, layer);
    push(62, color);
    push(10, x.toFixed(3));
    push(20, y.toFixed(3));
    push(30, '0.0');
    push(40, height.toFixed(2));
    push(1, txt);
    if (Math.abs(rotDeg) > 0.1) {
      push(50, rotDeg.toFixed(2));
    }
  };

  const addPolyline = (layer: string, color: number, pts: Point2D[], closed = false, elev = 0) => {
    if (pts.length < 2) return;
    push(0, 'LWPOLYLINE');
    push(8, layer);
    push(62, color);
    push(90, pts.length);
    push(70, closed ? 1 : 0);
    if (Math.abs(elev) > 1e-4) push(38, elev.toFixed(3));
    for (const p of pts) {
      push(10, p.x.toFixed(3));
      push(20, p.y.toFixed(3));
    }
  };

  // Boundary & exclusions
  addPolyline('SNVN_BIEN', 5, boundary.vertices, true);
  for (const ex of exclusions) {
    addPolyline('SNVN_VUNG_BOQUA', 6, ex.vertices, true);
  }

  // Contours
  for (const c of contours) {
    const layer = c.isMajor ? 'SNVN_DONGMUC_CAI' : 'SNVN_DONGMUC_CON';
    const color = c.surface === 'mhtn' ? (c.isMajor ? 30 : 8) : 4;
    addPolyline(layer, color, c.points, false, c.elevation);
    if (c.labelPoint) {
      addText(
        'SNVN_NHAN_DONGMUC',
        color,
        c.labelPoint.x,
        c.labelPoint.y,
        1.4,
        c.elevation.toFixed(1),
        (c.labelPoint.angleRad * 180) / Math.PI
      );
    }
  }

  // Grid cells & SNVN circle badges
  for (const cell of gridResult.cells) {
    if (!cell.active) continue;
    for (let i = 0; i < 4; i++) {
      const a = cell.corners[i];
      const b = cell.corners[(i + 1) % 4];
      addLine('SNVN_LUOI', 7, a.x, a.y, b.x, b.y);
    }
    for (const sub of cell.subPolygons) {
      const color = sub.type === 'fill' ? 1 : 2; // 1=Red Fill, 2=Yellow Cut
      const layer = sub.type === 'fill' ? 'SNVN_DAP' : 'SNVN_DAO';
      const r = Math.min(4.2, Math.max(2.0, Math.sqrt(sub.area) * 0.22));
      addCircle(layer, color, sub.centroid.x, sub.centroid.y, r);
      addLine(layer, color, sub.centroid.x - r, sub.centroid.y, sub.centroid.x + r, sub.centroid.y);
      addLine(layer, color, sub.centroid.x, sub.centroid.y, sub.centroid.x, sub.centroid.y + r);
      addText(layer, color, sub.centroid.x - r * 0.78, sub.centroid.y + r * 0.2, 0.85, sub.area.toFixed(1));
      addText(layer, color, sub.centroid.x + r * 0.12, sub.centroid.y + r * 0.2, 0.85, sub.avgDeltaH.toFixed(2));
      addText(layer, color, sub.centroid.x - r * 0.55, sub.centroid.y - r * 0.55, 0.95, sub.volume.toFixed(1));
    }
  }

  // Zero-lines (Ranh giới đào đắp)
  for (const seg of gridResult.zeroLines) {
    addLine('SNVN_RANHGIOI_0', 4, seg.p1.x, seg.p1.y, seg.p2.x, seg.p2.y);
  }

  // Node labels (4 quadrants per SNVN)
  for (const row of gridResult.nodes) {
    for (const n of row) {
      if (!n.insideBoundary) continue;
      addText('SNVN_NUT_TN', 3, n.x - 4.2, n.y + 0.6, 0.9, n.hTN.toFixed(2));
      addText('SNVN_NUT_TK', 1, n.x + 0.5, n.y + 0.6, 0.9, n.hTK.toFixed(2));
      addText('SNVN_NUT_DH', 2, n.x - 4.2, n.y - 1.4, 0.9, Math.abs(n.deltaH).toFixed(2));
      addText('SNVN_NUT_ID', 5, n.x + 0.5, n.y - 1.4, 0.85, n.id);
    }
  }

  // Taluy 2D hatch ticks & toe lines
  for (const seg of taluyResult.segments) {
    const color = seg.type === 'fill' ? 1 : 2;
    addPolyline('SNVN_TALUY_CHAN', color, seg.toeLine.map(({ x, y }) => ({ x, y })), false);
  }
  for (const tick of taluyResult.ticks2D) {
    addLine('SNVN_TALUY_VACH', tick.type === 'fill' ? 1 : 2, tick.p1.x, tick.p1.y, tick.p2.x, tick.p2.y);
  }

  push(0, 'ENDSEC');
  push(0, 'EOF');

  const blob = new Blob([lines.join('\r\n')], { type: 'application/dxf' });
  const safeName = projectName.replace(/[^a-zA-Z0-9_-]/g, '_');
  downloadBlob(blob, `SNVN_BanVe_${safeName}.dxf`);
}

/**
 * Export AutoCAD 2022 .SCR script to draw grid, zero lines, and cross-section directly via drag-and-drop.
 */
export function exportAutoCadScript(
  projectName: string,
  gridResult: GridCalculationResult,
  section?: CrossSectionResult | null
): void {
  const cmds: string[] = [
    '; SNVN Studio - AutoCAD 2022 Script File',
    'OSMODE 0',
    '-LAYER M SNVN_LUOI C 7 SNVN_LUOI M SNVN_RANHGIOI_0 C 4 SNVN_RANHGIOI_0 M SNVN_MATCAT C 3 SNVN_MATCAT ',
    '-LAYER S SNVN_LUOI ',
  ];

  for (const cell of gridResult.cells) {
    if (!cell.active) continue;
    const pts = cell.corners.map((p) => `${p.x.toFixed(3)},${p.y.toFixed(3)}`).join(' ');
    cmds.push(`_PLINE ${pts} C`);
  }

  cmds.push('-LAYER S SNVN_RANHGIOI_0 ');
  for (const seg of gridResult.zeroLines) {
    cmds.push(`_LINE ${seg.p1.x.toFixed(3)},${seg.p1.y.toFixed(3)} ${seg.p2.x.toFixed(3)},${seg.p2.y.toFixed(3)} `);
  }

  if (section && section.stations.length >= 2) {
    cmds.push('-LAYER S SNVN_MATCAT ');
    const ox = 0;
    const oy = -140;
    const scaleY = section.def.horizontalScale / section.def.verticalScale;
    const tnPts = section.stations
      .map((s) => `${(ox + s.dist).toFixed(2)},${(oy + (s.hTN - section.datumElevation) * scaleY).toFixed(2)}`)
      .join(' ');
    const tkPts = section.stations
      .map((s) => `${(ox + s.dist).toFixed(2)},${(oy + (s.hTK - section.datumElevation) * scaleY).toFixed(2)}`)
      .join(' ');
    cmds.push(`_PLINE ${tnPts} `);
    cmds.push(`_PLINE ${tkPts} `);
  }

  cmds.push('ZOOM E');
  const blob = new Blob([cmds.join('\r\n')], { type: 'text/plain;charset=utf-8' });
  const safeName = projectName.replace(/[^a-zA-Z0-9_-]/g, '_');
  downloadBlob(blob, `SNVN_AutoCAD2022_${safeName}.scr`);
}
