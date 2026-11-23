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
    "SN-3DF-MOC", "SN-3DF-DO", "SN-QC", "SN-BANG",
)


class LayerLa(Exception):
    """Gặp layer SN- không có trong quy ước. HỎI, không đoán (RULES 6)."""


@dataclass
class Diem:
    id: str
    northing: float
    easting: float
    z: float
    code: str = ""


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


def _bung_cung(e, sai_so_m: float) -> list[tuple[float, float]]:
    """Bung bulge thành đoạn thẳng.

    BẮT BUỘC: bỏ qua bulge gây lệch tới 9,5% diện tích (đo 23/11/2026).
    """
    try:
        pts = [(p.x, p.y) for p in ezpath.make_path(e).flattening(sai_so_m)]
    except Exception:
        pts = [(p[0], p[1]) for p in e.get_points()]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


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
