"""Đọc DXF headless — không mở AutoCAD, không cần license.

Kiểm chứng 23/11/2026: 1.017 điểm + biên + đứt gãy + đồng mức đọc hết trong 0,04 s.
DWG thì không đọc trực tiếp được: đổi DWG -> DXF bằng ODA File Converter trước.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

import ezdxf
from ezdxf import path as ezpath

LAYER_NGUON = {
    "SN-DIEM-MOC": "diem_moc",
    "SN-DIEM-DO": "diem_do",
    "SN-DUTGAY": "dut_gay",
    "SN-DONGMUC": "dong_muc",
    "SN-BIENLO": "bien_lo",
    "SN-LOAITRU": "loai_tru",
}
LAYER_KET_QUA = (
    "SN-LUOI", "SN-LUOI-NHAN", "SN-LUOI-O", "SN-RANH-DAODAP",
    "SN-3DF-MOC", "SN-3DF-DO", "SN-QC", "SN-BANG", "SN-MATCAT",
)


class LoiBien(Exception):
    """Biên lô người khai không xác định được duy nhất. DỪNG, không đoán (RULES 7)."""


class LayerLa(Exception):
    """Gặp layer SN- không có trong quy ước. HỎI, không đoán (RULES 6)."""


@dataclass
class Diem:
    id: str
    northing: float
    easting: float
    z: float
    code: str = ""
    nguon: str = ""   # vị trí trong file gốc, vd "Sheet1!hàng 12" — để QS tra lại đúng dòng


@dataclass
class DuongBao:
    dinh: list[tuple[float, float]]
    khep_kin: bool
    dien_tich_m2: float


@dataclass
class DocDuoc:
    dxf: Path
    hash_sha256: str
    acad: str
    layers: list[str] = field(default_factory=list)
    diem_moc: list[Diem] = field(default_factory=list)
    diem_do: list[Diem] = field(default_factory=list)
    dut_gay: list[list[tuple[float, float, float]]] = field(default_factory=list)
    bien_lo: list[DuongBao] = field(default_factory=list)
    loai_tru: list[DuongBao] = field(default_factory=list)
    dong_muc: list[tuple[float, list[tuple[float, float]]]] = field(default_factory=list)


def _hash(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def dien_tich(dinh: list[tuple[float, float]]) -> float:
    """Shoelace. Giá trị tuyệt đối — chiều chuẩn hóa ở bước sau."""
    s = 0.0
    n = len(dinh)
    for i in range(n):
        x1, y1 = dinh[i]
        x2, y2 = dinh[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def bung_bulge(pts: list[tuple[float, float, float]], dong: bool,
               sai_so_m: float) -> list[tuple[float, float]]:
    """Bung các cạnh có bulge của LWPOLYLINE thành đoạn thẳng, GIỮ NGUYÊN DIỆN TÍCH.

    Đỉnh giữa của mỗi cung đặt ở bán kính ρ = r·√(Δθ/sinΔθ) để đa giác có đúng diện tích
    hình quạt; hai đầu cung giữ đúng toạ độ gốc. Độ lệch hình học tối đa so với cung thật
    ≤ `sai_so_m`. Cách thường dùng (đỉnh nằm trên đường tròn, hoặc Bézier của ezdxf) đều
    lệch diện tích cỡ 4s/(3r), có thể vượt ngưỡng 0,01 % so với lệnh AREA.
    """
    import math
    n = len(pts)
    ra: list[tuple[float, float]] = []
    for i in range(n):
        x1, y1, b = pts[i]
        if i == n - 1 and not dong:
            ra.append((x1, y1))
            break
        x2, y2, _ = pts[(i + 1) % n]
        ra.append((x1, y1))
        if b == 0.0:
            continue
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L == 0.0:
            continue
        theta = 4.0 * math.atan(b)                       # góc ở tâm, có dấu
        r = L / (2.0 * abs(math.sin(theta / 2.0)))
        h = (L / 2.0) / math.tan(theta / 2.0)
        cx, cy = (x1 + x2) / 2.0 - dy / L * h, (y1 + y2) / 2.0 + dx / L * h
        phi0 = math.atan2(y1 - cy, x1 - cx)
        dmax = 2.0 * math.acos(max(-1.0, 1.0 - sai_so_m / r)) if sai_so_m < r else math.pi / 2
        so_doan = max(2, math.ceil(abs(theta) / max(dmax, 1e-6)))
        d = abs(theta) / so_doan
        rho = r * math.sqrt(d / math.sin(d))
        for k in range(1, so_doan):
            a = phi0 + theta * k / so_doan
            ra.append((cx + rho * math.cos(a), cy + rho * math.sin(a)))
    return ra


def _bung_cung(e, sai_so_m: float) -> list[tuple[float, float]]:
    """Bung bulge thành đoạn thẳng.

    BẮT BUỘC: bỏ qua bulge gây lệch tới 9,5% diện tích (đo 23/11/2026).
    LWPOLYLINE tự bung (bảo toàn diện tích); loại khác nhờ ezdxf.
    """
    if e.dxftype() == "LWPOLYLINE":
        return bung_bulge([(p[0], p[1], p[2]) for p in e.get_points("xyb")],
                          bool(e.closed), sai_so_m)
    try:
        pts = [(p.x, p.y) for p in ezpath.make_path(e).flattening(sai_so_m)]
    except Exception:
        pts = [(p[0], p[1]) for p in e.get_points()]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def doc_bien_polyline(dxf_path: Path, layer: str, so_dinh: int, cung_tron_sai_so_mm: float = 5.0) -> DuongBao:
    """Biên lô = đa tuyến KHÉP KÍN trên `layer` có đúng `so_dinh` đỉnh (đếm trên bản vẽ gốc, trước khi bung cung).

    Dùng khi bản vẽ nhà thầu chưa gán layer SN-BIENLO và agent không được sửa 00_input. Phải khớp
    ĐÚNG MỘT đa tuyến; 0 hoặc nhiều hơn thì dừng và nói rõ có những ứng viên nào.
    """
    if not Path(dxf_path).is_file():
        raise LoiBien(f"Không thấy {dxf_path}")
    msp = ezdxf.readfile(dxf_path).modelspace()
    ung = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer == layer]
    khop = [e for e in ung if e.closed and len(e) == so_dinh]
    if len(khop) != 1:
        co = ", ".join(f"{len(e)} đỉnh" + (" khép kín" if e.closed else "") for e in ung) or "không có đa tuyến nào"
        raise LoiBien(f"Khai biên lô = đa tuyến khép kín {so_dinh} đỉnh trên layer «{layer}» của {Path(dxf_path).name}, "
                      f"nhưng tìm thấy {len(khop)} đa tuyến như vậy. Ứng viên trên layer này: {co}.")
    pts = _bung_cung(khop[0], cung_tron_sai_so_mm / 1000.0)
    return DuongBao(pts, True, dien_tich(pts))


def _doc_diem_tu_msp(msp, layer: str, prefix: str) -> list[Diem]:
    """Đọc POINT, INSERT và TEXT (có giá trị số) trên một layer của modelspace."""
    ds: list[Diem] = []
    i = 0
    for e in msp.query("POINT"):
        if e.dxf.layer != layer:
            continue
        i += 1
        loc = e.dxf.location
        ds.append(Diem(f"{prefix}-{i:05d}", loc.y, loc.x, loc.z))
    for e in msp.query("INSERT"):
        if e.dxf.layer != layer:
            continue
        i += 1
        loc = e.dxf.insert
        ds.append(Diem(f"{prefix}-{i:05d}", loc.y, loc.x, loc.z, "block"))
    for e in msp.query("TEXT"):
        if e.dxf.layer != layer:
            continue
        try:
            z = float(str(e.dxf.text).strip())
        except ValueError:
            continue
        i += 1
        loc = e.dxf.insert
        ds.append(Diem(f"{prefix}-{i:05d}", loc.y, loc.x, z, "text"))
    for e in msp.query("LINE"):
        if e.dxf.layer != layer:
            continue
        for pt in (e.dxf.start, e.dxf.end):
            i += 1
            ds.append(Diem(f"{prefix}-{i:05d}", pt.y, pt.x, pt.z, "line"))
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer != layer:
            continue
        elev = float(getattr(e.dxf, "elevation", 0.0) or 0.0)
        for pt in e.get_points():
            i += 1
            ds.append(Diem(f"{prefix}-{i:05d}", float(pt[1]), float(pt[0]), elev, "pline2d"))
    for e in msp.query("POLYLINE"):
        if e.dxf.layer != layer or getattr(e, "is_poly_face_mesh", False):
            continue
        for v in e.vertices:
            loc = v.dxf.location
            i += 1
            ds.append(Diem(f"{prefix}-{i:05d}", loc.y, loc.x, loc.z, "pline3d"))
    return ds


def doc_dut_gay_json(json_path: Path) -> tuple[list[list[tuple[float, float, float]]], str]:
    """Đọc danh sách đường đứt gãy (breakline) 3D người dùng chọn trực tiếp trong AutoCAD (ghi ra JSON)."""
    import json
    if not Path(json_path).is_file():
        raise LoiBien(f"Không thấy file đứt gãy {json_path}")
    raw = json.loads(Path(json_path).read_text(encoding="utf-8-sig"))
    ds_in = raw if isinstance(raw, list) else raw.get("dut_gay", [])
    ra: list[list[tuple[float, float, float]]] = []
    for duong in ds_in:
        if len(duong) >= 2:
            ra.append([(float(p[0]), float(p[1]), float(p[2])) for p in duong])
    return ra, _hash(Path(json_path))


def doc_bien_json(json_path: Path, cung_tron_sai_so_mm: float = 5.0) -> tuple[list[DuongBao], str]:
    """Đọc biên lô (hoặc vùng loại trừ) người dùng chọn trực tiếp bằng nút lệnh trong AutoCAD (ghi ra JSON)."""
    import json
    if not Path(json_path).is_file():
        raise LoiBien(f"Không thấy file biên lô {json_path}")
    raw = json.loads(Path(json_path).read_text(encoding="utf-8-sig"))
    vongs = raw if isinstance(raw, list) else raw.get("vong", [])
    sai_so_m = cung_tron_sai_so_mm / 1000.0
    ra: list[DuongBao] = []
    for item in vongs:
        pts_raw = item if isinstance(item, list) else item.get("dinh", [])
        khep = True if isinstance(item, list) else bool(item.get("khep_kin", True))
        if not pts_raw:
            continue
        if len(pts_raw) >= 3:
            khep = True
        co_bulge = any(len(p) >= 3 and float(p[2]) != 0.0 for p in pts_raw)
        if co_bulge:
            pts = bung_bulge([(float(p[0]), float(p[1]), float(p[2]) if len(p) >= 3 else 0.0) for p in pts_raw],
                             khep, sai_so_m)
        else:
            pts = [(float(p[0]), float(p[1])) for p in pts_raw]
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts = pts[:-1]
        ra.append(DuongBao(pts, khep, dien_tich(pts)))
    if not ra:
        raise LoiBien(f"File biên lô {Path(json_path).name} không có đa tuyến hợp lệ.")
    return ra, _hash(Path(json_path))


def doc_diem_layer(dxf_path: Path, layer: str, prefix: str) -> tuple[list[Diem], str]:
    """Đọc danh sách điểm từ một file DXF và layer chỉ định (khi khai file + layer riêng)."""
    doc_ = ezdxf.readfile(dxf_path)
    msp = doc_.modelspace()
    if layer in ("*", "ALL", ""):
        ds: list[Diem] = []
        for l in sorted(ly.dxf.name for ly in doc_.layers if not ly.dxf.name.upper().startswith("SN-")):
            ds.extend(_doc_diem_tu_msp(msp, l, prefix))
        for i, p in enumerate(ds, 1):
            p.id = f"{prefix}-{i:05d}"
        return ds, _hash(dxf_path)
    return _doc_diem_tu_msp(msp, layer, prefix), _hash(dxf_path)


def _trich_luoi_tu_doan(doan: list[tuple[float, float, float, float]], tol_m: float = 0.05) -> dict:
    """Từ danh sách đoạn thẳng (x1, y1, x2, y2) của lưới ô vuông/chữ nhật → nhận diện gốc lưới, góc xoay, cột (cot_m), hàng (hang_m)."""
    import math
    if len(doan) < 2:
        raise LoiBien("Cần ít nhất 2 đường lưới (cột và hàng) để nhận diện lưới từ CAD/DXF.")
    # Tìm góc chủ đạo (trong [0, pi/2)) từ các đoạn dài nhất
    dai_ds = sorted(((math.hypot(x2 - x1, y2 - y1), x1, y1, x2, y2) for x1, y1, x2, y2 in doan), reverse=True)
    if dai_ds[0][0] < 1e-3:
        raise LoiBien("Các đoạn lưới quá ngắn.")
    _, x1, y1, x2, y2 = dai_ds[0]
    ang = math.atan2(y2 - y1, x2 - x1) % (math.pi / 2.0)
    if abs(ang - math.pi / 2.0) < 1e-4:
        ang = 0.0
    c, s = math.cos(ang), math.sin(ang)

    u_lines: list[float] = []
    v_lines: list[float] = []
    u_pts: list[float] = []
    v_pts: list[float] = []
    for l, ax, ay, bx, by in dai_ds:
        if l < 1e-3:
            continue
        u1, v1 = c * ax + s * ay, -s * ax + c * ay
        u2, v2 = c * bx + s * by, -s * bx + c * by
        u_pts.extend((u1, u2))
        v_pts.extend((v1, v2))
        du, dv = abs(u2 - u1), abs(v2 - v1)
        if dv <= max(tol_m, 0.02 * l) and du > dv:       # đường ngang (hàng): v gần hằng số
            v_lines.append((v1 + v2) / 2.0)
        elif du <= max(tol_m, 0.02 * l) and dv > du:     # đường dọc (cột): u gần hằng số
            u_lines.append((u1 + u2) / 2.0)

    def gom_moc(vals: list[float]) -> list[float]:
        if not vals:
            return []
        sv = sorted(vals)
        ra = [sv[0]]
        for v in sv[1:]:
            if v - ra[-1] > tol_m:
                ra.append(v)
            else:
                ra[-1] = (ra[-1] + v) / 2.0
        return ra

    us = gom_moc(u_lines)
    vs = gom_moc(v_lines)
    if len(us) < 2 or len(vs) < 2:
        # Dự phòng khi lưới vẽ bằng các ô chữ nhật rời (LWPOLYLINE 4 đỉnh): gom mọi toạ độ đỉnh
        us = gom_moc(u_pts)
        vs = gom_moc(v_pts)
    if len(us) < 2 or len(vs) < 2:
        raise LoiBien(f"Không nhận diện đủ cột và hàng từ dữ liệu lưới (tìm thấy {len(us)} đường dọc, {len(vs)} đường ngang).")
    cot_m = [round(us[i + 1] - us[i], 4) for i in range(len(us) - 1) if us[i + 1] - us[i] > tol_m]
    hang_m = [round(vs[j + 1] - vs[j], 4) for j in range(len(vs) - 1) if vs[j + 1] - vs[j] > tol_m]
    u0, v0 = us[0], vs[0]
    e0, n0 = c * u0 - s * v0, s * u0 + c * v0
    from collections import Counter
    kt_pho_bien = Counter(cot_m + hang_m).most_common(1)[0][0]
    return {"goc_luoi": [round(e0, 4), round(n0, 4)], "goc_xoay_do": round(math.degrees(ang), 4),
            "cot_m": cot_m, "hang_m": hang_m, "kich_thuoc_o_m": kt_pho_bien,
            "nx": len(cot_m), "ny": len(hang_m)}


def doc_luoi_dxf(path: Path, layer: str | None = None) -> dict:
    """Import thông số lưới ô vuông/chữ nhật từ file DXF hoặc file JSON đoạn thẳng do AutoCAD xuất."""
    import json
    p = Path(path)
    if not p.is_file():
        raise LoiBien(f"Không thấy file lưới: {p}")
    if p.suffix.lower() == ".json":
        raw = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict) and "cot_m" in raw and "hang_m" in raw:
            return raw
        doan_in = raw if isinstance(raw, list) else raw.get("doan", [])
        doan = [(float(d[0]), float(d[1]), float(d[2]), float(d[3])) for d in doan_in if len(d) >= 4]
        return _trich_luoi_tu_doan(doan)
    doc_ = ezdxf.readfile(p)
    msp = doc_.modelspace()
    # Nếu không chỉ định layer: ưu tiên layer SN-LUOI / LUOI, nếu không có thì đọc tất cả LINE/LWPOLYLINE
    if not layer or layer in ("*", "ALL"):
        ten_ly = {ly.dxf.name.upper(): ly.dxf.name for ly in doc_.layers}
        chon_ly = None
        for k in ("SN-LUOI", "LUOI", "GRID"):
            if k in ten_ly:
                chon_ly = ten_ly[k]
                break
    else:
        chon_ly = layer
    doan: list[tuple[float, float, float, float]] = []
    for e in msp.query("LINE"):
        if chon_ly and e.dxf.layer.upper() != chon_ly.upper():
            continue
        doan.append((float(e.dxf.start.x), float(e.dxf.start.y), float(e.dxf.end.x), float(e.dxf.end.y)))
    for e in msp.query("LWPOLYLINE"):
        if chon_ly and e.dxf.layer.upper() != chon_ly.upper():
            continue
        pts = [(float(pt[0]), float(pt[1])) for pt in e.get_points()]
        if e.closed and len(pts) >= 3:
            pts.append(pts[0])
        for a, b in zip(pts, pts[1:]):
            doan.append((a[0], a[1], b[0], b[1]))
    return _trich_luoi_tu_doan(doan)


def doc(dxf_path: Path, cung_tron_sai_so_mm: float = 5.0,
        cho_phep_layer_la: bool = False) -> DocDuoc:
    doc_ = ezdxf.readfile(dxf_path)
    msp = doc_.modelspace()
    sai_so_m = cung_tron_sai_so_mm / 1000.0

    sn = sorted(l.dxf.name for l in doc_.layers if l.dxf.name.upper().startswith("SN-"))
    la = [n for n in sn
          if n.upper() not in LAYER_NGUON
          and not any(n.upper().startswith(k) for k in LAYER_KET_QUA)]
    if la and not cho_phep_layer_la:
        raise LayerLa(
            "Layer SN- không có trong quy ước: " + ", ".join(la)
            + ". Hỏi người dùng vai trò của chúng (RULES 6)."
        )

    kq = DocDuoc(dxf=dxf_path, hash_sha256=_hash(dxf_path),
                 acad=str(doc_.acad_release), layers=sn)

    kq.diem_moc.extend(_doc_diem_tu_msp(msp, "SN-DIEM-MOC", "DIEM-MOC"))
    kq.diem_do.extend(_doc_diem_tu_msp(msp, "SN-DIEM-DO", "DIEM-DO"))

    for e in msp.query('POLYLINE[layer=="SN-DUTGAY"]'):
        kq.dut_gay.append([(v.dxf.location.x, v.dxf.location.y, v.dxf.location.z)
                           for v in e.vertices])
    for e in msp.query('LINE[layer=="SN-DUTGAY"]'):
        s, t = e.dxf.start, e.dxf.end
        kq.dut_gay.append([(s.x, s.y, s.z), (t.x, t.y, t.z)])

    for layer, gan in (("SN-BIENLO", kq.bien_lo), ("SN-LOAITRU", kq.loai_tru)):
        for e in msp.query(f'LWPOLYLINE[layer=="{layer}"]'):
            pts = _bung_cung(e, sai_so_m)
            gan.append(DuongBao(pts, bool(e.closed), dien_tich(pts)))

    for e in msp.query('LWPOLYLINE[layer=="SN-DONGMUC"]'):
        kq.dong_muc.append((float(e.dxf.elevation),
                            [(p[0], p[1]) for p in e.get_points()]))

    return kq
