"""Verb `luoi` và `hieuchinh` (giai đoạn 4): đặt lưới ô vuông, nội suy cao độ đỉnh lưới.

Lưới = điểm gốc + góc xoay + kích thước từng cột/hàng. Mọi phép tính trong hệ toạ độ
cục bộ (dời gốc về trọng tâm); đổi lại VN-2000 chỉ khi ghi file.
"""
from __future__ import annotations
import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import io_out, qc
from .geom import Goc, cat_loi
from .lo import LoChuan, doc_lo
from .mat import DauVaoDaDoi, kiem_hash_dau_vao
from .paths import Lot
from .tin import LOAI_THIEU_DU_LIEU, Tin

Vong = list[tuple[float, float]]


class LuoiLoi(Exception):
    """Khai báo lưới sai hoặc kết quả mâu thuẫn. DỪNG (RULES 7)."""


def ma_dinh(i: int, j: int) -> str:
    return f"D{i + 1:02d}-{j + 1:02d}"


def ma_o(i: int, j: int) -> str:
    return f"O{i + 1:02d}-{j + 1:02d}"


# =========================================================================== hình học lưới
@dataclass
class Luoi:
    """Lưới trong toạ độ cục bộ: gốc (x0,y0), góc xoay, độ rộng từng cột / cao từng hàng."""
    x0: float
    y0: float
    goc_rad: float
    cot: list[float]
    hang: list[float]
    U: list[float] = field(init=False)
    V: list[float] = field(init=False)

    def __post_init__(self):
        self.U = [0.0]
        for w in self.cot:
            self.U.append(self.U[-1] + w)
        self.V = [0.0]
        for h in self.hang:
            self.V.append(self.V[-1] + h)

    @property
    def nx(self) -> int:
        return len(self.cot)

    @property
    def ny(self) -> int:
        return len(self.hang)

    def xy(self, u: float, v: float) -> tuple[float, float]:
        c, s = math.cos(self.goc_rad), math.sin(self.goc_rad)
        return self.x0 + u * c - v * s, self.y0 + u * s + v * c

    def nut(self, i: int, j: int) -> tuple[float, float]:
        return self.xy(self.U[i], self.V[j])

    def o(self, i: int, j: int) -> Vong:
        """Bốn góc ô, ngược chiều kim đồng hồ."""
        return [self.xy(self.U[i], self.V[j]), self.xy(self.U[i + 1], self.V[j]),
                self.xy(self.U[i + 1], self.V[j + 1]), self.xy(self.U[i], self.V[j + 1])]

    def dt_day_du(self, i: int, j: int) -> float:
        return self.cot[i] * self.hang[j]

    def thanh_dict(self, goc: Goc) -> dict:
        e, n = goc.ra(self.x0, self.y0)
        return {"goc_luoi": [round(e, 4), round(n, 4)],
                "goc_xoay_do": round(math.degrees(self.goc_rad), 6),
                "cot_m": self.cot, "hang_m": self.hang, "nx": self.nx, "ny": self.ny}


def dat_luoi(L: LoChuan, kich_thuoc: float, goc_rad: float, goc_luoi: tuple[float, float] | None = None,
             cot: list[float] | None = None, hang: list[float] | None = None,
             dich_u: float = 0.0, dich_v: float = 0.0) -> Luoi:
    """Đặt lưới vừa khít hộp bao XOAY của biên lô.

    goc_luoi (toạ độ cục bộ) cho trước thì lưới đi qua điểm đó (lùi về nguyên số ô cho phủ
    kín lô). dich_u/dich_v: lùi gốc thêm một đoạn theo trục lưới (dùng cho --sweep).
    """
    if kich_thuoc <= 0:
        raise LuoiLoi("Kích thước ô phải dương")
    c, s = math.cos(goc_rad), math.sin(goc_rad)
    pts = [p for v in L.ngoai for p in v]
    us = [c * x + s * y for x, y in pts]
    vs = [-s * x + c * y for x, y in pts]
    umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
    if goc_luoi is not None:
        uo = c * goc_luoi[0] + s * goc_luoi[1]
        vo = -s * goc_luoi[0] + c * goc_luoi[1]
        # Chỉ "lùi về nguyên số ô cho phủ kín lô" theo trục có kích thước TỰ ĐẶT. Hàng/cột do người khai
        # tường minh (hiệu chỉnh trong CAD) thì giữ ĐÚNG gốc người đặt.
        if cot is None:
            uo += math.floor((umin - uo) / kich_thuoc) * kich_thuoc
        if hang is None:
            vo += math.floor((vmin - vo) / kich_thuoc) * kich_thuoc
    else:
        uo, vo = umin, vmin
    uo -= dich_u
    vo -= dich_v
    if cot is None:
        nx = max(1, math.ceil((umax - uo) / kich_thuoc - 1e-9))
        cot = [kich_thuoc] * nx
    if hang is None:
        ny = max(1, math.ceil((vmax - vo) / kich_thuoc - 1e-9))
        hang = [kich_thuoc] * ny
    return Luoi(c * uo - s * vo, s * uo + c * vo, goc_rad, list(cot), list(hang))


# =========================================================================== đánh giá lưới
@dataclass
class OLuoi:
    i: int
    j: int
    dt_huu_hieu: float
    dt_day_du: float
    z_moc: list[float | None]         # bốn góc: (i,j) (i+1,j) (i+1,j+1) (i,j+1)
    z_do: list[float | None]
    thieu_du_lieu: bool
    ngoai_suy: bool = False           # có đỉnh lấy cao độ NGOẠI SUY (người đã chấp nhận)

    @property
    def vat_ranh_lo(self) -> bool:
        return self.dt_huu_hieu < self.dt_day_du * (1 - 1e-9)


def tam_giac_thieu(tin: Tin) -> list[Vong]:
    ra = []
    for k, (a, b, c) in enumerate(tin.tris):
        if tin.loai[k] == LOAI_THIEU_DU_LIEU:
            ra.append([(tin.x[a], tin.y[a]), (tin.x[b], tin.y[b]), (tin.x[c], tin.y[c])])
    return ra


def danh_gia_luoi(luoi: Luoi, L: LoChuan, tin_moc: Tin, tin_do: Tin,
                  gap: list[Vong] | None = None, ngoai_suy_m=0.0) -> tuple[list[OLuoi], dict]:
    """Nội suy cao độ hai bề mặt lên các đỉnh và tính diện tích hữu hiệu từng ô.

    Ô nào có đỉnh ngoài TIN, hoặc chạm tam giác thiếu dữ liệu TRONG lô, bị đánh dấu
    `thieu_du_lieu` — không tính khối lượng (RULES 8). Trả (ô, cache nút).

    `ngoai_suy_m` > 0 (người đã chấp nhận, ghi ở lot.yaml; có thể là (mét, kiểu)): đỉnh ngoài TIN trong
    khoảng cách này lấy cao độ từ điểm gần nhất của vùng đo (hoặc mặt phẳng kéo dài). Ô nào dùng cách
    đó mang cờ `ngoai_suy`.
    """
    ngoai_suy_m, kieu_ns = ngoai_suy_m if isinstance(ngoai_suy_m, tuple) else (ngoai_suy_m, "gan_nhat")
    bu_diem = kieu_ns == "diem_gan_nhat" and ngoai_suy_m > 0
    if gap is None:
        gap = tam_giac_thieu(tin_moc) + tam_giac_thieu(tin_do)
    cache: dict[tuple[int, int], tuple[float | None, float | None, bool, bool]] = {}
    xa = {"max": 0.0}

    def tra(tin, x, y):
        r = tin.tra_xy(x, y)
        if bu_diem:
            # Người đã quyết: vùng thiếu dữ liệu (ngoài vùng đo HOẶC trong tam giác quá lớn) lấy cao độ
            # của ĐIỂM ĐO gần nhất trong bán kính ngoai_suy_m.
            if r is None or r[1] == LOAI_THIEU_DU_LIEU:
                e = tin.dinh_gan_nhat(x, y, ngoai_suy_m)
                if e is not None:
                    xa["max"] = max(xa["max"], e[1])
                    return (e[0], 0), True
            return r, False
        if r is not None or ngoai_suy_m <= 0:
            return r, False
        e = tin.tra_ngoai_suy(x, y, ngoai_suy_m, kieu_ns)
        if e is not None:
            xa["max"] = max(xa["max"], e[2])
        return (None if e is None else (e[0], e[1])), e is not None

    def nut(i, j):
        if (i, j) not in cache:
            x, y = luoi.nut(i, j)
            (m, em), (d, ed) = tra(tin_moc, x, y), tra(tin_do, x, y)
            cache[(i, j)] = (None if m is None else m[0], None if d is None else d[0],
                             any(r is not None and r[1] == LOAI_THIEU_DU_LIEU for r in (m, d)), em or ed)
        return cache[(i, j)]

    ra: list[OLuoi] = []
    for j in range(luoi.ny):
        for i in range(luoi.nx):
            poly = luoi.o(i, j)
            a = L.dien_tich_trong(poly)
            if a <= 1e-9:
                continue
            goc4 = [nut(i, j), nut(i + 1, j), nut(i + 1, j + 1), nut(i, j + 1)]
            thieu = any(g[0] is None or g[1] is None or g[2] for g in goc4)
            ra.append(OLuoi(i, j, a, luoi.dt_day_du(i, j), [g[0] for g in goc4],
                            [g[1] for g in goc4], thieu, any(g[3] for g in goc4)))
    # tam giác thiếu dữ liệu nằm lọt trong ô nhưng không chạm đỉnh nào
    if gap and not bu_diem:
        theo = {(o.i, o.j): o for o in ra}
        for t in gap:
            xs = [p[0] for p in t]; ys = [p[1] for p in t]
            for (i, j), o in theo.items():
                if o.thieu_du_lieu:
                    continue
                q = luoi.o(i, j)
                qx = [p[0] for p in q]; qy = [p[1] for p in q]
                if max(xs) < min(qx) or min(xs) > max(qx) or max(ys) < min(qy) or min(ys) > max(qy):
                    continue
                manh = cat_loi(t, q)
                if len(manh) >= 3 and L.dien_tich_trong(manh) > 1e-6:
                    o.thieu_du_lieu = True
    return ra, {"nut": cache, "ngoai_suy_max_m": xa["max"]}


# =========================================================================== verb luoi
def tham_so_tu_cfg(cfg: dict, o: float | None, goc: str | None,
                   goc_luoi: str | None, L: LoChuan, ngoai_suy: float | None = None,
                   kieu_ns: str | None = None) -> dict:
    cl = cfg.get("luoi", {})
    kt = float(o if o is not None else cl["kich_thuoc_o_m"])
    g = goc if goc is not None else cl.get("goc_xoay_do", 0)
    if isinstance(g, str) and g.strip().lower() == "auto":
        goc_rad, chon = L.huong_canh_dai(), "tự đặt theo cạnh dài của lô"
    else:
        goc_rad, chon = math.radians(float(g)), "theo tham số"
    gl = None
    if goc_luoi:
        e, n = (float(v) for v in str(goc_luoi).split(","))
        gl = (e, n)
    elif cl.get("goc_luoi"):
        gl = tuple(cl["goc_luoi"])
    return {"kich_thuoc": kt, "goc_rad": goc_rad, "goc_luoi_en": gl, "chon_goc": chon,
            "cot": cl.get("cot_m"), "hang": cl.get("hang_m"),
            "ngoai_suy_m": float(ngoai_suy if ngoai_suy is not None else cl.get("ngoai_suy_m", 0) or 0),
            "ngoai_suy_kieu": kieu_ns or cl.get("ngoai_suy_kieu", "gan_nhat")}


def _doc_be_mat(lot: Lot) -> tuple[Tin, Tin]:
    ps = lot.process_dir
    for ten in ("surface_moc.json", "surface_do.json"):
        if not (ps / ten).exists():
            raise DauVaoDaDoi(f"Chưa có {ten} — chạy `mat` trước.")
    moc, do = (Tin.from_dict(io_out.doc_json(ps / f"surface_{n}.json")) for n in ("moc", "do"))
    if moc.goc != do.goc:
        raise LuoiLoi("Hai bề mặt dựng ở hai gốc toạ độ khác nhau — chạy lại `mat` cho cả hai.")
    return moc, do


def nap_dau_vao(lot: Lot) -> tuple[Tin, Tin, LoChuan, dict]:
    qi = kiem_hash_dau_vao(lot)
    moc, do = _doc_be_mat(lot)
    L = doc_lo(lot, moc.goc)
    return moc, do, L, qi


def chay_luoi(lot: Lot, cfg: dict, preview: bool, o=None, goc=None, goc_luoi=None, ngoai_suy=None,
              kieu_ns=None) -> int:
    moc, do, L, qi = nap_dau_vao(lot)
    ts = tham_so_tu_cfg(cfg, o, goc, goc_luoi, L, ngoai_suy, kieu_ns)
    if ts["ngoai_suy_kieu"] not in ("gan_nhat", "mat_phang", "diem_gan_nhat"):
        raise LuoiLoi("ngoai_suy_kieu chỉ nhận diem_gan_nhat, gan_nhat hoặc mat_phang")
    gl_local = moc.goc.vao(*ts["goc_luoi_en"]) if ts["goc_luoi_en"] else None
    luoi = dat_luoi(L, ts["kich_thuoc"], ts["goc_rad"], gl_local, ts["cot"], ts["hang"])
    o_list, cache = danh_gia_luoi(luoi, L, moc, do, ngoai_suy_m=(ts["ngoai_suy_m"], ts["ngoai_suy_kieu"]))

    tong = sum(o.dt_huu_hieu for o in o_list)
    dt_lo = L.dien_tich()
    phat_hien: list[dict] = []
    if abs(tong - dt_lo) > max(1e-6, 1e-9 * dt_lo):
        phat_hien.append(qc._phat_hien(
            "", "tong_o_khac_dt_lo", "chan",
            f"Tổng diện tích các ô {tong:,.6f} ≠ diện tích lô {dt_lo:,.6f} m² (thiếu {dt_lo - tong:,.3f} m²): "
            "lưới chưa phủ hết lô (nếu vừa hiệu chỉnh hàng/cột/gốc/góc) hoặc lỗi phần mềm",
            lua_chon=["(a) hiệu chỉnh lại lưới cho phủ hết lô", "(b) nếu lưới đã phủ hết mà vẫn lệch: báo lỗi phần mềm"],
            he_qua="mọi khối lượng theo ô sai; không làm tròn cho khớp"))
    thieu = [o for o in o_list if o.thieu_du_lieu]
    for o in thieu[:30]:
        x, y = luoi.nut(o.i, o.j)
        e, n = moc.goc.ra(x, y)
        phat_hien.append(qc._phat_hien(
            "", "o_thieu_du_lieu", "canh_bao",
            f"Ô {ma_o(o.i, o.j)} có đỉnh ngoài TIN hoặc chạm vùng thiếu dữ liệu — không tính khối lượng (RULES 8)",
            vi_tri=(e, n), lua_chon=["(a) yêu cầu đo bổ sung", "(b) dịch/đổi kích thước lưới để tránh",
                                     "(c) người chấp nhận nội suy và ghi decisions.md"],
            he_qua="ô bị loại khỏi số nộp; diện tích đào + đắp ít hơn diện tích lô"))
    if len(thieu) > 30:
        phat_hien.append(qc._phat_hien("", "o_thieu_du_lieu", "canh_bao",
                                       f"còn {len(thieu) - 30} ô thiếu dữ liệu nữa chưa liệt kê"))
    ngoai = [o for o in o_list if o.ngoai_suy and not o.thieu_du_lieu]
    if ngoai:
        phat_hien.append(qc._phat_hien(
            "", "o_ngoai_suy", "canh_bao",
            f"{len(ngoai)} ô ({sum(o.dt_huu_hieu for o in ngoai):,.2f} m²) dùng cao độ NGOẠI SUY ở đỉnh nằm ngoài "
            f"vùng đo (≤ {ts['ngoai_suy_m']:g} m, theo lot.yaml luoi.ngoai_suy_m): {', '.join(ma_o(o.i, o.j) for o in ngoai[:12])}"
            f"{'…' if len(ngoai) > 12 else ''}. Cách bù: " + {
                "diem_gan_nhat": f"cao độ của ĐIỂM ĐO gần nhất (xa nhất {cache['ngoai_suy_max_m']:.2f} m).",
                "gan_nhat": "cao độ tại điểm gần nhất trên mép vùng đo.",
                "mat_phang": "kéo dài mặt phẳng tam giác (dễ sai trên mái dốc)."}[ts["ngoai_suy_kieu"]],
            lua_chon=["(a) giữ — người đã chấp nhận ngoại suy (ghi decisions.md)", "(b) yêu cầu đo bù ra ngoài biên rồi tắt ngoại suy"],
            he_qua="RULES 8 mặc định cấm đoán cao độ ngoài vùng đo; số nộp ở ô này là ước lượng, không phải số đo"))
    qc.danh_ma(phat_hien, "L")
    chan = [p for p in phat_hien if p["muc"] == "chan"]
    vat = sum(1 for o in o_list if o.vat_ranh_lo)
    print(f"Lưới {luoi.nx}×{luoi.ny} ô, {ts['kich_thuoc']:g} m, góc {math.degrees(luoi.goc_rad):.3f}° "
          f"({ts['chon_goc']}); {len(o_list)} ô trong lô ({vat} ô vắt ranh), {len(thieu)} ô thiếu dữ liệu"
          + (f", {len(ngoai)} ô có đỉnh bù dữ liệu thiếu (xa nhất {cache['ngoai_suy_max_m']:.2f} m, "
             f"giới hạn {ts['ngoai_suy_m']:g} m, kiểu {ts['ngoai_suy_kieu']})" if ngoai else ""))
    print(f"Tổng diện tích các ô {tong:,.4f} m² — diện tích lô {dt_lo:,.4f} m² "
          f"(chênh {tong - dt_lo:+.2e})")
    if preview:
        print("\n-- XEM TRƯỚC (RULES 4). Sẽ ghi grid.json. Chạy lại không có --preview để ghi.")
        return 1 if chan else 0

    lot.ensure()
    nut_ra = {}
    dung = {(o.i + di, o.j + dj) for o in o_list for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1))}
    for (i, j) in sorted(dung):
        x, y = luoi.nut(i, j)
        e, n = moc.goc.ra(x, y)
        zm, zd = cache["nut"].get((i, j), (None, None, False, False))[:2]
        nut_ra[ma_dinh(i, j)] = {"i": i, "j": j, "e": round(e, 4), "n": round(n, 4),
                                 # cao độ NỘI SUY giữ 6 chữ số: làm tròn 0,1 mm nhân diện tích
                                 # hàng nghìn m² là hàng chục lít, và làm số nộp lệch số kiểm
                                 "z_moc": None if zm is None else round(zm, 6),
                                 "z_do": None if zd is None else round(zd, 6)}
    io_out.ghi_json(lot, "grid.json", {
        "hash_dau_vao": qi.get("hash_dau_vao"), "goc": [moc.goc.e0, moc.goc.n0],
        "tham_so": {**luoi.thanh_dict(moc.goc), "kich_thuoc_o_m": ts["kich_thuoc"],
                    "chon_goc": ts["chon_goc"], "ngoai_suy_m": ts["ngoai_suy_m"],
                    "ngoai_suy_kieu": ts["ngoai_suy_kieu"]},
        "nut": nut_ra,
        "o": [{"ma": ma_o(o.i, o.j), "i": o.i, "j": o.j, "dt_huu_hieu_m2": round(o.dt_huu_hieu, 6),
               "dt_day_du_m2": round(o.dt_day_du, 6), "vat_ranh_lo": o.vat_ranh_lo,
               "thieu_du_lieu": o.thieu_du_lieu, "ngoai_suy": o.ngoai_suy,
               "nut": [ma_dinh(o.i, o.j), ma_dinh(o.i + 1, o.j), ma_dinh(o.i + 1, o.j + 1),
                       ma_dinh(o.i, o.j + 1)]} for o in o_list],
        "tong": {"dt_o_m2": round(tong, 6), "dt_lo_m2": round(dt_lo, 6), "so_o": len(o_list)}})
    io_out.ghi_json(lot, "qc_luoi.json", {"verb": "luoi", "hash_dau_vao": qi.get("hash_dau_vao"),
                                          "phat_hien": phat_hien})
    io_out.ghi_viec_gop(lot, "luoi (cổng 3)", ["qc_luoi.json"])
    print(f"\nĐã ghi grid.json ({len(nut_ra)} đỉnh). Việc cần làm: "
          f"{sum(1 for p in phat_hien if p['muc'] != 'thong_tin')} ({len(chan)} chặn)")
    return 1 if chan else 0


# =========================================================================== hiệu chỉnh
def doc_luoi(lot: Lot) -> dict:
    p = lot.process_dir / "grid.json"
    if not p.exists():
        raise DauVaoDaDoi("Chưa có grid.json — chạy `luoi` trước.")
    return io_out.doc_json(p)


def doc_hieu_chinh(lot: Lot) -> list[dict]:
    p = lot.process_dir / "grid_adjusted.json"
    return io_out.doc_json(p)["ghi_de"] if p.exists() else []


def nut_hieu_luc(grid: dict, ghi_de: list[dict]) -> dict[str, dict]:
    """Cao độ đỉnh đang HIỆU LỰC: giá trị nội suy, ghi đè bởi `grid_adjusted.json`."""
    nut = {k: dict(v) for k, v in grid["nut"].items()}
    for g in ghi_de:
        if g["ma"] in nut:
            nut[g["ma"]]["z_" + g["be_mat"]] = g["z_moi"]
    return nut


def khoi_luong_o(o: dict, nut: dict[str, dict]) -> dict | None:
    """Phương pháp lưới: V = chênh cao TB 4 góc × diện tích hữu hiệu (dương = đắp)."""
    if o["thieu_du_lieu"]:
        return None
    dz = [nut[m]["z_do"] - nut[m]["z_moc"] for m in o["nut"]]
    tb = sum(dz) / 4.0
    return {"dz_tb": tb, "kl_m3": tb * o["dt_huu_hieu_m2"], "dt": o["dt_huu_hieu_m2"]}


def ghi_hieu_chinh(lot: Lot, ghi_de: list[dict], grid: dict) -> None:
    io_out.ghi_json(lot, "grid_adjusted.json",
                    {"hash_dau_vao": grid.get("hash_dau_vao"), "ghi_de": ghi_de})


def chay_hieuchinh(lot: Lot, cfg: dict, preview: bool, dinh: str | None, z: float | None,
                   be_mat: str, ly_do: str, tu_file: Path | None, bo: str | None) -> int:
    kiem_hash_dau_vao(lot)
    grid = doc_luoi(lot)
    ghi_de = doc_hieu_chinh(lot)
    moi: list[dict] = []
    if tu_file:
        with tu_file.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                moi.append({"ma": r["ma"].strip(), "be_mat": (r.get("be_mat") or be_mat).strip(),
                            "z_moi": float(str(r["z"]).replace(",", ".")),
                            "ly_do": (r.get("ly_do") or ly_do).strip()})
    elif dinh is not None and z is not None:
        moi.append({"ma": dinh, "be_mat": be_mat, "z_moi": z, "ly_do": ly_do})
    elif bo is None:
        print("Thiếu --dinh <mã> --z <giá trị>, hoặc --tu-file <csv: ma,z[,be_mat,ly_do]>, hoặc --bo <mã>")
        return 2
    for m in moi:
        if m["ma"] not in grid["nut"]:
            raise LuoiLoi(f"Không có đỉnh {m['ma']} trong lưới. Mã dạng D03-05 (cột-hàng, tính từ 1).")
        if m["be_mat"] not in ("moc", "do"):
            raise LuoiLoi("--be-mat chỉ nhận moc hoặc do")
    truoc = nut_hieu_luc(grid, ghi_de)
    cu = {(g["ma"], g["be_mat"]): g for g in ghi_de}
    for m in moi:
        goc_z = grid["nut"][m["ma"]]["z_" + m["be_mat"]]
        cu[(m["ma"], m["be_mat"])] = {**m, "z_goc": goc_z,
                                      "luc": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if bo:
        for k in [k for k in cu if k[0] == bo]:
            del cu[k]
    moi_ghi_de = [cu[k] for k in sorted(cu)]
    sau = nut_hieu_luc(grid, moi_ghi_de)

    dung = {m["ma"] for m in moi} | ({bo} if bo else set())
    print(f"{'Áp' if moi else 'Bỏ'} hiệu chỉnh {len(moi) or 1} đỉnh; ô bị ảnh hưởng (tự tính lại chênh cao):")
    tong_truoc = tong_sau = 0.0
    for o in grid["o"]:
        if not (set(o["nut"]) & dung):
            continue
        a, b = khoi_luong_o(o, truoc), khoi_luong_o(o, sau)
        if a is None or b is None:
            continue
        tong_truoc += a["kl_m3"]; tong_sau += b["kl_m3"]
        print(f"  {o['ma']}: chênh cao TB {a['dz_tb']:+.4f} → {b['dz_tb']:+.4f} m; "
              f"KL {a['kl_m3']:+,.3f} → {b['kl_m3']:+,.3f} m³ (dương = đắp)")
    print(f"  Cộng các ô trên: {tong_truoc:+,.3f} → {tong_sau:+,.3f} m³")
    if preview:
        print("\n-- XEM TRƯỚC (RULES 4). Chạy lại không có --preview để ghi grid_adjusted.json.")
        return 0
    lot.ensure()
    ghi_hieu_chinh(lot, moi_ghi_de, grid)
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        luc = datetime.now().strftime("%Y-%m-%d %H:%M")
        for m in moi:
            f.write(f"- {luc} · hieuchinh · Đỉnh {m['ma']} ({m['be_mat']}): "
                    f"{grid['nut'][m['ma']]['z_' + m['be_mat']]} → {m['z_moi']} m"
                    f"{' — ' + m['ly_do'] if m['ly_do'] else ''}\n")
        if bo:
            f.write(f"- {luc} · hieuchinh · Bỏ hiệu chỉnh đỉnh {bo}\n")
    print(f"\nĐã ghi grid_adjusted.json ({len(moi_ghi_de)} hiệu chỉnh) và decisions.md")
    return 0


def chay_resync(lot: Lot, cfg: dict, preview: bool, tu_file: Path | None, chap_nhan: bool) -> int:
    """Đọc ngược cao độ đỉnh từ nhãn CAD. BÁO chênh lệch; chỉ nhận khi có --chap-nhan."""
    kiem_hash_dau_vao(lot)
    grid = doc_luoi(lot)
    if not tu_file:
        print("Cần --tu-file <json hoặc csv> do `cad_read_grid_z` xuất: danh sách {ma, z[, be_mat]}.")
        return 2
    if tu_file.suffix.lower() == ".json":
        doc = json.loads(tu_file.read_text(encoding="utf-8"))
        ds = doc if isinstance(doc, list) else doc.get("nut", [])
    else:
        with tu_file.open(encoding="utf-8-sig", newline="") as f:
            ds = list(csv.DictReader(f))
    ghi_de = doc_hieu_chinh(lot)
    hieu_luc = nut_hieu_luc(grid, ghi_de)
    lech = []
    for r in ds:
        ma, be = r["ma"], r.get("be_mat", "do")
        zc = float(str(r["z"]).replace(",", "."))
        if ma not in hieu_luc:
            raise LuoiLoi(f"Nhãn CAD có đỉnh {ma} không thuộc lưới")
        if abs(hieu_luc[ma]["z_" + be] - zc) > 5e-4:
            lech.append({"ma": ma, "be_mat": be, "z_he_thong": hieu_luc[ma]["z_" + be], "z_cad": zc})
    if not lech:
        print("Nhãn trong bản vẽ khớp hệ thống — không có gì để đồng bộ.")
        return 0
    print(f"{len(lech)} đỉnh trong bản vẽ KHÁC hệ thống:")
    for x in lech[:50]:
        print(f"  {x['ma']} ({x['be_mat']}): hệ thống {x['z_he_thong']:.4f} · bản vẽ {x['z_cad']:.4f} m")
    if not chap_nhan:
        print("\nChưa nhận. Người xem rồi chạy lại với --chap-nhan để cập nhật hệ thống theo bản vẽ.")
        return 1
    if preview:
        print("\n-- XEM TRƯỚC (RULES 4): chưa ghi.")
        return 0
    cu = {(g["ma"], g["be_mat"]): g for g in ghi_de}
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    for x in lech:
        cu[(x["ma"], x["be_mat"])] = {"ma": x["ma"], "be_mat": x["be_mat"], "z_moi": x["z_cad"],
                                      "z_goc": grid["nut"][x["ma"]]["z_" + x["be_mat"]],
                                      "ly_do": "đồng bộ từ nhãn CAD (luoi --resync)", "luc": luc}
    ghi_hieu_chinh(lot, [cu[k] for k in sorted(cu)], grid)
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · luoi --resync · nhận {len(lech)} đỉnh sửa tay trong CAD: "
                + ", ".join(f"{x['ma']}={x['z_cad']}" for x in lech[:20]) + "\n")
    print(f"\nĐã cập nhật grid_adjusted.json ({len(lech)} đỉnh) theo bản vẽ.")
    return 0
