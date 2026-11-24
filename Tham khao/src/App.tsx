import React, { useMemo, useState } from 'react';
import { Plug } from 'lucide-react';
import {
  ActiveWorkspaceTab,
  Breakline,
  CanvasToolMode,
  ContourConfig,
  CrossSectionDef,
  DesignSurfaceSpec,
  GridConfig,
  LayerVisibility,
  McpLogEntry,
  Point2D,
  PolygonZone,
  SurveyPoint,
  TaluyConfig,
} from './types/snvn';
import { PROJECT_PRESETS } from './engine/presets';
import { buildConstrainedTin, buildDesignTin } from './engine/tin';
import {
  autoFitGridToBoundary,
  computeSnvnGrid,
  optimizeBalanceElevationShift,
} from './engine/grid';
import { computeSnvnTaluy } from './engine/taluy';
import { generateTinContours } from './engine/contours';
import { computeCrossSection } from './engine/crossSection';
import {
  exportAutoCadScript,
  exportSnvnDxf,
  exportSnvnExcelWorkbook,
  parseSurveyDxf,
  parseSurveyExcelOrCsv,
} from './engine/ioExport';
import { invokeMcpTool } from './mcp/mcpClient';
import { CadCanvas2D } from './components/CadCanvas2D';
import { Terrain3DView } from './components/Terrain3DView';
import { CrossSectionView } from './components/CrossSectionView';
import { ReportsChartsView } from './components/ReportsChartsView';
import { WorkflowSidebar } from './components/WorkflowSidebar';
import { InspectorPanel } from './components/InspectorPanel';
import { McpBridgeModal } from './components/McpBridgeModal';

const INITIAL_PRESET = PROJECT_PRESETS[0];

const DEFAULT_TALUY: TaluyConfig = {
  enabled: true,
  cutSlopeN: 1.0,
  fillSlopeN: 1.5,
  bermHeight: 6.0,
  bermWidth: 2.0,
  bermSlopePct: 4.0,
  stepLength: 5.0,
  tickSpacing: 6.0,
  shortTicksPerLong: 1,
  retainingWall: false,
  retainingWallHeight: 2.0,
};

const DEFAULT_CONTOUR: ContourConfig = {
  minorInterval: 0.5,
  majorInterval: 2.5,
  smoothIterations: 1,
  showLabels: true,
  targetSurface: 'both',
};

const DEFAULT_LAYERS: LayerVisibility = {
  points: false,
  tinMhtn: true,
  breaklines: true,
  contoursMhtn: true,
  contoursMhtk: false,
  boundary: true,
  gridLines: true,
  nodeLabels: true,
  cellVolumes: true,
  zeroLine: true,
  taluy: true,
  axisTotals: false,
  crossSections: true,
  heatmap: true,
};

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveWorkspaceTab>('cad2d');
  const [activePresetId, setActivePresetId] = useState<string>(INITIAL_PRESET.id);
  const [projectName, setProjectName] = useState<string>(INITIAL_PRESET.name);

  // Core Survey & Terrain State
  const [points, setPoints] = useState<SurveyPoint[]>(INITIAL_PRESET.points);
  const [breaklines, setBreaklines] = useState<Breakline[]>(INITIAL_PRESET.breaklines);
  const [boundary, setBoundary] = useState<PolygonZone>(INITIAL_PRESET.boundary);
  const [exclusions, setExclusions] = useState<PolygonZone[]>(INITIAL_PRESET.exclusions);

  // Design, Grid, Taluy, Contour, Cross-Sections State
  const [designSpec, setDesignSpec] = useState<DesignSurfaceSpec>(INITIAL_PRESET.defaultDesign);
  const [gridConfig, setGridConfig] = useState<GridConfig>(INITIAL_PRESET.defaultGrid);
  const [nodeOverrides, setNodeOverrides] = useState<Record<string, number>>({});
  const [mergedPairs, setMergedPairs] = useState<[string, string][]>([]);
  const [taluyConfig, setTaluyConfig] = useState<TaluyConfig>(DEFAULT_TALUY);
  const [contourConfig, setContourConfig] = useState<ContourConfig>(DEFAULT_CONTOUR);
  const [sections, setSections] = useState<CrossSectionDef[]>(INITIAL_PRESET.defaultSections);
  const [activeSectionId, setActiveSectionId] = useState<string>(
    INITIAL_PRESET.defaultSections[0].id
  );
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);

  // Interactive Canvas Selection State
  const [toolMode, setToolMode] = useState<CanvasToolMode>('pan');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null);
  const [pendingMergeCellId, setPendingMergeCellId] = useState<string | null>(null);

  // AutoCAD 2022 MCP Bridge State
  const [mcpModalOpen, setMcpModalOpen] = useState(false);
  const [mcpEndpoint, setMcpEndpoint] = useState('http://127.0.0.1:8765/mcp');
  const [mcpUseSandbox, setMcpUseSandbox] = useState(true);
  const [mcpConnectionInfo, setMcpConnectionInfo] = useState(
    'Chế độ Mô phỏng (Sandbox) đang bật — Tắt Sandbox sau khi chạy cầu nối Python ActiveX hoặc C# ObjectARX trên Windows.'
  );
  const [mcpLogs, setMcpLogs] = useState<McpLogEntry[]>([]);

  // Transient feedback toast
  const [toast, setToast] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => {
      setToast((curr) => (curr === msg ? null : curr));
    }, 3600);
  };

  // --- Computed Engineering Pipeline ---
  const mhtn = useMemo(
    () => buildConstrainedTin('MHTN', points, breaklines),
    [points, breaklines]
  );

  const mhtk = useMemo(
    () => buildDesignTin(designSpec, mhtn.bounds, null),
    [designSpec, mhtn.bounds]
  );

  const gridResult = useMemo(
    () =>
      computeSnvnGrid(
        mhtn,
        designSpec,
        gridConfig,
        boundary,
        exclusions,
        nodeOverrides,
        mergedPairs,
        null
      ),
    [mhtn, designSpec, gridConfig, boundary, exclusions, nodeOverrides, mergedPairs]
  );

  const taluyResult = useMemo(
    () => computeSnvnTaluy(mhtn, designSpec, boundary, taluyConfig, null),
    [mhtn, designSpec, boundary, taluyConfig]
  );

  const contours = useMemo(() => {
    const list = generateTinContours(mhtn, 'mhtn', contourConfig);
    if (layers.contoursMhtk) {
      list.push(...generateTinContours(mhtk, 'mhtk', contourConfig));
    }
    return list;
  }, [mhtn, mhtk, contourConfig, layers.contoursMhtk]);

  const activeSectionDef = useMemo(
    () => sections.find((s) => s.id === activeSectionId) ?? sections[0] ?? null,
    [sections, activeSectionId]
  );

  const activeSectionResult = useMemo(
    () =>
      activeSectionDef
        ? computeCrossSection(activeSectionDef, mhtn, designSpec, breaklines, null)
        : null,
    [activeSectionDef, mhtn, designSpec, breaklines]
  );

  // Locate selected node / cell for Inspector
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    for (const row of gridResult.nodes) {
      for (const n of row) {
        if (n.id === selectedNodeId) return n;
      }
    }
    return null;
  }, [gridResult.nodes, selectedNodeId]);

  const selectedCell = useMemo(
    () => gridResult.cells.find((c) => c.id === selectedCellId) ?? null,
    [gridResult.cells, selectedCellId]
  );

  // --- Event Handlers ---
  const handleSelectPreset = (presetId: string) => {
    const preset = PROJECT_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    setActivePresetId(preset.id);
    setProjectName(preset.name);
    setPoints(preset.points);
    setBreaklines(preset.breaklines);
    setBoundary(preset.boundary);
    setExclusions(preset.exclusions);
    setDesignSpec(preset.defaultDesign);
    setGridConfig(preset.defaultGrid);
    setSections(preset.defaultSections);
    setActiveSectionId(preset.defaultSections[0].id);
    setNodeOverrides({});
    setMergedPairs([]);
    setSelectedNodeId(null);
    setSelectedCellId(null);
    showToast(`Đã nạp dự án mẫu: ${preset.name}`);
  };

  const applyImportedSurvey = (
    name: string,
    importedPts: SurveyPoint[],
    importedBls: Breakline[],
    importedBoundary?: Point2D[]
  ) => {
    if (importedPts.length < 3) {
      showToast('Tệp không đủ tối thiểu 3 điểm tọa độ X, Y, Z để dựng bề mặt TIN.');
      return;
    }
    setProjectName(name);
    setPoints(importedPts);
    setBreaklines(importedBls);

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity,
      sumZ = 0;
    for (const p of importedPts) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
      sumZ += p.z;
    }
    const avgZ = Number((sumZ / importedPts.length).toFixed(2));
    const padX = (maxX - minX) * 0.08;
    const padY = (maxY - minY) * 0.08;

    const nextBoundaryVerts: Point2D[] =
      importedBoundary && importedBoundary.length >= 3
        ? importedBoundary
        : [
            { x: minX + padX, y: minY + padY },
            { x: maxX - padX, y: minY + padY },
            { x: maxX - padX, y: maxY - padY },
            { x: minX + padX, y: maxY - padY },
          ];

    setBoundary({
      id: 'BND-IMP',
      name: 'Biên đào đắp nhập mới',
      type: 'boundary',
      vertices: nextBoundaryVerts,
    });
    setExclusions([]);
    setDesignSpec({
      mode: 'flat',
      baseElevation: avgZ,
      refPoint: { x: (minX + maxX) / 2, y: (minY + maxY) / 2 },
      slopeAngleDeg: 0,
      longitudinalSlopePct: 0.5,
      transverseSlopePct: 0.5,
      elevationShift: 0,
    });

    const fit = autoFitGridToBoundary(nextBoundaryVerts, 20, 20, 0);
    setGridConfig((prev) => ({
      ...prev,
      originX: fit.originX,
      originY: fit.originY,
      colSpec: fit.colSpec,
      rowSpec: fit.rowSpec,
      angleDeg: 0,
    }));

    const midY = (minY + maxY) / 2;
    const newSec: CrossSectionDef = {
      id: `SEC-IMP-${Date.now()}`,
      name: 'MC 1-1 (Tự động)',
      start: { x: minX + padX * 0.5, y: midY },
      end: { x: maxX - padX * 0.5, y: midY },
      horizontalScale: 500,
      verticalScale: 100,
    };
    setSections([newSec]);
    setActiveSectionId(newSec.id);
    setNodeOverrides({});
    setMergedPairs([]);
    showToast(
      `Đã nhập ${importedPts.length} điểm đo và ${importedBls.length} đường đứt gãy từ ${name}.`
    );
  };

  const handleUploadExcel = async (file: File) => {
    try {
      const parsed = await parseSurveyExcelOrCsv(file);
      applyImportedSurvey(file.name, parsed.points, parsed.breaklines);
    } catch {
      showToast('Không đọc được tệp Excel/CSV. Kiểm tra các cột X, Y, Z.');
    }
  };

  const handleUploadDxf = async (file: File) => {
    try {
      const parsed = await parseSurveyDxf(file);
      applyImportedSurvey(file.name, parsed.points, parsed.breaklines, parsed.boundary);
    } catch {
      showToast('Không đọc được tệp DXF. Hãy đảm bảo tệp là ASCII DXF.');
    }
  };

  const handleAutoBalance = () => {
    const res = optimizeBalanceElevationShift(
      mhtn,
      designSpec,
      gridConfig,
      boundary,
      exclusions,
      null
    );
    setDesignSpec((prev) => ({ ...prev, elevationShift: res.optimalShift }));
    setNodeOverrides({});
    showToast(
      `Đã tối ưu cân bằng đào–đắp: dịch chỉnh ΔZ = ${res.optimalShift >= 0 ? '+' : ''}${res.optimalShift.toFixed(2)}m`
    );
  };

  const handleAutoFitGrid = () => {
    const fit = autoFitGridToBoundary(boundary.vertices, 20, 20, gridConfig.angleDeg);
    setGridConfig((prev) => ({
      ...prev,
      originX: fit.originX,
      originY: fit.originY,
      colSpec: fit.colSpec,
      rowSpec: fit.rowSpec,
    }));
    setNodeOverrides({});
    setMergedPairs([]);
    showToast(`Đã căn lưới vừa biên đào đắp (${fit.width}m × ${fit.height}m).`);
  };

  const handleMergeCellClick = (cellId: string) => {
    if (!pendingMergeCellId) {
      setPendingMergeCellId(cellId);
      setSelectedCellId(cellId);
      return;
    }
    if (pendingMergeCellId === cellId) {
      setPendingMergeCellId(null);
      return;
    }
    const cA = gridResult.cells.find((c) => c.id === pendingMergeCellId);
    const cB = gridResult.cells.find((c) => c.id === cellId);
    if (!cA || !cB) {
      setPendingMergeCellId(null);
      return;
    }
    const isAdj = Math.abs(cA.row - cB.row) + Math.abs(cA.col - cB.col) === 1;
    const samePureType =
      (cA.fillArea > 0 && cA.cutArea < 0.05 && cB.fillArea > 0 && cB.cutArea < 0.05) ||
      (cA.cutArea > 0 && cA.fillArea < 0.05 && cB.cutArea > 0 && cB.fillArea < 0.05);

    if (!isAdj) {
      showToast('Lệnh Cộng ô (DD_MC) yêu cầu 2 ô phải nằm liền kề nhau.');
      setPendingMergeCellId(null);
      return;
    }
    if (!samePureType) {
      showToast('Chỉ có thể cộng gộp 2 ô thuần cùng loại (cùng Đào hoặc cùng Đắp).');
      setPendingMergeCellId(null);
      return;
    }
    setMergedPairs((prev) => [...prev, [pendingMergeCellId, cellId]]);
    setPendingMergeCellId(null);
    showToast(`Đã cộng gộp ô ${cA.id} và ô ${cB.id} (DD_MC).`);
  };

  const handleCreateSection = (start: Point2D, end: Point2D) => {
    const idx = sections.length + 1;
    const newSec: CrossSectionDef = {
      id: `SEC-${Date.now()}`,
      name: `MC ${idx}-${idx}`,
      start,
      end,
      horizontalScale: 500,
      verticalScale: 100,
    };
    setSections((prev) => [...prev, newSec]);
    setActiveSectionId(newSec.id);
    setToolMode('pan');
    setActiveTab('section');
    showToast(`Đã tạo mặt cắt ngang ${newSec.name} chuẩn TCVN.`);
  };

  // --- AutoCAD 2022 MCP Tool Dispatcher ---
  const handleRunMcpTool = async (toolName: string) => {
    const activeNodes = gridResult.nodes
      .flat()
      .filter((n) => n.insideBoundary)
      .map((n) => ({ id: n.id, x: n.x, y: n.y, hTN: n.hTN, hTK: n.hTK, deltaH: n.deltaH }));

    const activeCells = gridResult.cells
      .filter((c) => c.active)
      .map((c) => ({ id: c.id, corners: c.corners, subPolygons: c.subPolygons }));

    const toolArgsMap: Record<string, Record<string, unknown>> = {
      autocad_ping: {},
      autocad_read_survey_entities: {
        entityTypes: ['POINT', 'BLOCK', 'TEXT', 'LINE', 'POLYLINE2D', 'POLYLINE3D'],
      },
      autocad_read_boundaries: {
        boundaryLayer: 'SNVN_BIEN',
        exclusionLayer: 'SNVN_VUNG_BOQUA',
      },
      autocad_draw_grid_results: {
        gridName: gridConfig.name,
        nodes: activeNodes,
        cells: activeCells,
        zeroLines: gridResult.zeroLines,
      },
      autocad_draw_contours_taluy: {
        contours: contours.map((c) => ({
          elevation: c.elevation,
          isMajor: c.isMajor,
          points: c.points,
        })),
        taluyTicks: taluyResult.ticks2D,
      },
      autocad_draw_cross_section: activeSectionResult
        ? {
            name: activeSectionResult.def.name,
            datumElevation: activeSectionResult.datumElevation,
            verticalExaggeration:
              activeSectionResult.def.horizontalScale / activeSectionResult.def.verticalScale,
            stations: activeSectionResult.stations,
          }
        : {},
      autocad_insert_snvn_tables: {
        title: `BẢNG TỔNG HỢP KHỐI LƯỢNG SAN NỀN — ${projectName}`,
        rows: [
          { label: 'Diện tích khu đất', unit: 'm²', value: gridResult.totalLandArea },
          { label: 'Diện tích đào', unit: 'm²', value: gridResult.totalCutArea },
          { label: 'Diện tích đắp', unit: 'm²', value: gridResult.totalFillArea },
          { label: 'Khối lượng đào lưới', unit: 'm³', value: gridResult.totalCutVolume },
          { label: 'Khối lượng đắp lưới', unit: 'm³', value: gridResult.totalFillVolume },
          { label: 'Khối lượng đào Taluy', unit: 'm³', value: taluyResult.totalCutVolume },
          { label: 'Khối lượng đắp Taluy', unit: 'm³', value: taluyResult.totalFillVolume },
        ],
      },
    };

    const summaryMap: Record<string, string> = {
      autocad_ping: 'Đã kết nối AutoCAD 2022 (24.1s) · DWG đang mở sẵn sàng',
      autocad_read_survey_entities: `Đã trích xuất ${points.length} điểm trắc địa và ${breaklines.length} đường đứt gãy từ ModelSpace`,
      autocad_read_boundaries: `Đã nạp ranh giới đào đắp (${boundary.vertices.length} đỉnh) & ${exclusions.length} vùng bỏ qua`,
      autocad_draw_grid_results: `Đã vẽ ${activeCells.length} ô lưới, ${activeNodes.length} nút 4 góc và ${gridResult.zeroLines.length} đoạn ranh giới 0`,
      autocad_draw_contours_taluy: `Đã ghi ${contours.length} đường đồng mức và ${taluyResult.ticks2D.length} vạch Taluy 2D`,
      autocad_draw_cross_section: `Đã vẽ mặt cắt ngang ${activeSectionDef?.name ?? ''} chuẩn TCVN lên ModelSpace`,
      autocad_insert_snvn_tables: 'Đã chèn bảng AcDbTable khối lượng chuẩn SNVN VI.1.3',
    };

    const resp = await invokeMcpTool(
      mcpEndpoint,
      toolName,
      toolArgsMap[toolName] ?? {},
      {
        useSandbox: mcpUseSandbox,
        summaryLabel: summaryMap[toolName] ?? toolName,
        sandboxHandler: () => ({
          engine: 'Local Sandbox Emulator (AutoCAD 2022 MCP Protocol)',
          acadVersion: '24.1s (AutoCAD 2022)',
          drawingName: `${projectName.replace(/\s+/g, '_')}.dwg`,
          status: summaryMap[toolName] ?? 'OK',
        }),
      }
    );

    setMcpLogs((prev) => [resp.logEntry, ...prev].slice(0, 40));

    if (resp.ok) {
      if (toolName === 'autocad_ping' && resp.result) {
        const r = resp.result as Record<string, unknown>;
        setMcpConnectionInfo(
          `Đã kết nối: ${String(r.engine ?? 'MCP')} · ${String(r.drawingName ?? 'AutoCAD 2022')}`
        );
      }
      if (
        toolName === 'autocad_read_survey_entities' &&
        resp.mode === 'live' &&
        resp.result
      ) {
        const r = resp.result as { points?: SurveyPoint[]; breaklines?: Breakline[] };
        if (Array.isArray(r.points) && r.points.length >= 3) {
          applyImportedSurvey('AutoCAD 2022 Live DWG', r.points, r.breaklines ?? []);
        }
      }
      showToast(resp.logEntry.summary);
    } else {
      showToast(resp.error ?? 'Lỗi kết nối cầu nối AutoCAD 2022 MCP');
    }
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0B0F17] text-[#E6EDF7]">
      {/* Strict 3-Zone Top Bar Contract (1 single row, gap-8, whitespace-nowrap) */}
      <header className="flex h-13 shrink-0 items-center justify-between gap-8 border-b border-[#263248] bg-[#111827] px-5">
        {/* Zone 1: Single text element wordmark */}
        <span className="text-base font-bold tracking-tight text-slate-100 whitespace-nowrap shrink-0">
          SNVN Studio
        </span>

        {/* Zone 2: 4 Clean single-line navigation links */}
        <nav className="flex items-center gap-7 text-xs font-medium">
          {[
            { id: 'cad2d', label: 'Bản vẽ 2D' },
            { id: 'view3d', label: 'Mô hình 3D' },
            { id: 'section', label: 'Mặt cắt TCVN' },
            { id: 'reports', label: 'Báo cáo & Biểu đồ' },
          ].map((nav) => {
            const active = activeTab === nav.id;
            return (
              <button
                key={nav.id}
                type="button"
                onClick={() => setActiveTab(nav.id as ActiveWorkspaceTab)}
                className={`relative py-3.5 transition-colors whitespace-nowrap shrink-0 ${
                  active ? 'text-sky-400' : 'text-slate-400 hover:text-slate-100'
                }`}
              >
                {nav.label}
                {active && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-sky-400" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Zone 3: 1 Primary Action Button */}
        <div className="flex items-center shrink-0">
          <button
            type="button"
            onClick={() => setMcpModalOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-sky-500 whitespace-nowrap shrink-0"
          >
            <Plug className="h-3.5 w-3.5" />
            Cầu nối AutoCAD MCP
          </button>
        </div>
      </header>

      {/* Main Engineering Workspace */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Left 6-Step SNVN Workflow Sidebar */}
        <WorkflowSidebar
          presets={PROJECT_PRESETS}
          activePresetId={activePresetId}
          onSelectPreset={handleSelectPreset}
          onUploadExcel={handleUploadExcel}
          onUploadDxf={handleUploadDxf}
          onOpenMcpModal={() => setMcpModalOpen(true)}
          mhtn={mhtn}
          breaklineCount={breaklines.length}
          designSpec={designSpec}
          onDesignChange={setDesignSpec}
          onAutoBalance={handleAutoBalance}
          gridConfig={gridConfig}
          onGridConfigChange={setGridConfig}
          onAutoFitGrid={handleAutoFitGrid}
          onQuickShiftHTK={(delta) =>
            setDesignSpec((prev) => ({
              ...prev,
              elevationShift: Number((prev.elevationShift + delta).toFixed(2)),
            }))
          }
          taluyConfig={taluyConfig}
          onTaluyConfigChange={setTaluyConfig}
          contourConfig={contourConfig}
          onContourConfigChange={setContourConfig}
          layers={layers}
          onToggleLayer={(key) =>
            setLayers((prev) => ({ ...prev, [key]: !prev[key] }))
          }
        />

        {/* Center Dominant Viewport */}
        <main className="relative min-w-0 flex-1 overflow-hidden">
          {activeTab === 'cad2d' && (
            <CadCanvas2D
              mhtn={mhtn}
              designSpec={designSpec}
              points={points}
              breaklines={breaklines}
              boundary={boundary}
              exclusions={exclusions}
              gridResult={gridResult}
              contours={contours}
              taluyResult={taluyResult}
              sections={sections}
              activeSectionId={activeSectionId}
              layers={layers}
              toolMode={toolMode}
              onToolModeChange={setToolMode}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              selectedCellId={selectedCellId}
              onSelectCell={setSelectedCellId}
              pendingMergeCellId={pendingMergeCellId}
              onMergeCellClick={handleMergeCellClick}
              onCreateSection={handleCreateSection}
            />
          )}

          {activeTab === 'view3d' && (
            <Terrain3DView
              mhtn={mhtn}
              mhtk={mhtk}
              designSpec={designSpec}
              breaklines={breaklines}
              boundary={boundary}
              taluyResult={taluyResult}
            />
          )}

          {activeTab === 'section' && (
            <CrossSectionView
              sections={sections}
              activeSectionId={activeSectionId}
              sectionResult={activeSectionResult}
              onSelectSection={setActiveSectionId}
              onUpdateScale={(id, hScale, vScale) =>
                setSections((prev) =>
                  prev.map((s) =>
                    s.id === id
                      ? { ...s, horizontalScale: hScale, verticalScale: vScale }
                      : s
                  )
                )
              }
              onDeleteSection={(id) => {
                setSections((prev) => {
                  const next = prev.filter((s) => s.id !== id);
                  if (next.length > 0 && activeSectionId === id) {
                    setActiveSectionId(next[0].id);
                  }
                  return next;
                });
              }}
              onStartDrawSection={() => {
                setActiveTab('cad2d');
                setToolMode('draw_section');
              }}
              onPushSectionToMcp={() => handleRunMcpTool('autocad_draw_cross_section')}
            />
          )}

          {activeTab === 'reports' && (
            <ReportsChartsView
              projectName={projectName}
              mhtn={mhtn}
              designSpec={designSpec}
              gridConfig={gridConfig}
              boundary={boundary}
              exclusions={exclusions}
              gridResult={gridResult}
              taluyResult={taluyResult}
              onExportExcel={() => {
                exportSnvnExcelWorkbook(projectName, gridResult, taluyResult);
                showToast('Đã xuất tệp Excel 6 sheet chuẩn SNVN (.xlsx).');
              }}
              onExportDxf={() => {
                exportSnvnDxf(projectName, boundary, exclusions, gridResult, contours, taluyResult);
                showToast('Đã xuất bản vẽ CAD chuẩn SNVN (.dxf).');
              }}
              onExportScript={() => {
                exportAutoCadScript(projectName, gridResult, activeSectionResult);
                showToast('Đã xuất tập lệnh AutoCAD 2022 (.scr).');
              }}
              onPushTablesToMcp={() => handleRunMcpTool('autocad_insert_snvn_tables')}
              onAutoBalance={handleAutoBalance}
            />
          )}
        </main>

        {/* Right Summary & Object Inspector (shown on 2D CAD view for uncluttered 3D/Section/Reports) */}
        {activeTab === 'cad2d' && (
          <InspectorPanel
            gridResult={gridResult}
            taluyResult={taluyResult}
            selectedNode={selectedNode}
            selectedCell={selectedCell}
            nodeOverrideCount={Object.keys(nodeOverrides).length}
            mergedPairCount={mergedPairs.length}
            onUpdateNodeHTK={(nodeId, newHTK) => {
              setNodeOverrides((prev) => ({ ...prev, [nodeId]: newHTK }));
              showToast(`Đã cập nhật CĐTK nút ${nodeId} = ${newHTK.toFixed(2)}m.`);
            }}
            onResetNodeHTK={(nodeId) => {
              setNodeOverrides((prev) => {
                const next = { ...prev };
                delete next[nodeId];
                return next;
              });
              showToast(`Đã khôi phục nút ${nodeId} theo MHTK.`);
            }}
            onResetAllOverrides={() => {
              setNodeOverrides({});
              showToast('Đã đặt lại toàn bộ cao độ nút theo bề mặt thiết kế.');
            }}
            onClearMergedCells={() => {
              setMergedPairs([]);
              showToast('Đã tách toàn bộ các ô cộng gộp.');
            }}
            onExportExcel={() => {
              exportSnvnExcelWorkbook(projectName, gridResult, taluyResult);
              showToast('Đã xuất tệp Excel 6 sheet chuẩn SNVN (.xlsx).');
            }}
            onExportDxf={() => {
              exportSnvnDxf(projectName, boundary, exclusions, gridResult, contours, taluyResult);
              showToast('Đã xuất bản vẽ CAD chuẩn SNVN (.dxf).');
            }}
            onPushGridToMcp={() => handleRunMcpTool('autocad_draw_grid_results')}
          />
        )}
      </div>

      {/* AutoCAD 2022 MCP Bridge Studio Modal */}
      <McpBridgeModal
        open={mcpModalOpen}
        onClose={() => setMcpModalOpen(false)}
        endpoint={mcpEndpoint}
        onEndpointChange={setMcpEndpoint}
        useSandbox={mcpUseSandbox}
        onUseSandboxChange={setMcpUseSandbox}
        connectionInfo={mcpConnectionInfo}
        logs={mcpLogs}
        onRunTool={handleRunMcpTool}
      />

      {/* Non-intrusive Action Feedback Toast */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 rounded-lg border border-sky-500/40 bg-[#141B29] px-4 py-2.5 text-xs font-medium text-sky-200 shadow-xl">
          {toast}
        </div>
      )}
    </div>
  );
}
