"""KẾ HOẠCH VẼ (JSON) — Python quyết định VẼ GÌ, add-in C# (SanNenDraw.dll) chỉ việc vẽ bằng API AutoCAD.

    python -X utf8 -m sannen_cad.ke_hoach --lot <thư mục lô> --ra <ke_hoach.json> [--lop luoi,nhan,o,ranh,3d,bang] [--dang polyface]

Chỉ ĐỌC lô (grid.json, volume.json, surface_*.json, lo.json, bang_in_cad.json, matcat_*.json) — không ghi file nào của lô.
Mọi con số và bố cục lấy từ đúng hàm sẵn có (`ve.ve_ket_qua`, `bo_cuc`): lớp `BackendKeHoach` bên dưới là một backend
nữa của giao diện `Backend`, chỉ khác là GOM đối tượng thành JSON thay vì sinh .lsp hay ghi DXF. Cùng lô + cùng tham số
luôn ra cùng từng byte (deterministic).

LƯỢC ĐỒ (phien_ban = 1) — toạ độ làm tròn 4 chữ số thập phân (0,1 mm; VN-2000 vẫn đủ), chiều cao chữ 4 chữ số:
    {
      "phien_ban": 1,
      "lenh": "ve" | "tin3d" | "mat_cat",
      "dinh_dang": {"chu_so_thap_phan": 4},
      "truy_vet": {"ma_lo": "...", "dot": 1, "hash_dau_vao": "<16 ký tự>"},       # → XDATA appid SANNEN của MỌI đối tượng
      "xoa":  [{"loai": "luoi"}, {"loai": "mat_cat", "ex": ["ten=MC1"]}, ...],     # purge đúng lô+đợt TRƯỚC khi vẽ
      "lop":  [{"ten": "SN-LUOI", "mau": 8, "tat": false, "dat_mau": false}, ...], # tạo nếu thiếu (tat: tắt khi tạo)
      "doi_tuong": [ {"kieu": ..., "loai": ..., "lop": ..., "mau": 256?, "ex": ["k=v", ...]?, ...}, ... ],
      "hien_lop": [{"ten": "SN-3DF-MOC", "bat": true}, ...],                       # chỉ lệnh tin3d: bật/tắt SAU khi vẽ
      "tom_tat": {"so_doi_tuong": N, "theo_loai": {...}, "theo_lop": {...}}
    }
Các kiểu đối tượng (`kieu`):
    polyface  {dinh: [[x,y,z]...], mat: [[a,b,c]...] (chỉ số đỉnh 0-based)}   MỘT khối ≤ 30000 đỉnh, vượt thì chia khối
    3dface    {p: [[x,y,z] ×3]}                                                (dang = 3dface, lối cũ)
    polyline  {diem: [[x,y]...], dong: bool}                                   LWPOLYLINE (cũng dùng cho đoạn thẳng, khung)
    text      {diem: [x,y], noi_dung, cao}                                     TEXT căn trái, góc 0
    mtext     {diem: [x,y], noi_dung, cao}                                     MTEXT căn giữa (`\\P` = xuống dòng)
`mau` vắng = 256 (theo layer). `ex` vắng = không có "k=v" phụ. XDATA do C# gắn cho mỗi đối tượng đúng như sannen.lsp:
    (1001 "SANNEN") (1000 mã_lô) (1000 đợt) (1000 hash) (1000 loại) (1000 "k=v")...
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from sannen.config import doc_lot
from sannen.paths import Lot
from sannen import io_out

from . import bo_cuc, ve
from .backend import (MAU_LAYER, TOI_DA_DINH_POLYFACE, Backend, chia_polyface, hinh_luoi, kiem_dang_3d, ten_layer)

PHIEN_BAN = 1
SO_THAP_PHAN = 4


def _r(x) -> float:
    return round(float(x), SO_THAP_PHAN)


def _p2(p) -> list[float]:
    return [_r(p[0]), _r(p[1])]


def _p3(p) -> list[float]:
    return [_r(p[0]), _r(p[1]), _r(p[2])]


class BackendKeHoach(Backend):
    """Backend gom đối tượng thành kế hoạch JSON. Các công cụ ĐỌC bản vẽ không có nghĩa ở đây (C# đọc/xóa trong CAD)."""
    toi_da_dinh = TOI_DA_DINH_POLYFACE

    def __init__(self, lenh: str = "ve"):
        self.lenh = lenh
        self.truy_vet: dict | None = None
        self.xoa: list[dict] = []
        self.lop: dict[str, dict] = {}
        self.doi_tuong: list[dict] = []
        self.hien_lop: list[dict] = []
        self._lo_dot: tuple[str, int] | None = None

    # ---- tiện ích -------------------------------------------------------------------------
    def _tv(self, ma_lo: str, dot: int, hash_tv: str) -> None:
        tv = {"ma_lo": str(ma_lo), "dot": int(dot), "hash_dau_vao": str(hash_tv)}
        if self.truy_vet is None:
            self.truy_vet = tv
        elif self.truy_vet != tv:
            raise ValueError(f"Một kế hoạch chỉ có một lô/đợt/hash: {self.truy_vet} ≠ {tv}")

    def _lop(self, goc: str, dot: int | None, tat: bool = False, dat_mau: bool = False) -> str:
        ten = ten_layer(goc, dot)
        if ten not in self.lop:
            self.lop[ten] = {"ten": ten, "mau": MAU_LAYER.get(goc, 7), "tat": bool(tat), "dat_mau": bool(dat_mau)}
        return ten

    def _them(self, kieu: str, loai: str, lop: str, ex: list[str] | None = None, mau: int = 256, **truong) -> None:
        d: dict = {"kieu": kieu, "loai": loai, "lop": lop}
        if mau != 256:
            d["mau"] = int(mau)
        if ex:
            d["ex"] = [str(x) for x in ex]
        d.update(truong)
        self.doi_tuong.append(d)

    def _kq(self, ten: str, xem_truoc: bool, **kq) -> dict:
        return {"cong_cu": ten, "xem_truoc": xem_truoc, "da_ghi": not xem_truoc, **kq}

    # ---- đọc: không làm được từ kế hoạch --------------------------------------------------
    def cad_doc_info(self) -> dict:
        raise NotImplementedError("Kế hoạch vẽ không đọc bản vẽ")

    def cad_read_points(self, layer: str) -> list[list[float]]:
        raise NotImplementedError("Kế hoạch vẽ không đọc bản vẽ")

    def cad_read_polylines(self, layer: str) -> list[dict]:
        raise NotImplementedError("Kế hoạch vẽ không đọc bản vẽ")

    def cad_export_dxf(self, duong_dan: str) -> dict:
        raise NotImplementedError("Kế hoạch vẽ không xuất DXF")

    def cad_read_grid_z(self, ma_lo: str, dot: int | None = None) -> list[dict]:
        raise NotImplementedError("Đọc nhãn đỉnh: lệnh CAD SN_DONGBO (bước 3 của lộ trình)")

    def cad_zoom_to(self, e: float, n: float, kich_thuoc: float = 50.0) -> dict:
        raise NotImplementedError("Zoom do add-in C# làm (SN_TIN3D_NET)")

    # ---- ghi ------------------------------------------------------------------------------
    def cad_purge_sn(self, ma_lo: str, dot: int | None = None, xem_truoc: bool = True,
                     loai: tuple[str, ...] | None = None, ex: list[str] | None = None) -> dict:
        """Ghi danh sách `xoa`. C# xóa MỌI mục `xoa` trước khi vẽ bất cứ gì — đúng thứ tự gọi của `ve_ket_qua`."""
        if dot is not None and not xem_truoc:
            self._tv_lo_dot(ma_lo, dot)
        for l in (loai or ()):
            m: dict = {"loai": l}
            if ex:
                m["ex"] = list(ex)
            self.xoa.append(m)
        return self._kq("cad_purge_sn", xem_truoc, ma_lo=ma_lo, loai=list(loai) if loai else None)

    def _tv_lo_dot(self, ma_lo, dot) -> None:
        """Purge chạy trước khi biết hash: chỉ ghi nhớ lô/đợt để kiểm không lẫn lô khác."""
        if self._lo_dot not in (None, (str(ma_lo), int(dot))):
            raise ValueError("Một kế hoạch chỉ có một lô/đợt")
        self._lo_dot = (str(ma_lo), int(dot))

    def cad_draw_grid(self, ma_lo, dot, hash_tv, luoi, xem_truoc=True) -> dict:
        duong = hinh_luoi(luoi)
        if not xem_truoc:
            self._tv(ma_lo, dot, hash_tv)
            ten = self._lop("SN-LUOI", dot)
            for a, b in duong:
                self._them("polyline", "luoi", ten, diem=[_p2(a), _p2(b)], dong=False)
        return self._kq("cad_draw_grid", xem_truoc, so_duong=len(duong))

    def cad_set_vertex_z(self, ma_lo, dot, hash_tv, nut, xem_truoc=True) -> dict:
        moi = 0
        if not xem_truoc and nut:
            self._tv(ma_lo, dot, hash_tv)
            ten = self._lop("SN-LUOI-NHAN", dot)
            if not any(x["loai"] == "nhan_dinh" and "ex" not in x and "ex_mot_trong" not in x for x in self.xoa):    # xóa nhãn cũ cùng mã đỉnh
                self.xoa.append({"loai": "nhan_dinh", "ex_mot_trong": ["ma=" + str(d["ma"]) for d in nut]})
            for d in nut:
                dz = None if d.get("z_do") is None or d.get("z_moc") is None else d["z_do"] - d["z_moc"]
                for be, z, dy in (("moc", d.get("z_moc"), 0.0), ("do", d.get("z_do"), -1.0), ("dz", dz, -2.0)):
                    if z is None:
                        continue
                    txt = f"{z:+.3f}" if be == "dz" else f"{z:.3f}"
                    self._them("text", "nhan_dinh", ten, ["ma=" + str(d["ma"]), "be_mat=" + be],
                               diem=_p2((d["e"] + 0.3, d["n"] + 0.3 + dy * 0.7)), noi_dung=txt, cao=0.5)
                    moi += 1
        return self._kq("cad_set_vertex_z", xem_truoc, so_nhan=moi)

    def cad_label_cells(self, ma_lo, dot, hash_tv, o, xem_truoc=True) -> dict:
        if not xem_truoc:
            self._tv(ma_lo, dot, hash_tv)
            ten = self._lop("SN-LUOI-O", dot)
            for c in o:
                van_ban = f"{c['ma']}\\PĐào {c['kl_dao_m3']:,.1f}\\PĐắp {c['kl_dap_m3']:,.1f}"
                if c.get("thieu_du_lieu"):
                    van_ban = f"{c['ma']}\\PTHIẾU DỮ LIỆU"
                self._them("mtext", "nhan_o", ten, ["ma=" + str(c["ma"])], diem=_p2((c["e"], c["n"])),
                           noi_dung=van_ban, cao=0.8)
        return self._kq("cad_label_cells", xem_truoc, so_nhan=len(o))

    def cad_draw_cutfill_line(self, ma_lo, dot, hash_tv, doan, xem_truoc=True) -> dict:
        if not xem_truoc and doan:
            self._tv(ma_lo, dot, hash_tv)
            ten = self._lop("SN-RANH-DAODAP", dot)
            for a, b in doan:
                self._them("polyline", "ranh_dao_dap", ten, diem=[_p2(a), _p2(b)], dong=False)
        return self._kq("cad_draw_cutfill_line", xem_truoc, so_doan=len(doan))

    def cad_draw_3dface(self, ma_lo, dot, hash_tv, be_mat, tam_giac, loai="mat", xem_truoc=True, dang="3dface") -> dict:
        kiem_dang_3d(dang)
        goc = "SN-QC" if loai == "qc" else ("SN-3DF-MOC" if be_mat == "moc" else "SN-3DF-DO")
        ten = ten_layer(goc, dot)
        loai_tv = "qc" if loai == "qc" else "mat_3d"
        kq: dict = {}
        khoi = chia_polyface(tam_giac, self.toi_da_dinh) if dang == "polyface" else []
        if dang == "polyface":
            kq = {"dang": "polyface", "so_polyface": len(khoi), "so_dinh": sum(len(d) for d, _ in khoi)}
            if len(khoi) > 1:
                kq["ghi_chu"] = (f"Bề mặt có {kq['so_dinh']} đỉnh — vượt giới hạn một polyface của AutoCAD, "
                                 f"đã chia thành {len(khoi)} khối liên tiếp (mỗi khối ≤ {self.toi_da_dinh} đỉnh)")
        if not xem_truoc and tam_giac:
            self._tv(ma_lo, dot, hash_tv)
            self._lop(goc, dot, tat=goc.startswith("SN-3DF"), dat_mau=True)          # mặt 3D tắt mặc định (layer-convention)
            if dang == "polyface":
                for i, (dinh, mat) in enumerate(khoi, 1):
                    self._them("polyface", loai_tv, ten,
                               [f"be_mat={be_mat}", f"so_mat={len(mat)}", f"khoi={i}/{len(khoi)}"],
                               dinh=[_p3(p) for p in dinh], mat=[list(m) for m in mat])
            else:
                for t in tam_giac:
                    self._them("3dface", loai_tv, ten, [f"be_mat={be_mat}"], p=[_p3(p) for p in t[:3]])
        return self._kq("cad_draw_3dface", xem_truoc, layer=ten, so_mat=len(tam_giac), **kq)

    def cad_draw_table(self, ma_lo, dot, hash_tv, bang, goc_ve, chieu_cao_chu=1.25, xem_truoc=True) -> dict:
        kq = self.ve_ent(ma_lo, dot, hash_tv, "bang", "SN-BANG", bo_cuc.bang_ent(bang, goc_ve, chieu_cao_chu), xem_truoc)
        return {**kq, "cong_cu": "cad_draw_table", "so_khoi": len(bang["khoi"])}

    def ve_ent(self, ma_lo, dot, hash_tv, loai, layer, ent, xem_truoc=True, **them) -> dict:
        """Đối tượng đơn giản của bo_cuc (chữ, khung, đoạn, đa tuyến) → polyline/text. `them` → "k=v" trong dấu truy vết."""
        if not xem_truoc and ent:
            self._tv(ma_lo, dot, hash_tv)
            ten = self._lop(layer, dot)
            ex = [f"{k}={v}" for k, v in them.items()]
            for x in ent:
                if x[0] == "text":
                    self._them("text", loai, ten, ex, mau=x[5] if len(x) > 5 else 256,
                               diem=_p2((x[2], x[3])), noi_dung=str(x[1]), cao=_r(x[4]))
                elif x[0] == "khung":
                    _, fx, fy, fw, fh = x
                    self._them("polyline", loai, ten, ex,
                               diem=[_p2(p) for p in ((fx, fy), (fx + fw, fy), (fx + fw, fy - fh), (fx, fy - fh))], dong=True)
                elif x[0] == "doan":
                    self._them("polyline", loai, ten, ex, mau=x[5] if len(x) > 5 else 256,
                               diem=[_p2((x[1], x[2])), _p2((x[3], x[4]))], dong=False)
                elif x[0] == "pl":
                    self._them("polyline", loai, ten, ex, mau=x[3] if len(x) > 3 else 256,
                               diem=[_p2(p) for p in x[1]], dong=bool(x[2]))
                else:
                    raise ValueError(f"Phần tử bố cục lạ: {x[0]}")
        return self._kq("ve_ent", xem_truoc, loai=loai, so_doi_tuong=len(ent))

    def bat_lop(self, goc: str, dot: int | None, bat: bool) -> None:
        """Bật/tắt layer SAU khi vẽ (SN_TIN3D). C# bỏ qua nếu layer chưa có."""
        self.hien_lop.append({"ten": ten_layer(goc, dot), "bat": bool(bat)})

    # ---- kết xuất ---------------------------------------------------------------------------
    def ke_hoach(self) -> dict:
        theo_loai: dict[str, int] = {}
        theo_lop: dict[str, int] = {}
        for d in self.doi_tuong:
            theo_loai[d["loai"]] = theo_loai.get(d["loai"], 0) + 1
            theo_lop[d["lop"]] = theo_lop.get(d["lop"], 0) + 1
        tv = self.truy_vet
        if tv is None:                                      # chỉ có purge (không vẽ gì): lô/đợt lấy từ lời gọi purge
            lo, dot = self._lo_dot or ("", 1)
            tv = {"ma_lo": lo, "dot": dot, "hash_dau_vao": ""}
        return {"phien_ban": PHIEN_BAN, "lenh": self.lenh, "dinh_dang": {"chu_so_thap_phan": SO_THAP_PHAN},
                "truy_vet": tv, "xoa": self.xoa, "lop": list(self.lop.values()), "doi_tuong": self.doi_tuong,
                "hien_lop": self.hien_lop,
                "tom_tat": {"so_doi_tuong": len(self.doi_tuong), "theo_loai": theo_loai, "theo_lop": theo_lop}}


# =========================================================================== tạo kế hoạch
def tao_ke_hoach(lot_root, lop: list[str] | None = None, dang: str = "polyface") -> dict:
    """Kế hoạch vẽ lại các nhóm `lop` (mặc định tất cả) — đúng thứ tự và đúng nội dung của `ve.ve_ket_qua`."""
    be = BackendKeHoach("ve")
    kiem_dang_3d(dang)
    ve.ve_ket_qua(be, lot_root, xem_truoc=False, lop=lop, dang=dang)
    return be.ke_hoach()


def tao_ke_hoach_tin3d(lot_root, be_mat: str = "ca-hai", dang: str = "polyface") -> dict:
    """Mặt 3D polyface của bề mặt đã chọn (xóa hai mặt cũ rồi vẽ lại), bật lớp đã chọn + SN-QC, tắt lớp còn lại."""
    chon = {"moc": ["moc"], "do": ["do"], "ca-hai": ["moc", "do"]}.get(be_mat)
    if chon is None:
        raise ValueError("be_mat phải là moc, do hoặc ca-hai")
    kiem_dang_3d(dang)
    lot = Lot(Path(lot_root).resolve())
    ps = lot.process_dir
    for n in chon:
        if not (ps / f"surface_{n}.json").exists():
            raise FileNotFoundError(f"Chưa có surface_{n}.json — chạy `mat` trước")
    cfg = doc_lot(lot.lot_yaml)
    s0 = io_out.doc_json(ps / f"surface_{chon[0]}.json")
    hash_tv = str((s0.get("sinh_tu") or {}).get("hash_dau_vao") or "")[:16]
    nc = {"lot": lot, "ps": ps, "ma_lo": str(cfg["ma_lo"]), "dot": int(cfg["dot"]), "hash_tv": hash_tv}
    be = BackendKeHoach("tin3d")
    be.cad_purge_sn(nc["ma_lo"], nc["dot"], xem_truoc=False, loai=("mat_3d", "qc"))
    ve.ve_mat_3d(be, nc, chon, dang=dang)
    be.bat_lop("SN-3DF-MOC", nc["dot"], "moc" in chon)
    be.bat_lop("SN-3DF-DO", nc["dot"], "do" in chon)
    be.bat_lop("SN-QC", nc["dot"], True)
    return be.ke_hoach()


def bo_cuc_mat_cat(lot: Lot, kq: dict, ty_le: float = 5.0, goc_ve=None, trai_x=None, duoi_y=None):
    """(đối tượng bố cục, góc vẽ, có phải mặc định không). Người chọn điểm đặt luôn được ưu tiên; không có thì đặt DƯỚI
    toàn bộ kết quả của lô + đệm ≥ 30 m. Ném ValueError nếu mặt cắt không có đoạn nào nằm trong TIN."""
    if goc_ve:
        gv, mac_dinh = (float(goc_ve[0]), float(goc_ve[1])), False
    else:
        if trai_x is None or duoi_y is None:                # không đo được bản vẽ → dùng hộp bao lô + bảng in
            hb = io_out.doc_json(lot.process_dir / "lo.json")["hop_bao"]
            bp = lot.output_dir / "bang_in_cad.json"
            tx, dy = bo_cuc.duoi_mac_dinh_lot(hb, io_out.doc_json(bp) if bp.exists() else None)
            trai_x = tx if trai_x is None else trai_x
            duoi_y = dy if duoi_y is None else duoi_y
        gv, mac_dinh = bo_cuc.goc_mat_cat_mac_dinh(kq, ty_le, float(trai_x), float(duoi_y)), True
    return bo_cuc.mat_cat_ent(kq, gv, ty_le), gv, mac_dinh


def tao_ke_hoach_mat_cat(lot_root, ten: str, goc_ve=None, ty_le: float = 5.0, trai_x=None, duoi_y=None) -> dict:
    """Vẽ lại mặt cắt `ten` từ matcat_<ten>.json đã có (không tính lại, không ghi lô). Xóa bản vẽ cũ CÙNG TÊN trước."""
    lot = Lot(Path(lot_root).resolve())
    p = lot.process_dir / f"matcat_{ten}.json"
    if not p.exists():
        raise FileNotFoundError(f"Chưa có {p.name} — tạo mặt cắt trước (mat-cat)")
    kq = io_out.doc_json(p)
    ent, gv, _ = bo_cuc_mat_cat(lot, kq, ty_le, goc_ve, trai_x, duoi_y)
    cfg = doc_lot(lot.lot_yaml)
    ma_lo, dot, hs = str(cfg["ma_lo"]), int(cfg["dot"]), str(kq.get("hash_dau_vao") or "")[:16]
    be = BackendKeHoach("mat_cat")
    be.cad_purge_sn(ma_lo, dot, xem_truoc=False, loai=("mat_cat",), ex=[f"ten={ten}"])
    be.ve_ent(ma_lo, dot, hs, "mat_cat", "SN-MATCAT", ent, False, ten=ten)
    return be.ke_hoach()


def tao_ke_hoach_bang(lot_root, loai: str, goc_ve: tuple[float, float]) -> dict:
    """Kế hoạch vẽ bảng biểu (`tong`, `tong-hop`, hoặc `o`) tại `goc_ve`. Xóa bảng cùng `kieu=` trước."""
    if loai not in ("tong", "tong-hop", "o"):
        raise ValueError("--loai phải là tong, tong-hop hoặc o")
    nc = ve.ngu_canh(lot_root)
    vol = nc["vol"]
    if loai == "o":
        import yaml
        from sannen import xuat
        from sannen.config import nguong
        lot = Lot(Path(lot_root).resolve())
        cfg = doc_lot(lot.lot_yaml)
        pj = lot.root.parent.parent / "project.yaml"
        du_an = (yaml.safe_load(pj.read_text(encoding="utf-8")) or {}) if pj.exists() else {}
        kt = xuat.kiem_khop(vol, nguong(cfg))
        ent = bo_cuc.bang_ent(xuat.tao_bang_in_cad(cfg, du_an, vol, kt), goc_ve)
    else:
        tieu, hang = bo_cuc.hang_bang_tong(vol, loai)
        ent = bo_cuc.bang_don_gian_ent(tieu, hang, goc_ve)
    be = BackendKeHoach("bang")
    be.cad_purge_sn(nc["ma_lo"], nc["dot"], xem_truoc=False, loai=("bang",), ex=[f"kieu={loai}"])
    be.ve_ent(nc["ma_lo"], nc["dot"], nc["hash_tv"], "bang", "SN-BANG", ent, False, kieu=loai)
    return be.ke_hoach()


def ghi_json(kh: dict) -> bytes:
    """JSON UTF-8 gọn (không BOM, không khoảng trắng thừa) — cùng kế hoạch thì cùng từng byte."""
    return (json.dumps(kh, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sannen_cad.ke_hoach")
    ap.add_argument("--lot", required=True, type=Path)
    ap.add_argument("--ra", type=Path, help="file kế hoạch JSON; bỏ trống = in ra stdout")
    ap.add_argument("--lop", help="nhóm: " + ",".join(ve.TAT_CA))
    ap.add_argument("--dang", choices=("polyface", "3dface"), default="polyface")
    ap.add_argument("--tin3d", choices=("moc", "do", "ca-hai"), help="kế hoạch xem 3D thay vì vẽ lại nhóm")
    ap.add_argument("--mat-cat", help="tên mặt cắt cần vẽ lại")
    a = ap.parse_args(argv)
    if a.tin3d:
        kh = tao_ke_hoach_tin3d(a.lot, a.tin3d, a.dang)
    elif a.mat_cat:
        kh = tao_ke_hoach_mat_cat(a.lot, a.mat_cat)
    else:
        kh = tao_ke_hoach(a.lot, [x.strip() for x in a.lop.split(",") if x.strip()] if a.lop else None, a.dang)
    b = ghi_json(kh)
    if a.ra:
        a.ra.parent.mkdir(parents=True, exist_ok=True)
        a.ra.write_bytes(b)
    else:
        sys.stdout.buffer.write(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
