import React, { useEffect, useState } from 'react';
import { Download, FileSpreadsheet, RotateCcw, Send, Trash2 } from 'lucide-react';
import { GridCalculationResult, GridCell, GridNode, TaluyCalculationResult } from '../types/snvn';

interface InspectorPanelProps {
  gridResult: GridCalculationResult;
  taluyResult: TaluyCalculationResult;
  selectedNode: GridNode | null;
  selectedCell: GridCell | null;
  nodeOverrideCount: number;
  mergedPairCount: number;
  onUpdateNodeHTK: (nodeId: string, newHTK: number) => void;
  onResetNodeHTK: (nodeId: string) => void;
  onResetAllOverrides: () => void;
  onClearMergedCells: () => void;
  onExportExcel: () => void;
  onExportDxf: () => void;
  onPushGridToMcp: () => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  gridResult,
  taluyResult,
  selectedNode,
  selectedCell,
  nodeOverrideCount,
  mergedPairCount,
  onUpdateNodeHTK,
  onResetNodeHTK,
  onResetAllOverrides,
  onClearMergedCells,
  onExportExcel,
  onExportDxf,
  onPushGridToMcp,
}) => {
  const [nodeInput, setNodeInput] = useState('');

  useEffect(() => {
    if (selectedNode) {
      setNodeInput(selectedNode.hTK.toFixed(2));
    }
  }, [selectedNode]);

  const fmt = (n: number) =>
    n.toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  const totalCut = gridResult.totalCutVolume + taluyResult.totalCutVolume;
  const totalFill = gridResult.totalFillVolume + taluyResult.totalFillVolume;
  const net = totalFill - totalCut;
  const maxVol = Math.max(totalCut, totalFill, 1);

  return (
    <aside className="flex h-full w-[276px] shrink-0 flex-col border-l border-[#263248] bg-[#141B29] overflow-y-auto">
      {/* Live Volume Summary Block */}
      <div className="border-b border-[#263248] p-4">
        <div className="text-xs font-semibold text-slate-200">Tổng hợp Khối lượng tức thời</div>
        <div className="mt-1 font-mono text-[11px] tabular-nums text-slate-400">
          Diện tích lô: {fmt(gridResult.totalLandArea)} m² · {gridResult.cells.filter((c) => c.active).length} ô tính
        </div>

        <div className="mt-3.5 space-y-2.5 text-xs">
          {/* Cut bar */}
          <div>
            <div className="flex justify-between font-mono tabular-nums">
              <span className="font-sans text-amber-300">Khối lượng Đào</span>
              <span className="font-semibold text-amber-300">{fmt(totalCut)} m³</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[#0B0F17]">
              <div
                className="h-full bg-amber-400"
                style={{ width: `${Math.min(100, (totalCut / maxVol) * 100)}%` }}
              />
            </div>
            <div className="mt-0.5 flex justify-between font-mono text-[10px] tabular-nums text-slate-500">
              <span>Lưới: {fmt(gridResult.totalCutVolume)}</span>
              <span>Taluy: {fmt(taluyResult.totalCutVolume)}</span>
            </div>
          </div>

          {/* Fill bar */}
          <div>
            <div className="flex justify-between font-mono tabular-nums">
              <span className="font-sans text-red-400">Khối lượng Đắp</span>
              <span className="font-semibold text-red-400">{fmt(totalFill)} m³</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[#0B0F17]">
              <div
                className="h-full bg-red-500"
                style={{ width: `${Math.min(100, (totalFill / maxVol) * 100)}%` }}
              />
            </div>
            <div className="mt-0.5 flex justify-between font-mono text-[10px] tabular-nums text-slate-500">
              <span>Lưới: {fmt(gridResult.totalFillVolume)}</span>
              <span>Taluy: {fmt(taluyResult.totalFillVolume)}</span>
            </div>
          </div>

          {/* Net Balance */}
          <div className="flex items-center justify-between border-t border-[#263248] pt-2.5">
            <span className="text-slate-400">Chênh lệch (Đắp − Đào)</span>
            <span
              className={`font-mono font-semibold tabular-nums ${
                Math.abs(net) < 300
                  ? 'text-emerald-400'
                  : net > 0
                  ? 'text-red-300'
                  : 'text-amber-300'
              }`}
            >
              {net >= 0 ? '+' : ''}
              {fmt(net)} m³
            </span>
          </div>
        </div>
      </div>

      {/* Selected Grid Node Editor (SNVN IV.2.3.2 GridNodeInfo) */}
      <div className="border-b border-[#263248] p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-200">
            Thuộc tính Đối tượng đang chọn
          </span>
        </div>

        {selectedNode ? (
          <div className="mt-3 space-y-2.5 text-xs">
            <div className="flex items-center justify-between font-mono text-[11px] text-sky-300">
              <span>Nút lưới (Hàng–Cột)</span>
              <span className="font-semibold">{selectedNode.id}</span>
            </div>

            <div className="grid grid-cols-2 gap-2 rounded-md border border-[#263248] bg-[#0B0F17] p-2.5 font-mono text-[11px] tabular-nums">
              <div>
                <div className="text-[10px] text-slate-500">Tọa độ X</div>
                <div className="text-slate-200">{selectedNode.x.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">Tọa độ Y</div>
                <div className="text-slate-200">{selectedNode.y.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-[10px] text-emerald-400">Cao độ TN (NE)</div>
                <div className="text-emerald-300">{selectedNode.hTN.toFixed(2)} m</div>
              </div>
              <div>
                <div className="text-[10px] text-amber-300">Chênh cao (D)</div>
                <div className={selectedNode.deltaH >= 0 ? 'text-red-300' : 'text-amber-300'}>
                  {selectedNode.deltaH >= 0 ? '+' : ''}
                  {selectedNode.deltaH.toFixed(2)} m
                </div>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-[11px] text-slate-400">
                Hiệu chỉnh Cao độ TK (DE — GridNodeInfo)
              </label>
              <div className="flex gap-1.5">
                <input
                  type="number"
                  step={0.05}
                  value={nodeInput}
                  onChange={(e) => setNodeInput(e.target.value)}
                  className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2.5 py-1.5 font-mono text-xs text-red-300 focus:border-sky-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => {
                    const v = parseFloat(nodeInput);
                    if (!Number.isNaN(v)) onUpdateNodeHTK(selectedNode.id, v);
                  }}
                  className="rounded-md bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500 whitespace-nowrap shrink-0"
                >
                  Lưu
                </button>
              </div>
            </div>

            {selectedNode.isCustomHTK && (
              <button
                type="button"
                onClick={() => onResetNodeHTK(selectedNode.id)}
                className="flex w-full items-center justify-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] py-1.5 text-[11px] text-slate-300 hover:text-white"
              >
                <RotateCcw className="h-3 w-3" />
                Khôi phục cao độ theo MHTK
              </button>
            )}
          </div>
        ) : selectedCell ? (
          <div className="mt-3 space-y-2 text-xs">
            <div className="flex items-center justify-between font-mono text-[11px] text-sky-300">
              <span>Ô lưới đang chọn</span>
              <span className="font-semibold">Ô {selectedCell.id}</span>
            </div>
            <div className="space-y-1.5 rounded-md border border-[#263248] bg-[#0B0F17] p-2.5 font-mono text-[11px] tabular-nums">
              <div className="flex justify-between">
                <span className="text-slate-400">Tổng diện tích:</span>
                <span className="text-slate-100">{selectedCell.totalArea.toFixed(2)} m²</span>
              </div>
              <div className="flex justify-between">
                <span className="text-amber-300">Diện tích đào:</span>
                <span className="text-amber-300">{selectedCell.cutArea.toFixed(2)} m²</span>
              </div>
              <div className="flex justify-between">
                <span className="text-amber-300">Thể tích đào:</span>
                <span className="text-amber-300">{selectedCell.cutVolume.toFixed(2)} m³</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-400">Diện tích đắp:</span>
                <span className="text-red-400">{selectedCell.fillArea.toFixed(2)} m²</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-400">Thể tích đắp:</span>
                <span className="text-red-400">{selectedCell.fillVolume.toFixed(2)} m³</span>
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-2.5 text-[11px] leading-relaxed text-slate-400">
            Chuyển sang công cụ <strong className="text-slate-200">Chọn / Sửa nút</strong> trên bản vẽ 2D và nhấn vào nút lưới để chỉnh trực tiếp cao độ thiết kế (CĐTK) hoặc xem chi tiết từng ô.
          </p>
        )}

        {(nodeOverrideCount > 0 || mergedPairCount > 0) && (
          <div className="mt-3 space-y-1.5 border-t border-[#263248] pt-3 text-[11px]">
            {nodeOverrideCount > 0 && (
              <div className="flex items-center justify-between text-slate-400">
                <span>Nút chỉnh tay: {nodeOverrideCount}</span>
                <button
                  type="button"
                  onClick={onResetAllOverrides}
                  className="text-sky-400 hover:underline"
                >
                  Đặt lại
                </button>
              </div>
            )}
            {mergedPairCount > 0 && (
              <div className="flex items-center justify-between text-slate-400">
                <span>Cặp ô đã gộp (DD_MC): {mergedPairCount}</span>
                <button
                  type="button"
                  onClick={onClearMergedCells}
                  className="flex items-center gap-1 text-red-400 hover:underline"
                >
                  <Trash2 className="h-3 w-3" />
                  Tách lại
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick Export & Sync Actions */}
      <div className="mt-auto space-y-2 p-4">
        <div className="text-[11px] font-semibold text-slate-400">Xuất hồ sơ &amp; Đồng bộ CAD</div>
        <button
          type="button"
          onClick={onPushGridToMcp}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-sky-600 px-3 py-2 text-xs font-semibold text-white hover:bg-sky-500"
        >
          <Send className="h-3.5 w-3.5" />
          Đẩy bản vẽ sang AutoCAD 2022
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onExportExcel}
            className="flex items-center justify-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-2.5 py-1.5 text-xs font-medium text-emerald-300 hover:border-emerald-500/40"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            Excel .xlsx
          </button>
          <button
            type="button"
            onClick={onExportDxf}
            className="flex items-center justify-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:border-sky-500/40"
          >
            <Download className="h-3.5 w-3.5" />
            Bản vẽ DXF
          </button>
        </div>
      </div>
    </aside>
  );
};
