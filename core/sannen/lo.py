"""Verb `lo` — chuẩn hóa biên lô và vùng loại trừ (giai đoạn 3).

Biên ngoài ngược chiều kim đồng hồ, vùng loại trừ thuận chiều: công thức diện tích có
dấu tự trừ phần lỗ, và mọi phép tích phân về sau chỉ cần CỘNG các vòng.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from . import io_out, qc
from .config import nguong
from .geom import (Goc, cat_loi, dien_tich_co_dau, giao_doan, huong_canh_dai,
                   tich_phan_tuyen_tinh, trong_da_giac, tu_cat_nhau)
from .mat import doc_geojson, kiem_hash_dau_vao, DauVaoDaDoi
from .paths import Lot

Vong = list[tuple[float, float]]


@dataclass
class LoChuan:
    """Biên lô đã chuẩn hóa, tính trong hệ toạ độ cục bộ của `goc`."""
    goc: Goc
    ngoai: list[Vong] = field(default_factory=list)     # ngược chiều kim đồng hồ
    lo: list[Vong] = field(default_factory=list)        # thuận chiều

    def vong(self):
        return self.ngoai + self.lo

    def dien_tich(self) -> float:
        return sum(dien_tich_co_dau(v) for v in self.vong())

    def dien_tich_trong(self, loi: Vong) -> float:
        """Diện tích phần lô (đã trừ loại trừ) nằm trong đa giác LỒI `loi` (ngược chiều kim)."""
        return sum(dien_tich_co_dau(cat_loi(v, loi)) for v in self.vong())

    def tich_phan_trong(self, loi: Vong, f) -> float:
        """∫ f dA (f tuyến tính) trên phần lô nằm trong `loi`."""
        return sum(tich_phan_tuyen_tinh(cat_loi(v, loi), f) for v in self.vong())

    def trong(self, x: float, y: float) -> bool:
        if any(trong_da_giac((x, y), v) for v in self.lo):
            return False
        return any(trong_da_giac((x, y), v) for v in self.ngoai)

    def hop_bao(self) -> tuple[float, float, float, float]:
        xs = [p[0] for v in self.ngoai for p in v]
        ys = [p[1] for v in self.ngoai for p in v]
        return min(xs), min(ys), max(xs), max(ys)

    def huong_canh_dai(self) -> float:
        return huong_canh_dai([p for v in self.ngoai for p in v])


def _doc_vong(f: dict) -> Vong:
    v = [(c[0], c[1]) for c in f["geometry"]["coordinates"][0]]
    if len(v) > 1 and v[0] == v[-1]:
        v = v[:-1]
    return v


def doc_lo(lot: Lot, goc: Goc | None = None) -> LoChuan:
    """Đọc lo.json (đã chuẩn hóa, toạ độ VN-2000) và dời về gốc cục bộ."""
    p = lot.process_dir / "lo.json"
    if not p.exists():
        raise DauVaoDaDoi("Chưa có lo.json — chạy `lo` trước.")
    d = io_out.doc_json(p)
    if goc is None:
        goc = Goc(d["goc"][0], d["goc"][1])
    return LoChuan(goc,
                   [[goc.vao(e, n) for e, n in b["vong"]] for b in d["bien_lo"]],
                   [[goc.vao(e, n) for e, n in b["vong"]] for b in d["loai_tru"]])


def _cat_nhau_giua(a: Vong, b: Vong) -> bool:
    for i in range(len(a)):
        p1, p2 = a[i], a[(i + 1) % len(a)]
        for j in range(len(b)):
            if giao_doan(p1, p2, b[j], b[(j + 1) % len(b)]):
                return True
    return False


def chay(lot: Lot, cfg: dict, preview: bool) -> int:
    ng = nguong(cfg)
    qi = kiem_hash_dau_vao(lot)
    bien_f = doc_geojson(lot.process_dir / "boundary.geojson")
    lo_f = doc_geojson(lot.process_dir / "exclude.geojson")
    if not bien_f:
        raise DauVaoDaDoi("Không có biên lô (layer SN-BIENLO) — xuất DXF biên lô rồi chạy lại `nhap`.")

    tat_ca = [(f, _doc_vong(f), "bien_lo") for f in bien_f] + [(f, _doc_vong(f), "loai_tru") for f in lo_f]
    goc = Goc.trong_tam([p for _, v, _ in tat_ca for p in v])
    phat_hien: list[dict] = []
    ngoai: list[Vong] = []
    lo: list[Vong] = []
    ten_vong: list[str] = []

    for k, (f, v, vai) in enumerate(tat_ca):
        ten = f"{'biên lô' if vai == 'bien_lo' else 'vùng loại trừ'} #{sum(1 for x in tat_ca[:k + 1] if x[2] == vai)}"
        ten_vong.append(ten)
        if len(v) < 3:
            phat_hien.append(qc._phat_hien("", "vong_thieu_dinh", "chan", f"{ten}: chỉ có {len(v)} đỉnh"))
            continue
        if not f["properties"].get("khep_kin", True):
            phat_hien.append(qc._phat_hien(
                "", "bien_khong_khep", "chan", f"{ten}: không khép kín — diện tích sai dấu",
                vi_tri=v[0], lua_chon=["(a) khép kín trong bản vẽ rồi xuất DXF lại"],
                he_qua="mọi phép tính diện tích sai"))
        loc = [goc.vao(*p) for p in v]
        for g in tu_cat_nhau(loc)[:5]:
            e, n = goc.ra(*g)
            phat_hien.append(qc._phat_hien(
                "", "tu_cat", "chan", f"{ten}: tự cắt — biên giao chính nó",
                vi_tri=(e, n), lua_chon=["(a) sửa biên trong bản vẽ rồi xuất DXF lại"],
                he_qua="diện tích có dấu bị triệt tiêu từng phần, khối lượng sai không báo lỗi"))
        a = dien_tich_co_dau(loc)
        if vai == "bien_lo":
            ngoai.append(v if a >= 0 else v[::-1])
        else:
            lo.append(v if a <= 0 else v[::-1])

    L = LoChuan(goc, [[goc.vao(*p) for p in v] for v in ngoai], [[goc.vao(*p) for p in v] for v in lo])

    # vùng loại trừ phải nằm trọn trong một biên lô và không chồng nhau
    for i, h in enumerate(L.lo):
        nam_trong = [any(trong_da_giac(p, o) for o in L.ngoai) for p in h]
        cat = any(_cat_nhau_giua(h, o) for o in L.ngoai)
        if not all(nam_trong) or cat:
            e, n = goc.ra(*h[0])
            phat_hien.append(qc._phat_hien(
                "", "loai_tru_ra_ngoai", "chan", f"vùng loại trừ #{i + 1} không nằm trọn trong biên lô",
                vi_tri=(e, n), lua_chon=["(a) sửa vùng loại trừ", "(b) người xác nhận và ghi decisions.md"],
                he_qua="diện tích trừ đi nhiều hơn phần thật sự nằm trong lô"))
        for j in range(i + 1, len(L.lo)):
            if _cat_nhau_giua(h, L.lo[j]):
                e, n = goc.ra(*h[0])
                phat_hien.append(qc._phat_hien("", "loai_tru_chong_nhau", "chan",
                                               f"vùng loại trừ #{i + 1} và #{j + 1} chồng nhau — bị trừ hai lần",
                                               vi_tri=(e, n)))
    for i, o in enumerate(L.ngoai):
        for j in range(i + 1, len(L.ngoai)):
            if _cat_nhau_giua(o, L.ngoai[j]):
                e, n = goc.ra(*o[0])
                phat_hien.append(qc._phat_hien("", "bien_chong_nhau", "chan",
                                               f"biên lô #{i + 1} và #{j + 1} cắt nhau — diện tích cộng hai lần",
                                               vi_tri=(e, n)))

    # đối chiếu lệnh AREA
    cad = cfg.get("dien_tich_area_cad_m2") or {}
    cad_bien, cad_lo = cad.get("bien_lo"), cad.get("loai_tru")
    ds_bien = [abs(dien_tich_co_dau(v)) for v in L.ngoai]
    ds_lo = [abs(dien_tich_co_dau(v)) for v in L.lo]
    for ten, tinh_, so_cad in (("biên lô", ds_bien, cad_bien), ("vùng loại trừ", ds_lo, cad_lo)):
        if so_cad is None:
            if tinh_:
                phat_hien.append(qc._phat_hien(
                    "", "chua_doi_chieu_area", "thong_tin",
                    f"{ten}: chưa có số lệnh AREA của AutoCAD trong lot.yaml (dien_tich_area_cad_m2) "
                    f"— lõi tính {', '.join(f'{x:,.3f}' for x in tinh_)} m²"))
            continue
        if len(so_cad) != len(tinh_):
            phat_hien.append(qc._phat_hien("", "area_sai_so_luong", "chan",
                                           f"{ten}: lot.yaml khai {len(so_cad)} số AREA nhưng bản vẽ có {len(tinh_)}"))
            continue
        for i, (a, b) in enumerate(zip(tinh_, so_cad)):
            lech = abs(a - b) / b * 100 if b else float("inf")
            if lech > ng["area_lech_pct"]:
                phat_hien.append(qc._phat_hien(
                    "", "area_lech", "chan",
                    f"{ten} #{i + 1}: lõi {a:,.3f} m² so AREA {b:,.3f} m² — lệch {lech:.4f} % "
                    f"(ngưỡng {ng['area_lech_pct']} %). DỪNG và hỏi (thường do cung tròn hoặc biên lỗi)",
                    lua_chon=["(a) soát lại biên trong bản vẽ", "(b) soát lại số AREA đã đọc"],
                    he_qua="diện tích lô sai thì mọi khối lượng chia theo ô đều lệch"))

    qc.danh_ma(phat_hien, "L")
    chan = [p for p in phat_hien if p["muc"] == "chan"]
    viec = [p for p in phat_hien if p["muc"] != "thong_tin"]
    dt_ngoai, dt_lo = sum(ds_bien), sum(ds_lo)
    print(f"Biên lô: {len(L.ngoai)} vòng, {dt_ngoai:,.3f} m²; loại trừ: {len(L.lo)} vùng, {dt_lo:,.3f} m²; "
          f"DT hữu dụng {dt_ngoai - dt_lo:,.3f} m²")
    for p in phat_hien:
        if p["muc"] == "chan":
            print(f"  CHẶN {p['ma']}: {p['mo_ta']}")

    if preview:
        print(f"\n-- XEM TRƯỚC (RULES 4). Sẽ ghi lo.json, qc_lo.json, viec_can_lam.md")
        print(f"-- Phát hiện: {len(viec)} việc, {len(chan)} chặn")
        return 1 if chan else 0

    lot.ensure()

    def mo_ta_vong(v: Vong, a: float, so_cad):
        return {"vong": [[round(x, 4), round(y, 4)] for x, y in v],
                "so_dinh": len(v), "dien_tich_m2": round(a, 4),
                "dien_tich_area_cad_m2": so_cad}
    io_out.ghi_json(lot, "lo.json", {
        "goc": [goc.e0, goc.n0], "hash_dau_vao": qi.get("hash_dau_vao"),
        "bien_lo": [mo_ta_vong(v, a, (cad_bien or [None] * 99)[i]) for i, (v, a) in enumerate(zip(ngoai, ds_bien))],
        "loai_tru": [mo_ta_vong(v, a, (cad_lo or [None] * 99)[i]) for i, (v, a) in enumerate(zip(lo, ds_lo))],
        "tong": {"dt_bien_lo_m2": round(dt_ngoai, 4), "dt_loai_tru_m2": round(dt_lo, 4),
                 "dt_hieu_dung_m2": round(dt_ngoai - dt_lo, 4)},
        "hop_bao": list(map(lambda v: round(v, 3), [*goc.ra(*L.hop_bao()[:2]), *goc.ra(*L.hop_bao()[2:])])),
        "huong_canh_dai_rad": round(L.huong_canh_dai(), 6)})
    io_out.ghi_json(lot, "qc_lo.json", {"verb": "lo", "hash_dau_vao": qi.get("hash_dau_vao"),
                                        "phat_hien": phat_hien})
    io_out.ghi_viec_gop(lot, "mat + lo (cổng 2)", ["qc_surface.json", "qc_lo.json"])
    print(f"\nĐã ghi lo.json, qc_lo.json. Việc cần làm: {len(viec)} ({len(chan)} chặn)")
    return 1 if chan else 0
