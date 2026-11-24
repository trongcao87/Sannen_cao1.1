import React, { useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Compass,
  Eye,
  Grid3X3,
  Layers,
  Mountain,
  Plug,
  Scale,
  Sliders,
  Upload,
} from 'lucide-react';
import {
  ContourConfig,
  DesignSurfaceMode,
  DesignSurfaceSpec,
  GridConfig,
  LayerVisibility,
  ProjectPreset,
  TaluyConfig,
  TinSurface,
} from '../types/snvn';

interface WorkflowSidebarProps {
  presets: ProjectPreset[];
  activePresetId: string;
  onSelectPreset: (presetId: string) => void;
  onUploadExcel: (file: File) => void;
  onUploadDxf: (file: File) => void;
  onOpenMcpModal: () => void;
  mhtn: TinSurface;
  breaklineCount: number;
  designSpec: DesignSurfaceSpec;
  onDesignChange: (next: DesignSurfaceSpec) => void;
  onAutoBalance: () => void;
  gridConfig: GridConfig;
  onGridConfigChange: (next: GridConfig) => void;
  onAutoFitGrid: () => void;
  onQuickShiftHTK: (delta: number) => void;
  taluyConfig: TaluyConfig;
  onTaluyConfigChange: (next: TaluyConfig) => void;
  contourConfig: ContourConfig;
  onContourConfigChange: (next: ContourConfig) => void;
  layers: LayerVisibility;
  onToggleLayer: (key: keyof LayerVisibility) => void;
}

type StepKey = 'step1' | 'step2' | 'step3' | 'step4' | 'step5' | 'layers';

export const WorkflowSidebar: React.FC<WorkflowSidebarProps> = ({
  presets,
  activePresetId,
  onSelectPreset,
  onUploadExcel,
  onUploadDxf,
  onOpenMcpModal,
  mhtn,
  breaklineCount,
  designSpec,
  onDesignChange,
  onAutoBalance,
  gridConfig,
  onGridConfigChange,
  onAutoFitGrid,
  onQuickShiftHTK,
  taluyConfig,
  onTaluyConfigChange,
  contourConfig,
  onContourConfigChange,
  layers,
  onToggleLayer,
}) => {
  const [openStep, setOpenStep] = useState<StepKey>('step1');
  const excelInputRef = useRef<HTMLInputElement>(null);
  const dxfInputRef = useRef<HTMLInputElement>(null);

  const toggle = (key: StepKey) => {
    setOpenStep((prev) => (prev === key ? key : key));
  };

  const layerItems: { key: keyof LayerVisibility; label: string; color: string }[] = [
    { key: 'gridLines', label: 'Lưới ô vuông', color: '#94A3B8' },
    { key: 'nodeLabels', label: 'Cao độ nút lưới (4 góc)', color: '#4ADE80' },
    { key: 'cellVolumes', label: 'Vòng tròn KL Đào/Đắp', color: '#FACC15' },
    { key: 'zeroLine', label: 'Ranh giới Đào–Đắp (ΔH=0)', color: '#38BDF8' },
    { key: 'boundary', label: 'Biên lô & Vùng bỏ qua', color: '#60A5FA' },
    { key: 'taluy', label: 'Mặt bằng Taluy 2D', color: '#EF4444' },
    { key: 'contoursMhtn', label: 'Đường đồng mức TN', color: '#F5B971' },
    { key: 'contoursMhtk', label: 'Đường đồng mức TK', color: '#7DD3FC' },
    { key: 'breaklines', label: 'Đường đứt gãy 3D', color: '#D946EF' },
    { key: 'tinMhtn', label: 'Lưới tam giác TIN', color: '#22C55E' },
    { key: 'heatmap', label: 'Bản đồ nhiệt cao độ', color: '#34D399' },
    { key: 'axisTotals', label: 'Lập trục tổng (DD_LAPTRUC)', color: '#CBD5E1' },
    { key: 'crossSections', label: 'Tuyến mặt cắt ngang', color: '#38BDF8' },
    { key: 'points', label: 'Điểm đo khảo sát', color: '#94A3B8' },
  ];

  const SectionHeader: React.FC<{
    stepKey: StepKey;
    title: string;
    icon: React.ReactNode;
  }> = ({ stepKey, title, icon }) => {
    const isOpen = openStep === stepKey;
    return (
      <button
        type="button"
        onClick={() => toggle(stepKey)}
        className={`flex w-full items-center justify-between px-3.5 py-2.5 text-left text-xs font-semibold transition-colors ${
          isOpen
            ? 'bg-[#1C2538] text-sky-300'
            : 'text-slate-300 hover:bg-[#182132] hover:text-slate-100'
        }`}
      >
        <span className="flex items-center gap-2 truncate">
          {icon}
          <span className="truncate">{title}</span>
        </span>
        {isOpen ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-500" />
        )}
      </button>
    );
  };

  return (
    <aside className="flex h-full w-[280px] shrink-0 flex-col border-r border-[#263248] bg-[#141B29] overflow-y-auto">
      {/* Hidden File Inputs */}
      <input
        ref={excelInputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUploadExcel(f);
          e.target.value = '';
        }}
      />
      <input
        ref={dxfInputRef}
        type="file"
        accept=".dxf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUploadDxf(f);
          e.target.value = '';
        }}
      />

      <div className="divide-y divide-[#263248]">
        {/* STEP 1: Survey Data & MHTN TIN */}
        <div>
          <SectionHeader
            stepKey="step1"
            title="1. Dữ liệu & Mô hình TIN (MHTN)"
            icon={<Mountain className="h-3.5 w-3.5 shrink-0" />}
          />
          {openStep === 'step1' && (
            <div className="space-y-3 bg-[#101725] p-3.5 text-xs">
              <div>
                <label className="mb-1 block text-[11px] text-slate-400">
                  Dự án trắc địa mẫu (có đường đứt gãy)
                </label>
                <select
                  value={activePresetId}
                  onChange={(e) => onSelectPreset(e.target.value)}
                  className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2.5 py-1.5 text-xs text-slate-100 focus:border-sky-500 focus:outline-none"
                >
                  {presets.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => excelInputRef.current?.click()}
                  className="flex items-center justify-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-2 py-1.5 text-[11px] font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap"
                >
                  <Upload className="h-3 w-3 text-emerald-400" />
                  Nhập Excel/CSV
                </button>
                <button
                  type="button"
                  onClick={() => dxfInputRef.current?.click()}
                  className="flex items-center justify-center gap-1.5 rounded-md border border-[#263248] bg-[#1C2538] px-2 py-1.5 text-[11px] font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap"
                >
                  <Upload className="h-3 w-3 text-sky-400" />
                  Nhập DXF
                </button>
              </div>

              <button
                type="button"
                onClick={onOpenMcpModal}
                className="flex w-full items-center justify-center gap-1.5 rounded-md border border-sky-500/40 bg-sky-500/10 px-2.5 py-1.5 text-[11px] font-medium text-sky-300 hover:bg-sky-500/20"
              >
                <Plug className="h-3.5 w-3.5" />
                Đọc DWG từ AutoCAD 2022 (MCP)
              </button>

              <div className="rounded-md border border-[#263248] bg-[#0B0F17] p-2.5 font-mono text-[11px] tabular-nums text-slate-300 space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-400">Đỉnh TIN (CDT):</span>
                  <span>{mhtn.vertices.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Số tam giác Delaunay:</span>
                  <span>{mhtn.triangles.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Đường đứt gãy (3D):</span>
                  <span className="text-fuchsia-400">{breaklineCount} tuyến</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Dải cao độ TN:</span>
                  <span className="text-emerald-400">
                    {mhtn.bounds.minZ.toFixed(2)} – {mhtn.bounds.maxZ.toFixed(2)}m
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* STEP 2: Design Surface (MHTK) & Optimization */}
        <div>
          <SectionHeader
            stepKey="step2"
            title="2. Mô hình Thiết kế (MHTK)"
            icon={<Compass className="h-3.5 w-3.5 shrink-0" />}
          />
          {openStep === 'step2' && (
            <div className="space-y-3 bg-[#101725] p-3.5 text-xs">
              <div>
                <label className="mb-1 block text-[11px] text-slate-400">
                  Phương pháp tạo MHTK (SNVN III.4)
                </label>
                <select
                  value={designSpec.mode}
                  onChange={(e) =>
                    onDesignChange({ ...designSpec, mode: e.target.value as DesignSurfaceMode })
                  }
                  className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2.5 py-1.5 text-xs text-slate-100"
                >
                  <option value="flat">Cao độ phẳng cố định</option>
                  <option value="single_slope">Mặt dốc đơn giản (Offset 3D)</option>
                  <option value="ridge_slope">Thiết kế hướng dốc 2 mái</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">CĐ khống chế (m)</label>
                  <input
                    type="number"
                    step={0.1}
                    value={designSpec.baseElevation}
                    onChange={(e) =>
                      onDesignChange({
                        ...designSpec,
                        baseElevation: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Dịch chỉnh ΔZ (m)</label>
                  <input
                    type="number"
                    step={0.1}
                    value={designSpec.elevationShift}
                    onChange={(e) =>
                      onDesignChange({
                        ...designSpec,
                        elevationShift: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-sky-300"
                  />
                </div>
              </div>

              {designSpec.mode !== 'flat' && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="mb-1 block text-[11px] text-slate-400">Độ dốc dọc (%)</label>
                    <input
                      type="number"
                      step={0.1}
                      value={designSpec.longitudinalSlopePct}
                      onChange={(e) =>
                        onDesignChange({
                          ...designSpec,
                          longitudinalSlopePct: parseFloat(e.target.value) || 0,
                        })
                      }
                      className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-slate-400">Góc hướng (°)</label>
                    <input
                      type="number"
                      step={5}
                      value={designSpec.slopeAngleDeg}
                      onChange={(e) =>
                        onDesignChange({
                          ...designSpec,
                          slopeAngleDeg: parseFloat(e.target.value) || 0,
                        })
                      }
                      className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                    />
                  </div>
                </div>
              )}

              {designSpec.mode === 'ridge_slope' && (
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Độ dốc ngang hai mái (%)</label>
                  <input
                    type="number"
                    step={0.1}
                    value={designSpec.transverseSlopePct}
                    onChange={(e) =>
                      onDesignChange({
                        ...designSpec,
                        transverseSlopePct: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
              )}

              {/* Quick Nâng/Hạ CĐTK (DD_NANGCDTK) */}
              <div>
                <div className="mb-1 text-[11px] text-slate-400">Nâng / Hạ nhanh CĐTK (DD_NANGCDTK)</div>
                <div className="grid grid-cols-4 gap-1 font-mono text-[11px]">
                  {[-0.5, -0.1, 0.1, 0.5].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => onQuickShiftHTK(d)}
                      className="rounded border border-[#263248] bg-[#1C2538] py-1 text-slate-200 hover:border-sky-500/50"
                    >
                      {d > 0 ? `+${d}` : d}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                onClick={onAutoBalance}
                className="flex w-full items-center justify-center gap-1.5 rounded-md bg-amber-500/15 border border-amber-500/40 px-2.5 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/25"
              >
                <Scale className="h-3.5 w-3.5" />
                Tự động cân bằng Đào – Đắp
              </button>
            </div>
          )}
        </div>

        {/* STEP 3: Rectangular Grid Setup (DD_TAOLUOI) */}
        <div>
          <SectionHeader
            stepKey="step3"
            title="3. Lưới ô vuông (DD_TAOLUOI)"
            icon={<Grid3X3 className="h-3.5 w-3.5 shrink-0" />}
          />
          {openStep === 'step3' && (
            <div className="space-y-3 bg-[#101725] p-3.5 text-xs">
              <div>
                <label className="mb-1 block text-[11px] text-slate-400">
                  Chiều rộng các cột (vd: 12x20 hoặc 4x20,4x15,4x20)
                </label>
                <input
                  type="text"
                  value={gridConfig.colSpec}
                  onChange={(e) => onGridConfigChange({ ...gridConfig, colSpec: e.target.value })}
                  className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2.5 py-1.5 font-mono text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="mb-1 block text-[11px] text-slate-400">
                  Chiều cao các hàng (vd: 9x20 hoặc 5x20,4x15)
                </label>
                <input
                  type="text"
                  value={gridConfig.rowSpec}
                  onChange={(e) => onGridConfigChange({ ...gridConfig, rowSpec: e.target.value })}
                  className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2.5 py-1.5 font-mono text-xs text-slate-100"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Gốc X₀ (m)</label>
                  <input
                    type="number"
                    step={2}
                    value={gridConfig.originX}
                    onChange={(e) =>
                      onGridConfigChange({
                        ...gridConfig,
                        originX: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Gốc Y₀ (m)</label>
                  <input
                    type="number"
                    step={2}
                    value={gridConfig.originY}
                    onChange={(e) =>
                      onGridConfigChange({
                        ...gridConfig,
                        originY: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Góc nghiêng (°)</label>
                  <input
                    type="number"
                    step={5}
                    value={gridConfig.angleDeg}
                    onChange={(e) =>
                      onGridConfigChange({
                        ...gridConfig,
                        angleDeg: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Hệ số đầm chặt K</label>
                  <input
                    type="number"
                    step={0.02}
                    min={1}
                    max={1.4}
                    value={gridConfig.compactionFactor}
                    onChange={(e) =>
                      onGridConfigChange({
                        ...gridConfig,
                        compactionFactor: Math.max(1, parseFloat(e.target.value) || 1.08),
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={onAutoFitGrid}
                className="w-full rounded-md border border-sky-500/40 bg-sky-500/10 py-1.5 text-xs font-medium text-sky-300 hover:bg-sky-500/20"
              >
                Tự động căn lưới vừa biên đào đắp
              </button>
            </div>
          )}
        </div>

        {/* STEP 4: Taluy Embankment Design (Chapter V) */}
        <div>
          <SectionHeader
            stepKey="step4"
            title="4. Thiết kế Taluy (Chương V)"
            icon={<Sliders className="h-3.5 w-3.5 shrink-0" />}
          />
          {openStep === 'step4' && (
            <div className="space-y-3 bg-[#101725] p-3.5 text-xs">
              <label className="flex items-center justify-between text-slate-200">
                <span>Bật tính toán &amp; vẽ Taluy biên</span>
                <input
                  type="checkbox"
                  checked={taluyConfig.enabled}
                  onChange={(e) =>
                    onTaluyConfigChange({ ...taluyConfig, enabled: e.target.checked })
                  }
                  className="h-4 w-4 accent-sky-500"
                />
              </label>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Mái đào 1:n</label>
                  <input
                    type="number"
                    step={0.25}
                    min={0.5}
                    value={taluyConfig.cutSlopeN}
                    onChange={(e) =>
                      onTaluyConfigChange({
                        ...taluyConfig,
                        cutSlopeN: Math.max(0.25, parseFloat(e.target.value) || 1),
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-amber-300"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Mái đắp 1:n</label>
                  <input
                    type="number"
                    step={0.25}
                    min={0.5}
                    value={taluyConfig.fillSlopeN}
                    onChange={(e) =>
                      onTaluyConfigChange({
                        ...taluyConfig,
                        fillSlopeN: Math.max(0.25, parseFloat(e.target.value) || 1.5),
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-red-300"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-1.5">
                <div>
                  <label className="mb-1 block text-[10px] text-slate-400">H giật cơ (m)</label>
                  <input
                    type="number"
                    step={1}
                    value={taluyConfig.bermHeight}
                    onChange={(e) =>
                      onTaluyConfigChange({
                        ...taluyConfig,
                        bermHeight: parseFloat(e.target.value) || 6,
                      })
                    }
                    className="w-full rounded border border-[#263248] bg-[#0B0F17] px-1.5 py-1 font-mono text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] text-slate-400">B giật cơ (m)</label>
                  <input
                    type="number"
                    step={0.5}
                    value={taluyConfig.bermWidth}
                    onChange={(e) =>
                      onTaluyConfigChange({
                        ...taluyConfig,
                        bermWidth: parseFloat(e.target.value) || 2,
                      })
                    }
                    className="w-full rounded border border-[#263248] bg-[#0B0F17] px-1.5 py-1 font-mono text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[10px] text-slate-400">Bước chia (m)</label>
                  <input
                    type="number"
                    step={1}
                    min={2}
                    value={taluyConfig.stepLength}
                    onChange={(e) =>
                      onTaluyConfigChange({
                        ...taluyConfig,
                        stepLength: Math.max(2, parseFloat(e.target.value) || 5),
                      })
                    }
                    className="w-full rounded border border-[#263248] bg-[#0B0F17] px-1.5 py-1 font-mono text-xs text-slate-200"
                  />
                </div>
              </div>

              <label className="flex items-center justify-between text-slate-300">
                <span>Có tường chắn đất (mái đắp)</span>
                <input
                  type="checkbox"
                  checked={taluyConfig.retainingWall}
                  onChange={(e) =>
                    onTaluyConfigChange({ ...taluyConfig, retainingWall: e.target.checked })
                  }
                  className="h-4 w-4 accent-sky-500"
                />
              </label>
            </div>
          )}
        </div>

        {/* STEP 5: Automatic Contours */}
        <div>
          <SectionHeader
            stepKey="step5"
            title="5. Đường đồng mức tự động"
            icon={<Layers className="h-3.5 w-3.5 shrink-0" />}
          />
          {openStep === 'step5' && (
            <div className="space-y-3 bg-[#101725] p-3.5 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Đồng mức con (m)</label>
                  <select
                    value={contourConfig.minorInterval}
                    onChange={(e) => {
                      const minor = parseFloat(e.target.value);
                      onContourConfigChange({
                        ...contourConfig,
                        minorInterval: minor,
                        majorInterval: minor * 5,
                      });
                    }}
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  >
                    <option value={0.25}>0.25 m</option>
                    <option value={0.5}>0.50 m</option>
                    <option value={1.0}>1.00 m</option>
                    <option value={2.0}>2.00 m</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-[11px] text-slate-400">Đồng mức cái (m)</label>
                  <input
                    type="number"
                    step={0.5}
                    value={contourConfig.majorInterval}
                    onChange={(e) =>
                      onContourConfigChange({
                        ...contourConfig,
                        majorInterval: Math.max(
                          contourConfig.minorInterval,
                          parseFloat(e.target.value) || 2.5
                        ),
                      })
                    }
                    className="w-full rounded-md border border-[#263248] bg-[#0B0F17] px-2 py-1 font-mono text-xs text-slate-100"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-[11px] text-slate-400">
                  Mức độ làm mượt đường cong (Chaikin)
                </label>
                <input
                  type="range"
                  min={0}
                  max={3}
                  step={1}
                  value={contourConfig.smoothIterations}
                  onChange={(e) =>
                    onContourConfigChange({
                      ...contourConfig,
                      smoothIterations: parseInt(e.target.value, 10),
                    })
                  }
                  className="w-full accent-sky-400"
                />
              </div>
            </div>
          )}
        </div>

        {/* STEP 6: Layer Visibility Manager */}
        <div>
          <SectionHeader
            stepKey="layers"
            title="6. Quản lý Lớp bản vẽ (Layers)"
            icon={<Eye className="h-3.5 w-3.5 shrink-0" />}
          />
          {openStep === 'layers' && (
            <div className="space-y-1.5 bg-[#101725] p-3 text-xs">
              {layerItems.map((item) => (
                <label
                  key={item.key}
                  className="flex cursor-pointer items-center justify-between rounded px-2 py-1 hover:bg-[#1C2538]"
                >
                  <span className="flex items-center gap-2 text-slate-300">
                    <span
                      className="inline-block h-2.5 w-2.5 shrink-0 rounded-xs"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="truncate text-[11px]">{item.label}</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={layers[item.key]}
                    onChange={() => onToggleLayer(item.key)}
                    className="h-3.5 w-3.5 accent-sky-500"
                  />
                </label>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
