import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { ChevronDown, ChevronUp, RotateCcw } from 'lucide-react';
import {
  Breakline,
  DesignSurfaceSpec,
  PolygonZone,
  TaluyCalculationResult,
  TinSurface,
} from '../types/snvn';
import { evaluateDesignElevation } from '../engine/tin';

interface Terrain3DViewProps {
  mhtn: TinSurface;
  mhtk: TinSurface;
  designSpec: DesignSurfaceSpec;
  customDesignTin?: TinSurface | null;
  breaklines: Breakline[];
  boundary: PolygonZone;
  taluyResult: TaluyCalculationResult;
}

type ColorMode3D = 'cutfill' | 'hypsometric';

function probeSoftwareWebGL(): boolean {
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    if (!gl) return true;
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const param = ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER;
    const gpu = String(gl.getParameter(param));
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return /SwiftShader|llvmpipe|softpipe|Software|Basic Render/i.test(gpu);
  } catch {
    return true;
  }
}

export const Terrain3DView: React.FC<Terrain3DViewProps> = ({
  mhtn,
  mhtk,
  designSpec,
  customDesignTin,
  breaklines,
  boundary,
  taluyResult,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [exaggeration, setExaggeration] = useState(2.2);
  const [explodeOffset, setExplodeOffset] = useState(0);
  const [colorMode, setColorMode] = useState<ColorMode3D>('cutfill');
  const [showMhtn, setShowMhtn] = useState(true);
  const [showMhtk, setShowMhtk] = useState(true);
  const [showWireframe, setShowWireframe] = useState(true);
  const [showTaluy, setShowTaluy] = useState(true);
  const [dockOpen, setDockOpen] = useState(true);
  const [webglError, setWebglError] = useState<string | null>(null);

  const sceneRefs = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    dataGroup: THREE.Group;
    mhtkGroup: THREE.Group;
    requestRender: () => void;
    cameraGoal: { pos: THREE.Vector3; target: THREE.Vector3 } | null;
  } | null>(null);

  // Initialize Three.js renderer & studio rig once
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const isSoftwareGl = probeSoftwareWebGL();
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: !isSoftwareGl,
        powerPreference: 'high-performance',
      });
    } catch {
      setWebglError('Trình duyệt không hỗ trợ WebGL2 cho mô hình 3D.');
      return;
    }

    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = !isSoftwareGl;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const width = Math.max(300, container.clientWidth);
    const height = Math.max(260, container.clientHeight);
    renderer.setSize(width, height);
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const bgHex = 0x0b0f17;
    scene.background = new THREE.Color(bgHex);
    scene.fog = new THREE.FogExp2(bgHex, 0.0014);

    // Mandatory studio environment map via RoomEnvironment
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envTex;
    pmrem.dispose();

    // 3-point warm/cool studio lighting rig
    const hemiLight = new THREE.HemisphereLight(0xbcd8ff, 0x1e293b, 0.9);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight(0xfff4e0, 1.55);
    keyLight.position.set(160, 220, 140);
    if (!isSoftwareGl) {
      keyLight.castShadow = true;
      keyLight.shadow.mapSize.set(1024, 1024);
      keyLight.shadow.bias = -0.0005;
      keyLight.shadow.normalBias = 0.02;
    }
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x38bdf8, 0.65);
    rimLight.position.set(-150, 90, -140);
    scene.add(rimLight);

    const camera = new THREE.PerspectiveCamera(44, width / height, 1, 2500);
    camera.position.set(220, 165, 230);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = !isSoftwareGl;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.minDistance = 40;
    controls.maxDistance = 900;

    // Ground drafting reference grid
    const gridHelper = new THREE.GridHelper(360, 18, 0x334155, 0x1e293b);
    gridHelper.position.y = -2;
    scene.add(gridHelper);

    const dataGroup = new THREE.Group();
    const mhtkGroup = new THREE.Group();
    scene.add(dataGroup);
    scene.add(mhtkGroup);

    // On-demand render scheduler with software-GL fence pacing
    let frameId = 0;
    let renderBusy = false;
    let renderDirty = false;
    let disposed = false;

    const afterDraw = (cb: () => void) => {
      const gl = renderer.getContext() as WebGL2RenderingContext;
      const sync = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      gl.flush();
      const poll = () => {
        if (disposed) return;
        const status = sync && gl.getSyncParameter(sync, gl.SYNC_STATUS);
        if (status === gl.UNSIGNALED) {
          frameId = window.setTimeout(poll, 5);
        } else {
          if (sync) gl.deleteSync(sync);
          frameId = window.setTimeout(cb, 80);
        }
      };
      frameId = window.setTimeout(poll, 5);
    };

    const requestRender = () => {
      if (disposed) return;
      if (renderBusy) {
        renderDirty = true;
        return;
      }
      renderBusy = true;
      frameId = requestAnimationFrame(() => {
        if (disposed) return;
        renderDirty = false;

        // Smooth camera preset damping
        const goal = sceneRefs.current?.cameraGoal;
        if (goal) {
          camera.position.lerp(goal.pos, 0.14);
          controls.target.lerp(goal.target, 0.14);
          if (
            camera.position.distanceTo(goal.pos) < 0.8 &&
            controls.target.distanceTo(goal.target) < 0.8
          ) {
            camera.position.copy(goal.pos);
            controls.target.copy(goal.target);
            if (sceneRefs.current) sceneRefs.current.cameraGoal = null;
          } else {
            renderDirty = true;
          }
        }

        controls.update();
        renderer.render(scene, camera);

        const done = () => {
          renderBusy = false;
          if (renderDirty) requestRender();
        };
        if (isSoftwareGl) afterDraw(done);
        else done();
      });
    };

    controls.addEventListener('change', requestRender);
    controls.addEventListener('start', () => {
      if (sceneRefs.current) sceneRefs.current.cameraGoal = null;
    });

    const onContextLost = (e: Event) => {
      e.preventDefault();
      setWebglError('Ngữ cảnh WebGL tạm ngưng. Vui lòng chuyển tab hoặc tải lại.');
    };
    renderer.domElement.addEventListener('webglcontextlost', onContextLost);

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = Math.max(300, Math.floor(entry.contentRect.width));
        const h = Math.max(260, Math.floor(entry.contentRect.height));
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        requestRender();
      }
    });
    ro.observe(container);

    sceneRefs.current = {
      scene,
      camera,
      controls,
      dataGroup,
      mhtkGroup,
      requestRender,
      cameraGoal: null,
    };

    requestRender();

    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      clearTimeout(frameId);
      ro.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost);
      envTex.dispose();
      renderer.dispose();
      sceneRefs.current = null;
    };
  }, []);

  // Rebuild 3D TIN & Taluy geometries whenever data or visualization parameters change
  useEffect(() => {
    const refs = sceneRefs.current;
    if (!refs) return;

    const clearGroup = (grp: THREE.Group) => {
      while (grp.children.length > 0) {
        const child = grp.children[0];
        grp.remove(child);
        child.traverse((obj) => {
          if ((obj as THREE.Mesh).geometry) (obj as THREE.Mesh).geometry.dispose();
          const mat = (obj as THREE.Mesh).material;
          if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
          else if (mat) mat.dispose();
        });
      }
    };

    clearGroup(refs.dataGroup);
    clearGroup(refs.mhtkGroup);

    const cx = (mhtn.bounds.minX + mhtn.bounds.maxX) / 2;
    const cy = (mhtn.bounds.minY + mhtn.bounds.maxY) / 2;
    const baseZ = mhtn.bounds.minZ;
    const zRange = Math.max(1, mhtn.bounds.maxZ - mhtn.bounds.minZ);

    // Helper: Surveying (X, Y, Z) -> Three.js Right-Handed (x = X - cx, y = (Z - baseZ) * exag, z = -(Y - cy))
    const to3D = (x: number, y: number, z: number, extraY = 0) =>
      new THREE.Vector3(x - cx, (z - baseZ) * exaggeration + extraY, -(y - cy));

    // 1. MHTN Natural Terrain TIN Mesh
    if (showMhtn && mhtn.triangles.length > 0) {
      const nVerts = mhtn.vertices.length;
      const positions = new Float32Array(nVerts * 3);
      const colors = new Float32Array(nVerts * 3);
      const tmpColor = new THREE.Color();

      for (let i = 0; i < nVerts; i++) {
        const v = mhtn.vertices[i];
        const p = to3D(v.x, v.y, v.z);
        positions[i * 3] = p.x;
        positions[i * 3 + 1] = p.y;
        positions[i * 3 + 2] = p.z;

        if (colorMode === 'cutfill') {
          const hTK = evaluateDesignElevation(designSpec, v.x, v.y, customDesignTin);
          const dh = hTK - v.z; // + fill (red), - cut (amber)
          const mag = Math.min(1, Math.abs(dh) / 4.5);
          if (dh >= 0.08) {
            tmpColor.setRGB(0.42 + mag * 0.52, 0.22 + (1 - mag) * 0.25, 0.22);
          } else if (dh <= -0.08) {
            tmpColor.setRGB(0.45 + mag * 0.48, 0.42 + mag * 0.34, 0.14);
          } else {
            tmpColor.setRGB(0.22, 0.65, 0.78); // zero-line transition
          }
        } else {
          const t = (v.z - mhtn.bounds.minZ) / zRange;
          tmpColor.setHSL(0.42 - t * 0.32, 0.48, 0.3 + t * 0.26);
        }
        colors[i * 3] = tmpColor.r;
        colors[i * 3 + 1] = tmpColor.g;
        colors[i * 3 + 2] = tmpColor.b;
      }

      const indices = new Uint32Array(mhtn.triangles.length * 3);
      mhtn.triangles.forEach((tri, idx) => {
        indices[idx * 3] = tri.a;
        indices[idx * 3 + 1] = tri.b;
        indices[idx * 3 + 2] = tri.c;
      });

      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geo.setIndex(new THREE.BufferAttribute(indices, 1));
      geo.computeVertexNormals();

      const mat = new THREE.MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.76,
        metalness: 0.08,
        side: THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.receiveShadow = true;
      refs.dataGroup.add(mesh);

      if (showWireframe) {
        const wireGeo = new THREE.WireframeGeometry(geo);
        const wireMat = new THREE.LineBasicMaterial({
          color: 0x0f172a,
          transparent: true,
          opacity: 0.28,
        });
        refs.dataGroup.add(new THREE.LineSegments(wireGeo, wireMat));
      }
    }

    // 2. Breaklines as crisp 3D tubes
    for (const bl of breaklines) {
      if (bl.vertices.length < 2) continue;
      const curvePts = bl.vertices.map((v) => to3D(v.x, v.y, v.z, 0.35));
      const curve = new THREE.CatmullRomCurve3(curvePts);
      const tubeGeo = new THREE.TubeGeometry(curve, Math.max(12, bl.vertices.length * 4), 0.45, 6, false);
      const tubeMat = new THREE.MeshStandardMaterial({
        color: 0xd946ef,
        roughness: 0.35,
        metalness: 0.2,
      });
      refs.dataGroup.add(new THREE.Mesh(tubeGeo, tubeMat));
    }

    // 3. MHTK Design Surface Mesh (placed in mhtkGroup so explodeOffset lifts it cleanly)
    if (showMhtk && mhtk.triangles.length > 0) {
      const nVerts = mhtk.vertices.length;
      const positions = new Float32Array(nVerts * 3);
      for (let i = 0; i < nVerts; i++) {
        const v = mhtk.vertices[i];
        const p = to3D(v.x, v.y, v.z, 0.12);
        positions[i * 3] = p.x;
        positions[i * 3 + 1] = p.y;
        positions[i * 3 + 2] = p.z;
      }
      const indices = new Uint32Array(mhtk.triangles.length * 3);
      mhtk.triangles.forEach((tri, idx) => {
        indices[idx * 3] = tri.a;
        indices[idx * 3 + 1] = tri.b;
        indices[idx * 3 + 2] = tri.c;
      });
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geo.setIndex(new THREE.BufferAttribute(indices, 1));
      geo.computeVertexNormals();

      const mat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        roughness: 0.35,
        metalness: 0.15,
        transparent: true,
        opacity: 0.36,
        depthWrite: false,
        side: THREE.DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -1,
      });
      refs.mhtkGroup.add(new THREE.Mesh(geo, mat));

      const wireGeo = new THREE.WireframeGeometry(geo);
      const wireMat = new THREE.LineBasicMaterial({
        color: 0x7dd3fc,
        transparent: true,
        opacity: 0.42,
      });
      refs.mhtkGroup.add(new THREE.LineSegments(wireGeo, wireMat));
    }

    // Boundary perimeter line on MHTK
    if (boundary.vertices.length >= 3) {
      const bPts = [...boundary.vertices, boundary.vertices[0]].map((p) => {
        const z = evaluateDesignElevation(designSpec, p.x, p.y, customDesignTin);
        return to3D(p.x, p.y, z, 0.5);
      });
      const bGeo = new THREE.BufferGeometry().setFromPoints(bPts);
      const bMat = new THREE.LineBasicMaterial({ color: 0x60a5fa });
      refs.mhtkGroup.add(new THREE.Line(bGeo, bMat));
    }

    // 4. 3D Taluy Sloped Embankment Skirts
    if (showTaluy && taluyResult.segments.length > 0) {
      const buildTaluyMesh = (type: 'cut' | 'fill', hex: number) => {
        const coords: number[] = [];
        for (const seg of taluyResult.segments) {
          if (seg.type !== type) continue;
          for (const [p1, p2, p3] of seg.meshTriangles) {
            const v1 = to3D(p1.x, p1.y, p1.z, 0.18);
            const v2 = to3D(p2.x, p2.y, p2.z, 0.18);
            const v3 = to3D(p3.x, p3.y, p3.z, 0.18);
            coords.push(v1.x, v1.y, v1.z, v2.x, v2.y, v2.z, v3.x, v3.y, v3.z);
          }
        }
        if (coords.length === 0) return;
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.Float32BufferAttribute(coords, 3));
        geo.computeVertexNormals();
        const mat = new THREE.MeshStandardMaterial({
          color: hex,
          roughness: 0.62,
          metalness: 0.1,
          side: THREE.DoubleSide,
        });
        refs.dataGroup.add(new THREE.Mesh(geo, mat));
      };
      buildTaluyMesh('fill', 0xef4444);
      buildTaluyMesh('cut', 0xeab308);
    }

    refs.mhtkGroup.position.y = explodeOffset;
    refs.requestRender();
  }, [
    mhtn,
    mhtk,
    designSpec,
    customDesignTin,
    breaklines,
    boundary,
    taluyResult,
    exaggeration,
    explodeOffset,
    colorMode,
    showMhtn,
    showMhtk,
    showWireframe,
    showTaluy,
  ]);

  const setCameraPreset = (preset: 'iso' | 'top' | 'side') => {
    const refs = sceneRefs.current;
    if (!refs) return;
    if (preset === 'iso') {
      refs.cameraGoal = { pos: new THREE.Vector3(210, 155, 220), target: new THREE.Vector3(0, 10, 0) };
    } else if (preset === 'top') {
      refs.cameraGoal = { pos: new THREE.Vector3(0, 320, 18), target: new THREE.Vector3(0, 0, 0) };
    } else {
      refs.cameraGoal = { pos: new THREE.Vector3(280, 48, 0), target: new THREE.Vector3(0, 12, 0) };
    }
    refs.requestRender();
  };

  if (webglError) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#0B0F17] p-6 text-sm text-slate-300">
        {webglError}
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-[#0B0F17]">
      {/* Isolated WebGL canvas mount */}
      <div ref={mountRef} className="h-full w-full" />

      {/* Minimal Top-Left Specification Header (no blur over WebGL) */}
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-lg border border-[#263248] bg-[#141B29]/95 px-3.5 py-2 text-xs">
        <div className="font-semibold text-slate-100">Mô hình 3D TIN Địa hình &amp; Thiết kế</div>
        <div className="mt-0.5 font-mono tabular-nums text-[11px] text-slate-400">
          {mhtn.vertices.length} đỉnh TIN · {mhtn.triangles.length} tam giác · Đứt gãy: {breaklines.length} · Phóng đại Z: {exaggeration.toFixed(1)}×
        </div>
      </div>

      {/* Collapsible Bottom Control Dock (Zero Side-Panel Occlusion per threejs/SKILL.md) */}
      <div className="absolute bottom-4 left-1/2 z-10 w-[min(920px,95%)] -translate-x-1/2">
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => setDockOpen((o) => !o)}
            className="flex items-center gap-1.5 rounded-t-lg border border-b-0 border-[#263248] bg-[#141B29] px-3 py-1 text-[11px] font-medium text-slate-300 hover:text-white whitespace-nowrap shrink-0"
          >
            {dockOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
            {dockOpen ? 'Thu gọn điều khiển 3D' : 'Mở điều khiển 3D'}
          </button>
        </div>

        {dockOpen && (
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#263248] bg-[#141B29]/95 px-4 py-3 text-xs">
            {/* Sliders */}
            <div className="flex flex-wrap items-center gap-5">
              <label className="flex items-center gap-2 text-slate-300">
                <span className="whitespace-nowrap text-[11px] text-slate-400">Phóng đại Z</span>
                <input
                  type="range"
                  min={1}
                  max={6}
                  step={0.2}
                  value={exaggeration}
                  onChange={(e) => setExaggeration(parseFloat(e.target.value))}
                  className="w-24 accent-sky-400"
                />
                <span className="w-8 font-mono tabular-nums text-sky-300">{exaggeration.toFixed(1)}×</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300">
                <span className="whitespace-nowrap text-[11px] text-slate-400">Tách lớp MHTK</span>
                <input
                  type="range"
                  min={0}
                  max={45}
                  step={1}
                  value={explodeOffset}
                  onChange={(e) => setExplodeOffset(parseFloat(e.target.value))}
                  className="w-24 accent-sky-400"
                />
                <span className="w-8 font-mono tabular-nums text-sky-300">+{explodeOffset}m</span>
              </label>
            </div>

            {/* Color & Layer Toggles */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center rounded-md border border-[#263248] bg-[#0B0F17] p-0.5">
                <button
                  type="button"
                  onClick={() => setColorMode('cutfill')}
                  className={`rounded px-2 py-1 text-[11px] font-medium whitespace-nowrap shrink-0 ${
                    colorMode === 'cutfill' ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Màu Đào/Đắp
                </button>
                <button
                  type="button"
                  onClick={() => setColorMode('hypsometric')}
                  className={`rounded px-2 py-1 text-[11px] font-medium whitespace-nowrap shrink-0 ${
                    colorMode === 'hypsometric' ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Dải Cao độ
                </button>
              </div>

              {[
                { label: 'MHTN', active: showMhtn, toggle: () => setShowMhtn((v) => !v) },
                { label: 'MHTK', active: showMhtk, toggle: () => setShowMhtk((v) => !v) },
                { label: 'Lưới TIN', active: showWireframe, toggle: () => setShowWireframe((v) => !v) },
                { label: 'Taluy 3D', active: showTaluy, toggle: () => setShowTaluy((v) => !v) },
              ].map((btn) => (
                <button
                  key={btn.label}
                  type="button"
                  onClick={btn.toggle}
                  className={`rounded-md border px-2 py-1 text-[11px] font-medium whitespace-nowrap shrink-0 transition-colors ${
                    btn.active
                      ? 'border-sky-500/40 bg-sky-500/15 text-sky-300'
                      : 'border-[#263248] bg-[#0B0F17] text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {btn.label}
                </button>
              ))}
            </div>

            {/* Camera Presets */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setCameraPreset('iso')}
                className="rounded-md border border-[#263248] bg-[#1C2538] px-2 py-1 text-[11px] font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
              >
                Phối cảnh
              </button>
              <button
                type="button"
                onClick={() => setCameraPreset('top')}
                className="rounded-md border border-[#263248] bg-[#1C2538] px-2 py-1 text-[11px] font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
              >
                Đỉnh
              </button>
              <button
                type="button"
                onClick={() => setCameraPreset('side')}
                className="rounded-md border border-[#263248] bg-[#1C2538] px-2 py-1 text-[11px] font-medium text-slate-200 hover:border-sky-500/50 whitespace-nowrap shrink-0"
              >
                Mặt bên
              </button>
              <button
                type="button"
                onClick={() => {
                  setExaggeration(2.2);
                  setExplodeOffset(0);
                  setCameraPreset('iso');
                }}
                className="rounded-md border border-[#263248] bg-[#0B0F17] p-1 text-slate-400 hover:text-white"
                title="Đặt lại góc nhìn"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
