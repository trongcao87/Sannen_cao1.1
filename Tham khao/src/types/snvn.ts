export interface Point2D {
  x: number;
  y: number;
}

export interface Point3D {
  x: number;
  y: number;
  z: number;
}

export type CadEntitySource =
  | 'POINT'
  | 'BLOCK'
  | 'TEXT'
  | 'LINE'
  | 'POLYLINE2D'
  | 'POLYLINE3D'
  | 'EXCEL'
  | 'PRESET';

export interface SurveyPoint extends Point3D {
  id: string;
  source: CadEntitySource;
  layer: string;
  label?: string;
}

export interface Breakline {
  id: string;
  name: string;
  vertices: Point3D[];
  is3D: boolean;
  layer: string;
}

export interface PolygonZone {
  id: string;
  name: string;
  vertices: Point2D[];
  type: 'boundary' | 'exclusion';
}

export interface BoundingBox {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  minZ: number;
  maxZ: number;
}

export interface TinTriangle {
  a: number;
  b: number;
  c: number;
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

export interface TinSurface {
  name: string;
  vertices: Point3D[];
  triangles: TinTriangle[];
  constrainedEdges: [number, number][];
  bounds: BoundingBox;
}

export type DesignSurfaceMode = 'flat' | 'single_slope' | 'ridge_slope' | 'custom_tin';

export interface DesignSurfaceSpec {
  mode: DesignSurfaceMode;
  baseElevation: number;
  refPoint: Point2D;
  /** Azimuth angle in degrees for single_slope or ridge main direction */
  slopeAngleDeg: number;
  /** Longitudinal slope in % (e.g. 1.5 means 1.5%) */
  longitudinalSlopePct: number;
  /** Transverse slope in % for ridge_slope mode (sheds downward on both sides) */
  transverseSlopePct: number;
  /** Global vertical offset applied on top (used by Nâng/Hạ CĐTK & Auto-Balance) */
  elevationShift: number;
  /** Optional custom design points if mode === 'custom_tin' */
  customPoints?: SurveyPoint[];
}

export interface GridConfig {
  name: string;
  /** SNVN format e.g. "12x20" or "4x20,4x15,4x20" */
  colSpec: string;
  /** SNVN format e.g. "9x20" or "5x20,4x15" */
  rowSpec: string;
  originX: number;
  originY: number;
  angleDeg: number;
  layer: string;
  compactionFactor: number;
}

export interface GridNode {
  id: string; // e.g., "row-col" (1-based display, 0-based indices)
  row: number;
  col: number;
  x: number;
  y: number;
  hTN: number;
  hTK: number;
  deltaH: number; // hTK - hTN (+ fill / đắp, - cut / đào)
  isCustomHTK: boolean;
  insideBoundary: boolean;
}

export interface SubPolygonVolume {
  type: 'cut' | 'fill';
  polygon: Point2D[];
  area: number;
  avgDeltaH: number; // positive magnitude
  volume: number; // positive m3
  centroid: Point2D;
}

export interface GridCell {
  id: string; // "r-c"
  row: number;
  col: number;
  corners: Point2D[]; // 4 unclipped grid corners
  clippedPolygon: Point2D[]; // clipped against boundary & exclusions
  active: boolean;
  totalArea: number;
  cutArea: number;
  fillArea: number;
  cutAvgH: number;
  fillAvgH: number;
  cutVolume: number;
  fillVolume: number;
  subPolygons: SubPolygonVolume[];
  mergedGroupId?: string;
}

export interface ZeroLineSegment {
  p1: Point2D;
  p2: Point2D;
}

export interface MergedCellGroup {
  id: string;
  cellIds: string[];
  type: 'cut' | 'fill';
  area: number;
  avgH: number;
  volume: number;
  centroid: Point2D;
}

export interface ColumnSummary {
  col: number;
  label: string;
  cutArea: number;
  fillArea: number;
  cutVolume: number;
  fillVolume: number;
}

export interface RowSummary {
  row: number;
  label: string;
  cutArea: number;
  fillArea: number;
  cutVolume: number;
  fillVolume: number;
}

export interface GridCalculationResult {
  colWidths: number[];
  rowHeights: number[];
  nodes: GridNode[][]; // [row][col]
  cells: GridCell[];
  mergedGroups: MergedCellGroup[];
  zeroLines: ZeroLineSegment[];
  colSummaries: ColumnSummary[];
  rowSummaries: RowSummary[];
  totalLandArea: number;
  totalCutArea: number;
  totalFillArea: number;
  totalCutVolume: number;
  totalFillVolume: number;
  effectiveFillVolume: number; // totalFillVolume * compactionFactor
  netVolume: number; // totalFillVolume - totalCutVolume
}

export interface TaluyConfig {
  enabled: boolean;
  /** Cut slope 1:n (e.g. 1.0 means 1:1) */
  cutSlopeN: number;
  /** Fill slope 1:n (e.g. 1.5 means 1:1.5) */
  fillSlopeN: number;
  /** Berm height H giật cơ (m) */
  bermHeight: number;
  /** Berm width B giật cơ (m) */
  bermWidth: number;
  /** Berm slope i giật cơ (%) */
  bermSlopePct: number;
  /** Cross-section step Bước chia (m) */
  stepLength: number;
  /** 2D hatch long tick spacing (m) */
  tickSpacing: number;
  /** Short ticks between long ticks */
  shortTicksPerLong: number;
  /** Optional retaining wall on fill edges */
  retainingWall: boolean;
  retainingWallHeight: number;
}

export interface TaluyTick2D {
  p1: Point2D;
  p2: Point2D;
  isLong: boolean;
  type: 'cut' | 'fill';
}

export interface TaluySegmentResult {
  id: string; // C1, C2... or G1, G2...
  kind: 'edge' | 'corner';
  type: 'cut' | 'fill';
  length: number;
  area: number;
  volume: number;
  avgHeight: number;
  sectionCount: number;
  topLine: Point3D[];
  toeLine: Point3D[];
  meshTriangles: [Point3D, Point3D, Point3D][];
}

export interface TaluyCalculationResult {
  segments: TaluySegmentResult[];
  ticks2D: TaluyTick2D[];
  totalCutArea: number;
  totalFillArea: number;
  totalCutVolume: number;
  totalFillVolume: number;
}

export interface ContourConfig {
  minorInterval: number;
  majorInterval: number;
  smoothIterations: number;
  showLabels: boolean;
  targetSurface: 'mhtn' | 'mhtk' | 'both';
}

export interface ContourPolyline {
  elevation: number;
  isMajor: boolean;
  surface: 'mhtn' | 'mhtk';
  points: Point2D[];
  labelPoint?: { x: number; y: number; angleRad: number };
}

export interface CrossSectionDef {
  id: string;
  name: string;
  start: Point2D;
  end: Point2D;
  horizontalScale: number; // e.g. 500 -> 1:500
  verticalScale: number; // e.g. 100 -> 1:100
}

export interface CrossSectionStation {
  dist: number; // cumulative distance from start (m)
  segDist: number; // delta distance from previous station (m)
  x: number;
  y: number;
  hTN: number;
  hTK: number;
  deltaH: number; // hTK - hTN
  note?: string;
}

export interface CrossSectionResult {
  def: CrossSectionDef;
  totalLength: number;
  datumElevation: number;
  minElevation: number;
  maxElevation: number;
  cutArea: number; // m2
  fillArea: number; // m2
  stations: CrossSectionStation[];
}

export interface LayerVisibility {
  points: boolean;
  tinMhtn: boolean;
  breaklines: boolean;
  contoursMhtn: boolean;
  contoursMhtk: boolean;
  boundary: boolean;
  gridLines: boolean;
  nodeLabels: boolean;
  cellVolumes: boolean;
  zeroLine: boolean;
  taluy: boolean;
  axisTotals: boolean;
  crossSections: boolean;
  heatmap: boolean;
}

export type CanvasToolMode = 'pan' | 'edit_node' | 'merge_cell' | 'draw_section';

export type ActiveWorkspaceTab = 'cad2d' | 'view3d' | 'section' | 'reports';

export interface McpLogEntry {
  id: string;
  timestamp: string;
  method: string;
  mode: 'live' | 'sandbox';
  status: 'ok' | 'error';
  summary: string;
  requestPayload: unknown;
  responsePayload: unknown;
}

export interface ProjectPreset {
  id: string;
  name: string;
  location: string;
  description: string;
  points: SurveyPoint[];
  breaklines: Breakline[];
  boundary: PolygonZone;
  exclusions: PolygonZone[];
  defaultDesign: DesignSurfaceSpec;
  defaultGrid: GridConfig;
  defaultSections: CrossSectionDef[];
}
