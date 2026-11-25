"""Mẫu HTML tự chứa cho trình xem 3D (xem `xem3d.py`).

Không dùng thư viện ngoài, không CDN: chạy offline bằng canvas 2D (thuật toán người họa sĩ,
đổ bóng Lambert). Hai chỗ thay thế: `__TIEU_DE__` và `__DU_LIEU__` (JSON đã dời gốc về trọng tâm).
"""

MAU_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Xem 3D bề mặt TIN — __TIEU_DE__</title>
<style>
:root{--nen:#0b0f17;--panel:rgba(17,24,39,.88);--vien:#273244;--chu:#e5e7eb;--mo:#94a3b8;--nhan:#38bdf8}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--nen);color:var(--chu);
  font:13px/1.45 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;overflow:hidden;user-select:none}
#cv{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab}
#cv.keo{cursor:grabbing}
.hop{background:var(--panel);border:1px solid var(--vien);border-radius:8px;backdrop-filter:blur(4px)}
#bang{position:absolute;left:12px;top:12px;width:248px;max-height:calc(100% - 24px);overflow:auto;padding:10px 12px}
#bang h1{font-size:14px;margin:0 0 2px;font-weight:600}
#bang .phu{color:var(--mo);font-size:11.5px;margin-bottom:6px}
#bang h2{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mo);margin:10px 0 4px;font-weight:600}
#bang label{display:flex;align-items:center;gap:6px;padding:1.5px 0;cursor:pointer}
#bang input[type=checkbox],#bang input[type=radio]{accent-color:var(--nhan);margin:0}
#bang .hang{display:flex;align-items:center;gap:8px;padding:2px 0}
#bang .hang span.gt{width:44px;text-align:right;color:var(--nhan);font-variant-numeric:tabular-nums}
#bang input[type=range]{flex:1;accent-color:var(--nhan);min-width:0}
.mau{display:inline-block;width:10px;height:10px;border-radius:2px;flex:none}
#an{position:absolute;left:12px;top:12px;display:none;padding:5px 10px;cursor:pointer}
#goc{position:absolute;right:12px;top:12px;display:flex;gap:6px;padding:6px}
button{background:#1f2937;color:var(--chu);border:1px solid var(--vien);border-radius:6px;padding:4px 10px;
  font:inherit;cursor:pointer}
button:hover{background:#2b3a52;border-color:#3b4d6a}
button.dang{background:#0c4a6e;border-color:#0284c7}
#chuthich{position:absolute;left:272px;bottom:12px;padding:8px 12px;min-width:250px;max-width:420px}
#chuthich .ten{font-size:11px;color:var(--mo);margin-bottom:4px}
#chuthich .thang{height:12px;border-radius:3px;border:1px solid var(--vien)}
#chuthich .nhan{display:flex;justify-content:space-between;font-size:11.5px;margin-top:2px;font-variant-numeric:tabular-nums}
#chuthich .dong{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:6px;font-size:11.5px}
#chuthich .dong span{display:inline-flex;align-items:center;gap:5px}
#sl{position:absolute;right:12px;bottom:12px;padding:7px 11px;font-size:11.5px;color:var(--mo);
  text-align:right;font-variant-numeric:tabular-nums}
#sl b{color:var(--chu);font-weight:600}
#tip{position:absolute;display:none;pointer-events:none;padding:6px 9px;font-size:12px;white-space:pre;
  background:rgba(2,6,23,.94);border:1px solid #334155;border-radius:6px;z-index:5;
  font-variant-numeric:tabular-nums}
#tip b{color:var(--nhan)}
#huongdan{position:absolute;left:50%;bottom:6px;transform:translateX(-50%);font-size:11px;color:#64748b;pointer-events:none}
@media(max-width:900px){#chuthich{left:12px;bottom:110px;max-width:calc(100% - 24px)}#huongdan{display:none}#sl{font-size:10.5px}}
</style>
</head>
<body>
<canvas id="cv"></canvas>

<div id="bang" class="hop">
  <h1>Xem 3D bề mặt TIN</h1>
  <div class="phu" id="lylich"></div>
  <h2>Bề mặt</h2>
  <label><input type="checkbox" id="hMoc" checked><span class="mau" style="background:#4ade80"></span>Mốc (tự nhiên)</label>
  <label><input type="checkbox" id="hDo" checked><span class="mau" style="background:#60a5fa"></span>Đo (sau san lấp)</label>
  <h2>Chế độ màu</h2>
  <label><input type="radio" name="che" value="dd" checked>Đào / Đắp (Δz = Đo − Mốc)</label>
  <label><input type="radio" name="che" value="cd">Dải cao độ</label>
  <label><input type="radio" name="che" value="mm">Một màu</label>
  <h2>Hình học</h2>
  <div class="hang">Phóng đại Z<input type="range" id="pdz" min="1" max="10" step="0.5"><span class="gt" id="pdzv"></span></div>
  <div class="hang">Tách lớp (m)<input type="range" id="tach" min="0" max="20" step="0.5" value="0"><span class="gt" id="tachv"></span></div>
  <h2>Hiển thị</h2>
  <label><input type="checkbox" id="vLuoiTin">Lưới TIN (đường tam giác)</label>
  <label><input type="checkbox" id="vThieu" checked>Tô tam giác thiếu dữ liệu</label>
  <label><input type="checkbox" id="vBien" checked>Biên lô</label>
  <label><input type="checkbox" id="vRanh" checked>Ranh đào–đắp</label>
  <label><input type="checkbox" id="vLuoiO">Lưới ô</label>
  <button id="thu" style="margin-top:10px;width:100%">Thu gọn bảng</button>
</div>
<button id="an" class="hop">Bảng điều khiển</button>

<div id="goc" class="hop">
  <button data-v="pc" class="dang">Phối cảnh</button>
  <button data-v="dinh">Đỉnh</button>
  <button data-v="ben">Mặt bên</button>
  <button data-v="dat">Đặt lại</button>
</div>

<div id="chuthich" class="hop"></div>
<div id="sl" class="hop"></div>
<div id="tip" class="hop"></div>
<div id="huongdan">Kéo chuột trái: xoay · Chuột phải / Shift + kéo: dời · Lăn chuột: thu phóng</div>

<script type="application/json" id="du-lieu">__DU_LIEU__</script>
<script>
(function () {
'use strict';
var D = JSON.parse(document.getElementById('du-lieu').textContent);
var $ = function (id) { return document.getElementById(id); };
var cv = $('cv'), ctx = cv.getContext('2d');
var W = 0, H = 0, DPR = 1, dirty = true, mouse = null;

// ---------- định dạng số kiểu Việt Nam (dấu phẩy thập phân)
function f(v, d) { return v.toFixed(d === undefined ? 3 : d).replace('.', ','); }
function fs(v, d) { return (v > 0 ? '+' : v < 0 ? '−' : '') + f(Math.abs(v), d); }

// ---------- dữ liệu bề mặt
function dungBeMat(ten, S, mau) {
  var n = S.p.length, nt = S.t.length, s = {
    ten: ten, mau: mau, n: n, nt: nt,
    X: new Float64Array(n), Y: new Float64Array(n), Z: new Float64Array(n), ZD: new Float64Array(n),
    DZ: new Float64Array(n), T: new Int32Array(nt * 3), L: new Int8Array(nt),
    SX: new Float64Array(n), SY: new Float64Array(n), DEP: new Float64Array(n), OK: new Uint8Array(n),
    sh: new Float32Array(nt), fill: new Array(nt), bad: 0, coDz: !!S.dz
  };
  for (var i = 0; i < n; i++) {
    s.X[i] = S.p[i][0]; s.Y[i] = S.p[i][1]; s.Z[i] = S.p[i][2];
    s.DZ[i] = (S.dz && S.dz[i] !== null) ? S.dz[i] : NaN;
  }
  for (var k = 0; k < nt; k++) {
    s.T[3 * k] = S.t[k][0]; s.T[3 * k + 1] = S.t[k][1]; s.T[3 * k + 2] = S.t[k][2];
    s.L[k] = S.l ? S.l[k] : 0;
    if (s.L[k] !== 0) s.bad++;
  }
  return s;
}
var BM = [dungBeMat('Mốc', D.moc, [74, 222, 128]), dungBeMat('Đo', D['do'], [96, 165, 250])];
var MOC = BM[0], DO = BM[1];

var x0 = 1e30, x1 = -1e30, y0 = 1e30, y1 = -1e30, zs = 0, zn = 0, zmin = 1e30, zmax = -1e30;
BM.forEach(function (s) {
  for (var i = 0; i < s.n; i++) {
    if (s.X[i] < x0) x0 = s.X[i]; if (s.X[i] > x1) x1 = s.X[i];
    if (s.Y[i] < y0) y0 = s.Y[i]; if (s.Y[i] > y1) y1 = s.Y[i];
    if (s.Z[i] < zmin) zmin = s.Z[i]; if (s.Z[i] > zmax) zmax = s.Z[i];
    zs += s.Z[i]; zn++;
  }
});
var zref = zn ? zs / zn : 0, tx = (x0 + x1) / 2, ty = (y0 + y1) / 2;
var dzAbs = [];
for (var i = 0; i < DO.n; i++) { var a = Math.abs(DO.DZ[i]); if (a === a) dzAbs.push(a); }
dzAbs.sort(function (p, q) { return p - q; });
var dzMax = dzAbs.length ? dzAbs[Math.min(dzAbs.length - 1, Math.floor(dzAbs.length * 0.95))] : 0;   // phân vị 95 %: vài đỉnh lạ không làm nhạt cả thang
var LDZ = Math.max(0.5, Math.ceil(dzMax * 2) / 2);   // biên thang màu Δz (m); ngoài biên tô bằng màu biên
var DB = 0.02;                                         // vùng "≈ 0" của Δz (m)

// ---------- trạng thái giao diện
var coMoc = MOC.n > 0 && MOC.nt > 0, coDo = DO.n > 0 && DO.nt > 0;
var st = {
  moc: coMoc || !coDo, do_: coDo, che: (coMoc && coDo) ? 'dd' : 'cd', pdz: D.phong_dai_z, tach: 0,
  luoiTin: (MOC.nt + DO.nt) < 3000, thieu: true, bien: true, ranh: true, luoiO: false
};
var cam = { az: -0.52, el: 0.62, dist: 1, f: 1, px: 0, py: 0, persp: true };
var RAD = 1, anim = null;

// ---------- màu
function lerp(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function theoDai(stops, t) {
  t = Math.max(0, Math.min(1, t));
  for (var i = 1; i < stops.length; i++) if (t <= stops[i][0]) {
    var u = (t - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0] || 1);
    return lerp(stops[i - 1][1], stops[i][1], u);
  }
  return stops[stops.length - 1][1];
}
var CYAN = [34, 211, 238];
var DAP = [[0, CYAN], [.35, [251, 146, 120]], [1, [220, 38, 38]]];
var DAO = [[0, CYAN], [.35, [253, 224, 71]], [1, [217, 119, 6]]];
var CAODO = [[0, [43, 108, 176]], [.25, [56, 178, 172]], [.5, [104, 211, 145]], [.75, [236, 201, 75]], [1, [197, 82, 32]]];
var XAM = [120, 128, 140], THIEU = [112, 44, 56];
function mauDz(dz) {
  if (dz !== dz) return XAM;
  if (Math.abs(dz) <= DB) return CYAN;
  var t = (Math.abs(dz) - DB) / (LDZ - DB);
  return theoDai(dz > 0 ? DAP : DAO, t);
}
function mauCaoDo(z) { return theoDai(CAODO, zmax > zmin ? (z - zmin) / (zmax - zmin) : .5); }

// ---------- hình học hiển thị (phụ thuộc phóng đại Z, tách lớp) và màu từng tam giác
var LUX = (function () { var v = [-0.35, -0.45, 0.82], m = Math.hypot(v[0], v[1], v[2]); return [v[0] / m, v[1] / m, v[2] / m]; })();
function dungLai() {
  BM.forEach(function (s, si) {
    var off = (si === 1) ? st.tach : 0;
    for (var i = 0; i < s.n; i++) s.ZD[i] = (s.Z[i] - zref) * st.pdz + off;
    for (var k = 0; k < s.nt; k++) {
      var a = s.T[3 * k], b = s.T[3 * k + 1], c = s.T[3 * k + 2];
      var ux = s.X[b] - s.X[a], uy = s.Y[b] - s.Y[a], uz = s.ZD[b] - s.ZD[a];
      var vx = s.X[c] - s.X[a], vy = s.Y[c] - s.Y[a], vz = s.ZD[c] - s.ZD[a];
      var nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      var m = Math.hypot(nx, ny, nz) || 1;
      var d = Math.abs((nx * LUX[0] + ny * LUX[1] + nz * LUX[2]) / m);   // hai mặt (DoubleSide)
      s.sh[k] = Math.max(0.3, Math.min(1.15, 0.35 + 0.8 * d));
    }
  });
  tinhMau();
}
function tinhMau() {
  BM.forEach(function (s, si) {
    for (var k = 0; k < s.nt; k++) {
      var a = s.T[3 * k], b = s.T[3 * k + 1], c = s.T[3 * k + 2], rgb;
      if (st.thieu && s.L[k] !== 0) rgb = THIEU;
      else if (st.che === 'dd' && si === 1) rgb = mauDz((s.DZ[a] + s.DZ[b] + s.DZ[c]) / 3);
      else if (st.che === 'cd') rgb = mauCaoDo((s.Z[a] + s.Z[b] + s.Z[c]) / 3);
      else rgb = s.mau;
      var h = s.sh[k];
      s.fill[k] = 'rgb(' + Math.min(255, Math.round(rgb[0] * h)) + ',' + Math.min(255, Math.round(rgb[1] * h)) + ',' +
                  Math.min(255, Math.round(rgb[2] * h)) + ')';
    }
  });
  capNhatChuThich();
  dirty = true;
}

// ---------- khung nhìn
function hinhHoc() {
  var zlo = (zmin - zref) * st.pdz, zhi = (zmax - zref) * st.pdz + (st.do_ ? st.tach : 0);
  var ex = x1 - x0, ey = y1 - y0, ez = Math.max(zhi - zlo, 0);
  RAD = Math.max(0.5 * Math.hypot(ex, ey, ez), 1);
}
// tính độ phóng (f) và độ dời (px, py) để hình vừa khung nhìn ở góc (az, el)
function vuaKhung(az, el, dist) {
  var ca = Math.cos(az), sa = Math.sin(az), ce = Math.cos(el), se = Math.sin(el);
  var tz = st.do_ ? st.tach * 0.5 : 0, a = 1e30, b = -1e30, c = 1e30, d = -1e30, n = 0;
  BM.forEach(function (s, si) {
    if (n && (si === 0 ? !st.moc : !st.do_)) return;
    for (var i = 0; i < s.n; i++) {
      var dx = s.X[i] - tx, dy = s.Y[i] - ty, dz = s.ZD[i] - tz;
      var cx = dx * ca + dy * sa, cy = -dx * sa + dy * ca, up = dz * ce + cy * se;
      if (cx < a) a = cx; if (cx > b) b = cx; if (up < c) c = up; if (up > d) d = up; n++;
    }
  });
  var rx = Math.max(b - a, 1e-6), ry = Math.max(d - c, 1e-6);
  var sc = Math.min(W * 0.86 / rx, H * 0.78 / ry);
  return { f: sc * dist, px: -sc * (a + b) / 2, py: sc * (c + d) / 2 };
}
function datLai(den, nhanh) {
  hinhHoc();
  var dich = { az: -0.52, el: 0.62, dist: RAD * 3.0, persp: true };
  if (den === 'dinh') dich = { az: 0, el: Math.PI / 2, dist: RAD * 3.0, persp: false };
  if (den === 'ben') dich = { az: 0, el: 0.07, dist: RAD * 3.0, persp: false };
  var v = vuaKhung(dich.az, dich.el, dich.dist);
  dich.f = v.f; dich.px = v.px; dich.py = v.py;
  document.querySelectorAll('#goc button[data-v]').forEach(function (b) {
    b.classList.toggle('dang', b.getAttribute('data-v') === (den === 'dat' ? 'pc' : den));
  });
  cam.persp = dich.persp;
  if (nhanh) { for (var k in dich) cam[k] = dich[k]; dirty = true; return; }
  anim = { t0: performance.now(), d: 380,
           tu: { az: cam.az, el: cam.el, px: cam.px, py: cam.py, dist: cam.dist, f: cam.f }, den: dich };
}function buoc(now) {
  if (!anim) return;
  var u = Math.min(1, (now - anim.t0) / anim.d), e = u < .5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
  ['az', 'el', 'px', 'py', 'dist', 'f'].forEach(function (k) { cam[k] = anim.tu[k] + (anim.den[k] - anim.tu[k]) * e; });
  dirty = true;
  if (u >= 1) anim = null;
}

function chieu(s) {
  var ca = Math.cos(cam.az), sa = Math.sin(cam.az), ce = Math.cos(cam.el), se = Math.sin(cam.el);
  var dist = cam.dist, near = dist * 0.04, persp = cam.persp, F = cam.f;
  var tz = st.do_ ? st.tach * 0.5 : 0, cx0 = W / 2 + cam.px, cy0 = H / 2 + cam.py;
  for (var i = 0; i < s.n; i++) {
    var dx = s.X[i] - tx, dy = s.Y[i] - ty, dz = s.ZD[i] - tz;
    var cx = dx * ca + dy * sa, cy = -dx * sa + dy * ca;
    var up = dz * ce + cy * se, dep = cy * ce - dz * se, w = dep + dist;
    s.DEP[i] = dep;
    if (persp && w < near) { s.OK[i] = 0; continue; }
    var sc = persp ? F / w : F / dist;
    s.OK[i] = 1; s.SX[i] = cx0 + cx * sc; s.SY[i] = cy0 - up * sc;
  }
}
// chiếu một điểm bất kỳ (cho lớp phủ); trả về mảng [sx, sy, ok]
var PJ = [0, 0, 0];
function chieuDiem(x, y, z) {
  var ca = Math.cos(cam.az), sa = Math.sin(cam.az), ce = Math.cos(cam.el), se = Math.sin(cam.el);
  var dx = x - tx, dy = y - ty, dz = z - (st.do_ ? st.tach * 0.5 : 0);
  var cx = dx * ca + dy * sa, cy = -dx * sa + dy * ca;
  var up = dz * ce + cy * se, dep = cy * ce - dz * se, w = dep + cam.dist;
  if (cam.persp && w < cam.dist * 0.04) { PJ[2] = 0; return PJ; }
  var sc = cam.persp ? cam.f / w : cam.f / cam.dist;
  PJ[0] = W / 2 + cam.px + cx * sc; PJ[1] = H / 2 + cam.py - up * sc; PJ[2] = 1;
  return PJ;
}

// ---------- vẽ
var KD = new Float64Array(MOC.nt + DO.nt);
var daVe = [];         // [{s, k}] theo thứ tự xa -> gần của khung vừa vẽ
var hover = null;      // {s, k, v}
var ORDER = [];

function zLopPhu(p) {  // p = [x, y, zMoc, zDo]
  if (st.do_ && p[3] !== null) return (p[3] - zref) * st.pdz + st.tach;
  if (p[2] !== null) return (p[2] - zref) * st.pdz;
  return p[3] !== null ? (p[3] - zref) * st.pdz : 0;
}
function veDuong(ds, mau, rong, khep, nhoMo) {
  ctx.strokeStyle = mau; ctx.lineWidth = rong; ctx.lineJoin = 'round';
  if (nhoMo) ctx.setLineDash(nhoMo);
  for (var i = 0; i < ds.length; i++) {
    var pl = ds[i], bd = false;
    ctx.beginPath();
    for (var j = 0; j < pl.length; j++) {
      var q = chieuDiem(pl[j][0], pl[j][1], zLopPhu(pl[j]));
      if (!q[2]) { bd = false; continue; }
      if (!bd) { ctx.moveTo(q[0], q[1]); bd = true; } else ctx.lineTo(q[0], q[1]);
    }
    if (khep && bd) ctx.closePath();
    ctx.stroke();
  }
  if (nhoMo) ctx.setLineDash([]);
}

function veTamGiac(s, k) {
  var a = s.T[3 * k], b = s.T[3 * k + 1], c = s.T[3 * k + 2];
  ctx.beginPath();
  ctx.moveTo(s.SX[a], s.SY[a]); ctx.lineTo(s.SX[b], s.SY[b]); ctx.lineTo(s.SX[c], s.SY[c]); ctx.closePath();
}

function render() {
  dirty = false;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  var g = ctx.createRadialGradient(W / 2, H * 0.45, 10, W / 2, H * 0.45, Math.max(W, H) * 0.75);
  g.addColorStop(0, '#131b2a'); g.addColorStop(1, '#0b0f17');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

  var ds = [], kd = KD;             // ds: mã tam giác (Mốc: 0…, Đo: từ MOC.nt); kd: độ sâu trung bình
  BM.forEach(function (s, si) {
    if (si === 0 ? !st.moc : !st.do_) return;
    chieu(s);
    var SX = s.SX, SY = s.SY, OK = s.OK, T = s.T, DEP = s.DEP;
    for (var k = 0; k < s.nt; k++) {
      var a = T[3 * k], b = T[3 * k + 1], c = T[3 * k + 2];
      if (!(OK[a] && OK[b] && OK[c])) continue;
      var xa = SX[a], xb = SX[b], xc = SX[c], ya = SY[a], yb = SY[b], yc = SY[c];
      if ((xa < 0 && xb < 0 && xc < 0) || (xa > W && xb > W && xc > W) ||
          (ya < 0 && yb < 0 && yc < 0) || (ya > H && yb > H && yc > H)) continue;
      var id = si ? MOC.nt + k : k;
      ds.push(id); kd[id] = (DEP[a] + DEP[b] + DEP[c]) / 3;
    }
  });
  ds.sort(function (p, q) { return kd[q] - kd[p]; });       // xa trước, gần sau
  daVe = ds;

  var vien = st.luoiTin, boNet = !vien && ds.length > 5000;  // nhiều tam giác: bỏ nét lấp khe cho mượt
  ctx.lineJoin = 'round';
  if (vien) { ctx.strokeStyle = 'rgba(6,10,18,.55)'; ctx.lineWidth = 0.6; }
  else ctx.lineWidth = 0.7;
  for (var i = 0; i < ds.length; i++) {
    var s = ds[i] >= MOC.nt ? DO : MOC, k = ds[i] >= MOC.nt ? ds[i] - MOC.nt : ds[i];
    var a = s.T[3 * k], b = s.T[3 * k + 1], c = s.T[3 * k + 2];
    ctx.beginPath();
    ctx.moveTo(s.SX[a], s.SY[a]); ctx.lineTo(s.SX[b], s.SY[b]); ctx.lineTo(s.SX[c], s.SY[c]); ctx.closePath();
    ctx.fillStyle = s.fill[k]; ctx.fill();
    if (vien) ctx.stroke();
    else if (!boNet) { ctx.strokeStyle = s.fill[k]; ctx.stroke(); }   // lấp khe răng cưa giữa các tam giác
  }
  // lớp phủ
  if (st.luoiO) veDuong(D.luoi, 'rgba(226,232,240,.38)', 0.8, false);
  if (st.bien) {
    veDuong(D.bien, '#f8fafc', 1.8, true);
    veDuong(D.loai_tru, '#f472b6', 1.5, true, [5, 3]);
  }
  if (st.ranh) veDuong(D.ranh, '#e879f9', 1.6, false);

  // chọn điểm dưới con trỏ (từ gần ra xa)
  hover = null;
  if (mouse && !keo) {
    for (var j = ds.length - 1; j >= 0; j--) {
      var s2 = ds[j] >= MOC.nt ? DO : MOC, k2 = ds[j] >= MOC.nt ? ds[j] - MOC.nt : ds[j];
      var a = s2.T[3 * k2], b = s2.T[3 * k2 + 1], c = s2.T[3 * k2 + 2];
      var ax = s2.SX[a], ay = s2.SY[a], bx = s2.SX[b], by = s2.SY[b], cx = s2.SX[c], cy = s2.SY[c];
      var den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy);
      if (Math.abs(den) < 1e-9) continue;
      var l1 = ((by - cy) * (mouse.x - cx) + (cx - bx) * (mouse.y - cy)) / den;
      var l2 = ((cy - ay) * (mouse.x - cx) + (ax - cx) * (mouse.y - cy)) / den;
      var l3 = 1 - l1 - l2;
      if (l1 < 0 || l2 < 0 || l3 < 0) continue;
      var vs = [a, b, c], ls = [l1, l2, l3], best = -1, bd = 10;
      for (var m = 0; m < 3; m++) {
        var dd = Math.hypot(s2.SX[vs[m]] - mouse.x, s2.SY[vs[m]] - mouse.y);
        if (dd < bd) { bd = dd; best = m; }
      }
      hover = { s: s2, k: k2, v: best >= 0 ? vs[best] : -1, l: ls, vs: vs };
      break;
    }
  }
  if (hover) {
    veTamGiac(hover.s, hover.k);
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.6; ctx.stroke();
    if (hover.v >= 0) {
      ctx.beginPath(); ctx.arc(hover.s.SX[hover.v], hover.s.SY[hover.v], 4.5, 0, 6.2832);
      ctx.fillStyle = '#fde047'; ctx.fill(); ctx.strokeStyle = '#0b0f17'; ctx.lineWidth = 1.5; ctx.stroke();
    }
  }
  veLaBan();
  hienTip();
}

function veLaBan() {   // mũi tên hướng Bắc, góc dưới bên phải phía trên khung số liệu
  var cx = W - 40, cy = H - 92, L = 22, sa = Math.sin(cam.az), ca = Math.cos(cam.az), se = Math.sin(cam.el);
  var dx = sa * L, dy = -ca * se * L;
  ctx.save();
  ctx.strokeStyle = '#94a3b8'; ctx.fillStyle = '#94a3b8'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(cx, cy, L + 6, 0, 6.2832); ctx.globalAlpha = .35; ctx.stroke(); ctx.globalAlpha = 1;
  ctx.strokeStyle = '#f87171'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + dx, cy + dy); ctx.stroke();
  ctx.fillStyle = '#f87171'; ctx.font = '600 11px Segoe UI, Arial'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText('B', cx + dx * 1.35, cy + dy * 1.35);
  ctx.restore();
}

// ---------- tooltip
var tip = $('tip');
function hienTip() {
  if (!hover || keo) { tip.style.display = 'none'; return; }
  var s = hover.s, t = [], k = hover.k;
  var e0 = D.goc[0], n0 = D.goc[1];
  if (hover.v >= 0) {
    var v = hover.v;
    t.push('<b>' + s.ten + '</b> · đỉnh #' + v);
    t.push('E ' + f(e0 + s.X[v]) + '   N ' + f(n0 + s.Y[v]));
    t.push('Cao độ z = <b>' + f(s.Z[v]) + '</b> m');
    if (s === DO) {
      var dz = s.DZ[v];
      t.push(dz === dz ? 'Δz = <b>' + fs(dz) + '</b> m (' + (Math.abs(dz) <= DB ? '≈ 0' : dz > 0 ? 'đắp' : 'đào') + ')'
                       : 'Δz: ngoài vùng Mốc');
    }
  } else {
    var a = s.T[3 * k], b = s.T[3 * k + 1], c = s.T[3 * k + 2], l = hover.l;
    var ex = l[0] * s.X[a] + l[1] * s.X[b] + l[2] * s.X[c];
    var ey = l[0] * s.Y[a] + l[1] * s.Y[b] + l[2] * s.Y[c];
    var ez = l[0] * s.Z[a] + l[1] * s.Z[b] + l[2] * s.Z[c];
    t.push('<b>' + s.ten + '</b> · tam giác #' + k);
    t.push('E ' + f(e0 + ex) + '   N ' + f(n0 + ey));
    t.push('Cao độ z = <b>' + f(ez) + '</b> m');
    if (s === DO) {
      var da = s.DZ[a], db = s.DZ[b], dc = s.DZ[c];
      if (da === da && db === db && dc === dc) {
        var dz2 = l[0] * da + l[1] * db + l[2] * dc;
        t.push('Δz = <b>' + fs(dz2) + '</b> m (' + (Math.abs(dz2) <= DB ? '≈ 0' : dz2 > 0 ? 'đắp' : 'đào') + ')');
      }
    }
    if (s.L[k] !== 0) t.push('<span style="color:#fca5a5">Tam giác thiếu dữ liệu (loại ' + s.L[k] + ')</span>');
  }
  tip.innerHTML = t.join('\n');
  tip.style.display = 'block';
  var tw = tip.offsetWidth, th = tip.offsetHeight;
  var px = mouse.x + 16, py = mouse.y + 16;
  if (px + tw > W - 8) px = mouse.x - tw - 16;
  if (py + th > H - 8) py = mouse.y - th - 16;
  tip.style.left = Math.max(4, px) + 'px'; tip.style.top = Math.max(4, py) + 'px';
}

// ---------- chú giải & số liệu
function gradCss(fn, n) {
  var cs = [];
  for (var i = 0; i <= n; i++) { var c = fn(i / n); cs.push('rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ') ' + Math.round(100 * i / n) + '%'); }
  return 'linear-gradient(90deg,' + cs.join(',') + ')';
}
function chip(rgb, nhan) {
  return '<span><i class="mau" style="background:rgb(' + rgb.join(',') + ')"></i>' + nhan + '</span>';
}
function capNhatChuThich() {
  var h = '';
  if (st.che === 'dd') {
    h += '<div class="ten">Δz = z Đo − z Mốc (m) · đào ← 0 → đắp (thang theo phân vị 95 %)</div>';
    h += '<div class="thang" style="background:' + gradCss(function (u) { var z = (u * 2 - 1) * LDZ; return mauDz(z); }, 24) + '"></div>';
    h += '<div class="nhan"><span>' + fs(-LDZ, 2) + ' (đào)</span><span>0</span><span>' + fs(LDZ, 2) + ' (đắp)</span></div>';
    h += '<div class="dong">' + chip(XAM, 'Ngoài vùng Mốc') + chip(MOC.mau, 'Mốc (một màu)') + '</div>';
  } else if (st.che === 'cd') {
    h += '<div class="ten">Cao độ z (m)</div>';
    h += '<div class="thang" style="background:' + gradCss(function (u) { return theoDai(CAODO, u); }, 12) + '"></div>';
    h += '<div class="nhan"><span>' + f(zmin, 2) + '</span><span>' + f((zmin + zmax) / 2, 2) + '</span><span>' + f(zmax, 2) + '</span></div>';
  } else {
    h += '<div class="ten">Một màu theo bề mặt</div>';
    h += '<div class="dong">' + chip(MOC.mau, 'Mốc') + chip(DO.mau, 'Đo') + '</div>';
  }
  if (st.thieu && (MOC.bad || DO.bad)) h += '<div class="dong">' + chip(THIEU, 'Tam giác thiếu dữ liệu') + '</div>';
  $('chuthich').innerHTML = h;
}
function capNhatSoLieu() {
  var h = '';
  h += '<div><b>Mốc</b>: ' + MOC.n + ' đỉnh · ' + MOC.nt + ' tam giác' + (MOC.bad ? ' (' + MOC.bad + ' thiếu)' : '') + '</div>';
  h += '<div><b>Đo</b>: ' + DO.n + ' đỉnh · ' + DO.nt + ' tam giác' + (DO.bad ? ' (' + DO.bad + ' thiếu)' : '') + '</div>';
  var lo = 1e30, hi = -1e30, c = 0;
  for (var i = 0; i < DO.n; i++) { var v = DO.DZ[i]; if (v === v) { c++; if (v < lo) lo = v; if (v > hi) hi = v; } }
  if (c) h += '<div>Δz tại đỉnh Đo: ' + fs(lo, 2) + ' … ' + fs(hi, 2) + ' m</div>';
  h += '<div>Cao độ z: ' + f(zmin, 2) + ' … ' + f(zmax, 2) + ' m · đơn vị: m</div>';
  $('sl').innerHTML = h;
  $('lylich').textContent = 'Lô ' + D.ma_lo + ' · đợt ' + D.dot + (D.hash ? ' · #' + D.hash : '');
}

// ---------- điều khiển
function nap() {
  st.moc = $('hMoc').checked; st.do_ = $('hDo').checked;
  st.che = document.querySelector('input[name=che]:checked').value;
  st.pdz = parseFloat($('pdz').value); st.tach = parseFloat($('tach').value);
  $('pdzv').textContent = '×' + f(st.pdz, 1); $('tachv').textContent = f(st.tach, 1);
  st.luoiTin = $('vLuoiTin').checked; st.thieu = $('vThieu').checked;
  st.bien = $('vBien').checked; st.ranh = $('vRanh').checked; st.luoiO = $('vLuoiO').checked;
  dungLai();
}
$('pdz').value = st.pdz; $('vLuoiTin').checked = st.luoiTin;
$('hMoc').checked = st.moc; $('hDo').checked = st.do_;
document.querySelectorAll('input[name=che]').forEach(function (e) { e.checked = (e.value === st.che); });
['hMoc', 'hDo', 'pdz', 'tach', 'vLuoiTin', 'vThieu', 'vBien', 'vRanh', 'vLuoiO'].forEach(function (id) {
  $(id).addEventListener('input', nap);
});
document.querySelectorAll('input[name=che]').forEach(function (e) { e.addEventListener('change', nap); });
document.querySelectorAll('#goc button[data-v]').forEach(function (b) {
  b.addEventListener('click', function () { datLai(b.getAttribute('data-v')); });
});
$('thu').addEventListener('click', function () { $('bang').style.display = 'none'; $('an').style.display = 'block'; $('chuthich').style.left = '12px'; });
$('an').addEventListener('click', function () { $('bang').style.display = ''; $('an').style.display = 'none'; $('chuthich').style.left = ''; });

var keo = null;
cv.addEventListener('contextmenu', function (e) { e.preventDefault(); });
cv.addEventListener('mousedown', function (e) {
  keo = { x: e.clientX, y: e.clientY, pan: e.button !== 0 || e.shiftKey };
  anim = null; cv.classList.add('keo'); e.preventDefault();
});
window.addEventListener('mousemove', function (e) {
  var r = cv.getBoundingClientRect();
  mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
  if (keo) {
    var dx = e.clientX - keo.x, dy = e.clientY - keo.y;
    keo.x = e.clientX; keo.y = e.clientY;
    if (keo.pan) { cam.px += dx; cam.py += dy; }
    else { cam.az -= dx * 0.006; cam.el = Math.max(0, Math.min(Math.PI / 2, cam.el + dy * 0.006)); cam.persp = cam.persp; }
    document.querySelectorAll('#goc button[data-v]').forEach(function (b) { b.classList.remove('dang'); });
  }
  dirty = true;
});
window.addEventListener('mouseup', function () { keo = null; cv.classList.remove('keo'); dirty = true; });
cv.addEventListener('mouseleave', function () { mouse = null; dirty = true; });
cv.addEventListener('wheel', function (e) {
  e.preventDefault();
  var k = e.deltaY > 0 ? 1.1 : 1 / 1.1, d = cam.dist * k;
  cam.dist = Math.max(RAD * 0.15, Math.min(RAD * 25, d));
  anim = null; dirty = true;
}, { passive: false });
window.addEventListener('resize', batDau);

function batDau() {
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  W = cv.clientWidth; H = cv.clientHeight;
  cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  dirty = true;
}

if (window.innerWidth < 700) { $('thu').click(); }   // màn hẹp: gọn bảng điều khiển ngay từ đầu
hinhHoc();
batDau();
capNhatSoLieu();
nap();
datLai('pc', true);
(function vong(now) {
  buoc(now || 0);
  if (dirty) render();
  requestAnimationFrame(vong);
})();
window.__xem3d = { cam: cam, st: st, thongKe: function () { return { moc: [MOC.n, MOC.nt], do_: [DO.n, DO.nt], ve: daVe.length }; } };
})();
</script>
</body>
</html>
"""
