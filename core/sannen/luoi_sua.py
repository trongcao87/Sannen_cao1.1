"""Hiệu chỉnh lưới theo kiểu SNVN (menu Ctrl + chuột phải): đổi kích thước hàng/cột, chèn, xóa,
di chuyển, xoay lưới — và nhập kích thước theo mẫu `Số×KT,Số×KT` (vd `10x20,5x15`).

Lưới sau hiệu chỉnh ghi vào `luoi_tuy_chinh.yaml` ở thư mục lô (GHI ĐÈ mục `luoi` của lot.yaml khi đọc,
xem config.doc_lot) và một dòng vào 90_log/decisions.md: đó là quyết định của người.

Quy ước (khác SNVN ở chỗ nói rõ cái SNVN để ngầm):
  - Chỉ số hàng/cột tính từ 1. Cột đếm theo trục X lưới, hàng theo trục Y lưới.
  - Chèn cột/hàng: ngay SAU cột/hàng chỉ định (0 = chèn trước cột/hàng đầu, gốc lưới lùi lại tương ứng).
  - Xóa/đổi kích thước: gốc lưới giữ nguyên, các cột/hàng sau dịch theo (lưới co/giãn về phía cuối).
  - Xoay: quanh TÂM lưới (xoay quanh gốc làm lưới trôi khỏi lô).
"""
from __future__ import annotations
import math
import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from .luoi import LuoiLoi, doc_luoi
from .paths import Lot

FILE_TUY_CHINH = "luoi_tuy_chinh.yaml"
KHOA = ("kich_thuoc_o_m", "goc_xoay_do", "goc_luoi", "cot_m", "hang_m", "ngoai_suy_m", "ngoai_suy_kieu")


class SuaLuoiLoi(LuoiLoi):
    """Lệnh hiệu chỉnh lưới sai. Báo đúng chỗ sai, không đoán."""


# --------------------------------------------------------------------------- mẫu Số×KT
def phan_tich(mau: str) -> list[float]:
    """`10x20,5x15` → [20]*10 + [15]*5. Chấp nhận ×, X, dấu `;`. Số thập phân dùng dấu chấm."""
    ra: list[float] = []
    for tok in str(mau).replace("×", "x").replace("X", "x").replace(";", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(?:(\d+)\s*x\s*)?(\d+(?:\.\d+)?)", tok)
        if not m:
            raise SuaLuoiLoi(f"«{tok}» không đúng dạng Số×KT (vd 10x20,5x15 — số thập phân dùng dấu chấm)")
        n, k = int(m[1]) if m[1] else 1, float(m[2])
        if n <= 0 or k <= 0:
            raise SuaLuoiLoi(f"«{tok}»: số lượng và kích thước phải dương")
        ra += [k] * n
    if not ra:
        raise SuaLuoiLoi("Chưa nhập kích thước (vd 10x20,5x15)")
    return ra


def dinh_dang(ds: list[float]) -> str:
    """[20,20,15] → `2x20,1x15` (gộp các phần tử liền nhau bằng nhau)."""
    out, i = [], 0
    while i < len(ds):
        j = i
        while j + 1 < len(ds) and abs(ds[j + 1] - ds[i]) < 1e-9:
            j += 1
        out.append(f"{j - i + 1}x{ds[i]:g}")
        i = j + 1
    return ",".join(out)


# --------------------------------------------------------------------------- trạng thái
def trang_thai(lot: Lot) -> dict:
    """Thông số lưới đang dùng (từ grid.json). Hộp thoại CAD hiện đúng các số này."""
    ts = doc_luoi(lot)["tham_so"]
    return {"kich_thuoc_o_m": ts["kich_thuoc_o_m"], "goc_xoay_do": ts["goc_xoay_do"],
            "goc_luoi": list(ts["goc_luoi"]), "cot_m": list(ts["cot_m"]), "hang_m": list(ts["hang_m"]),
            "ngoai_suy_m": ts.get("ngoai_suy_m", 0.0), "ngoai_suy_kieu": ts.get("ngoai_suy_kieu", "gan_nhat")}


def _chi_so(i, so_luong: int, ten: str, cho_phep_0: bool = False) -> int:
    i = int(i)
    lo = 0 if cho_phep_0 else 1
    if not (lo <= i <= so_luong):
        raise SuaLuoiLoi(f"{ten} {i} không có: lưới có {so_luong} {ten.lower()}"
                         + (" (0 = chèn trước cái đầu)" if cho_phep_0 else ""))
    return i


def _truc(st: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    t = math.radians(st["goc_xoay_do"])
    return (math.cos(t), math.sin(t)), (-math.sin(t), math.cos(t))


def ap_dung(st: dict, lenh: str, **kw) -> dict:
    """Áp một lệnh hiệu chỉnh lên bản sao trạng thái. Trả trạng thái mới."""
    st = {**st, "cot_m": list(st["cot_m"]), "hang_m": list(st["hang_m"]), "goc_luoi": list(st["goc_luoi"])}
    def kt() -> float:
        v = float(kw.get("kich_thuoc", 0) or 0)
        if v <= 0:
            raise SuaLuoiLoi("Kích thước phải dương")
        return v

    if lenh in ("doi_cot", "doi_hang"):
        ds = st["cot_m" if lenh == "doi_cot" else "hang_m"]
        ds[_chi_so(kw["chi_so"], len(ds), "Cột" if lenh == "doi_cot" else "Hàng") - 1] = kt()
    elif lenh in ("chen_cot", "chen_hang"):
        cot = lenh == "chen_cot"
        ds = st["cot_m" if cot else "hang_m"]
        sau = _chi_so(kw["sau"], len(ds), "Cột" if cot else "Hàng", cho_phep_0=True)
        k = kt()
        ds.insert(sau, k)
        if sau == 0:                               # chèn trước cái đầu: lùi gốc để các ô cũ đứng yên
            (ux, uy), (vx, vy) = _truc(st)
            d = (ux, uy) if cot else (vx, vy)
            st["goc_luoi"] = [st["goc_luoi"][0] - d[0] * k, st["goc_luoi"][1] - d[1] * k]
    elif lenh in ("xoa_cot", "xoa_hang"):
        cot = lenh == "xoa_cot"
        ds = st["cot_m" if cot else "hang_m"]
        if len(ds) <= 1:
            raise SuaLuoiLoi("Không thể xóa: lưới chỉ còn 1 " + ("cột" if cot else "hàng"))
        del ds[_chi_so(kw["chi_so"], len(ds), "Cột" if cot else "Hàng") - 1]
    elif lenh == "di_chuyen":
        if "den" in kw:                            # điểm gốc mới (E,N)
            st["goc_luoi"] = [float(kw["den"][0]), float(kw["den"][1])]
        else:                                      # hoặc dịch (dE,dN) — như lệnh Move: hai điểm cơ sở cũ/mới
            st["goc_luoi"] = [st["goc_luoi"][0] + float(kw["dx"]), st["goc_luoi"][1] + float(kw["dy"])]
    elif lenh == "xoay":
        (ux, uy), (vx, vy) = _truc(st)
        w, h = sum(st["cot_m"]), sum(st["hang_m"])
        tam = (st["goc_luoi"][0] + ux * w / 2 + vx * h / 2, st["goc_luoi"][1] + uy * w / 2 + vy * h / 2)
        st["goc_xoay_do"] = float(kw["goc_do"])
        (ux, uy), (vx, vy) = _truc(st)
        st["goc_luoi"] = [tam[0] - ux * w / 2 - vx * h / 2, tam[1] - uy * w / 2 - vy * h / 2]
    elif lenh == "dat":                            # nhập cả mẫu Số×KT như hộp thoại "Tạo lưới" của SNVN
        if kw.get("cot") is not None:
            st["cot_m"] = phan_tich(kw["cot"])
        if kw.get("hang") is not None:
            st["hang_m"] = phan_tich(kw["hang"])
        for k_, ten in (("goc_do", "goc_xoay_do"), ("o", "kich_thuoc_o_m"),
                        ("ngoai_suy_m", "ngoai_suy_m"), ("ngoai_suy_kieu", "ngoai_suy_kieu")):
            if kw.get(k_) is not None:
                st[ten] = kw[k_]
        if kw.get("goc_luoi") is not None:
            st["goc_luoi"] = [float(kw["goc_luoi"][0]), float(kw["goc_luoi"][1])]
    else:
        raise SuaLuoiLoi(f"Lệnh hiệu chỉnh lưới lạ: {lenh}")
    return st


# --------------------------------------------------------------------------- ghi
def _hinh_hoc(st: dict) -> tuple:
    return (tuple(round(x, 6) for x in st["cot_m"]), tuple(round(x, 6) for x in st["hang_m"]),
            tuple(round(x, 4) for x in st["goc_luoi"]), round(st["goc_xoay_do"], 6))


def ghi_tuy_chinh(lot: Lot, st: dict, ly_do: str) -> dict:
    """Ghi luoi_tuy_chinh.yaml + decisions.md. Hình học lưới đổi thì hiệu chỉnh đỉnh cũ không còn đúng mã
    (D03-02 trỏ sang ô khác) → cất sang file có đuôi thời gian, KHÔNG xóa."""
    cu = trang_thai(lot) if (lot.process_dir / "grid.json").exists() else None
    ghi = {k: st[k] for k in KHOA if k in st and st[k] is not None}
    ghi["cot_m"] = [round(float(x), 6) for x in ghi["cot_m"]]
    ghi["hang_m"] = [round(float(x), 6) for x in ghi["hang_m"]]
    ghi["goc_luoi"] = [round(float(x), 4) for x in ghi["goc_luoi"]]
    p = lot.root / FILE_TUY_CHINH
    p.write_text("# Lưới do NGƯỜI hiệu chỉnh trong CAD — ghi đè mục `luoi` của lot.yaml. Xóa file này để quay về lot.yaml.\n"
                 + yaml.safe_dump({"luoi": ghi}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cat = None
    adj = lot.process_dir / "grid_adjusted.json"
    if adj.exists() and (cu is None or _hinh_hoc(cu) != _hinh_hoc(st)):
        cat = lot.process_dir / f"grid_adjusted.cu_{datetime.now():%Y%m%d_%H%M%S}.json"
        shutil.move(str(adj), cat)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · luoi (CAD) · {ly_do}: lưới {len(st['cot_m'])} cột × {len(st['hang_m'])} hàng "
                f"[cột {dinh_dang(st['cot_m'])} | hàng {dinh_dang(st['hang_m'])}], góc {st['goc_xoay_do']:g}°, "
                f"gốc ({st['goc_luoi'][0]:.3f}, {st['goc_luoi'][1]:.3f})"
                + (f"; hiệu chỉnh đỉnh cũ cất tại {cat.name}" if cat else "") + "\n")
    return {"da_ghi": str(p), "da_cat_hieu_chinh_dinh": cat.name if cat else None}


def xoa_tuy_chinh(lot: Lot) -> bool:
    p = lot.root / FILE_TUY_CHINH
    if p.exists():
        p.unlink()
        return True
    return False
