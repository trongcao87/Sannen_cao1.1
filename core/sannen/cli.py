"""CLI — một verb, ba lối gọi (AutoCAD, CLI, MCP) cho cùng một kết quả.

    python -m sannen.cli <verb> --lot <thư mục lô>

Giai đoạn 0: `nhap` đã chạy thật. Sáu verb còn lại là khung, báo rõ giai đoạn nào cài.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .paths import Lot
from .config import doc_lot, nguong, ThieuKhaiBao
from . import bang_in, dxfio, qc, io_out, lo, luoi, mat, tin, tinh, xem3d, xuat

VERBS = ("nhap", "mat", "lo", "luoi", "hieuchinh", "tinh", "xuat", "xem3d")
CHUA_CAI: dict[str, int] = {}


def _log(lot: Lot, ban_ghi: dict) -> None:
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    p = lot.log_dir / f"run_{datetime.now(timezone.utc):%Y-%m-%dT%H%M}.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")


LAYER_BE_MAT = {"moc": "SN-DIEM-MOC", "do": "SN-DIEM-DO"}


def _nap_be_mat(cfg: dict, nhan: str, d: "dxfio.DocDuoc | None", preview: bool,
                xac_nhan: bool, lot: Lot):
    """Một bề mặt, theo nguồn lot.yaml khai: dxf_layer | excel | csv.

    Trả về (điểm, kết quả bảng hoặc None). Nguồn lạ thì dừng — không đoán (RULES 7).
    """
    ch = cfg[f"be_mat_{nhan}"]
    nguon = ch.get("nguon", "dxf_layer")
    if nguon == "dxf_layer":
        if d is None:
            raise bang_in.LoiNguon(
                f"be_mat_{nhan} lấy từ DXF nhưng 00_input/ không có file .dxf nào.")
        layer = ch.get("layer", LAYER_BE_MAT[nhan])
        if layer.upper() != LAYER_BE_MAT[nhan]:
            raise bang_in.LoiNguon(
                f"be_mat_{nhan}.layer = {layer} khác quy ước {LAYER_BE_MAT[nhan]} "
                "(kb/layer-convention.md). Đổi tên layer trong bản vẽ, đừng đổi quy ước.")
        return (d.diem_moc if nhan == "moc" else d.diem_do), None
    if nguon in ("excel", "csv"):
        kq = bang_in.doc_bang(lot, ch, cfg, nhan, xac_nhan=xac_nhan, ghi=not preview)
        return kq.diem, kq
    raise bang_in.LoiNguon(f"be_mat_{nhan}.nguon = {nguon} chưa cài đặt "
                           "(nguồn hợp lệ ở giai đoạn 1: dxf_layer, excel, csv).")


def _mo_ta_bang(nhan: str, kq: "bang_in.KetQuaBang") -> None:
    print(f"Bảng  {nhan}: {kq.file.name}  sheet «{kq.sheet}»  hàng tiêu đề {kq.hang_tieu_de}  "
          f"{kq.so_khoi} khối/dòng")
    print(f"      ánh xạ cột ({kq.nguon_anh_xa}): "
          + ", ".join(f"{t}=«{v}»" for t, v in kq.anh_xa.items()))
    print(f"      đọc {len(kq.diem)} điểm, {kq.so_dong_hong} dòng hỏng, "
          f"{kq.so_hang_khong_phai_du_lieu} dòng chữ bỏ qua")


def verb_nhap(lot: Lot, cfg: dict, preview: bool, xac_nhan: bool = False) -> int:
    ng = nguong(cfg)
    dxfs = sorted(lot.input_dir.glob("*.dxf"))
    t0 = time.perf_counter()
    # Biên lô có thể do NGƯỜI khai trong lot.yaml là một đa tuyến cụ thể của bản vẽ nhà thầu (chưa gán layer SN-)
    # — agent không được ghi layer vào 00_input (RULES 3), nên người chỉ ra đúng đa tuyến nào, lõi đọc nguyên trạng.
    bien_cfg = cfg.get("bien_lo")
    can_dxf = any(cfg[f"be_mat_{n}"].get("nguon", "dxf_layer") == "dxf_layer" for n in ("moc", "do"))
    d = (dxfio.doc(dxfs[0], cung_tron_sai_so_mm=ng["cung_tron_sai_so_mm"])
         if dxfs and (can_dxf or not bien_cfg) else None)
    bien_khai = None
    if bien_cfg:
        if bien_cfg.get("nguon") != "dxf_polyline" or not bien_cfg.get("file"):
            raise bang_in.LoiNguon("lot.yaml: bien_lo cần {nguon: dxf_polyline, file, layer, so_dinh}")
        bien_khai = dxfio.doc_bien_polyline(lot.input_dir / bien_cfg["file"], str(bien_cfg.get("layer", "0")),
                                            int(bien_cfg["so_dinh"]), ng["cung_tron_sai_so_mm"])
        print(f"Biên  do người khai: đa tuyến {bien_cfg['so_dinh']} đỉnh, layer «{bien_cfg.get('layer', '0')}» "
              f"của {bien_cfg['file']}: {bien_khai.dien_tich_m2:,.3f} m² (khép kín={bien_khai.khep_kin})")

    if d is not None:
        print(f"DXF   {d.dxf.name}  ({d.acad})")
        print(f"Layer {', '.join(d.layers) or '(không có layer SN-)'}")
        print(f"Biên  {len(d.bien_lo)} biên lô, {len(d.loai_tru)} vùng loại trừ, "
              f"{len(d.dut_gay)} đứt gãy, {len(d.dong_muc)} đường đồng mức")
        for b in d.bien_lo:
            print(f"      biên lô: {len(b.dinh)} đỉnh, khép kín={b.khep_kin}, "
                  f"diện tích {b.dien_tich_m2:,.3f} m²")

    diem_moc, bang_moc = _nap_be_mat(cfg, "moc", d, preview, xac_nhan, lot)
    diem_do, bang_do = _nap_be_mat(cfg, "do", d, preview, xac_nhan, lot)
    for nhan, kq in (("mốc", bang_moc), ("đo", bang_do)):
        if kq is not None:
            _mo_ta_bang(nhan, kq)
    print(f"Điểm  mốc {len(diem_moc)}   đo {len(diem_do)}   "
          f"(đọc xong trong {time.perf_counter() - t0:.2f} s)")

    hd = cfg.get("he_toa_do", "")
    phat_hien = [p for kq in (bang_moc, bang_do) if kq for p in kq.phat_hien]
    phat_hien += qc.kiem_tra(diem_moc, ng, "bề mặt mốc", hd) + \
                 qc.kiem_tra(diem_do, ng, "bề mặt đo", hd)
    if d is None and bien_khai is None:
        phat_hien.append({"loai": "thieu_dxf", "muc": "canh_bao",
                          "mo_ta": "Không có file .dxf: chưa có biên lô, đứt gãy, vùng loại trừ "
                                   "— các verb `mat` và `lo` sẽ không chạy được.",
                          "lua_chon": ["(a) xuất DXF biên lô từ AutoCAD vào 00_input/"]})
    else:
        for b in (d.bien_lo if d else []) + ([bien_khai] if bien_khai else []):
            if not b.khep_kin:
                phat_hien.append({"loai": "bien_khong_khep", "muc": "chan",
                                  "mo_ta": "Biên lô không khép kín — mọi phép tính diện tích sai dấu"})
    qc.danh_ma(phat_hien)
    viec = [p for p in phat_hien if p["muc"] != "thong_tin"]
    chan = [p for p in phat_hien if p["muc"] == "chan"]

    if preview:
        print(f"\n-- XEM TRƯỚC (RULES 4). Sẽ ghi 7 file vào {lot.process_dir}")
        print(f"-- Phát hiện: {len(viec)} việc, trong đó {len(chan)} việc chặn")
        for p in chan:
            print(f"--   {p['ma']} {p['mo_ta']}")
        print("-- Chạy lại không có --preview để ghi.")
        return 1 if chan else 0

    lot.ensure()
    nguon_in = {"dxf": ({"file": d.dxf.name, "hash_sha256": d.hash_sha256} if d else None)}
    if bien_khai is not None:
        nguon_in["bien_lo"] = {"file": bien_cfg["file"],
                               "hash_sha256": bang_in.bam_sha256(lot.input_dir / bien_cfg["file"]),
                               "layer": str(bien_cfg.get("layer", "0")), "so_dinh": int(bien_cfg["so_dinh"])}
    for nhan, kq in (("moc", bang_moc), ("do", bang_do)):
        if kq is not None:
            nguon_in[f"be_mat_{nhan}"] = {
                "file": kq.file.name, "hash_sha256": kq.hash_sha256, "sheet": kq.sheet,
                "hang_tieu_de": kq.hang_tieu_de, "anh_xa_cot": kq.anh_xa,
                "nguon_anh_xa": kq.nguon_anh_xa, "dau_van_tay": kq.dau_van_tay,
                "so_diem": len(kq.diem), "so_dong_hong": kq.so_dong_hong}
    hash_dau_vao = hashlib.sha256("|".join(sorted(
        v["hash_sha256"] for v in nguon_in.values() if v)).encode()).hexdigest()
    sinh_tu = {"nguon": nguon_in, "hash_dau_vao": hash_dau_vao,
               "cung_tron_sai_so_mm": ng["cung_tron_sai_so_mm"]}
    io_out.ghi_points(lot, "points_moc.csv", diem_moc)
    io_out.ghi_points(lot, "points_do.csv", diem_do)
    dut_gay, bien_lo, loai_tru = (d.dut_gay, d.bien_lo, d.loai_tru) if d else ([], [], [])
    if bien_khai is not None:
        bien_lo = [bien_khai]                        # biên do người khai thay cho layer SN-BIENLO
    io_out.ghi_geojson(lot, "breaklines.geojson",
                       [io_out.feature_dut_gay(x) for x in dut_gay],
                       {**sinh_tu, "layer": "SN-DUTGAY"})
    io_out.ghi_geojson(lot, "boundary.geojson",
                       [io_out.feature_bao(b, "bien_lo") for b in bien_lo],
                       {**sinh_tu, "layer": "SN-BIENLO"})
    io_out.ghi_geojson(lot, "exclude.geojson",
                       [io_out.feature_bao(b, "loai_tru") for b in loai_tru],
                       {**sinh_tu, "layer": "SN-LOAITRU"})
    io_out.ghi_json(lot, "qc_input.json",
                    {"verb": "nhap", "nguon": nguon_in, "hash_dau_vao": hash_dau_vao,
                     "nguong_da_dung": ng, "phat_hien": phat_hien})
    io_out.ghi_viec_can_lam(lot, "nhap", phat_hien)
    _log(lot, {"verb": "nhap", "luc": datetime.now(timezone.utc).isoformat(),
               "phien_ban_loi": __version__, "nguon": nguon_in,
               "hash_dau_vao": hash_dau_vao,
               "so_diem": {"moc": len(diem_moc), "do": len(diem_do)},
               "so_phat_hien": len(viec), "so_chan": len(chan)})

    print(f"\nĐã ghi 7 file vào {lot.process_dir}")
    print(f"Việc cần làm: {len(viec)} ({len(chan)} chặn) — xem viec_can_lam.md")
    return 1 if chan else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sannen", description=__doc__)
    ap.add_argument("verb", choices=VERBS)
    ap.add_argument("--lot", required=True, type=Path, help="Thư mục lô")
    ap.add_argument("--preview", action="store_true",
                    help="Chỉ báo sẽ làm gì, không ghi (mặc định của agent)")
    ap.add_argument("--be-mat", choices=("moc", "do", "ca-hai"), default="ca-hai",
                    help="verb mat: dựng bề mặt nào")
    ap.add_argument("--sweep", action="store_true", help="tinh: quét ma trận phương án A/B")
    g = ap.add_argument_group("luoi / hieuchinh")
    g.add_argument("--o", type=float, help="luoi: kích thước ô (m), ghi đè lot.yaml")
    g.add_argument("--goc", help="luoi: góc xoay (độ) hoặc 'auto' = theo cạnh dài của lô")
    g.add_argument("--goc-luoi", help="luoi: điểm gốc lưới 'E,N' (VN-2000)")
    g.add_argument("--ngoai-suy", type=float, help="luoi: NGƯỜI chấp nhận ngoại suy cao độ đỉnh ngoài vùng đo ≤ M mét "
                                                   "(RULES 8: mặc định 0 = cấm), ghi đè lot.yaml")
    g.add_argument("--ngoai-suy-kieu", choices=("diem_gan_nhat", "gan_nhat", "mat_phang"),
                   help="luoi: cách bù dữ liệu thiếu — diem_gan_nhat (cao độ điểm đo gần nhất, gồm cả tam giác "
                        "thiếu dữ liệu) · gan_nhat (mặc định: điểm gần nhất trên mép vùng đo) · mat_phang (dễ sai trên mái dốc)")
    g.add_argument("--resync", action="store_true", help="luoi: đọc ngược cao độ đỉnh từ nhãn CAD")
    g.add_argument("--chap-nhan", action="store_true", help="luoi --resync: người đã xem, nhận chênh lệch")
    g.add_argument("--tu-file", type=Path, help="hieuchinh/resync: file danh sách đỉnh")
    g.add_argument("--dinh", help="hieuchinh: mã đỉnh, vd D03-05")
    g.add_argument("--z", type=float, help="hieuchinh: cao độ mới (m)")
    g.add_argument("--be-mat-hc", dest="be_mat_hc", choices=("moc", "do"), default="do",
                   help="hieuchinh: bề mặt của đỉnh (mặc định do)")
    g.add_argument("--ly-do", default="", help="hieuchinh: lý do, ghi vào decisions.md")
    g.add_argument("--bo", help="hieuchinh: bỏ hiệu chỉnh của một đỉnh")
    x = ap.add_argument_group("xem3d")
    x.add_argument("--ra", type=Path, help="xem3d: file HTML đầu ra (mặc định 20_output/tin3d_view.html)")
    x.add_argument("--mo", action="store_true", help="xem3d: mở bằng trình duyệt mặc định sau khi tạo")
    x.add_argument("--phong-dai-z", type=float, default=2.0, help="xem3d: độ phóng đại Z ban đầu, 1–10 (mặc định 2)")
    ap.add_argument("--xac-nhan-anh-xa", action="store_true",
                    help="NGƯỜI đã soát ánh xạ cột đề xuất cho file Excel/CSV: ghi nhớ và chạy tiếp")
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
        try:
            return verb_nhap(lot, cfg, a.preview, a.xac_nhan_anh_xa)
        except bang_in.CanXacNhan as e:
            print(f"\nCẦN NGƯỜI XÁC NHẬN — dừng.\n{e}")
            return 2
        except (bang_in.LoiNguon, dxfio.LayerLa, dxfio.LoiBien) as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    if a.verb == "mat":
        try:
            return mat.chay(lot, cfg, a.be_mat, a.preview)
        except (mat.DauVaoDaDoi, tin.TinLoi) as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    if a.verb == "lo":
        try:
            return lo.chay(lot, cfg, a.preview)
        except mat.DauVaoDaDoi as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    if a.verb in ("luoi", "hieuchinh"):
        try:
            if a.verb == "luoi" and a.resync:
                return luoi.chay_resync(lot, cfg, a.preview, a.tu_file, a.chap_nhan)
            if a.verb == "luoi":
                return luoi.chay_luoi(lot, cfg, a.preview, a.o, a.goc, a.goc_luoi, a.ngoai_suy, a.ngoai_suy_kieu)
            return luoi.chay_hieuchinh(lot, cfg, a.preview, a.dinh, a.z, a.be_mat_hc,
                                       a.ly_do, a.tu_file, a.bo)
        except (mat.DauVaoDaDoi, luoi.LuoiLoi) as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    if a.verb == "tinh":
        try:
            return tinh.chay(lot, cfg, a.preview, a.sweep)
        except (mat.DauVaoDaDoi, luoi.LuoiLoi, tin.TinLoi) as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    if a.verb == "xuat":
        try:
            return xuat.chay(lot, cfg, a.preview)
        except (mat.DauVaoDaDoi, luoi.LuoiLoi, tin.TinLoi) as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    if a.verb == "xem3d":
        try:
            return xem3d.chay(lot, cfg, a.ra, a.phong_dai_z, a.mo)
        except xem3d.ThieuBeMat as e:
            print(f"\nRULES 7 — dừng: {e}")
            return 2

    gd = CHUA_CAI[a.verb]
    print(f"Verb `{a.verb}` chưa cài đặt — thuộc giai đoạn {gd} của lộ trình.")
    print(f"Đọc _agent/skills/{a.verb}/SKILL.md để biết nó phải làm gì.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
