"""Verb `mat` — dựng hai bề mặt TIN (giai đoạn 2). Đọc 10_process do `nhap` sinh ra."""
from __future__ import annotations
import csv
import json
from pathlib import Path

from . import io_out, qc
from .bang_in import bam_sha256
from .config import nguong
from .dxfio import Diem
from .geom import Goc, trong_da_giac
from .paths import Lot
from .tin import Tin, TinLoi, dung_tin


class DauVaoDaDoi(Exception):
    """Đầu vào đổi sau khi `nhap` chạy. Dừng và chạy lại `nhap` (RULES — Nguồn sự thật)."""


def doc_points(p: Path) -> list[Diem]:
    if not p.exists():
        raise TinLoi(f"Không thấy {p.name}. Chạy `nhap` trước.")
    with p.open(encoding="utf-8", newline="") as f:
        return [Diem(r["id"], float(r["northing"]), float(r["easting"]), float(r["z"]),
                     r.get("code", "")) for r in csv.DictReader(f)]


def doc_geojson(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("features", [])


def vong_ngoai(lot: Lot) -> list[list[tuple[float, float]]]:
    return [[(c[0], c[1]) for c in f["geometry"]["coordinates"][0]]
            for f in doc_geojson(lot.process_dir / "boundary.geojson")]


def kiem_hash_dau_vao(lot: Lot) -> dict:
    """So hash file nguồn với lúc `nhap` ghi nhận. Lệch thì dừng."""
    qi = lot.process_dir / "qc_input.json"
    if not qi.exists():
        raise DauVaoDaDoi("Chưa có qc_input.json — chạy `nhap` trước.")
    d = io_out.doc_json(qi)
    for ten, nguon in d.get("nguon", {}).items():
        if not nguon:
            continue
        p = lot.input_dir / nguon["file"]
        if not p.exists():
            p = lot.root / nguon["file"]
        if not p.exists() or bam_sha256(p) != nguon["hash_sha256"]:
            raise DauVaoDaDoi(f"{nguon['file']} đã thay đổi hoặc mất kể từ lần `nhap` gần nhất "
                              "— chạy lại `nhap` rồi duyệt lại (RULES: nguồn sự thật là file trong 00_input).")
    return d


def _ap_dung_dut_gay(cfg: dict, nhan: str) -> bool:
    ap = cfg.get("dut_gay_ap_dung", ["moc", "do"])
    return nhan in ap if isinstance(ap, list) else bool(ap)


def dung_be_mat(lot: Lot, cfg: dict, nhan: str, goc: Goc, ng: dict, diem: list[Diem]):
    dut_gay = []
    if _ap_dung_dut_gay(cfg, nhan):
        for f in doc_geojson(lot.process_dir / "breaklines.geojson"):
            dut_gay.append([(c[0], c[1], c[2]) for c in f["geometry"]["coordinates"]])
    return dung_tin(goc, [(p.easting, p.northing, p.z) for p in diem], dut_gay,
                    tol_trung_m=ng["trung_mat_bang_mm"] / 1000.0,
                    giao_dutgay_cm=ng["giao_dutgay_cm"], goc_det_do=ng["goc_tam_giac_det_do"],
                    lon_boi=ng["tam_giac_lon_boi"])


def phat_hien_be_mat(nhan: str, bc, bien: list, goc: Goc) -> list[dict]:
    ra: list[dict] = []
    ten = {"moc": "bề mặt mốc", "do": "bề mặt đo"}[nhan]
    for x in bc.xung_dot:
        chan = x["loai"] == "dut_gay_cat_nhau_lech_cao"
        mo_ta = (f"{ten}: hai đứt gãy cắt nhau nhưng cao độ lệch "
                 f"({x['z_duong_1']} so {x['z_duong_2']} m) — mâu thuẫn dữ liệu, không tự chọn"
                 if chan else
                 f"{ten}: đỉnh đứt gãy trùng điểm đo nhưng lệch cao độ "
                 f"({x['z_diem_do']} so {x['z_dut_gay']} m). TIN dùng cao độ điểm đo")
        ra.append(qc._phat_hien("", x["loai"], "chan" if chan else "canh_bao", mo_ta,
                                vi_tri=x["vi_tri"],
                                lua_chon=["(a) sửa đứt gãy trong bản vẽ rồi xuất DXF lại",
                                          "(b) hỏi lại đơn vị khảo sát"],
                                he_qua="mặt TIN gấp sai chỗ, kéo theo khối lượng quanh đó"))
    for x in bc.det_trong[:20]:
        ra.append(qc._phat_hien(
            "", "tam_giac_det", "canh_bao",
            f"{ten}: tam giác dẹt trong vùng dữ liệu, góc nhỏ nhất {x['goc_min_do']}°",
            vi_tri=x["vi_tri"],
            lua_chon=["(a) giữ — điểm đo đúng như vậy", "(b) yêu cầu đo bổ sung"],
            he_qua="nội suy trên tam giác gần suy biến khuếch đại sai số"))
    if len(bc.det_trong) > 20:
        ra.append(qc._phat_hien("", "tam_giac_det", "canh_bao",
                                f"{ten}: còn {len(bc.det_trong) - 20} tam giác dẹt nữa chưa liệt kê"))
    if bc.rac:
        ra.append(qc._phat_hien(
            "", "tam_giac_rac_o_mep", "thong_tin",
            f"{ten}: loại {len(bc.rac)} tam giác dẹt ở mép TIN (rác). Dải đó coi như chưa có dữ liệu."))
    trong_bien = []
    for x in bc.thieu_du_lieu:
        e, n = x["vi_tri"]
        p = goc.vao(e, n)
        if any(trong_da_giac(p, [goc.vao(*q) for q in v]) for v in bien):
            trong_bien.append(x)
    ngoai = len(bc.thieu_du_lieu) - len(trong_bien)
    for x in trong_bien[:20]:
        ra.append(qc._phat_hien(
            "", "thieu_du_lieu", "canh_bao",
            f"{ten}: vùng thiếu dữ liệu TRONG biên lô — tam giác cạnh dài {x['canh_dai_m']} m, "
            f"{x['dien_tich_m2']} m²",
            vi_tri=x["vi_tri"],
            lua_chon=["(a) yêu cầu đo bổ sung", "(b) người chấp nhận nội suy và ghi vào decisions.md"],
            he_qua="RULES 8: không tính khối lượng ở đây; ô lưới chạm vùng này bị loại khỏi số nộp"))
    if len(trong_bien) > 20:
        ra.append(qc._phat_hien("", "thieu_du_lieu", "canh_bao",
                                f"{ten}: còn {len(trong_bien) - 20} vùng thiếu dữ liệu nữa trong biên"))
    if ngoai:
        ra.append(qc._phat_hien("", "thieu_du_lieu_ngoai_bien", "thong_tin",
                                f"{ten}: {ngoai} tam giác quá lớn nằm ngoài biên lô — không ảnh hưởng"))
    return ra


def chay(lot: Lot, cfg: dict, be_mat: str, preview: bool) -> int:
    ng = nguong(cfg)
    qi = kiem_hash_dau_vao(lot)
    nhan_list = ["moc", "do"] if be_mat == "ca-hai" else [be_mat]
    diem = {n: doc_points(lot.process_dir / f"points_{n}.csv") for n in ("moc", "do")}
    # MỘT gốc chung cho cả hai bề mặt: mọi bước sau dùng đúng gốc này
    goc = Goc.trong_tam([(p.easting, p.northing) for n in diem for p in diem[n]])
    bien = vong_ngoai(lot)

    phat_hien: list[dict] = []
    thong_ke: dict = {}
    tin_ra: dict[str, Tin] = {}
    for n in nhan_list:
        tin, bc = dung_be_mat(lot, cfg, n, goc, ng, diem[n])
        tin_ra[n] = tin
        thong_ke[n] = {k: getattr(bc, k) for k in
                       ("so_diem_vao", "so_diem", "so_gop", "lech_gop_max_m", "khoang_cach_tb_m",
                        "so_dut_gay", "so_doan_ep")}
        thong_ke[n].update({"so_tam_giac": len(tin.tris),
                            "so_tam_giac_rac_loai": len(bc.rac),
                            "so_tam_giac_det": len(bc.det_trong),
                            "so_tam_giac_thieu_du_lieu": len(bc.thieu_du_lieu),
                            "dien_tich_phu_m2": round(sum(tin.dien_tich_tam_giac(i)
                                                          for i in range(len(tin.tris))), 3)})
        phat_hien += phat_hien_be_mat(n, bc, bien, goc)
        print(f"Mặt {n:3s}: {bc.so_diem_vao} điểm → {bc.so_diem} đỉnh, {len(tin.tris)} tam giác, "
              f"{bc.so_doan_ep} đoạn đứt gãy ép, gộp {bc.so_gop} điểm trùng, "
              f"loại {len(bc.rac)} rác, {len(bc.det_trong)} dẹt, {len(bc.thieu_du_lieu)} thiếu dữ liệu")
    qc.danh_ma(phat_hien, "M")
    chan = [p for p in phat_hien if p["muc"] == "chan"]
    viec = [p for p in phat_hien if p["muc"] != "thong_tin"]

    if preview:
        print(f"\n-- XEM TRƯỚC (RULES 4). Sẽ ghi surface_*.json, qc_surface.json, viec_can_lam.md")
        print(f"-- Phát hiện: {len(viec)} việc, {len(chan)} chặn")
        return 1 if chan else 0

    lot.ensure()
    for n, tin in tin_ra.items():
        d = tin.to_dict()
        d.update({"be_mat": n, "sinh_tu": {"hash_dau_vao": qi.get("hash_dau_vao"),
                                           "nguong": {k: ng[k] for k in
                                                      ("trung_mat_bang_mm", "giao_dutgay_cm",
                                                       "goc_tam_giac_det_do", "tam_giac_lon_boi")}},
                  "thong_ke": thong_ke[n]})
        io_out.ghi_json(lot, f"surface_{n}.json", d)
    io_out.ghi_json(lot, "qc_surface.json", {"verb": "mat", "thong_ke": thong_ke,
                                             "hash_dau_vao": qi.get("hash_dau_vao"),
                                             "phat_hien": phat_hien})
    io_out.ghi_viec_gop(lot, "mat + lo (cổng 2)", ["qc_surface.json", "qc_lo.json"])
    print(f"\nĐã ghi surface_*.json, qc_surface.json. Việc cần làm: {len(viec)} ({len(chan)} chặn)")
    return 1 if chan else 0
