import React, { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Download, FileCode2, FileSpreadsheet, Scale, Send } from 'lucide-react';
import {
  DesignSurfaceSpec,
  GridCalculationResult,
  GridConfig,
  PolygonZone,
  TaluyCalculationResult,
  TinSurface,
} from '../types/snvn';
import { computeBalanceCurve } from '../engine/grid';

interface ReportsChartsViewProps {
  projectName: string;
  mhtn: TinSurface;
  designSpec: DesignSurfaceSpec;
  gridConfig: GridConfig;
  boundary: PolygonZone;
  exclusions: PolygonZone[];
  customDesignTin?: TinSurface | null;
  gridResult: GridCalculationResult;
  taluyResult: TaluyCalculationResult;
  onExportExcel: () => void;
  onExportDxf: () => void;
  onExportScript: () => void;
  onPushTablesToMcp: () => void;
  onAutoBalance: () => void;
}

type SnvnTableTab = 'summary' | 'by_col' | 'taluy' | 'cell_area' | 'cell_vol';

export const ReportsChartsView: React.FC<ReportsChartsViewProps> = ({
  projectName,
  mhtn,
  designSpec,
  gridConfig,
  boundary,
  exclusions,
  customDesignTin,
  gridResult,
  taluyResult,
  onExportExcel,
  onExportDxf,
  onExportScript,
  onPushTablesToMcp,
  onAutoBalance,
}) => {
  const [tableTab, setTableTab] = useState<SnvnTableTab>('summary');
  const [cellFilter, setCellFilter] = useState<'all' | 'cut' | 'fill' | 'mixed'>('all');
  const [cellQuery, setCellQuery] = useState('');

  const colChartData = useMemo(
    () =>
      gridResult.colSummaries
        .filter((c) => c.cutVolume + c.fillVolume > 0.1)
        .map((c) => ({
          name: c.label,
          Đào: Math.round(c.cutVolume),
          Đắp: Math.round(c.fillVolume),
        })),
    [gridResult.colSummaries]
  );

  const balanceCurveData = useMemo(
    () =>
      computeBalanceCurve(mhtn, designSpec, gridConfig, boundary, exclusions, customDesignTin),
    [mhtn, designSpec, gridConfig, boundary, exclusions, customDesignTin]
  );

  const elevationHistogram = useMemo(() => {
    const { minZ, maxZ } = mhtn.bounds;
    const bins = 8;
    const step = Math.max(0.5, (maxZ - minZ) / bins);
    const counts = Array.from({ length: bins }, (_, i) => ({
      range: `${(minZ + i * step).toFixed(1)}–${(minZ + (i + 1) * step).toFixed(1)}m`,
      count: 0,
    }));
    for (const v of mhtn.vertices) {
      const idx = Math.min(bins - 1, Math.max(0, Math.floor((v.z - minZ) / step)));
      counts[idx].count += 1;
    }
    return counts;
  }, [mhtn]);

  const activeCells = useMemo(() => {
    return gridResult.cells.filter((cell) => {
      if (!cell.active) return false;
      if (cellQuery && !cell.id.includes(cellQuery.trim())) return false;
      if (cellFilter === 'cut') return cell.cutArea > 0.1 && cell.fillArea <= 0.1;
      if (cellFilter === 'fill') return cell.fillArea > 0.1 && cell.cutArea <= 0.1;
      if (cellFilter === 'mixed') return cell.cutArea > 0.1 && cell.fillArea > 0.1;
      return true;
    });
  }, [gridResult.cells, cellFilter, cellQuery]);

  const grandCut = gridResult.totalCutVolume + taluyResult.totalCutVolume;
  const grandFill = gridResult.totalFillVolume + taluyResult.totalFillVolume;
  const netBalance = grandFill - grandCut;

  const fmt = (n: number) =>
    n.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0B0F17]">
      {/* Report Export Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#263248] bg-[#141B29] px-5 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            Báo cáo Khối lượng Chuẩn SNVN &amp; Biểu đồ Địa hình
          </h2>
          <p className="text-xs text-slate-400">
            {projectName} · Lưới {gridConfig.name} · Hệ số đầm chặt K = {gridConfig.compactionFactor.toFixed(2)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onAutoBalance}
            className="flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-300 hover:bg-amber-500/20 whitespace-nowrap shrink-0"
          >
            <Scale className="h-3.5 w-3.5" />
            Tối ưu cân bằng Đào–Đắp
          </button>
          <button
            type="button"
            onClick={onExportExcel}
            className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 whitespace-nowrap shrink-0"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            Xuất Excel 6 Sheet (.xlsx)
          </button>
          <button
            type="button"
            onClick={onExportDxf}
            className="flex items-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
          >
            <Download className="h-3.5 w-3.5" />
            Xuất DXF
          </button>
          <button
            type="button"
            onClick={onExportScript}
            className="flex items-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
          >
            <FileCode2 className="h-3.5 w-3.5" />
            Xuất .SCR
          </button>
          <button
            type="button"
            onClick={onPushTablesToMcp}
            className="flex items-center gap-1.5 rounded-md bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500 whitespace-nowrap shrink-0"
          >
            <Send className="h-3.5 w-3.5" />
            Chèn bảng AutoCAD 2022
          </button>
        </div>
      </div>

      {/* Scrollable Content: KPI Strip + 3 Analytical Charts + 5 SNVN Tables */}
      <div className="flex-1 overflow-y-auto p-5">
        <div className="mx-auto max-w-[1240px] space-y-6">
          {/* 4-Column Executive KPI Row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <div className="text-xs text-slate-400">Diện tích san nền khu đất</div>
              <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-slate-100">
                {fmt(gridResult.totalLandArea)} <span className="text-xs font-normal text-slate-400">m²</span>
              </div>
              <div className="mt-1 font-mono text-[11px] tabular-nums text-slate-400">
                Đào: {fmt(gridResult.totalCutArea)} · Đắp: {fmt(gridResult.totalFillArea)}
              </div>
            </div>

            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <div className="text-xs text-amber-300">Tổng khối lượng Đào (Lưới + Taluy)</div>
              <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-amber-300">
                {fmt(grandCut)} <span className="text-xs font-normal text-amber-300/70">m³</span>
              </div>
              <div className="mt-1 font-mono text-[11px] tabular-nums text-slate-400">
                Lưới: {fmt(gridResult.totalCutVolume)} · Taluy: {fmt(taluyResult.totalCutVolume)}
              </div>
            </div>

            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <div className="text-xs text-red-300">Tổng khối lượng Đắp (Lưới + Taluy)</div>
              <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-red-400">
                {fmt(grandFill)} <span className="text-xs font-normal text-red-400/70">m³</span>
              </div>
              <div className="mt-1 font-mono text-[11px] tabular-nums text-slate-400">
                Lưới: {fmt(gridResult.totalFillVolume)} · Taluy: {fmt(taluyResult.totalFillVolume)}
              </div>
            </div>

            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <div className="text-xs text-slate-400">Chênh lệch cân bằng (Đắp − Đào)</div>
              <div
                className={`mt-1 font-mono text-xl font-semibold tabular-nums ${
                  Math.abs(netBalance) < 300
                    ? 'text-emerald-400'
                    : netBalance > 0
                    ? 'text-red-300'
                    : 'text-amber-300'
                }`}
              >
                {netBalance >= 0 ? '+' : ''}
                {fmt(netBalance)} <span className="text-xs font-normal text-slate-400">m³</span>
              </div>
              <div className="mt-1 text-[11px] text-slate-400">
                {Math.abs(netBalance) < 300
                  ? 'Trạng thái: Cân bằng tối ưu'
                  : netBalance > 0
                  ? 'Cần mua thêm đất đắp'
                  : 'Dư đất đào cần vận chuyển đi'}
              </div>
            </div>
          </div>

          {/* Analytical Charts Grid */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Chart 1: Cut / Fill per Grid Column */}
            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <h3 className="mb-3 text-xs font-semibold text-slate-200">
                Khối lượng Đào / Đắp theo Cột lưới (m³)
              </h3>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={colChartData} margin={{ top: 5, right: 8, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="name" tick={{ fill: '#94A3B8', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#94A3B8', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0F1521',
                        borderColor: '#263248',
                        fontSize: 11,
                        fontFamily: 'JetBrains Mono',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="Đào" fill="#EAB308" radius={[2, 2, 0, 0]} />
                    <Bar dataKey="Đắp" fill="#EF4444" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 2: Cut/Fill Balance Sensitivity Curve */}
            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <h3 className="mb-3 text-xs font-semibold text-slate-200">
                Đường cong Cân bằng Đào–Đắp theo ΔZ (m³)
              </h3>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={balanceCurveData}
                    margin={{ top: 5, right: 8, left: -12, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="label" tick={{ fill: '#94A3B8', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#94A3B8', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0F1521',
                        borderColor: '#263248',
                        fontSize: 11,
                        fontFamily: 'JetBrains Mono',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line
                      type="monotone"
                      dataKey="cutVol"
                      name="KL Đào"
                      stroke="#EAB308"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="fillVol"
                      name="KL Đắp (×K)"
                      stroke="#EF4444"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Chart 3: Natural Elevation Distribution Histogram */}
            <div className="rounded-lg border border-[#263248] bg-[#141B29] p-4">
              <h3 className="mb-3 text-xs font-semibold text-slate-200">
                Phân bố Cao độ Địa hình Tự nhiên (MHTN)
              </h3>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={elevationHistogram}
                    margin={{ top: 5, right: 8, left: -16, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="range" tick={{ fill: '#94A3B8', fontSize: 9 }} />
                    <YAxis tick={{ fill: '#94A3B8', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0F1521',
                        borderColor: '#263248',
                        fontSize: 11,
                        fontFamily: 'JetBrains Mono',
                      }}
                    />
                    <Bar dataKey="count" name="Số đỉnh TIN" fill="#22C55E" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* 5 Standardized SNVN Tables (Chapter VI) */}
          <div className="rounded-lg border border-[#263248] bg-[#141B29]">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#263248] px-4 py-3">
              <div className="flex flex-wrap items-center gap-1 rounded-lg border border-[#263248] bg-[#0B0F17] p-1">
                {[
                  { id: 'summary', label: '1. Bảng tổng hợp (VI.1.3)' },
                  { id: 'by_col', label: '2. Bảng theo cột (VI.1.1)' },
                  { id: 'taluy', label: '3. Bảng Taluy (VI.1.2)' },
                  { id: 'cell_area', label: '4. Diện tích ô (VI.1.4)' },
                  { id: 'cell_vol', label: '5. Khối lượng ô (VI.1.4)' },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTableTab(t.id as SnvnTableTab)}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
                      tableTab === t.id
                        ? 'bg-sky-500/20 text-sky-300'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {(tableTab === 'cell_area' || tableTab === 'cell_vol') && (
                <div className="flex items-center gap-2 text-xs">
                  <input
                    type="text"
                    value={cellQuery}
                    onChange={(e) => setCellQuery(e.target.value)}
                    placeholder="Lọc mã ô (vd: 3-4)..."
                    className="w-36 rounded-md border border-[#263248] bg-[#0B0F17] px-2.5 py-1 font-mono text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
                  />
                  <select
                    value={cellFilter}
                    onChange={(e) => setCellFilter(e.target.value as 'all' | 'cut' | 'fill' | 'mixed')}
                    className="rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 text-xs text-slate-200"
                  >
                    <option value="all">Tất cả ô ({gridResult.cells.filter((c) => c.active).length})</option>
                    <option value="cut">Chỉ ô đào</option>
                    <option value="fill">Chỉ ô đắp</option>
                    <option value="mixed">Ô hỗn hợp (có đường 0)</option>
                  </select>
                </div>
              )}
            </div>

            <div className="overflow-x-auto p-4">
              {tableTab === 'summary' && (
                <table className="w-full max-w-2xl text-left text-xs">
                  <thead className="border-b border-[#263248] bg-[#0F1521] text-slate-400">
                    <tr>
                      <th className="px-4 py-2.5 font-medium">Hạng mục (Mẫu SNVN VI.1.3)</th>
                      <th className="px-4 py-2.5 text-center font-medium">Đơn vị</th>
                      <th className="px-4 py-2.5 text-right font-medium">Khối lượng</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B]">
                    {[
                      { label: 'Diện tích khu đất', unit: 'm²', val: gridResult.totalLandArea, cls: 'text-slate-100' },
                      { label: 'Diện tích đào (phần trong lưới)', unit: 'm²', val: gridResult.totalCutArea, cls: 'text-amber-300' },
                      { label: 'Diện tích đắp (phần trong lưới)', unit: 'm²', val: gridResult.totalFillArea, cls: 'text-red-300' },
                      { label: 'Khối lượng đào (phần trong lưới)', unit: 'm³', val: gridResult.totalCutVolume, cls: 'text-amber-300' },
                      { label: 'Khối lượng đắp (phần trong lưới)', unit: 'm³', val: gridResult.totalFillVolume, cls: 'text-red-300' },
                      {
                        label: `Khối lượng đắp quy đổi (K = ${gridConfig.compactionFactor.toFixed(2)})`,
                        unit: 'm³',
                        val: gridResult.effectiveFillVolume,
                        cls: 'text-red-300',
                      },
                      { label: 'Khối lượng đào Taluy', unit: 'm³', val: taluyResult.totalCutVolume, cls: 'text-amber-300' },
                      { label: 'Khối lượng đắp Taluy', unit: 'm³', val: taluyResult.totalFillVolume, cls: 'text-red-300' },
                      { label: 'Tổng cộng khối lượng đào', unit: 'm³', val: grandCut, cls: 'font-semibold text-amber-300' },
                      { label: 'Tổng cộng khối lượng đắp', unit: 'm³', val: grandFill, cls: 'font-semibold text-red-400' },
                    ].map((row) => (
                      <tr key={row.label} className="hover:bg-[#1C2538]/50">
                        <td className="px-4 py-2.5 text-slate-200">{row.label}</td>
                        <td className="px-4 py-2.5 text-center font-mono text-slate-400">{row.unit}</td>
                        <td className={`px-4 py-2.5 text-right font-mono tabular-nums ${row.cls}`}>
                          {fmt(row.val)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tableTab === 'by_col' && (
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[#263248] bg-[#0F1521] text-slate-400">
                    <tr>
                      <th className="sticky left-0 bg-[#0F1521] px-3 py-2 font-medium">Hạng mục</th>
                      {gridResult.colSummaries.map((c) => (
                        <th key={c.col} className="px-3 py-2 text-right font-mono font-medium">
                          {c.label}
                        </th>
                      ))}
                      <th className="px-3 py-2 text-center font-medium">Đơn vị</th>
                      <th className="px-3 py-2 text-right font-semibold text-sky-300">Khối lượng</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B] font-mono tabular-nums">
                    <tr>
                      <td className="sticky left-0 bg-[#141B29] px-3 py-2 font-sans text-amber-300">KL đào</td>
                      {gridResult.colSummaries.map((c) => (
                        <td key={c.col} className="px-3 py-2 text-right text-slate-300">
                          {fmt(c.cutVolume)}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-center text-slate-400">m³</td>
                      <td className="px-3 py-2 text-right font-semibold text-amber-300">
                        {fmt(gridResult.totalCutVolume)}
                      </td>
                    </tr>
                    <tr>
                      <td className="sticky left-0 bg-[#141B29] px-3 py-2 font-sans text-red-300">KL đắp</td>
                      {gridResult.colSummaries.map((c) => (
                        <td key={c.col} className="px-3 py-2 text-right text-slate-300">
                          {fmt(c.fillVolume)}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-center text-slate-400">m³</td>
                      <td className="px-3 py-2 text-right font-semibold text-red-400">
                        {fmt(gridResult.totalFillVolume)}
                      </td>
                    </tr>
                    <tr>
                      <td className="sticky left-0 bg-[#141B29] px-3 py-2 font-sans text-slate-300">Diện tích đào</td>
                      {gridResult.colSummaries.map((c) => (
                        <td key={c.col} className="px-3 py-2 text-right text-slate-400">
                          {fmt(c.cutArea)}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-center text-slate-400">m²</td>
                      <td className="px-3 py-2 text-right text-slate-200">{fmt(gridResult.totalCutArea)}</td>
                    </tr>
                    <tr>
                      <td className="sticky left-0 bg-[#141B29] px-3 py-2 font-sans text-slate-300">Diện tích đắp</td>
                      {gridResult.colSummaries.map((c) => (
                        <td key={c.col} className="px-3 py-2 text-right text-slate-400">
                          {fmt(c.fillArea)}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-center text-slate-400">m²</td>
                      <td className="px-3 py-2 text-right text-slate-200">{fmt(gridResult.totalFillArea)}</td>
                    </tr>
                  </tbody>
                </table>
              )}

              {tableTab === 'taluy' && (
                taluyResult.segments.length === 0 ? (
                  <p className="py-6 text-center text-xs text-slate-400">
                    Chức năng tính Taluy đang tắt hoặc không có chênh cao biên. Bật Taluy ở Bước 5 để xem bảng chi tiết.
                  </p>
                ) : (
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[#263248] bg-[#0F1521] text-slate-400">
                      <tr>
                        <th className="px-3 py-2 font-medium">Đoạn / Góc</th>
                        <th className="px-3 py-2 font-medium">Loại mái</th>
                        <th className="px-3 py-2 text-right font-medium">Chiều dài (m)</th>
                        <th className="px-3 py-2 text-right font-medium">Chiều cao TB (m)</th>
                        <th className="px-3 py-2 text-right font-medium">Số mặt cắt</th>
                        <th className="px-3 py-2 text-right font-medium">Diện tích (m²)</th>
                        <th className="px-3 py-2 text-right font-medium">Khối lượng (m³)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1E293B] font-mono tabular-nums">
                      {taluyResult.segments.map((seg) => (
                        <tr key={seg.id} className="hover:bg-[#1C2538]/50">
                          <td className="px-3 py-2 font-semibold text-slate-200">{seg.id}</td>
                          <td className="px-3 py-2 font-sans">
                            <span className={seg.type === 'fill' ? 'text-red-400' : 'text-amber-300'}>
                              {seg.type === 'fill' ? 'Taluy đắp' : 'Taluy đào'} ({seg.kind === 'corner' ? 'Góc lồi' : 'Cạnh biên'})
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300">
                            {seg.kind === 'corner' ? '—' : seg.length.toFixed(1)}
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300">{seg.avgHeight.toFixed(2)}</td>
                          <td className="px-3 py-2 text-right text-slate-400">{seg.sectionCount}</td>
                          <td className="px-3 py-2 text-right text-slate-200">{fmt(seg.area)}</td>
                          <td
                            className={`px-3 py-2 text-right font-semibold ${
                              seg.type === 'fill' ? 'text-red-400' : 'text-amber-300'
                            }`}
                          >
                            {fmt(seg.volume)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              )}

              {(tableTab === 'cell_area' || tableTab === 'cell_vol') && (
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[#263248] bg-[#0F1521] text-slate-400">
                    <tr>
                      <th className="px-3 py-2 font-medium">Mã ô (H-C)</th>
                      <th className="px-3 py-2 font-medium">Phân loại</th>
                      {tableTab === 'cell_area' ? (
                        <>
                          <th className="px-3 py-2 text-right font-medium">Diện tích đào (m²)</th>
                          <th className="px-3 py-2 text-right font-medium">Diện tích đắp (m²)</th>
                          <th className="px-3 py-2 text-right font-medium">Tổng diện tích (m²)</th>
                        </>
                      ) : (
                        <>
                          <th className="px-3 py-2 text-right font-medium">ΔH TB đào (m)</th>
                          <th className="px-3 py-2 text-right font-medium">KL đào (m³)</th>
                          <th className="px-3 py-2 text-right font-medium">ΔH TB đắp (m)</th>
                          <th className="px-3 py-2 text-right font-medium">KL đắp (m³)</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E293B] font-mono tabular-nums">
                    {activeCells.map((cell) => {
                      const kind =
                        cell.cutArea > 0.1 && cell.fillArea > 0.1
                          ? 'Hỗn hợp (có đường 0)'
                          : cell.fillArea > 0.1
                          ? 'Ô đắp'
                          : 'Ô đào';
                      return (
                        <tr key={cell.id} className="hover:bg-[#1C2538]/50">
                          <td className="px-3 py-2 font-semibold text-sky-300">{cell.id}</td>
                          <td className="px-3 py-2 font-sans text-slate-300">{kind}</td>
                          {tableTab === 'cell_area' ? (
                            <>
                              <td className="px-3 py-2 text-right text-amber-300">{fmt(cell.cutArea)}</td>
                              <td className="px-3 py-2 text-right text-red-300">{fmt(cell.fillArea)}</td>
                              <td className="px-3 py-2 text-right text-slate-100">{fmt(cell.totalArea)}</td>
                            </>
                          ) : (
                            <>
                              <td className="px-3 py-2 text-right text-slate-400">{cell.cutAvgH.toFixed(2)}</td>
                              <td className="px-3 py-2 text-right text-amber-300">{fmt(cell.cutVolume)}</td>
                              <td className="px-3 py-2 text-right text-slate-400">{cell.fillAvgH.toFixed(2)}</td>
                              <td className="px-3 py-2 text-right text-red-400">{fmt(cell.fillVolume)}</td>
                            </>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
