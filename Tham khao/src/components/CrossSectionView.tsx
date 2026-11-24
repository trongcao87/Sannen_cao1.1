import React, { useRef } from 'react';
import { Download, Plus, Send, Trash2 } from 'lucide-react';
import { CrossSectionDef, CrossSectionResult } from '../types/snvn';

interface CrossSectionViewProps {
  sections: CrossSectionDef[];
  activeSectionId: string;
  sectionResult: CrossSectionResult | null;
  onSelectSection: (id: string) => void;
  onUpdateScale: (id: string, hScale: number, vScale: number) => void;
  onDeleteSection: (id: string) => void;
  onStartDrawSection: () => void;
  onPushSectionToMcp: () => void;
}

export const CrossSectionView: React.FC<CrossSectionViewProps> = ({
  sections,
  activeSectionId,
  sectionResult,
  onSelectSection,
  onUpdateScale,
  onDeleteSection,
  onStartDrawSection,
  onPushSectionToMcp,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);

  const handleDownloadSvg = () => {
    if (!svgRef.current || !sectionResult) return;
    const serializer = new XMLSerializer();
    const str = serializer.serializeToString(svgRef.current);
    const blob = new Blob([str], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SNVN_MatCat_${sectionResult.def.name.replace(/\s+/g, '_')}.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (!sectionResult || sectionResult.stations.length < 2) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-[#0B0F17] p-8 text-center">
        <p className="text-sm text-slate-300">Chưa có tuyến mặt cắt ngang nào được chọn.</p>
        <button
          type="button"
          onClick={onStartDrawSection}
          className="mt-4 flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500"
        >
          <Plus className="h-4 w-4" />
          Kẻ tuyến mặt cắt mới trên bản vẽ 2D
        </button>
      </div>
    );
  }

  const { stations, datumElevation, maxElevation, totalLength, cutArea, fillArea, def } =
    sectionResult;

  // Architectural SVG Drafting Layout
  const svgW = 1120;
  const leftLabelW = 152;
  const rightPad = 42;
  const plotW = svgW - leftLabelW - rightPad;
  const topPad = 68;
  const plotH = 240;
  const rowH = 34;
  const bandRows = [
    { key: 'note', label: 'Ký hiệu cọc' },
    { key: 'hTK', label: 'Cao độ TK (m)' },
    { key: 'hTN', label: 'Cao độ TN (m)' },
    { key: 'dh', label: 'Đào / Đắp (m)' },
    { key: 'seg', label: 'Khoảng cách lẻ' },
    { key: 'cum', label: 'Cộng dồn (m)' },
  ];
  const tableTop = topPad + plotH + 22;
  const svgH = tableTop + bandRows.length * rowH + 26;

  const elevSpan = Math.max(4, Math.ceil(maxElevation + 1.5 - datumElevation));
  const xOf = (dist: number) => leftLabelW + (dist / Math.max(totalLength, 1)) * plotW;
  const yOf = (elev: number) => topPad + plotH - ((elev - datumElevation) / elevSpan) * plotH;

  const tnPath = stations
    .map((s, i) => `${i === 0 ? 'M' : 'L'} ${xOf(s.dist).toFixed(1)} ${yOf(s.hTN).toFixed(1)}`)
    .join(' ');

  const tkPath = stations
    .map((s, i) => `${i === 0 ? 'M' : 'L'} ${xOf(s.dist).toFixed(1)} ${yOf(s.hTK).toFixed(1)}`)
    .join(' ');

  // Build individual segment Cut / Fill shaded polygons between adjacent stations
  const segmentPolys = stations.slice(0, -1).map((s1, i) => {
    const s2 = stations[i + 1];
    const avgDh = (s1.deltaH + s2.deltaH) / 2;
    const isFill = avgDh >= 0;
    const pts = [
      `${xOf(s1.dist).toFixed(1)},${yOf(s1.hTN).toFixed(1)}`,
      `${xOf(s2.dist).toFixed(1)},${yOf(s2.hTN).toFixed(1)}`,
      `${xOf(s2.dist).toFixed(1)},${yOf(s2.hTK).toFixed(1)}`,
      `${xOf(s1.dist).toFixed(1)},${yOf(s1.hTK).toFixed(1)}`,
    ].join(' ');
    return { pts, isFill, key: i };
  });

  // Elevation gridlines every 2m (or 1m if narrow span)
  const elevStep = elevSpan <= 8 ? 1 : elevSpan <= 18 ? 2 : 5;
  const elevTicks: number[] = [];
  for (let z = datumElevation; z <= datumElevation + elevSpan + 0.01; z += elevStep) {
    elevTicks.push(Number(z.toFixed(1)));
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#0B0F17]">
      {/* Section Control Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#263248] bg-[#141B29] px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg border border-[#263248] bg-[#0B0F17] p-1">
            {sections.map((sec) => (
              <button
                key={sec.id}
                type="button"
                onClick={() => onSelectSection(sec.id)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium whitespace-nowrap shrink-0 transition-colors ${
                  sec.id === activeSectionId
                    ? 'bg-sky-500/20 text-sky-300'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {sec.name}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onStartDrawSection}
            className="flex items-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
          >
            <Plus className="h-3.5 w-3.5 text-sky-400" />
            Kẻ tuyến mới
          </button>

          {sections.length > 1 && (
            <button
              type="button"
              onClick={() => onDeleteSection(def.id)}
              className="rounded-md border border-[#263248] p-1.5 text-slate-400 hover:border-red-500/40 hover:text-red-400"
              title="Xóa tuyến mặt cắt này"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <span>Tỷ lệ ngang 1:</span>
            <select
              value={def.horizontalScale}
              onChange={(e) => onUpdateScale(def.id, Number(e.target.value), def.verticalScale)}
              className="rounded border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-slate-200"
            >
              <option value={200}>200</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
            <span>Đứng 1:</span>
            <select
              value={def.verticalScale}
              onChange={(e) => onUpdateScale(def.id, def.horizontalScale, Number(e.target.value))}
              className="rounded border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-slate-200"
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>

          <button
            type="button"
            onClick={handleDownloadSvg}
            className="flex items-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-3 py-1.5 font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
          >
            <Download className="h-3.5 w-3.5" />
            Xuất bản vẽ SVG
          </button>

          <button
            type="button"
            onClick={onPushSectionToMcp}
            className="flex items-center gap-1.5 rounded-md bg-sky-600 px-3 py-1.5 font-semibold text-white hover:bg-sky-500 whitespace-nowrap shrink-0"
          >
            <Send className="h-3.5 w-3.5" />
            Vẽ sang AutoCAD 2022
          </button>
        </div>
      </div>

      {/* Main Scrollable Drafting Sheet + Station Table */}
      <div className="flex-1 overflow-auto p-5">
        <div className="mx-auto max-w-[1160px] space-y-6">
          {/* Standard TCVN Cross-Section Vector Sheet */}
          <div className="overflow-x-auto rounded-lg border border-[#263248] bg-[#0E1420] p-4">
            <svg
              ref={svgRef}
              viewBox={`0 0 ${svgW} ${svgH}`}
              className="w-full min-w-[920px] h-auto"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <pattern
                  id="hatchCut"
                  width="8"
                  height="8"
                  patternTransform="rotate(45 0 0)"
                  patternUnits="userSpaceOnUse"
                >
                  <line x1="0" y1="0" x2="0" y2="8" stroke="#EAB308" strokeWidth="1.2" strokeOpacity="0.45" />
                </pattern>
                <pattern
                  id="hatchFill"
                  width="8"
                  height="8"
                  patternTransform="rotate(-45 0 0)"
                  patternUnits="userSpaceOnUse"
                >
                  <line x1="0" y1="0" x2="0" y2="8" stroke="#EF4444" strokeWidth="1.2" strokeOpacity="0.45" />
                </pattern>
              </defs>

              {/* Background */}
              <rect x="0" y="0" width={svgW} height={svgH} fill="#0B0F17" />

              {/* TCVN Sheet Title Header */}
              <text
                x={svgW / 2}
                y="26"
                textAnchor="middle"
                fill="#F1F5F9"
                fontSize="15"
                fontWeight="700"
                fontFamily="Plus Jakarta Sans, sans-serif"
              >
                MẶT CẮT NGANG THIẾT KẾ SAN NỀN — {def.name.toUpperCase()}
              </text>
              <text
                x={svgW / 2}
                y="45"
                textAnchor="middle"
                fill="#94A3B8"
                fontSize="11.5"
                fontFamily="JetBrains Mono, monospace"
              >
                {`TLN 1:${def.horizontalScale} · TLĐ 1:${def.verticalScale} · Chiều dài L = ${totalLength.toFixed(1)}m · Diện tích Đào Fđào = ${cutArea.toFixed(2)} m² · Diện tích Đắp Fđắp = ${fillArea.toFixed(2)} m²`}
              </text>

              {/* Horizontal Elevation Gridlines & Left Elevation Ruler */}
              {elevTicks.map((z) => {
                const yy = yOf(z);
                return (
                  <g key={z}>
                    <line
                      x1={leftLabelW}
                      y1={yy}
                      x2={leftLabelW + plotW}
                      y2={yy}
                      stroke="#1E293B"
                      strokeDasharray={z === datumElevation ? undefined : '4 4'}
                      strokeWidth={z === datumElevation ? 1.4 : 0.8}
                    />
                    <text
                      x={leftLabelW - 10}
                      y={yy + 4}
                      textAnchor="end"
                      fill="#94A3B8"
                      fontSize="10.5"
                      fontFamily="JetBrains Mono, monospace"
                    >
                      +{z.toFixed(1)}
                    </text>
                  </g>
                );
              })}

              {/* Vertical Elevation Axis */}
              <line
                x1={leftLabelW}
                y1={topPad}
                x2={leftLabelW}
                y2={topPad + plotH}
                stroke="#475569"
                strokeWidth="1.2"
              />

              {/* Datum Line Label (Mức so sánh) */}
              <text
                x="14"
                y={topPad + plotH + 15}
                fill="#38BDF8"
                fontSize="11"
                fontWeight="600"
                fontFamily="JetBrains Mono, monospace"
              >
                MSS: +{datumElevation.toFixed(2)} m
              </text>
              <line
                x1="12"
                y1={topPad + plotH + 20}
                x2={leftLabelW + plotW}
                y2={topPad + plotH + 20}
                stroke="#38BDF8"
                strokeWidth="1.2"
              />

              {/* Cut / Fill Shaded Polygons */}
              {segmentPolys.map((p) => (
                <polygon
                  key={p.key}
                  points={p.pts}
                  fill={p.isFill ? 'url(#hatchFill)' : 'url(#hatchCut)'}
                />
              ))}

              {/* Station Drop Lines */}
              {stations.map((s, idx) => {
                const xx = xOf(s.dist);
                const topY = Math.min(yOf(s.hTN), yOf(s.hTK));
                return (
                  <g key={idx}>
                    <line
                      x1={xx}
                      y1={topY}
                      x2={xx}
                      y2={tableTop}
                      stroke={s.note === 'Đứt gãy' ? '#D946EF' : '#334155'}
                      strokeWidth={s.note ? 1 : 0.7}
                      strokeDasharray={s.note === 'Điểm 0' ? '3 2' : undefined}
                    />
                    <circle cx={xx} cy={yOf(s.hTN)} r="2.6" fill="#22C55E" />
                    <circle cx={xx} cy={yOf(s.hTK)} r="2.6" fill="#EF4444" />
                  </g>
                );
              })}

              {/* Natural Ground Profile Line (MHTN - Green) */}
              <path d={tnPath} fill="none" stroke="#22C55E" strokeWidth="2.1" />

              {/* Design Surface Profile Line (MHTK - Red) */}
              <path d={tkPath} fill="none" stroke="#EF4444" strokeWidth="2.2" />

              {/* Inline Legend Top-Right */}
              <g transform={`translate(${leftLabelW + plotW - 250}, ${topPad + 6})`}>
                <line x1="0" y1="6" x2="22" y2="6" stroke="#22C55E" strokeWidth="2.2" />
                <text x="28" y="10" fill="#CBD5E1" fontSize="11" fontFamily="Plus Jakarta Sans, sans-serif">
                  Đường tự nhiên (TN)
                </text>
                <line x1="145" y1="6" x2="167" y2="6" stroke="#EF4444" strokeWidth="2.2" />
                <text x="173" y="10" fill="#CBD5E1" fontSize="11" fontFamily="Plus Jakarta Sans, sans-serif">
                  Thiết kế (TK)
                </text>
              </g>

              {/* TCVN Bottom Annotation Table Grid */}
              <rect
                x="12"
                y={tableTop}
                width={leftLabelW + plotW - 12}
                height={bandRows.length * rowH}
                fill="#0F1521"
                stroke="#475569"
                strokeWidth="1.2"
              />

              {/* Left Column Divider */}
              <line
                x1={leftLabelW}
                y1={tableTop}
                x2={leftLabelW}
                y2={tableTop + bandRows.length * rowH}
                stroke="#475569"
                strokeWidth="1.2"
              />

              {bandRows.map((row, rIdx) => {
                const ry = tableTop + rIdx * rowH;
                return (
                  <g key={row.key}>
                    {rIdx > 0 && (
                      <line
                        x1="12"
                        y1={ry}
                        x2={leftLabelW + plotW}
                        y2={ry}
                        stroke="#263248"
                        strokeWidth="1"
                      />
                    )}
                    <text
                      x="22"
                      y={ry + rowH / 2 + 4}
                      fill="#CBD5E1"
                      fontSize="11"
                      fontWeight="500"
                      fontFamily="Plus Jakarta Sans, sans-serif"
                    >
                      {row.label}
                    </text>
                  </g>
                );
              })}

              {/* Station Data Columns inside TCVN Grid */}
              {stations.map((s, idx) => {
                const xx = xOf(s.dist);
                const prevX = idx > 0 ? xOf(stations[idx - 1].dist) : xx;
                const midSegX = (xx + prevX) / 2;
                // Avoid label collision on very tight stations (< 28px apart)
                const tight = idx > 0 && xx - prevX < 28;

                return (
                  <g key={`col-${idx}`}>
                    <line
                      x1={xx}
                      y1={tableTop}
                      x2={xx}
                      y2={tableTop + bandRows.length * rowH}
                      stroke="#1E293B"
                      strokeWidth="0.8"
                    />

                    {/* Row 0: Note */}
                    {s.note && (
                      <text
                        x={xx}
                        y={tableTop + rowH * 0.5 + 3.5}
                        textAnchor="middle"
                        fill={s.note === 'Đứt gãy' ? '#E879F9' : '#38BDF8'}
                        fontSize="9.5"
                        fontWeight="600"
                        fontFamily="Plus Jakarta Sans, sans-serif"
                      >
                        {s.note}
                      </text>
                    )}

                    {/* Row 1: hTK */}
                    {!tight && (
                      <text
                        x={xx}
                        y={tableTop + rowH * 1.5 + 3.5}
                        textAnchor="middle"
                        fill="#FCA5A5"
                        fontSize="10"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {s.hTK.toFixed(2)}
                      </text>
                    )}

                    {/* Row 2: hTN */}
                    {!tight && (
                      <text
                        x={xx}
                        y={tableTop + rowH * 2.5 + 3.5}
                        textAnchor="middle"
                        fill="#86EFAC"
                        fontSize="10"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {s.hTN.toFixed(2)}
                      </text>
                    )}

                    {/* Row 3: deltaH */}
                    {!tight && (
                      <text
                        x={xx}
                        y={tableTop + rowH * 3.5 + 3.5}
                        textAnchor="middle"
                        fill={s.deltaH >= 0 ? '#F87171' : '#FACC15'}
                        fontSize="10"
                        fontWeight="600"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {s.deltaH >= 0 ? `+${s.deltaH.toFixed(2)}` : s.deltaH.toFixed(2)}
                      </text>
                    )}

                    {/* Row 4: Segment distance (centered between stations) */}
                    {idx > 0 && xx - prevX >= 22 && (
                      <text
                        x={midSegX}
                        y={tableTop + rowH * 4.5 + 3.5}
                        textAnchor="middle"
                        fill="#CBD5E1"
                        fontSize="10"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {s.segDist.toFixed(1)}
                      </text>
                    )}

                    {/* Row 5: Cumulative distance */}
                    {!tight && (
                      <text
                        x={xx}
                        y={tableTop + rowH * 5.5 + 3.5}
                        textAnchor="middle"
                        fill="#94A3B8"
                        fontSize="9.5"
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {s.dist.toFixed(1)}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Numeric Station Verification Table */}
          <div className="overflow-hidden rounded-lg border border-[#263248] bg-[#141B29]">
            <div className="flex items-center justify-between border-b border-[#263248] px-4 py-2.5 text-xs">
              <span className="font-semibold text-slate-200">
                Bảng chi tiết tọa độ &amp; cao độ cọc mặt cắt ({stations.length} cọc)
              </span>
              <span className="font-mono tabular-nums text-slate-400">
                Fđào: <strong className="text-amber-300">{cutArea.toFixed(2)} m²</strong> · Fđắp:{' '}
                <strong className="text-red-300">{fillArea.toFixed(2)} m²</strong>
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#263248] bg-[#0F1521] text-slate-400">
                  <tr>
                    <th className="px-3 py-2 font-medium">Cọc</th>
                    <th className="px-3 py-2 text-right font-medium">Lý trình (m)</th>
                    <th className="px-3 py-2 text-right font-medium">KC lẻ (m)</th>
                    <th className="px-3 py-2 text-right font-medium">X (m)</th>
                    <th className="px-3 py-2 text-right font-medium">Y (m)</th>
                    <th className="px-3 py-2 text-right font-medium">CĐTN (m)</th>
                    <th className="px-3 py-2 text-right font-medium">CĐTK (m)</th>
                    <th className="px-3 py-2 text-right font-medium">Chênh cao ΔH (m)</th>
                    <th className="px-3 py-2 font-medium">Ghi chú</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1E293B] font-mono tabular-nums">
                  {stations.map((s, idx) => (
                    <tr key={idx} className="hover:bg-[#1C2538]/60">
                      <td className="px-3 py-2 text-slate-300">C{idx + 1}</td>
                      <td className="px-3 py-2 text-right text-slate-200">{s.dist.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-slate-400">{s.segDist.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-slate-400">{s.x.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-slate-400">{s.y.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-emerald-400">{s.hTN.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-red-400">{s.hTK.toFixed(2)}</td>
                      <td
                        className={`px-3 py-2 text-right font-medium ${
                          s.deltaH >= 0 ? 'text-red-300' : 'text-amber-300'
                        }`}
                      >
                        {s.deltaH >= 0 ? `+${s.deltaH.toFixed(2)} (Đắp)` : `${s.deltaH.toFixed(2)} (Đào)`}
                      </td>
                      <td className="px-3 py-2 font-sans text-slate-400">{s.note ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
