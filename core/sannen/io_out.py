"""Ghi file dẫn xuất vào 10_process/. Mọi file đi kèm truy vết nguồn."""
from __future__ import annotations
import csv, json
from pathlib import Path
from .dxfio import DocDuoc, Diem, DuongBao
from .paths import Lot

COT = ["id", "northing", "easting", "z", "code"]


def ghi_points(lot: Lot, ten: str, diem: list[Diem]) -> Path:
    p = lot.process_dir / ten
    lot.guard_write(p)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COT)
        for d in diem:
            w.writerow([d.id, f"{d.northing:.4f}", f"{d.easting:.4f}",
                        f"{d.z:.4f}", d.code])
    return p


def _feature(geom_type, coords, props):
    return {"type": "Feature",
            "geometry": {"type": geom_type, "coordinates": coords},
            "properties": props}


def ghi_geojson(lot: Lot, ten: str, features: list[dict], sinh_tu: dict) -> Path:
    p = lot.process_dir / ten
    lot.guard_write(p)
    p.write_text(json.dumps(
        {"type": "FeatureCollection", "sinh_tu": sinh_tu, "features": features},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def feature_dut_gay(duong: list[tuple[float, float, float]]) -> dict:
    return _feature("LineString", [[round(x, 4), round(y, 4), round(z, 4)]
                                   for x, y, z in duong],
                    {"vai_tro": "dut_gay", "so_dinh": len(duong)})


def feature_bao(b: DuongBao, vai_tro: str) -> dict:
    vong = [[round(x, 4), round(y, 4)] for x, y in b.dinh]
    if vong and vong[0] != vong[-1]:
        vong.append(vong[0])
    return _feature("Polygon", [vong],
                    {"vai_tro": vai_tro, "khep_kin": b.khep_kin,
                     "so_dinh": len(b.dinh), "dien_tich_m2": round(b.dien_tich_m2, 4)})


def ghi_json(lot: Lot, ten: str, data: dict) -> Path:
    p = lot.process_dir / ten
    lot.guard_write(p)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def ghi_viec_can_lam(lot: Lot, verb: str, phat_hien: list[dict]) -> Path:
    """Phiếu việc cần làm (SPEC mục 13). Người trả lời gọn bằng mã: V-01 a, V-02 b."""
    p = lot.process_dir / "viec_can_lam.md"
    lot.guard_write(p)
    d = [f"# Việc cần làm — sau verb `{verb}`", ""]
    if not phat_hien:
        d.append("Không có việc nào. Dữ liệu qua hết các phép kiểm.")
    for v in phat_hien:
        d.append(f"## {v['ma']}  ·  {v['loai']}  ·  {v['muc']}")
        d.append(v["mo_ta"])
        if v.get("vi_tri"):
            d.append(f"- Vị trí: {' / '.join(str(x) for x in v['vi_tri'])}")
        for lc in v.get("lua_chon", []):
            d.append(f"- Chọn: {lc}")
        if v.get("he_qua_neu_bo_qua"):
            d.append(f"- Bỏ qua: {v['he_qua_neu_bo_qua']}")
        d.append("")
    p.write_text("\n".join(d), encoding="utf-8")
    return p
