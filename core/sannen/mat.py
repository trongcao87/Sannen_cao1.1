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


def vong_loai_tru(lot: Lot) -> list[list[tuple[float, float]]]:
    return [[(c[0], c[1]) for c in f["geometry"]["coordinates"][0]]
            for f in doc_geojson(lot.process_dir / "exclude.geojson")]


def cat_tin_theo_bien(tin: Tin, bien: list[list[tuple[float, float]]],
                      loai_tru: list[list[tuple[float, float]]] | None = None) -> int:
    """Loại bỏ các tam giác nằm hoàn toàn ngoài phạm vi đường bao `bien` (hoặc nằm trọn trong vùng loại trừ `loai_tru`).
    Giữ lại các tam giác có ít nhất một phần giao với phạm vi đường bao để không làm hở mép TIN sát biên lô.
    Trả về số tam giác đã loại bỏ."""
    if not bien:
        return 0
    from .geom import cat_loi, dien_tich_co_dau
    goc = tin.goc
    b_loc = []
    for v in bien:
        if len(v) >= 3:
            pts = [goc.vao(e, n) for e, n in v]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                b_loc.append(pts if dien_tich_co_dau(pts) >= 0 else pts[::-1])
    if not b_loc:
        return 0
    lt_loc = []
    for v in (loai_tru or []):
        if len(v) >= 3:
            pts = [goc.vao(e, n) for e, n in v]
            if len(pts) > 1 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                lt_loc.append(pts if dien_tich_co_dau(pts) >= 0 else pts[::-1])
    giu_t: list[tuple[int, int, int]] = []
    giu_l: list[int] = []
    bo = 0
    for idx, (a, b, c) in enumerate(tin.tris):
        tri = [(tin.x[a], tin.y[a]), (tin.x[b], tin.y[b]), (tin.x[c], tin.y[c])]
        if dien_tich_co_dau(tri) < 0:
            tri = tri[::-1]
        dt_trong = sum(dien_tich_co_dau(cat_loi(v, tri)) for v in b_loc)
        if lt_loc and dt_trong > 1e-9:
            dt_trong -= sum(dien_tich_co_dau(cat_loi(v, tri)) for v in lt_loc)
        if dt_trong > 1e-9:
            giu_t.append((a, b, c))
            giu_l.append(tin.loai[idx])
        else:
            bo += 1
    if bo > 0 and giu_t:
        tin.tris = giu_t
        tin.loai = giu_l
        tin._ban_do = None
    return bo if giu_t else 0


def kiem_hash_dau_vao(lot: Lot) -> dict:
    """So hash file nguồn với lúc `nhap` ghi nhận. Lệch thì dừng."""
    qi = lot.process_dir / "qc_input.json"
    if not qi.exists():
        raise DauVaoDaDoi("Chưa có qc_input.json — chạy `nhap` trước.")
    d = io_out.doc_json(qi)
    for ten, nguon in d.get("nguon", {}).items():
        if not nguon or nguon.get("file") == "chua_khai_bao" or nguon.get("nguon") == "chua_khai_bao":
            continue
        f_str = str(nguon["file"])
        p = Path(f_str)
        if not p.is_absolute():
            for cand in (lot.input_dir / f_str, lot.root / f_str, lot.process_dir / Path(f_str).name):
                if cand.is_file():
                    p = cand.resolve()
                    break
            else:
                p = lot.input_dir / f_str
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
    if be_mat == "ca-hai":
        nhan_list = [n for n in ("moc", "do") if len(diem[n]) >= 3]
        if not nhan_list:
            raise TinLoi("Chưa có bề mặt nào có đủ 3 điểm — hãy chọn tọa độ trên CAD hoặc import từ Excel trước.")
    else:
        if len(diem[be_mat]) < 3:
            ten_bm = "MHTN (mặt gốc)" if be_mat == "moc" else "MHTK (mặt thiết kế)"
            raise TinLoi(f"Chưa có dữ liệu tọa độ điểm cho {ten_bm} — hãy bấm «Lấy tọa độ trên CAD» hoặc «Import từ Excel» cho {ten_bm} trước khi Tạo TIN!")
    # MỘT gốc chung cho cả hai bề mặt (lấy từ tất cả các bề mặt đã có điểm)
    all_pts = [(p.easting, p.northing) for n in diem for p in diem[n]]
    goc = Goc.trong_tam(all_pts)
    bien = vong_ngoai(lot)
    loai_tru = vong_loai_tru(lot)

    phat_hien: list[dict] = []
    thong_ke: dict = {}
    tin_ra: dict[str, Tin] = {}
    for n in nhan_list:
        tin, bc = dung_be_mat(lot, cfg, n, goc, ng, diem[n])
        # Khi người dùng chọn phạm vi đường bao từ AutoCAD (nguon=cad_chon) hoặc khai cat_tin_theo_bien: true,
        # lưới tam giác TIN chỉ giữ các tam giác nằm trong/chạm phạm vi đường bao.
        bien_cfg = cfg.get("bien_lo") or {}
        cat_bien = bool(cfg.get("cat_tin_theo_bien", False) or bien_cfg.get("nguon") in ("cad_chon", "json"))
        so_ngoai_bien = cat_tin_theo_bien(tin, bien, loai_tru) if (bien and cat_bien) else 0
        if so_ngoai_bien > 0:
            # Lọc lại danh sách thiếu dữ liệu và tam giác dẹt nằm ngoài đường bao đã cắt
            b_loc = [[goc.vao(*q) for q in v] for v in bien if len(v) >= 3]
            lt_loc = [[goc.vao(*q) for q in v] for v in loai_tru if len(v) >= 3]
            trong_vung = lambda vt: (any(trong_da_giac(goc.vao(*vt), v) for v in b_loc)
                                     and not any(trong_da_giac(goc.vao(*vt), v) for v in lt_loc))
            bc.thieu_du_lieu = [x for x in bc.thieu_du_lieu if trong_vung(x["vi_tri"])]
            bc.det_trong = [x for x in bc.det_trong if trong_vung(x["vi_tri"])]
        tin_ra[n] = tin
        thong_ke[n] = {k: getattr(bc, k) for k in
                       ("so_diem_vao", "so_diem", "so_gop", "lech_gop_max_m", "khoang_cach_tb_m",
                        "so_dut_gay", "so_doan_ep")}
        thong_ke[n].update({"so_tam_giac": len(tin.tris),
                            "so_tam_giac_rac_loai": len(bc.rac),
                            "so_tam_giac_ngoai_bien_loai": so_ngoai_bien,
                            "so_tam_giac_det": len(bc.det_trong),
                            "so_tam_giac_thieu_du_lieu": len(bc.thieu_du_lieu),
                            "dien_tich_phu_m2": round(sum(tin.dien_tich_tam_giac(i)
                                                          for i in range(len(tin.tris))), 3)})
        phat_hien += phat_hien_be_mat(n, bc, bien, goc)
        print(f"Mặt {n:3s}: {bc.so_diem_vao} điểm → {bc.so_diem} đỉnh, {len(tin.tris)} tam giác"
              + (f" (đã cắt bỏ {so_ngoai_bien} tam giác ngoài đường bao)" if so_ngoai_bien else "")
              + f", {bc.so_doan_ep} đoạn đứt gãy ép, gộp {bc.so_gop} điểm trùng, "
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
