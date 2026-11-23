"""CLI — một verb, ba lối gọi (AutoCAD, CLI, MCP) cho cùng một kết quả.

    python -m sannen.cli <verb> --lot <thư mục lô>

Giai đoạn 0: `nhap` đã chạy thật. Sáu verb còn lại là khung, báo rõ giai đoạn nào cài.
"""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .paths import Lot
from .config import doc_lot, nguong, ThieuKhaiBao
from . import dxfio, qc, io_out

VERBS = ("nhap", "mat", "lo", "luoi", "hieuchinh", "tinh", "xuat")
CHUA_CAI = {"mat": 2, "lo": 3, "luoi": 4, "hieuchinh": 4, "tinh": 5, "xuat": 6}


def _log(lot: Lot, ban_ghi: dict) -> None:
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    p = lot.log_dir / f"run_{datetime.now(timezone.utc):%Y-%m-%dT%H%M}.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")


def verb_nhap(lot: Lot, cfg: dict, preview: bool) -> int:
    ng = nguong(cfg)
    dxfs = sorted(lot.input_dir.glob("*.dxf"))
    if not dxfs:
        print(f"Không thấy file .dxf nào trong {lot.input_dir}")
        print("Hãy xuất DXF từ AutoCAD và đặt vào đó (SPEC mục 13: đầu vào là DXF).")
        return 2
    t0 = time.perf_counter()
    d = dxfio.doc(dxfs[0], cung_tron_sai_so_mm=ng["cung_tron_sai_so_mm"])
    giay = time.perf_counter() - t0

    print(f"DXF   {d.dxf.name}  ({d.acad})   đọc trong {giay:.3f} s")
    print(f"Layer {', '.join(d.layers) or '(không có layer SN-)'}")
    print(f"Điểm  mốc {len(d.diem_moc)}   đo {len(d.diem_do)}")
    print(f"Biên  {len(d.bien_lo)} biên lô, {len(d.loai_tru)} vùng loại trừ, "
          f"{len(d.dut_gay)} đứt gãy, {len(d.dong_muc)} đường đồng mức")
    for b in d.bien_lo:
        print(f"      biên lô: {len(b.dinh)} đỉnh, khép kín={b.khep_kin}, "
              f"diện tích {b.dien_tich_m2:,.3f} m²")

    phat_hien = qc.kiem_tra(d.diem_moc, ng, "bề mặt mốc") + \
                qc.kiem_tra(d.diem_do, ng, "bề mặt đo")
    for b in d.bien_lo:
        if not b.khep_kin:
            phat_hien.append({"ma": "V-BL", "loai": "bien_khong_khep", "muc": "chan",
                              "mo_ta": "Biên lô không khép kín — mọi phép tính diện tích sai dấu"})
    chan = [p for p in phat_hien if p["muc"] == "chan"]

    if preview:
        print(f"\n-- XEM TRƯỚC (RULES 4). Sẽ ghi 6 file vào {lot.process_dir}")
        print(f"-- Phát hiện: {len(phat_hien)} việc, trong đó {len(chan)} việc chặn")
        print("-- Chạy lại không có --preview để ghi.")
        return 1 if chan else 0

    lot.ensure()
    sinh_tu = {"dxf": d.dxf.name, "hash": d.hash_sha256,
               "cung_tron_sai_so_mm": ng["cung_tron_sai_so_mm"]}
    io_out.ghi_points(lot, "points_moc.csv", d.diem_moc)
    io_out.ghi_points(lot, "points_do.csv", d.diem_do)
    io_out.ghi_geojson(lot, "breaklines.geojson",
                       [io_out.feature_dut_gay(x) for x in d.dut_gay],
                       {**sinh_tu, "layer": "SN-DUTGAY"})
    io_out.ghi_geojson(lot, "boundary.geojson",
                       [io_out.feature_bao(b, "bien_lo") for b in d.bien_lo],
                       {**sinh_tu, "layer": "SN-BIENLO"})
    io_out.ghi_geojson(lot, "exclude.geojson",
                       [io_out.feature_bao(b, "loai_tru") for b in d.loai_tru],
                       {**sinh_tu, "layer": "SN-LOAITRU"})
    io_out.ghi_json(lot, "qc_input.json",
                    {"verb": "nhap", "nguong_da_dung": ng, "phat_hien": phat_hien})
    io_out.ghi_viec_can_lam(lot, "nhap", phat_hien)
    _log(lot, {"verb": "nhap", "luc": datetime.now(timezone.utc).isoformat(),
               "phien_ban_loi": __version__, "dxf": d.dxf.name,
               "hash_sha256": d.hash_sha256,
               "so_diem": {"moc": len(d.diem_moc), "do": len(d.diem_do)},
               "so_phat_hien": len(phat_hien)})

    print(f"\nĐã ghi 6 file vào {lot.process_dir}")
    print(f"Việc cần làm: {len(phat_hien)} ({len(chan)} chặn) — xem viec_can_lam.md")
    return 1 if chan else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sannen", description=__doc__)
    ap.add_argument("verb", choices=VERBS)
    ap.add_argument("--lot", required=True, type=Path, help="Thư mục lô")
    ap.add_argument("--preview", action="store_true",
                    help="Chỉ báo sẽ làm gì, không ghi (mặc định của agent)")
    a = ap.parse_args(argv)

    lot = Lot(a.lot.expanduser().resolve())
    if not lot.root.is_dir():
        print(f"Không thấy thư mục lô: {lot.root}")
        return 2
    try:
        cfg = doc_lot(lot.lot_yaml)
    except ThieuKhaiBao as e:
        print(f"RULES 7 — dừng: {e}")
        return 2

    print(f"Lô {cfg['ma_lo']}  đợt {cfg['dot']}  "
          f"phương pháp nộp: {cfg['phuong_phap_chinh_thuc']}  (lõi {__version__})")
    if a.verb == "nhap":
        return verb_nhap(lot, cfg, a.preview)

    gd = CHUA_CAI[a.verb]
    print(f"Verb `{a.verb}` chưa cài đặt — thuộc giai đoạn {gd} của lộ trình.")
    print(f"Đọc _agent/skills/{a.verb}/SKILL.md để biết nó phải làm gì.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
