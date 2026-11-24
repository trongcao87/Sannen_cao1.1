"""Mặt cắt địa hình dọc một tuyến A–B qua hai bề mặt TIN (mốc và đo).

Chính xác, không lấy mẫu gần đúng: các điểm chia gồm MỌI giao điểm của tuyến với cạnh tam giác của cả hai TIN.
Giữa hai điểm chia liên tiếp, cả hai mặt đều nằm trong đúng một tam giác nên cao độ tuyến tính theo
khoảng cách — diện tích đào/đắp trên mặt cắt (m²) là tích phân đúng của |chênh cao|, cắt đôi tại điểm
chênh cao bằng 0. Chia thêm theo `buoc` chỉ để có bảng cao độ đều đặn mà in/vẽ.
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path

from .luoi import LuoiLoi, nap_dau_vao
from .paths import Lot
from .tin import LOAI_THIEU_DU_LIEU, Tin


class MatCatLoi(LuoiLoi):
    """Tuyến cắt không hợp lệ."""


def _t_giao(tin: Tin, a, b) -> list[float]:
    """Tham số t∈(0,1) nơi tuyến a→b đi vào/ra các tam giác của `tin` (cắt đoạn thẳng bằng ba nửa mặt phẳng)."""
    ra = []
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    dx, dy = b[0] - a[0], b[1] - a[1]
    for i in tin.tam_giac_gan(x0, y0, x1, y1):
        p = tin.da_giac(i)
        t0, t1 = 0.0, 1.0
        for k in range(3):                                   # nửa mặt phẳng bên trái cạnh p[k]→p[k+1] (tam giác CCW)
            u, v = p[k], p[(k + 1) % 3]
            nx, ny = -(v[1] - u[1]), (v[0] - u[0])
            f0 = nx * (a[0] - u[0]) + ny * (a[1] - u[1])
            df = nx * dx + ny * dy
            if abs(df) < 1e-15:
                if f0 < 0:
                    t0, t1 = 1.0, 0.0
                    break
                continue
            t = -f0 / df
            if df > 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                break
        if t0 < t1:
            ra += [t0, t1]
    return [t for t in ra if 1e-12 < t < 1 - 1e-12]


def tinh_mat_cat(moc: Tin, do: Tin, p1: tuple[float, float], p2: tuple[float, float], buoc: float = 1.0) -> dict:
    """p1, p2: toạ độ CỤC BỘ (cùng gốc với hai TIN). Trả dict số liệu mặt cắt (toạ độ cục bộ)."""
    dai = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if dai < 1e-6:
        raise MatCatLoi("Hai điểm của tuyến cắt trùng nhau")
    if buoc <= 0:
        raise MatCatLoi("Bước chia phải dương")
    ts = {0.0, 1.0}
    ts.update(_t_giao(moc, p1, p2))
    ts.update(_t_giao(do, p1, p2))
    n = max(1, math.ceil(dai / buoc))
    ts.update(k / n for k in range(1, n))
    ts = sorted(ts)
    ts = [t for i, t in enumerate(ts) if i == 0 or t - ts[i - 1] > 1e-12]

    tram = []
    for t in ts:
        x, y = p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])
        rm, rd = moc.tra_xy(x, y), do.tra_xy(x, y)
        zm = None if rm is None else rm[0]
        zd = None if rd is None else rd[0]
        tram.append({"ly_trinh": t * dai, "x": x, "y": y, "z_moc": zm, "z_do": zd,
                     "dz": None if zm is None or zd is None else zd - zm,
                     "thieu_du_lieu": any(r is not None and r[1] == LOAI_THIEU_DU_LIEU for r in (rm, rd))})
    # tích phân |dz| theo lý trình, cắt tại dz = 0
    dao = dap = thieu = 0.0
    for a, b in zip(tram, tram[1:]):
        ds = b["ly_trinh"] - a["ly_trinh"]
        if a["dz"] is None or b["dz"] is None:
            thieu += ds
            continue
        za, zb = a["dz"], b["dz"]
        if za * zb >= 0:
            ar = (abs(za) + abs(zb)) / 2 * ds
            if za + zb >= 0:
                dap += ar
            else:
                dao += ar
        else:
            t = za / (za - zb)                              # điểm chênh cao bằng 0
            for dz_, dl in ((za, t * ds), (zb, (1 - t) * ds)):
                ar = abs(dz_) * dl / 2
                if dz_ > 0:
                    dap += ar
                else:
                    dao += ar
    zs = [v for s in tram for v in (s["z_moc"], s["z_do"]) if v is not None]
    return {"chieu_dai_m": dai, "tram": tram, "dien_tich_dao_m2": dao, "dien_tich_dap_m2": dap,
            "doan_thieu_du_lieu_m": thieu, "z_min": min(zs) if zs else None, "z_max": max(zs) if zs else None}


def thuc_hien(lot: Lot, p1_en: tuple[float, float], p2_en: tuple[float, float], buoc: float = 1.0,
              ten: str = "MC1", ghi: bool = True) -> dict:
    """Mặt cắt giữa hai điểm VN-2000. Ghi 10_process/matcat_<ten>.json và 20_output/matcat_<ten>.csv."""
    moc, do, _L, qi = nap_dau_vao(lot)
    goc = moc.goc
    kq = tinh_mat_cat(moc, do, goc.vao(*p1_en), goc.vao(*p2_en), buoc)
    for s in kq["tram"]:
        s["e"], s["n"] = goc.ra(s.pop("x"), s.pop("y"))
    kq.update({"ten": ten, "a": list(p1_en), "b": list(p2_en), "buoc_m": buoc, "hash_dau_vao": qi.get("hash_dau_vao")})
    if ghi:
        lot.ensure()
        (lot.process_dir / f"matcat_{ten}.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
        p = lot.output_dir / f"matcat_{ten}.csv"
        lot.guard_write(p)
        with p.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["ly_trinh_m", "E", "N", "cao_do_moc_m", "cao_do_do_m", "chenh_cao_m", "thieu_du_lieu"])
            for s in kq["tram"]:
                w.writerow([f"{s['ly_trinh']:.3f}", f"{s['e']:.3f}", f"{s['n']:.3f}"]
                           + ["" if s[k] is None else f"{s[k]:.4f}" for k in ("z_moc", "z_do", "dz")]
                           + ["x" if s["thieu_du_lieu"] else ""])
    return kq
