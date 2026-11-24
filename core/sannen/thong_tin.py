"""Thông tin tổng hợp của một lô cho BẢNG ĐIỀU KHIỂN (lệnh SN_QL trong AutoCAD): TIN, lưới, khối lượng, ranh
đào–đắp, mặt cắt, bảng in, ba cổng duyệt và cảnh báo "kết quả cũ".

CHỈ ĐỌC: không tính lại gì, không ghi file nào (RULES 1 — con số do các verb của lõi tính, ở đây chỉ gom và trình bày).
Thiếu file thì mục đó nói "Chưa có …" chứ không lỗi. Cùng thư mục lô → cùng kết quả (thứ tự cố định).

    thong_tin(lot)          → dict số liệu có cấu trúc (cho test / MCP)
    dong_hien_thi(tt)       → {khoá nhóm: [[nhãn, giá trị chữ], ...]} đúng thứ tự hiển thị trong hộp thoại
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path

import yaml

from . import io_out, luoi_sua
from .config import doc_lot
from .cong import TEN_CONG, cong_da_duyet, doc_cong, viec_chan
from .paths import Lot

# Khoá nhóm hiển thị — đồng bộ với *sn-ql-nhom* trong cad/lisp/sannen.lsp (test_gd15_ql kiểm).
NHOM = ("moc", "do", "qc", "luoi", "nhan", "o", "ranh", "matcat", "bang", "khoiluong", "nguon")
BUOC = ("nhap", "mat", "lo", "luoi", "tinh", "xuat")
CHUA = "Chưa có"


# =========================================================================== đọc an toàn
def _doc(p: Path):
    """JSON → dict; file thiếu hoặc hỏng → None (hộp thoại nói 'Chưa có', không crash)."""
    try:
        return io_out.doc_json(p) if p.exists() else None
    except (OSError, ValueError):
        return None


def _so(x, nd: int = 2) -> str:
    if x is None:
        return "—"
    if isinstance(x, int):
        return f"{x:,}"
    return f"{x:,.{nd}f}"


def _gan(a, b, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def _ds_gan(a, b, tol: float) -> bool:
    return len(a) == len(b) and all(_gan(x, y, tol) for x, y in zip(a, b))


# =========================================================================== QC
def _dem_qc(phat_hien: list[dict], loai: tuple[str, ...], nhan: str) -> int:
    """Số phát hiện loại `loai` của bề mặt `nhan` ('bề mặt mốc'/'bề mặt đo'). Dòng gộp 'còn N …' tính đủ N,
    'N cặp' tính đủ N."""
    n = 0
    for f in phat_hien:
        if f.get("loai") not in loai or not str(f.get("mo_ta", "")).startswith(nhan):
            continue
        mo_ta = str(f.get("mo_ta", ""))
        m = re.search(r"còn (\d+)", mo_ta) or re.search(r"(\d+) cặp", mo_ta)
        n += int(m.group(1)) if m else 1
    return n


def _phat_hien_cac_qc(lot: Lot) -> dict[str, list[dict]]:
    ra = {}
    for ten in ("qc_input.json", "qc_surface.json", "qc_lo.json", "qc_luoi.json", "qc_volume.json"):
        d = _doc(lot.process_dir / ten)
        ra[ten] = list(d.get("phat_hien", [])) if d else []
    return ra


# =========================================================================== từng nhóm
def _tin(lot: Lot, nhan: str, qc: dict[str, list[dict]]) -> dict:
    s = _doc(lot.process_dir / f"surface_{nhan}.json")
    if s is None:
        return {"co": False, "ghi_chu": f"surface_{nhan}.json — chạy `mat`"}
    tk = s.get("thong_ke", {})
    zs = [p[2] for p in s.get("diem", [])]
    ten = {"moc": "bề mặt mốc", "do": "bề mặt đo"}[nhan]
    ph = qc["qc_input.json"] + qc["qc_surface.json"]
    return {"co": True, "so_dinh": len(s.get("diem", [])), "so_tam_giac": len(s.get("tam_giac", [])),
            "so_tam_giac_thieu": int(tk.get("so_tam_giac_thieu_du_lieu", 0)),
            "so_tam_giac_det": int(tk.get("so_tam_giac_det", 0)),
            "so_tam_giac_rac": int(tk.get("so_tam_giac_rac_loai", 0)),
            "dien_tich_phu_m2": tk.get("dien_tich_phu_m2"),
            "z_min": min(zs) if zs else None, "z_max": max(zs) if zs else None,
            "z_tb": sum(zs) / len(zs) if zs else None,
            "so_dut_gay": int(tk.get("so_dut_gay", 0)), "so_doan_ep": int(tk.get("so_doan_ep", 0)),
            "so_canh_rang_buoc": len(s.get("canh_rang_buoc", [])),
            "xung_dot_dut_gay": _dem_qc(ph, ("dut_gay_cat_nhau_lech_cao", "dut_gay_lech_diem_do"), ten),
            "so_diem_vao": int(tk.get("so_diem_vao", 0)), "so_gop": int(tk.get("so_gop", 0)),
            "diem_nghi_ngo": _dem_qc(ph, ("cao_do_bat_thuong",), ten),
            "diem_trung_lech_cao": _dem_qc(ph, ("diem_trung",), ten),
            "diem_trung_cung_cao": _dem_qc(ph, ("diem_trung_cung_cao_do",), ten),
            "khoang_cach_tb_m": tk.get("khoang_cach_tb_m")}


def _luoi(lot: Lot, qc: dict) -> dict:
    g = _doc(lot.process_dir / "grid.json")
    if g is None:
        return {"co": False, "ghi_chu": "grid.json — chạy `luoi`"}
    ts, tong = g["tham_so"], g["tong"]
    o = g.get("o", [])
    lo = _doc(lot.process_dir / "lo.json")
    vol = _doc(lot.process_dir / "volume.json")
    dt_lo = (lo or {}).get("tong", {}).get("dt_hieu_dung_m2", tong.get("dt_lo_m2"))
    lech = [c for c in (vol or {}).get("o", []) if c.get("o_lech_lon")]
    return {"co": True, "nx": ts["nx"], "ny": ts["ny"], "cot": luoi_sua.dinh_dang(ts["cot_m"]),
            "hang": luoi_sua.dinh_dang(ts["hang_m"]), "kich_thuoc_o_m": ts.get("kich_thuoc_o_m"),
            "goc_xoay_do": ts["goc_xoay_do"], "goc_luoi": list(ts["goc_luoi"]), "so_o": len(o),
            "dt_o_m2": tong["dt_o_m2"], "dt_lo_m2": dt_lo, "chenh_dt_m2": tong["dt_o_m2"] - (dt_lo if dt_lo is not None else 0.0),
            "so_o_thieu": sum(1 for c in o if c.get("thieu_du_lieu")),
            "so_o_vat_ranh": sum(1 for c in o if c.get("vat_ranh_lo")),
            "so_o_ngoai_suy": sum(1 for c in o if c.get("ngoai_suy")),
            "so_o_lech_lon": len(lech) if vol is not None else None,
            "so_dinh": len(g.get("nut", {})),
            "ngoai_suy_m": ts.get("ngoai_suy_m", 0.0), "ngoai_suy_kieu": ts.get("ngoai_suy_kieu", "gan_nhat"),
            "tuy_chinh": (lot.root / luoi_sua.FILE_TUY_CHINH).exists(),
            "so_hieu_chinh": len(luoi_sua_ghi_de(lot))}


def luoi_sua_ghi_de(lot: Lot) -> list[dict]:
    d = _doc(lot.process_dir / "grid_adjusted.json")
    return list(d.get("ghi_de", [])) if d else []


def _khoi_luong(lot: Lot) -> dict:
    v = _doc(lot.process_dir / "volume.json")
    if v is None:
        return {"co": False, "ghi_chu": "volume.json — chạy `tinh`"}
    nop, kiem, ch = v["so_nop"], v["so_kiem"], v.get("chenh_nop_kiem", {})
    return {"co": True, "phuong_phap": nop.get("phuong_phap"), "nop_dao": nop["dao_m3"], "nop_dap": nop["dap_m3"],
            "nop_rong": nop["rong_m3"], "kiem_dao": kiem["dao_m3"], "kiem_dap": kiem["dap_m3"],
            "kiem_rong": kiem["rong_m3"], "chenh_dao_m3": ch.get("dao_m3"), "chenh_dap_m3": ch.get("dap_m3"),
            "chenh_dao_pct": ch.get("dao_pct"), "chenh_dap_pct": ch.get("dap_pct"),
            "so_o": nop.get("so_o"), "so_o_thieu": nop.get("so_o_thieu"),
            "dt_thieu_m2": nop.get("dt_thieu_du_lieu_m2"),
            "so_o_lech_lon": sum(1 for c in v.get("o", []) if c.get("o_lech_lon")),
            "co_sweep": "sweep" in v}


def _ranh(lot: Lot) -> dict:
    v = _doc(lot.process_dir / "volume.json")
    if v is None:
        return {"co": False, "ghi_chu": "volume.json — chạy `tinh`"}
    doan = v.get("ranh_dao_dap", [])
    dai = 0.0
    for d in doan:
        for a, b in zip(d, d[1:]):
            dai += math.hypot(b[0] - a[0], b[1] - a[1])
    return {"co": True, "so_doan": len(doan), "chieu_dai_m": dai}


def _mat_cat(lot: Lot) -> dict:
    ds = []
    for p in sorted(lot.process_dir.glob("matcat_*.json")):
        d = _doc(p)
        if d is None:
            continue
        ds.append({"ten": d.get("ten", p.stem[len("matcat_"):]), "chieu_dai_m": d.get("chieu_dai_m"),
                   "dao_m2": d.get("dien_tich_dao_m2"), "dap_m2": d.get("dien_tich_dap_m2"),
                   "thieu_m": d.get("doan_thieu_du_lieu_m"), "so_tram": len(d.get("tram", [])),
                   "a": d.get("a"), "b": d.get("b")})
    ds.sort(key=lambda x: str(x["ten"]))
    return {"co": bool(ds), "ds": ds, "ghi_chu": "chưa tạo mặt cắt nào — dùng SN_MATCAT"}


def _chu_vi(vong: list) -> float:
    n = len(vong)
    return sum(math.hypot(vong[(i + 1) % n][0] - vong[i][0], vong[(i + 1) % n][1] - vong[i][1]) for i in range(n)) if n > 1 else 0.0


def _bien(lot: Lot) -> dict:
    """Biên lô đã chuẩn hóa (lo.json): số đỉnh, chu vi, diện tích, vùng loại trừ, hộp bao (cho tab «Biên lô»)."""
    lo = _doc(lot.process_dir / "lo.json")
    if lo is None:
        return {"co": False, "ghi_chu": "lo.json — chạy `lo`"}
    bl, lt = list(lo.get("bien_lo", [])), list(lo.get("loai_tru", []))
    tong = lo.get("tong", {})
    return {"co": True, "so_vong": len(bl), "so_dinh": sum(int(b.get("so_dinh") or len(b.get("vong", []))) for b in bl),
            "chu_vi_m": sum(_chu_vi(b.get("vong", [])) for b in bl),
            "dien_tich_m2": tong.get("dt_bien_lo_m2"),
            "dien_tich_area_cad_m2": (sum(float(b["dien_tich_area_cad_m2"]) for b in bl)
                                      if bl and all(b.get("dien_tich_area_cad_m2") is not None for b in bl) else None),
            "so_vung_loai_tru": len(lt), "dien_tich_loai_tru_m2": tong.get("dt_loai_tru_m2"),
            "dien_tich_hieu_dung_m2": tong.get("dt_hieu_dung_m2"), "hop_bao": lo.get("hop_bao")}


def dong_bien(tt: dict) -> list[list[str]]:
    """Dòng hiển thị tab «Biên lô» (đã định dạng chữ)."""
    t = tt["so_lieu"]["bien"]
    if not t["co"]:
        return [_c("Trạng thái", f"{CHUA} — {t.get('ghi_chu', '')}")]
    return [_c("Số vòng biên / số đỉnh", f"{_so(t['so_vong'])} / {_so(t['so_dinh'])}"),
            _c("Chu vi (m)", _so(t["chu_vi_m"], 3)), _c("Diện tích biên lô (m²)", _so(t["dien_tich_m2"], 3)),
            _c("Diện tích theo lệnh AREA (m²)", _so(t["dien_tich_area_cad_m2"], 3)),
            _c("Vùng loại trừ", f"{_so(t['so_vung_loai_tru'])} vùng, {_so(t['dien_tich_loai_tru_m2'], 3)} m²"),
            _c("Diện tích hiệu dụng (m²)", _so(t["dien_tich_hieu_dung_m2"], 3))]


def _bang(lot: Lot) -> dict:
    b = _doc(lot.output_dir / "bang_in_cad.json")
    if b is None:
        return {"co": False, "ghi_chu": "20_output/bang_in_cad.json — chạy `xuat`"}
    khoi = b.get("khoi", [])
    return {"co": True, "so_khoi": len(khoi), "so_dong": sum(len(k.get("hang", [])) for k in khoi),
            "kho_giay": b.get("kho_giay"), "ngay": (b.get("tieu_de") or {}).get("ngay"),
            "so_cot": len(b.get("cot", []))}


def _nguon(lot: Lot) -> dict:
    qi = _doc(lot.process_dir / "qc_input.json")
    if qi is None:
        return {"co": False, "ghi_chu": "qc_input.json — chạy `nhap`"}
    nguon = qi.get("nguon", {}) or {}
    ten = sorted(f"{k}: {v.get('file')}" if isinstance(v, dict) else str(k) for k, v in nguon.items())
    dem = {}
    for n in ("moc", "do"):
        p = lot.process_dir / f"points_{n}.csv"
        dem[n] = max(0, sum(1 for _ in p.open(encoding="utf-8")) - 1) if p.exists() else None
    return {"co": True, "nguon": ten, "so_diem_moc": dem["moc"], "so_diem_do": dem["do"],
            "so_phat_hien": len(qi.get("phat_hien", []))}


# =========================================================================== cảnh báo "kết quả cũ"
def _canh_bao_cu(lot: Lot) -> list[str]:
    ra: list[str] = []
    ps = lot.process_dir
    g, v = _doc(ps / "grid.json"), _doc(ps / "volume.json")
    try:
        cfg = doc_lot(lot.lot_yaml)
    except Exception:                                   # lot.yaml thiếu trường: lõi sẽ nói khi chạy verb
        cfg = None
    if g is not None and cfg is not None:
        cl, ts = cfg.get("luoi") or {}, g["tham_so"]
        sai = []
        if cl.get("cot_m") is not None and not _ds_gan(cl["cot_m"], ts["cot_m"], 1e-6):
            sai.append("cột")
        if cl.get("hang_m") is not None and not _ds_gan(cl["hang_m"], ts["hang_m"], 1e-6):
            sai.append("hàng")
        if cl.get("cot_m") is None and cl.get("kich_thuoc_o_m") is not None and not _gan(cl["kich_thuoc_o_m"], ts["kich_thuoc_o_m"], 1e-9):
            sai.append("kích thước ô")
        if cl.get("goc_luoi") is not None and not _ds_gan(cl["goc_luoi"], ts["goc_luoi"], 1e-3):
            sai.append("gốc lưới")
        gx = cl.get("goc_xoay_do")
        if isinstance(gx, (int, float)) and not isinstance(gx, bool) and not _gan(gx, ts["goc_xoay_do"], 1e-6):
            sai.append("góc xoay")
        if sai:
            ra.append("Lưới đã đổi (" + ", ".join(sai) + ") kể từ lần chạy `luoi` — số liệu lưới/khối lượng là KẾT QUẢ CŨ: "
                      "chạy lại `luoi` rồi `tinh` (hoặc SN_LUOI → Áp dụng).")
    elif g is None and (lot.root / luoi_sua.FILE_TUY_CHINH).exists():
        ra.append("Có lưới tùy chỉnh (luoi_tuy_chinh.yaml) nhưng chưa chạy `luoi` — chưa có kết quả theo lưới đó.")
    if g is not None and v is not None:
        a, b = g["tham_so"], v.get("tham_so", {})
        khac = [k for k in ("cot_m", "hang_m", "goc_luoi") if k in b and not _ds_gan(a[k], b[k], 1e-3)]
        if "goc_xoay_do" in b and not _gan(a["goc_xoay_do"], b["goc_xoay_do"], 1e-6):
            khac.append("goc_xoay_do")
        if khac or v.get("hash_dau_vao") != g.get("hash_dau_vao"):
            ra.append("Khối lượng (volume.json) tính trên lưới/đầu vào khác grid.json hiện tại — chạy lại `tinh`.")
        else:
            from .tinh import hash_hieu_chinh
            if b.get("hieu_chinh_hash") is not None and b["hieu_chinh_hash"] != hash_hieu_chinh(luoi_sua_ghi_de(lot)):
                ra.append("Cao độ đỉnh đã hiệu chỉnh (grid_adjusted.json) sau lần `tinh` — khối lượng là KẾT QUẢ CŨ: chạy lại `tinh`.")
    ms = _doc(ps / "surface_moc.json")
    if g is not None and ms is not None:
        h = (ms.get("sinh_tu") or {}).get("hash_dau_vao")
        if h and g.get("hash_dau_vao") and h != g["hash_dau_vao"]:
            ra.append("Lưới được nội suy từ bề mặt/đầu vào cũ (hash khác surface_moc.json) — chạy lại `luoi` và `tinh`.")
    for n in (1, 2, 3):
        d = doc_cong(lot).get(str(n))
        if d and d.get("duyet") and not cong_da_duyet(lot, n)[0]:
            ra.append(f"{TEN_CONG[n]}: ĐÃ duyệt nhưng kết quả đã thay đổi — phê duyệt mất hiệu lực, cần duyệt lại.")
    return ra


# =========================================================================== điểm vào
def thong_tin(lot: Lot) -> dict:
    ps = lot.process_dir
    co = lambda *ten: all((ps / t).exists() for t in ten)
    buoc = {"nhap": co("points_moc.csv", "qc_input.json"), "mat": co("surface_moc.json", "surface_do.json"),
            "lo": co("lo.json"), "luoi": co("grid.json"), "tinh": co("volume.json"),
            "xuat": (lot.output_dir / "phieu_truy_vet.json").exists()}
    cong = {}
    for n in (1, 2, 3):
        ok, ly = cong_da_duyet(lot, n)
        cong[str(n)] = {"da_duyet": ok, "ly_do_chua": "" if ok else ly, "viec_chan": len(viec_chan(lot, n))}
    try:
        cfg = doc_lot(lot.lot_yaml)
    except Exception:
        cfg = yaml.safe_load(lot.lot_yaml.read_text(encoding="utf-8")) or {}
    qc = _phat_hien_cac_qc(lot)
    so_lieu = {"moc": _tin(lot, "moc", qc), "do": _tin(lot, "do", qc),
               "qc": {"co": all((ps / f"surface_{n}.json").exists() for n in ("moc", "do")),
                      "ghi_chu": "surface_*.json — chạy `mat`"},
               "luoi": _luoi(lot, qc), "khoiluong": _khoi_luong(lot), "ranh": _ranh(lot), "matcat": _mat_cat(lot),
               "bang": _bang(lot), "nguon": _nguon(lot), "bien": _bien(lot)}
    so_lieu["qc"].update({k: sum(so_lieu[n].get(k, 0) for n in ("moc", "do") if so_lieu[n].get("co"))
                          for k in ("so_tam_giac_thieu", "so_tam_giac_det", "so_tam_giac_rac")})
    g = so_lieu["luoi"]
    so_lieu["nhan"] = {"co": g["co"], "so_dinh": g.get("so_dinh"), "so_hieu_chinh": g.get("so_hieu_chinh"),
                       "ghi_chu": g.get("ghi_chu")}
    so_lieu["o"] = {"co": g["co"], "so_o": g.get("so_o"), "so_o_thieu": g.get("so_o_thieu"),
                    "so_o_lech_lon": so_lieu["khoiluong"].get("so_o_lech_lon"), "ghi_chu": g.get("ghi_chu")}
    return {"lo": {"ma_lo": str(cfg.get("ma_lo", "")), "dot": int(cfg.get("dot", 1) or 1), "thu_muc": lot.root.name},
            "buoc": buoc, "buoc_ke_tiep": next((b for b in BUOC if not buoc[b]), None), "cong": cong,
            "canh_bao_cu": _canh_bao_cu(lot), "so_lieu": so_lieu}


def _c(nhan: str, gt) -> list[str]:
    return [nhan, str(gt)]


def dong_hien_thi(tt: dict) -> dict[str, list[list[str]]]:
    """Số liệu → từng nhóm một danh sách [nhãn, giá trị] đã định dạng sẵn, thiếu dữ liệu thì ghi 'Chưa có …'."""
    s = tt["so_lieu"]
    ra: dict[str, list[list[str]]] = {}

    def chua(k: str) -> list[list[str]]:
        return [_c("Trạng thái", f"{CHUA} — {s[k].get('ghi_chu', '')}")]

    for k, ten in (("moc", "mốc"), ("do", "đo")):
        t = s[k]
        if not t["co"]:
            ra[k] = chua(k)
            continue
        ra[k] = [_c("Số đỉnh", _so(t["so_dinh"])), _c("Số tam giác", _so(t["so_tam_giac"])),
                 _c("Tam giác thiếu dữ liệu", _so(t["so_tam_giac_thieu"])),
                 _c("Tam giác dẹt / rác ở mép", f"{_so(t['so_tam_giac_det'])} / {_so(t['so_tam_giac_rac'])}"),
                 _c("Diện tích phủ (m²)", _so(t["dien_tich_phu_m2"], 2)),
                 _c("Cao độ nhỏ nhất (m)", _so(t["z_min"], 3)), _c("Cao độ lớn nhất (m)", _so(t["z_max"], 3)),
                 _c("Cao độ trung bình các đỉnh (m)", _so(t["z_tb"], 3)),
                 _c("Đứt gãy / đoạn ép / cạnh ràng buộc", f"{_so(t['so_dut_gay'])} / {_so(t['so_doan_ep'])} / {_so(t['so_canh_rang_buoc'])}"),
                 _c("Xung đột đứt gãy (QC)", _so(t["xung_dot_dut_gay"])),
                 _c("Điểm vào / gộp trùng", f"{_so(t['so_diem_vao'])} / {_so(t['so_gop'])}"),
                 _c("QC: điểm nghi ngờ cao độ", _so(t["diem_nghi_ngo"])),
                 _c("QC: điểm trùng lệch cao độ", _so(t["diem_trung_lech_cao"])),
                 _c("QC: cặp trùng cùng cao độ", _so(t["diem_trung_cung_cao"]))]
    t = s["qc"]
    ra["qc"] = chua("qc") if not t["co"] else [
        _c("Tam giác thiếu dữ liệu (mốc + đo)", _so(t["so_tam_giac_thieu"])),
        _c("Tam giác dẹt trong vùng dữ liệu", _so(t["so_tam_giac_det"])),
        _c("Tam giác rác loại ở mép", _so(t["so_tam_giac_rac"])),
        _c("Ý nghĩa", "vùng thiếu dữ liệu KHÔNG được tính khối lượng (RULES 8)")]
    t = s["luoi"]
    if not t["co"]:
        ra["luoi"] = chua("luoi")
    else:
        ra["luoi"] = [_c("Số cột × hàng", f"{t['nx']} × {t['ny']}"), _c("Kích thước cột", t["cot"]),
                      _c("Kích thước hàng", t["hang"]), _c("Ô chuẩn (m)", _so(t["kich_thuoc_o_m"], 3)),
                      _c("Góc xoay (độ)", _so(t["goc_xoay_do"], 4)),
                      _c("Gốc lưới E, N", f"{t['goc_luoi'][0]:,.3f}, {t['goc_luoi'][1]:,.3f}"),
                      _c("Số ô trong lô", _so(t["so_o"])),
                      _c("Tổng diện tích ô (m²)", _so(t["dt_o_m2"], 3)), _c("Diện tích lô (m²)", _so(t["dt_lo_m2"], 3)),
                      _c("Chênh tổng ô − lô (m²)", f"{t['chenh_dt_m2']:+.3e}"),
                      _c("Ô thiếu dữ liệu", _so(t["so_o_thieu"])), _c("Ô vắt ranh lô", _so(t["so_o_vat_ranh"])),
                      _c("Ô lệch lớn (nộp so với kiểm)", _so(t["so_o_lech_lon"]) if t["so_o_lech_lon"] is not None else f"{CHUA} (chưa `tinh`)"),
                      _c("Ô dùng cao độ ngoại suy", _so(t["so_o_ngoai_suy"])),
                      _c("Lưới tùy chỉnh (luoi_tuy_chinh.yaml)", "có" if t["tuy_chinh"] else "không — theo lot.yaml")]
    t = s["nhan"]
    ra["nhan"] = chua("nhan") if not t["co"] else [
        _c("Số đỉnh lưới có nhãn", _so(t["so_dinh"])), _c("Đỉnh đã hiệu chỉnh cao độ", _so(t["so_hieu_chinh"])),
        _c("Ghi chú", "nhãn sửa tay trong CAD: dùng SN_DONGBO để nhận về lõi")]
    t = s["o"]
    ra["o"] = chua("o") if not t["co"] else [
        _c("Số ô có nhãn", _so(t["so_o"])), _c("Ô thiếu dữ liệu", _so(t["so_o_thieu"])),
        _c("Ô lệch lớn", _so(t["so_o_lech_lon"]) if t["so_o_lech_lon"] is not None else f"{CHUA} (chưa `tinh`)")]
    t = s["khoiluong"]
    if not t["co"]:
        ra["khoiluong"] = chua("khoiluong")
    else:
        ra["khoiluong"] = [_c("SỐ NỘP — đào (m³)", _so(t["nop_dao"], 3)), _c("SỐ NỘP — đắp (m³)", _so(t["nop_dap"], 3)),
                           _c("SỐ NỘP — ròng (m³)", f"{t['nop_rong']:+,.3f}"),
                           _c("SỐ KIỂM (lăng trụ) — đào (m³)", _so(t["kiem_dao"], 3)),
                           _c("SỐ KIỂM (lăng trụ) — đắp (m³)", _so(t["kiem_dap"], 3)),
                           _c("SỐ KIỂM — ròng (m³)", f"{t['kiem_rong']:+,.3f}"),
                           _c("Chênh nộp − kiểm: đào", f"{_so(t['chenh_dao_m3'], 3)} m³ ({_so(t['chenh_dao_pct'], 2)} %)"),
                           _c("Chênh nộp − kiểm: đắp", f"{_so(t['chenh_dap_m3'], 3)} m³ ({_so(t['chenh_dap_pct'], 2)} %)"),
                           _c("Ô lệch lớn", _so(t["so_o_lech_lon"])), _c("Ô thiếu dữ liệu", _so(t["so_o_thieu"])),
                           _c("Quét phương án (--sweep)", "có" if t["co_sweep"] else "không")]
    t = s["ranh"]
    ra["ranh"] = chua("ranh") if not t["co"] else [_c("Số đoạn ranh đào–đắp", _so(t["so_doan"])),
                                                   _c("Tổng chiều dài (m)", _so(t["chieu_dai_m"], 2))]
    t = s["matcat"]
    if not t["co"]:
        ra["matcat"] = [_c("Trạng thái", f"{CHUA} mặt cắt nào — dùng SN_MATCAT để tạo")]
    else:
        ra["matcat"] = [_c("Số mặt cắt đã tạo", _so(len(t["ds"])))]
        for m in t["ds"]:
            ra["matcat"] += [_c(f"[{m['ten']}] chiều dài (m)", _so(m["chieu_dai_m"], 2)),
                             _c(f"[{m['ten']}] diện tích đào / đắp (m²)", f"{_so(m['dao_m2'], 2)} / {_so(m['dap_m2'], 2)}"),
                             _c(f"[{m['ten']}] đoạn thiếu dữ liệu (m)", _so(m["thieu_m"], 2))]
    t = s["bang"]
    ra["bang"] = chua("bang") if not t["co"] else [
        _c("Số khối bảng", _so(t["so_khoi"])), _c("Số dòng dữ liệu (ô)", _so(t["so_dong"])),
        _c("Số cột", _so(t["so_cot"])), _c("Khổ giấy", t["kho_giay"] or "—"), _c("Ngày lập", t["ngay"] or "—")]
    t = s["nguon"]
    ra["nguon"] = chua("nguon") if not t["co"] else (
        [_c("Điểm mốc / đo đã nhập", f"{_so(t['so_diem_moc'])} / {_so(t['so_diem_do'])}"),
         _c("Phát hiện QC khi nhập", _so(t["so_phat_hien"]))] + [_c("Nguồn", n) for n in t["nguon"]])
    return ra
