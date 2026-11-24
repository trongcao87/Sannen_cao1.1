"""Verb `tinh` (giai đoạn 5): khối lượng đào/đắp bằng hai phương pháp, đối chiếu, ma trận phương án.

Quy ước dấu: chênh cao dz = z_đo − z_mốc. dz > 0 là ĐẮP, dz < 0 là ĐÀO.

  • Lưới ô vuông (SỐ NỘP, RULES 9): V = (dz trung bình 4 góc) × diện tích hữu hiệu của ô.
  • Lăng trụ (SỐ KIỂM): chồng CHÍNH XÁC hai TIN trên từng ô. Trên mỗi mảnh chồng cả hai
    mặt đều là mặt phẳng nên dz tuyến tính; mảnh vắt đường dz = 0 được cắt đôi, tích phân
    tuyến tính trên từng nửa cho kết quả đúng tuyệt đối — không xấp xỉ.
"""
from __future__ import annotations
import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import io_out, qc
from .config import nguong
from .geom import (Goc, cat_loi, cat_nua_mat_phang, dien_tich_co_dau, tich_phan_tuyen_tinh)
from .lo import LoChuan
from .luoi import (Luoi, LuoiLoi, dat_luoi, danh_gia_luoi, doc_hieu_chinh, doc_luoi, ma_dinh, ma_o,
                   nap_dau_vao, nut_hieu_luc, tam_giac_thieu)
from .mat import DauVaoDaDoi, doc_points, dung_be_mat
from .paths import Lot
from .tin import LOAI_THIEU_DU_LIEU, Tin

EPS_DT = 1e-12


# =========================================================================== lăng trụ
def _rong() -> dict:
    return {"dao": 0.0, "dap": 0.0, "dt_dao": 0.0, "dt_dap": 0.0,
            "gap_dao": 0.0, "gap_dap": 0.0, "gap_dt_dao": 0.0, "gap_dt_dap": 0.0, "phu": 0.0}


def lang_tru_o(poly: list[tuple[float, float]], full: bool, L: LoChuan, moc: Tin, do: Tin):
    """Khối lượng lăng trụ trong MỘT ô (đa giác lồi ngược chiều kim `poly`).

    Trả (số liệu, các đoạn ranh đào–đắp trong toạ độ cục bộ). `full`: ô nằm trọn trong lô
    nên khỏi cắt theo biên. Mảnh nào chạm tam giác `thiếu dữ liệu` được tính riêng (gap_*)
    để chọn B3 (gồm) hoặc B5 (loại).
    """
    kq = _rong()
    segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    for td in do.tam_giac_gan(min(xs), min(ys), max(xs), max(ys)):
        p1 = cat_loi(do.da_giac(td), poly)
        if len(p1) < 3 or abs(dien_tich_co_dau(p1)) < EPS_DT:
            continue
        Ad, Bd, Cd = do.mat_phang(td)
        bx = [p[0] for p in p1]; by = [p[1] for p in p1]
        for tm in moc.tam_giac_gan(min(bx), min(by), max(bx), max(by)):
            q = cat_loi(p1, moc.da_giac(tm))
            if len(q) < 3 or abs(dien_tich_co_dau(q)) < EPS_DT:
                continue
            Am, Bm, Cm = moc.mat_phang(tm)
            a, b, c = Ad - Am, Bd - Bm, Cd - Cm
            f = lambda x, y, a=a, b=b, c=c: a * x + b * y + c
            gap = do.loai[td] == LOAI_THIEU_DU_LIEU or moc.loai[tm] == LOAI_THIEU_DU_LIEU
            fv = [f(*p) for p in q]
            if min(fv) >= 0.0:
                phan = [(+1, q)]                              # toàn đắp (dz = 0 tính vào đắp)
            elif max(fv) <= 0.0:
                phan = [(-1, q)]
            else:
                phan = [(+1, cat_nua_mat_phang(q, a, b, c)), (-1, cat_nua_mat_phang(q, -a, -b, -c))]
                seg = _doan_khong(q, fv)
                if seg and (full or L.trong((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)):
                    segs.append(seg)
            for dau, part in phan:
                if len(part) < 3:
                    continue
                if full:
                    v, ar = tich_phan_tuyen_tinh(part, f), abs(dien_tich_co_dau(part))
                else:
                    v, ar = L.tich_phan_trong(part, f), L.dien_tich_trong(part)
                g = "gap_" if gap else ""
                if dau > 0:
                    kq[g + "dap"] += v; kq[g + "dt_dap"] += ar
                else:
                    kq[g + "dao"] += -v; kq[g + "dt_dao"] += ar
                kq["phu"] += ar
    return kq, segs


def _doan_khong(q, fv):
    pts = []
    n = len(q)
    for i in range(n):
        j = (i + 1) % n
        if (fv[i] < 0 < fv[j]) or (fv[j] < 0 < fv[i]):
            t = fv[i] / (fv[i] - fv[j])
            pts.append((q[i][0] + t * (q[j][0] - q[i][0]), q[i][1] + t * (q[j][1] - q[i][1])))
        elif fv[i] == 0 and fv[(i - 1) % n] * fv[j] < 0:
            pts.append(q[i])
    return (pts[0], pts[1]) if len(pts) >= 2 and pts[0] != pts[1] else None


def tinh_lang_tru(luoi: Luoi, L: LoChuan, moc: Tin, do: Tin, o_list) -> dict:
    """Lăng trụ trên các ô của lưới (chỉ để chia việc — tổng không phụ thuộc lưới)."""
    theo_o, tong, segs = {}, _rong(), []
    for o in o_list:
        kq, sg = lang_tru_o(luoi.o(o.i, o.j), not o.vat_ranh_lo, L, moc, do)
        theo_o[(o.i, o.j)] = kq
        segs += sg
        for k, v in kq.items():
            tong[k] += v
    return {"theo_o": theo_o, "tong": tong, "ranh": segs}


# =========================================================================== lưới ô vuông
def kl_luoi_o(o) -> dict | None:
    """Phương pháp lưới cho một ô. None nếu thiếu dữ liệu (RULES 8)."""
    if o.thieu_du_lieu:
        return None
    dz = [d - m for d, m in zip(o.z_do, o.z_moc)]
    tb = sum(dz) / 4.0
    v = tb * o.dt_huu_hieu
    return {"dz_tb": tb, "dao": -v if v < 0 else 0.0, "dap": v if v >= 0 else 0.0,
            "dt_dao": o.dt_huu_hieu if tb < 0 else 0.0, "dt_dap": o.dt_huu_hieu if tb >= 0 else 0.0,
            "z_tb_moc": sum(o.z_moc) / 4.0, "z_tb_do": sum(o.z_do) / 4.0}


def tong_luoi(o_list) -> dict:
    t = {"dao": 0.0, "dap": 0.0, "dt_dao": 0.0, "dt_dap": 0.0, "dt_thieu": 0.0,
         "so_o": 0, "so_o_vat_ranh": 0, "so_o_thieu": 0}
    for o in o_list:
        k = kl_luoi_o(o)
        t["so_o"] += 1
        t["so_o_vat_ranh"] += o.vat_ranh_lo
        if k is None:
            t["so_o_thieu"] += 1
            t["dt_thieu"] += o.dt_huu_hieu
            continue
        for key in ("dao", "dap", "dt_dao", "dt_dap"):
            t[key] += k[key]
    t["rong"] = t["dap"] - t["dao"]
    return t


def luoi_tu_grid(grid: dict, goc: Goc) -> Luoi:
    ts = grid["tham_so"]
    x0, y0 = goc.vao(*ts["goc_luoi"])
    return Luoi(x0, y0, math.radians(ts["goc_xoay_do"]), ts["cot_m"], ts["hang_m"])


def o_list_hieu_chinh(o_list, grid: dict, ghi_de: list[dict]):
    """Áp `grid_adjusted.json` lên cao độ đỉnh của các ô (nguồn sự thật, RULES — Nguồn sự thật)."""
    if not ghi_de:
        return o_list
    nut = nut_hieu_luc(grid, ghi_de)
    for o in o_list:
        ma = [ma_dinh(o.i, o.j), ma_dinh(o.i + 1, o.j), ma_dinh(o.i + 1, o.j + 1), ma_dinh(o.i, o.j + 1)]
        o.z_moc = [nut[m]["z_moc"] for m in ma]
        o.z_do = [nut[m]["z_do"] for m in ma]
    return o_list


# =========================================================================== ma trận phương án
def _hang_pa(ma, mo_ta, t, **them) -> dict:
    return {"ma": ma, "mo_ta": mo_ta, "dao": round(t["dao"], 3), "dap": round(t["dap"], 3),
            "rong": round(t["dap"] - t["dao"], 3), "dt_dao": round(t["dt_dao"], 3),
            "dt_dap": round(t["dt_dap"], 3), **them}


def _pa_luoi(ma, mo_ta, luoi, L, moc, do, gap, ns=(0.0, "gan_nhat")):
    ol, _ = danh_gia_luoi(luoi, L, moc, do, gap, ns)
    t = tong_luoi(ol)
    return _hang_pa(ma, mo_ta, t, so_o=t["so_o"], so_o_vat_ranh=t["so_o_vat_ranh"],
                    so_o_thieu=t["so_o_thieu"], dt_thieu=round(t["dt_thieu"], 3),
                    goc_xoay_do=round(math.degrees(luoi.goc_rad) % 180, 3))


def huong_ranh(segs) -> float | None:
    """Phương chủ đạo của ranh đào–đắp: trung bình có trọng số độ dài trên góc kép (mod 180°)."""
    sx = sy = 0.0
    for (x0, y0), (x1, y1) in segs:
        l = math.hypot(x1 - x0, y1 - y0)
        th = math.atan2(y1 - y0, x1 - x0)
        sx += l * math.cos(2 * th); sy += l * math.sin(2 * th)
    if math.hypot(sx, sy) < 1e-9:
        return None
    return (math.atan2(sy, sx) / 2.0) % math.pi


def quet_phuong_an(lot: Lot, cfg: dict, ng: dict, L: LoChuan, moc: Tin, do: Tin, grid: dict,
                   kt: float, lt_chinh: dict) -> dict:
    """Bảng A (cách đặt lưới) và Bảng B (phương pháp). Giữ nguyên kích thước ô ở bảng A."""
    goc = moc.goc
    gap = tam_giac_thieu(moc) + tam_giac_thieu(do)
    ns = (float(grid["tham_so"].get("ngoai_suy_m", 0) or 0), grid["tham_so"].get("ngoai_suy_kieu", "gan_nhat"))
    chinh = luoi_tu_grid(grid, goc)
    huong = L.huong_canh_dai()
    A: list[dict] = []
    A.append(_pa_luoi("A1", "Theo bản vẽ nhà thầu (gốc + phương trong lot.yaml)", chinh, L, moc, do, gap, ns))
    a2 = dat_luoi(L, kt, huong)
    A.append(_pa_luoi("A2", "Gốc tây-nam hộp bao, phương theo cạnh dài của lô", a2, L, moc, do, gap, ns))
    A.append(_pa_luoi("A3", "A2 dời ½ ô theo trục X lưới", dat_luoi(L, kt, huong, dich_u=kt / 2), L, moc, do, gap, ns))
    A.append(_pa_luoi("A4", "A2 dời ½ ô theo trục Y lưới", dat_luoi(L, kt, huong, dich_v=kt / 2), L, moc, do, gap, ns))
    A.append(_pa_luoi("A5", "A2 dời ½ ô theo cả hai trục", dat_luoi(L, kt, huong, dich_u=kt / 2, dich_v=kt / 2), L, moc, do, gap, ns))
    A.append(_pa_luoi("A6", "A2 xoay thêm 45°", dat_luoi(L, kt, huong + math.pi / 4), L, moc, do, gap, ns))
    h7 = huong_ranh(lt_chinh["ranh"])
    if h7 is None:
        A.append({"ma": "A7", "mo_ta": "Phương song song ranh đào–đắp chủ đạo", "bo_qua": "không có ranh đào–đắp (toàn đào hoặc toàn đắp)"})
    else:
        A.append(_pa_luoi("A7", "Phương song song ranh đào–đắp chủ đạo", dat_luoi(L, kt, h7), L, moc, do, gap, ns))
    luoi_a8 = []
    for ang in range(0, 91, 15):
        for ou in range(4):
            for ov in range(4):
                lu = dat_luoi(L, kt, math.radians(ang), dich_u=kt * ou / 4, dich_v=kt * ov / 4)
                ol, _ = danh_gia_luoi(lu, L, moc, do, gap, ns)
                t = tong_luoi(ol)
                luoi_a8.append({"goc_do": ang, "dich_u": ou / 4, "dich_v": ov / 4,
                                "dao": round(t["dao"], 3), "dap": round(t["dap"], 3),
                                "rong": round(t["rong"], 3), "so_o_vat_ranh": t["so_o_vat_ranh"],
                                "so_o_thieu": t["so_o_thieu"], "dt_thieu": round(t["dt_thieu"], 3)})
    ts = lambda k: [x[k] for x in luoi_a8]
    A.append({"ma": "A8", "mo_ta": "Quét 16 vị trí gốc × phương 0–90° bước 15°", "so_to_hop": len(luoi_a8),
              "dao": {"min": min(ts("dao")), "max": max(ts("dao")), "tb": round(statistics.mean(ts("dao")), 3)},
              "dap": {"min": min(ts("dap")), "max": max(ts("dap")), "tb": round(statistics.mean(ts("dap")), 3)},
              "rong": {"min": min(ts("rong")), "max": max(ts("rong")), "tb": round(statistics.mean(ts("rong")), 3)}})
    B: list[dict] = []
    for ma, k in (("B1", 10.0), ("B2", 5.0)):
        lu = dat_luoi(L, k, chinh.goc_rad, (chinh.x0, chinh.y0))
        B.append(_pa_luoi(ma, f"Ô {k:g}×{k:g} m, cách đặt như A1", lu, L, moc, do, gap, ns))

    def lt_tong(t, ten, ma, mo_ta, ca_gap=True):
        d, p = t["dao"] + (t["gap_dao"] if ca_gap else 0), t["dap"] + (t["gap_dap"] if ca_gap else 0)
        return _hang_pa(ma, mo_ta, {"dao": d, "dap": p,
                                    "dt_dao": t["dt_dao"] + (t["gap_dt_dao"] if ca_gap else 0),
                                    "dt_dap": t["dt_dap"] + (t["gap_dt_dap"] if ca_gap else 0)})
    tt = lt_chinh["tong"]
    B.append(lt_tong(tt, "", "B3", "Lăng trụ có đứt gãy, đã lọc tam giác rác"))
    co_dg = any(True for _ in _dut_gay_co(lot))
    if co_dg:
        cfg2 = {**cfg, "dut_gay_ap_dung": []}
        ng2 = nguong(cfg2)
        diem = {n: doc_points(lot.process_dir / f"points_{n}.csv") for n in ("moc", "do")}
        m2, _ = dung_be_mat(lot, cfg2, "moc", goc, ng2, diem["moc"])
        d2, _ = dung_be_mat(lot, cfg2, "do", goc, ng2, diem["do"])
        lu = luoi_tu_grid(grid, goc)
        ol, _ = danh_gia_luoi(lu, L, m2, d2, [], ns)
        t4 = tinh_lang_tru(lu, L, m2, d2, ol)["tong"]
        B.append(lt_tong(t4, "", "B4", "Lăng trụ bỏ đứt gãy"))
    else:
        B.append({**lt_tong(tt, "", "B4", "Lăng trụ bỏ đứt gãy"), "ghi_chu": "lô không có đứt gãy nên B4 = B3"})
    B.append(lt_tong(tt, "", "B5", "Lăng trụ, loại vùng thiếu dữ liệu khỏi phạm vi tính", ca_gap=False))

    # quy tắc đọc
    gross = lambda r: r["dao"] + r["dap"]
    ung = [r for r in A if "bo_qua" not in r and r["ma"] != "A8"]
    xet = [(gross(r), r["ma"]) for r in ung] + [(x["dao"] + x["dap"], f"A8[{x['goc_do']}°,{x['dich_u']},{x['dich_v']}]")
                                                for x in luoi_a8]
    thap, ten_thap = min(xet)
    dt_thieu_pa = [r.get("dt_thieu", 0.0) for r in ung] + [x["dt_thieu"] for x in luoi_a8]
    b3 = next(r for r in B if r["ma"] == "B3")
    return {"A": A, "A8_chi_tiet": luoi_a8, "B": B,
            "doc": {"cau": "Phương án cho số THẤP NHẤT là phương án có nhiều ô vắt ranh nhất, tức bỏ sót "
                           "nhiều công tác thật nhất. Gọi là 'cận dưới của phương pháp lưới' thì đúng; "
                           "gọi là 'tối ưu' thì không đứng được. Số nộp vẫn là A1 theo tham số hồ sơ duyệt (RULES 9).",
                    "can_duoi_tong_dao_dap_m3": round(thap, 3), "phuong_an_can_duoi": ten_thap,
                    "b3_tong_dao_dap_m3": round(gross(b3), 3),
                    "phan_bi_trieu_tiet_m3": round(gross(b3) - thap, 3),
                    "dt_thieu_du_lieu_m2": {"min": min(dt_thieu_pa), "max": max(dt_thieu_pa)},
                    "canh_bao_thieu_du_lieu": (
                        f"Các phương án loại khỏi số từ {min(dt_thieu_pa):,.1f} tới {max(dt_thieu_pa):,.1f} m² ô THIẾU DỮ LIỆU. "
                        "Phần chênh giữa các phương án gồm cả diện tích bị loại đó, KHÔNG chỉ do ô vắt ranh đào–đắp: "
                        "đo bù hoặc chấp nhận ngoại suy (luoi.ngoai_suy_m) trước khi đọc ma trận."
                        if max(dt_thieu_pa) > 0 else None)}}


def hash_hieu_chinh(ghi_de: list[dict]) -> str:
    """Dấu vân tay các hiệu chỉnh đỉnh — `xuat` dùng để biết volume.json còn mới hay không."""
    import hashlib
    ds = sorted((g["ma"], g["be_mat"], g["z_moi"]) for g in ghi_de)
    return hashlib.sha1(json.dumps(ds).encode()).hexdigest()[:12]


def _dut_gay_co(lot: Lot):
    p = lot.process_dir / "breaklines.geojson"
    if p.exists():
        yield from json.loads(p.read_text(encoding="utf-8")).get("features", [])


# =========================================================================== RULES 12
def kiem_am_bat_thuong(lot: Lot, cfg: dict, o_ra: list[dict], ng: dict) -> list[dict]:
    """Đào đi phần đã đắp ở đợt trước (hoặc ngược lại) phải được CẢNH BÁO, không bù trừ âm thầm."""
    ch = (cfg.get("dot_truoc") or {}).get("volume_json")
    if not ch:
        return []
    p = Path(ch) if Path(ch).is_absolute() else lot.root / ch
    if not p.exists():
        return [qc._phat_hien("", "dot_truoc_thieu_file", "chan", f"Khai dot_truoc.volume_json nhưng không thấy {p}")]
    truoc = {o["ma"]: o for o in json.loads(p.read_text(encoding="utf-8")).get("o", [])}
    ra = []
    for o in o_ra:
        t = truoc.get(o["ma"])
        if not t or o.get("thieu_du_lieu") or t.get("thieu_du_lieu"):
            continue
        rong_truoc, rong_nay = t["kl_dap_m3"] - t["kl_dao_m3"], o["kl_dap_m3"] - o["kl_dao_m3"]
        if rong_truoc * rong_nay < 0 and abs(rong_nay) > ng["o_lech_lon_m3"]:
            ra.append(qc._phat_hien(
                "", "khoi_luong_am_giua_hai_dot", "canh_bao",
                f"Ô {o['ma']}: đợt trước {rong_truoc:+,.2f} m³ ({'đắp' if rong_truoc > 0 else 'đào'}), "
                f"đợt này {rong_nay:+,.2f} m³ ({'đắp' if rong_nay > 0 else 'đào'}) — đảo chiều",
                lua_chon=["(a) giải thích được (đào lại, hạ cốt thiết kế)", "(b) soát lại số liệu hai đợt"],
                he_qua="RULES 12: không bù trừ âm thầm giữa hai đợt nghiệm thu"))
    return ra


# =========================================================================== verb
def chay(lot: Lot, cfg: dict, preview: bool, sweep: bool) -> int:
    ng = nguong(cfg)
    moc, do, L, qi = nap_dau_vao(lot)
    grid = doc_luoi(lot)
    if grid.get("hash_dau_vao") != qi.get("hash_dau_vao"):
        raise DauVaoDaDoi("grid.json sinh từ đầu vào khác — chạy lại `luoi`.")
    ghi_de = doc_hieu_chinh(lot)
    luoi = luoi_tu_grid(grid, moc.goc)
    gap = tam_giac_thieu(moc) + tam_giac_thieu(do)
    ns = (float(grid["tham_so"].get("ngoai_suy_m", 0) or 0), grid["tham_so"].get("ngoai_suy_kieu", "gan_nhat"))
    o_list, _ = danh_gia_luoi(luoi, L, moc, do, gap, ns)
    o_list = o_list_hieu_chinh(o_list, grid, ghi_de)
    lt = tinh_lang_tru(luoi, L, moc, do, o_list)

    # ---- số nộp: lưới ô vuông ------------------------------------------------
    tl = tong_luoi(o_list)
    phat_hien: list[dict] = []
    o_ra: list[dict] = []
    for o in o_list:
        k = kl_luoi_o(o)
        p = lt["theo_o"][(o.i, o.j)]
        ma = ma_o(o.i, o.j)
        # Số liệu từng ô để NGUYÊN độ chính xác: bảng tổng khớp đòi tổng chi tiết = tổng hợp
        # tuyệt đối; làm tròn chỉ ở bước hiển thị (định dạng ô Excel), không ở dữ liệu.
        d = {"ma": ma, "i": o.i, "j": o.j, "dt_huu_hieu_m2": o.dt_huu_hieu,
             "thieu_du_lieu": o.thieu_du_lieu, "vat_ranh_lo": o.vat_ranh_lo, "ngoai_suy": o.ngoai_suy,
             "lang_tru_dao_m3": p["dao"] + p["gap_dao"], "lang_tru_dap_m3": p["dap"] + p["gap_dap"]}
        if k:
            d.update({"z_tb_moc": k["z_tb_moc"], "z_tb_do": k["z_tb_do"],
                      "dz_tb": k["dz_tb"], "kl_dao_m3": k["dao"],
                      "kl_dap_m3": k["dap"], "dt_dao_m2": k["dt_dao"],
                      "dt_dap_m2": k["dt_dap"]})
            ref = max(d["lang_tru_dao_m3"], d["lang_tru_dap_m3"])
            lech = max(abs(k["dao"] - d["lang_tru_dao_m3"]), abs(k["dap"] - d["lang_tru_dap_m3"]))
            nguong_o = max(ng["o_lech_lon_pct"] / 100.0 * ref, ng["o_lech_lon_m3"])
            d.update({"lech_m3": round(lech, 4), "lech_pct": round(100 * lech / ref, 3) if ref else 0.0,
                      "o_lech_lon": lech > nguong_o})
        else:
            d.update({"kl_dao_m3": 0.0, "kl_dap_m3": 0.0, "dt_dao_m2": 0.0, "dt_dap_m2": 0.0,
                      "o_lech_lon": False})
        o_ra.append(d)

    lon = [o for o in o_ra if o["o_lech_lon"]]
    for o in lon[:20]:
        phat_hien.append(qc._phat_hien(
            "", "o_lech_lon", "canh_bao",
            f"Ô {o['ma']}: lưới ≠ lăng trụ {o['lech_m3']:,.2f} m³ ({o['lech_pct']:.1f} %) — "
            f"{'ô vắt ranh đào–đắp hoặc biên lô' if o['vat_ranh_lo'] or o['kl_dao_m3'] * o['kl_dap_m3'] == 0 else 'địa hình trong ô'}",
            lua_chon=["(a) giải thích được bằng 03_DOICHIEU", "(b) đổi kích thước/góc lưới rồi tính lại"],
            he_qua="số nộp (lưới) và số kiểm (lăng trụ) lệch nhau ở ô này"))
    if len(lon) > 20:
        phat_hien.append(qc._phat_hien("", "o_lech_lon", "canh_bao", f"còn {len(lon) - 20} ô lệch lớn nữa"))
    if tl["so_o_thieu"]:
        phat_hien.append(qc._phat_hien(
            "", "o_thieu_du_lieu", "canh_bao",
            f"{tl['so_o_thieu']} ô ({tl['dt_thieu']:,.2f} m²) KHÔNG tính khối lượng vì thiếu dữ liệu (RULES 8) "
            "— số nộp chưa phủ hết lô",
            lua_chon=["(a) yêu cầu đo bổ sung", "(b) người chấp nhận nội suy và ghi decisions.md"],
            he_qua="khối lượng thật của vùng đó chưa vào hồ sơ"))
    phat_hien += kiem_am_bat_thuong(lot, cfg, o_ra, ng)

    tong_lt = lt["tong"]
    lt_dao, lt_dap = tong_lt["dao"] + tong_lt["gap_dao"], tong_lt["dap"] + tong_lt["gap_dap"]
    dt_lo = L.dien_tich()
    dt_dd = tl["dt_dao"] + tl["dt_dap"]
    chenh_dt = dt_dd + tl["dt_thieu"] - dt_lo
    if abs(chenh_dt) > max(1e-6, 1e-9 * dt_lo):
        phat_hien.append(qc._phat_hien(
            "", "dt_dao_dap_khac_dt_lo", "chan",
            f"DT đào + đắp + thiếu dữ liệu = {dt_dd + tl['dt_thieu']:,.6f} ≠ diện tích lô {dt_lo:,.6f} m² — "
            "lỗi phần mềm, DỪNG (không làm tròn cho khớp)"))
    pct = lambda a, b: 100.0 * (a - b) / b if b else 0.0
    vol = {
        "hash_dau_vao": qi.get("hash_dau_vao"),
        "phien_ban_quy_uoc": "dz = z_do - z_moc; dz>0 dap, dz<0 dao",
        "tham_so": {"phuong_phap_nop": cfg["phuong_phap_chinh_thuc"], **grid["tham_so"],
                    "so_hieu_chinh": len(ghi_de), "hieu_chinh_hash": hash_hieu_chinh(ghi_de)},
        "so_nop": {"phuong_phap": "luoi_o_vuong", "dao_m3": tl["dao"], "dap_m3": tl["dap"],
                   "rong_m3": tl["rong"], "dt_dao_m2": tl["dt_dao"],
                   "dt_dap_m2": tl["dt_dap"], "dt_thieu_du_lieu_m2": tl["dt_thieu"],
                   "so_o": tl["so_o"], "so_o_thieu": tl["so_o_thieu"], "so_o_vat_ranh": tl["so_o_vat_ranh"]},
        "so_kiem": {"phuong_phap": "lang_tru_tam_giac", "dao_m3": lt_dao, "dap_m3": lt_dap,
                    "rong_m3": lt_dap - lt_dao,
                    "dt_dao_m2": tong_lt["dt_dao"] + tong_lt["gap_dt_dao"],
                    "dt_dap_m2": tong_lt["dt_dap"] + tong_lt["gap_dt_dap"],
                    "trong_do_vung_thieu_du_lieu": {"dao_m3": tong_lt["gap_dao"], "dap_m3": tong_lt["gap_dap"]}},
        "chenh_nop_kiem": {"dao_m3": tl["dao"] - lt_dao, "dap_m3": tl["dap"] - lt_dap,
                           "dao_pct": pct(tl["dao"], lt_dao), "dap_pct": pct(tl["dap"], lt_dap)},
        "dt_lo_m2": dt_lo, "dt_dao_dap_thieu_tru_dt_lo_m2": chenh_dt,
        "o": o_ra,
        "ranh_dao_dap": [[list(map(lambda v: round(v, 4), moc.goc.ra(*a))),
                          list(map(lambda v: round(v, 4), moc.goc.ra(*b)))] for a, b in lt["ranh"]],
    }
    qc.danh_ma(phat_hien, "T")
    chan = [p for p in phat_hien if p["muc"] == "chan"]
    print(f"SỐ NỘP (lưới ô vuông): đào {tl['dao']:,.3f} m³ · đắp {tl['dap']:,.3f} m³ · ròng {tl['rong']:+,.3f} m³ "
          f"· {tl['so_o']} ô ({tl['so_o_vat_ranh']} vắt ranh, {tl['so_o_thieu']} thiếu dữ liệu)")
    print(f"SỐ KIỂM (lăng trụ):    đào {lt_dao:,.3f} m³ · đắp {lt_dap:,.3f} m³ · ròng {lt_dap - lt_dao:+,.3f} m³")
    print(f"Chênh nộp − kiểm:      đào {tl['dao'] - lt_dao:+,.3f} m³ ({pct(tl['dao'], lt_dao):+.2f} %) · "
          f"đắp {tl['dap'] - lt_dap:+,.3f} m³ ({pct(tl['dap'], lt_dap):+.2f} %); {len(lon)} ô lệch lớn")
    print(f"Kiểm diện tích: đào + đắp + thiếu dữ liệu − diện tích lô = {chenh_dt:+.2e} m²")
    if sweep:
        kt = grid["tham_so"]["kich_thuoc_o_m"]
        vol["sweep"] = quet_phuong_an(lot, cfg, ng, L, moc, do, grid, kt, lt)
        d = vol["sweep"]["doc"]
        print(f"SWEEP: cận dưới đào+đắp {d['can_duoi_tong_dao_dap_m3']:,.3f} m³ ({d['phuong_an_can_duoi']}) "
              f"so B3 {d['b3_tong_dao_dap_m3']:,.3f} m³ → bị triệt tiêu {d['phan_bi_trieu_tiet_m3']:,.3f} m³")
    for p in phat_hien:
        if p["muc"] == "chan":
            print(f"  CHẶN {p['ma']}: {p['mo_ta']}")
    if preview:
        print("\n-- XEM TRƯỚC (RULES 4). Sẽ ghi volume.json, qc_volume.json. Chạy lại không có --preview để ghi.")
        return 1 if chan else 0

    lot.ensure()
    io_out.ghi_json(lot, "volume.json", vol)
    io_out.ghi_json(lot, "qc_volume.json", {"verb": "tinh", "hash_dau_vao": qi.get("hash_dau_vao"),
                                            "phat_hien": phat_hien})
    io_out.ghi_viec_gop(lot, "tinh (cổng 3)", ["qc_luoi.json", "qc_volume.json"])
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    with (lot.log_dir / f"run_{datetime.now():%Y-%m-%dT%H%M}.jsonl").open("a", encoding="utf-8") as f:
        from . import __version__
        f.write(json.dumps({"verb": "tinh", "luc": datetime.now().isoformat(), "phien_ban_loi": __version__,
                            "hash_dau_vao": qi.get("hash_dau_vao"), "so_nop": vol["so_nop"],
                            "so_kiem": vol["so_kiem"], "so_hieu_chinh": len(ghi_de), "sweep": sweep},
                           ensure_ascii=False) + "\n")
    print(f"\nĐã ghi volume.json. Việc cần làm: {sum(1 for p in phat_hien if p['muc'] != 'thong_tin')} ({len(chan)} chặn)")
    return 1 if chan else 0
