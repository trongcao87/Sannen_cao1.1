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

    for layer, gan in (("SN-DIEM-MOC", kq.diem_moc), ("SN-DIEM-DO", kq.diem_do)):
        i = 0
        for e in msp.query(f'POINT[layer=="{layer}"]'):
            i += 1
            loc = e.dxf.location
            gan.append(Diem(f"{layer[3:]}-{i:05d}", loc.y, loc.x, loc.z))
        for e in msp.query(f'INSERT[layer=="{layer}"]'):
            i += 1
            loc = e.dxf.insert
            gan.append(Diem(f"{layer[3:]}-{i:05d}", loc.y, loc.x, loc.z, "block"))
        for e in msp.query(f'TEXT[layer=="{layer}"]'):
            try:
                z = float(str(e.dxf.text).strip())
            except ValueError:
                continue
            i += 1
            loc = e.dxf.insert
            gan.append(Diem(f"{layer[3:]}-{i:05d}", loc.y, loc.x, z, "text"))

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
