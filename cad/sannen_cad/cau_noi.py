"""Cầu nối giữa AutoLISP (menu SAN NỀN trong AutoCAD) và lõi tính.

    python -X utf8 -m sannen_cad.cau_noi <lệnh> --lot <thư mục lô> --ra <file kết quả> [--lsp <file vẽ>] ...

LISP không phân tích được JSON, nên MỖI lệnh ghi vào `--ra` MỘT s-expression AutoLISP đọc được bằng `(read)`:

    (("ok" . T) ("thong_bao" . "chuỗi") ("du_lieu" . ...))

Lỗi thì ok = nil và thong_bao nói đúng nguyên nhân bằng tiếng Việt (không traceback). Khi cần vẽ vào bản vẽ,
lệnh ghi thêm file `--lsp` (BackendLisp) để LISP `(load)`. Mọi con số vẫn do lõi tính (RULES 1) — LISP chỉ hiển thị.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
import re
import sys
from pathlib import Path

import yaml

from sannen import cong, io_out, luoi as _luoi, luoi_sua, matcat, mcp_server, xuat
from sannen.config import doc_lot, nguong
from sannen.paths import Lot

from . import bo_cuc, ke_hoach, ve
from .backend import NHOM_LOP
from .backend_lisp import BackendLisp

QC_FILES = ("qc_input.json", "qc_surface.json", "qc_lo.json", "qc_luoi.json", "qc_volume.json")
VERB_CHO_PHEP = ("nhap", "mat", "lo", "luoi", "tinh", "xuat")


# =========================================================================== s-expression
def _so(x: float) -> str:
    if x != x or x in (math.inf, -math.inf):
        return "nil"
    s = f"{x:.9f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def _atom(o) -> str:
    if o is None or o is False:
        return "nil"
    if o is True:
        return "T"
    if isinstance(o, int):
        return str(o)
    if isinstance(o, float):
        return _so(o)
    return '"' + str(o).replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n") + '"'


def _cap(k, v) -> str:
    """Một phần tử alist: ("k" . atom) hoặc ("k" phần-tử...) khi giá trị là danh sách / alist."""
    ks = _atom(str(k))
    if isinstance(v, dict) and v:
        return f"({ks} " + " ".join(_cap(a, b) for a, b in v.items()) + ")"
    if isinstance(v, (list, tuple)) and v:
        return f"({ks} " + " ".join(sx(x) for x in v) + ")"
    if v is None or v is False or v == {} or v == [] or v == ():
        return f"({ks})"
    return f"({ks} . {_atom(v)})"


def sx(o) -> str:
    """Python → s-expression AutoLISP: dict → alist, list → (a b c), str → "…", bool → T/nil, None → nil."""
    if isinstance(o, dict):
        return "(" + " ".join(_cap(k, v) for k, v in o.items()) + ")" if o else "nil"
    if isinstance(o, (list, tuple)):
        return "(" + " ".join(sx(x) for x in o) + ")" if o else "nil"
    return _atom(o)


# =========================================================================== tiện ích
class Loi(Exception):
    """Lỗi có thể nói với người dùng — thông báo tiếng Việt đúng nguyên nhân (có thể kèm dữ liệu để hiển thị)."""

    def __init__(self, thong_bao: str, du_lieu=None):
        super().__init__(thong_bao)
        self.du_lieu = du_lieu


def _lot(a) -> Lot:
    p = Path(a.lot).expanduser().resolve()
    if not (p / "lot.yaml").is_file():
        raise Loi(f"{p} không phải thư mục lô (thiếu lot.yaml)")
    return Lot(p)


def _lsp(a) -> Path:
    if not a.lsp:
        raise Loi("Thiếu --lsp (đường dẫn file .lsp để ghi lệnh vẽ)")
    return Path(a.lsp)


def _en(s, ten: str) -> tuple[float, float]:
    try:
        e, n = (float(v) for v in str(s).replace(";", ",").split(","))
        return e, n
    except Exception:
        raise Loi(f"{ten} phải có dạng E,N (vd 445030.5,1113244.4) — nhận được «{s}»")


def _cli(lot: Lot, *argv: str) -> tuple[int, str]:
    return mcp_server._chay_cli([argv[0], "--lot", str(lot.root), *argv[1:]])


def _chan(lot: Lot, ten_qc: str, du_phong: str = "") -> str:
    p = lot.process_dir / ten_qc
    if p.exists():
        ds = [f"{f.get('ma')}: {f.get('mo_ta')}" for f in io_out.doc_json(p).get("phat_hien", []) if f.get("muc") == "chan"]
        if ds:
            return " | ".join(ds)
    return " ".join(du_phong.strip().splitlines()[-3:]) or "lõi báo lỗi"


def _dem(kq: dict) -> dict:
    """Số đối tượng đã vẽ theo từng bước của ve_ket_qua."""
    ra = {}
    for k, v in kq.items():
        for f in ("so_duong", "so_nhan", "so_doan", "so_mat", "so_doi_tuong"):
            if isinstance(v, dict) and f in v:
                ra[k] = v[f]
                break
    return ra


def _dang(a) -> str:
    """Dạng mặt 3D khi vẽ từ menu CAD: mặc định POLYFACE (một đối tượng/bề mặt); `--dang 3dface` giữ lối cũ."""
    d = getattr(a, "dang", None) or "polyface"
    if d not in ("polyface", "3dface"):
        raise Loi("--dang phải là polyface hoặc 3dface")
    return d


def _ve_lsp(lot: Lot, lsp: Path, lop: list[str] | None, dang: str = "polyface") -> dict:
    be = BackendLisp()
    try:
        kq = ve.ve_ket_qua(be, lot.root, lop=lop, dang=dang)
    except FileNotFoundError as e:
        raise Loi(str(e))
    be.luu(lsp)
    return _dem(kq)


def _luoi_doc(lot: Lot) -> dict:
    ts = luoi_sua.trang_thai(lot)
    tong = io_out.doc_json(lot.process_dir / "grid.json")["tong"]
    hb = None
    if (lot.process_dir / "lo.json").exists():
        hb = io_out.doc_json(lot.process_dir / "lo.json").get("hop_bao")
    return {"kich_thuoc": ts["kich_thuoc_o_m"], "goc_xoay_do": ts["goc_xoay_do"], "goc_luoi": ts["goc_luoi"],
            "cot": luoi_sua.dinh_dang(ts["cot_m"]), "hang": luoi_sua.dinh_dang(ts["hang_m"]),
            "nx": len(ts["cot_m"]), "ny": len(ts["hang_m"]), "ngoai_suy_m": ts["ngoai_suy_m"],
            "ngoai_suy_kieu": ts["ngoai_suy_kieu"], "dt_o": tong["dt_o_m2"], "dt_lo": tong["dt_lo_m2"], "so_o": tong["so_o"],
            "hop_bao": hb}


class GiaoDich:
    """Chụp lại các file mà `luoi_sua` + `luoi` + `tinh` sẽ đổi, để KHÔI PHỤC nguyên trạng nếu bước nào hỏng.
    Chỉnh lưới hỏng giữa chừng không được để lô nằm ở trạng thái nửa vời."""

    FILE_PROCESS = ("grid.json", "qc_luoi.json", "volume.json", "qc_volume.json", "grid_adjusted.json", "viec_can_lam.md")

    def __init__(self, lot: Lot):
        self.lot = lot
        self.dau: dict[Path, bytes | None] = {}
        for p in (lot.root / luoi_sua.FILE_TUY_CHINH, lot.log_dir / "decisions.md",
                  *[lot.process_dir / t for t in self.FILE_PROCESS]):
            self.dau[p] = p.read_bytes() if p.exists() else None
        self.cu = set(lot.process_dir.glob("grid_adjusted.cu_*.json"))

    def khoi_phuc(self) -> None:
        for p, b in self.dau.items():
            if b is None:
                if p.exists():
                    p.unlink()
            else:
                p.write_bytes(b)
        for p in set(self.lot.process_dir.glob("grid_adjusted.cu_*.json")) - self.cu:
            p.unlink()


def _tinh_lai(lot: Lot, chi_luoi: bool = False) -> None:
    """luoi rồi tinh (giữ --sweep nếu volume.json hiện có sweep). Nếu chi_luoi=True hoặc chưa có volume.json mà chỉ đặt lưới thì không ép chạy tinh."""
    sweep = False
    vp = lot.process_dir / "volume.json"
    if vp.exists():
        sweep = "sweep" in io_out.doc_json(vp)
    # Nếu người dùng tạo lưới trong CAD mà cổng 2 chưa ghi nhận duyệt (và không có việc chặn ở cổng 2), tự ghi nhận từ thao tác CAD
    ok_c2, _ = cong.cong_da_duyet(lot, 2)
    if not ok_c2 and (lot.process_dir / "surface_moc.json").exists() and (lot.process_dir / "lo.json").exists():
        if not cong.viec_chan(lot, 2):
            cong.duyet_cong({"lot": str(lot.root), "cong": 2, "nguoi_duyet": "Người dùng CAD",
                             "bang_chung": "Người dùng tạo/hiệu chỉnh lưới trong AutoCAD"})
    ma, ra = _cli(lot, "luoi")
    if ma >= 1:
        raise Loi("Lưới không dùng được: " + _chan(lot, "qc_luoi.json", ra))
    if chi_luoi:
        return
    ma, ra = _cli(lot, "tinh", *(["--sweep"] if sweep else []))
    if ma >= 1:
        raise Loi("Tính khối lượng bị chặn: " + _chan(lot, "qc_volume.json", ra))


# =========================================================================== các lệnh
def l_trang_thai(a, lot):
    import json
    van_ban, loi = mcp_server.trang_thai({"lot": str(lot.root)})
    if loi:
        raise Loi(van_ban)
    return json.loads(van_ban), ""


def l_ve(a, lot):
    lop = [x.strip() for x in a.lop.split(",") if x.strip()] if a.lop else None
    try:
        du = _ve_lsp(lot, _lsp(a), lop, _dang(a))
    except ValueError as e:
        raise Loi(str(e))
    return du, "Đã sinh lệnh vẽ — nạp file .lsp để vẽ vào bản vẽ"


def l_ve_ke_hoach(a, lot):
    """Kế hoạch vẽ JSON cho add-in C# (SanNenDraw.dll). CHỈ ĐỌC lô: ghi kế hoạch vào --ke-hoach (hoặc `-` = stdout)."""
    if not a.ke_hoach:
        raise Loi("Thiếu --ke-hoach (file JSON kế hoạch vẽ; `-` = in ra stdout)")
    che_do = a.che_do or "ve"
    dang = _dang(a)
    try:
        if che_do == "ve":
            lop = [x.strip() for x in a.lop.split(",") if x.strip()] if a.lop else None
            kh = ke_hoach.tao_ke_hoach(lot.root, lop, dang)
        elif che_do == "tin3d":
            kh = ke_hoach.tao_ke_hoach_tin3d(lot.root, a.be_mat or "ca-hai", dang)
        elif che_do == "mat-cat":
            if not a.ten:
                raise Loi("--che-do mat-cat cần --ten <tên mặt cắt>")
            kh = ke_hoach.tao_ke_hoach_mat_cat(lot.root, a.ten, _en(a.goc_ve, "--goc-ve") if a.goc_ve else None,
                                               float(a.ty_le_dung or 5.0), a.trai_x, a.duoi_y)
        elif che_do == "bang":
            if not a.loai or not a.goc_ve:
                raise Loi("--che-do bang cần --loai (tong|tong-hop|o) và --goc-ve E,N")
            kh = ke_hoach.tao_ke_hoach_bang(lot.root, a.loai, _en(a.goc_ve, "--goc-ve"))
        else:
            raise Loi("--che-do phải là ve, tin3d, mat-cat hoặc bang")
    except (FileNotFoundError, ValueError) as e:
        raise Loi(str(e))
    b = ke_hoach.ghi_json(kh)
    if a.ke_hoach == "-":
        sys.stdout.buffer.write(b)
    else:
        p = Path(a.ke_hoach)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    ts = kh["tom_tat"]
    return {"ke_hoach": a.ke_hoach, "che_do": che_do, "so_doi_tuong": ts["so_doi_tuong"], "theo_loai": ts["theo_loai"],
            "so_byte": len(b), "ma_lo": kh["truy_vet"]["ma_lo"], "dot": kh["truy_vet"]["dot"]}, \
        f"Kế hoạch vẽ: {ts['so_doi_tuong']} đối tượng"


def l_tin3d(a, lot):
    chon = {"moc": ["moc"], "do": ["do"], "ca-hai": ["moc", "do"]}.get(a.be_mat)
    if chon is None:
        raise Loi("--be-mat phải là moc, do hoặc ca-hai")
    ps = lot.process_dir
    for n in chon:
        if not (ps / f"surface_{n}.json").exists():
            raise Loi(f"Chưa có surface_{n}.json — chạy Tạo TIN cho bề mặt {n.upper()} trước")
    cfg = doc_lot(lot.lot_yaml)
    s0 = io_out.doc_json(ps / f"surface_{chon[0]}.json")
    hash_tv = str((s0.get("sinh_tu") or {}).get("hash_dau_vao") or "")[:16]
    nc = {"lot": lot, "ps": ps, "ma_lo": str(cfg["ma_lo"]), "dot": int(cfg["dot"]), "hash_tv": hash_tv}
    be = BackendLisp()
    be.cad_purge_sn(nc["ma_lo"], nc["dot"], xem_truoc=False, loai=("mat_3d", "qc"))     # xóa hai mặt cũ rồi vẽ lại đúng cái chọn
    dang = _dang(a)
    kq = ve.ve_mat_3d(be, nc, chon, dang=dang)
    be.bat_lop("SN-3DF-MOC", nc["dot"], "moc" in chon)
    be.bat_lop("SN-3DF-DO", nc["dot"], "do" in chon)
    be.bat_lop("SN-QC", nc["dot"], True)
    be.luu(_lsp(a))
    ghi_chu = [v["ghi_chu"] for v in kq.values() if isinstance(v, dict) and v.get("ghi_chu")]
    du = {"so_mat_moc": kq.get("mat_moc", {}).get("so_mat", 0), "so_mat_do": kq.get("mat_do", {}).get("so_mat", 0),
          "so_qc": sum(kq.get(f"qc_{n}", {}).get("so_mat", 0) for n in chon), "dang": dang,
          "so_polyface": sum(v.get("so_polyface", 0) for v in kq.values() if isinstance(v, dict)),
          "chia_khoi": bool(ghi_chu), "ghi_chu": " | ".join(ghi_chu)}
    return du, (f"Mặt 3D ({'polyface — mỗi bề mặt một đối tượng' if dang == 'polyface' else '3DFACE rời'}): "
                f"{' + '.join(chon)} (đã bật); bề mặt còn lại đã tắt" + (f". {' | '.join(ghi_chu)}" if ghi_chu else ""))


def l_tin3d_tat(a, lot):
    dot = int(doc_lot(lot.lot_yaml)["dot"])
    be = BackendLisp()
    be.bat_lop("SN-3DF-MOC", dot, False)
    be.bat_lop("SN-3DF-DO", dot, False)
    be.luu(_lsp(a))
    return None, "Đã tắt mặt 3D"


def _viec_can_lam(lot: Lot) -> list[dict]:
    """Các mục `## <mã> · <loại> · <mức>` của 10_process/viec_can_lam.md (kèm dòng mô tả đầu). Không có file → []."""
    p = lot.process_dir / "viec_can_lam.md"
    if not p.is_file():
        return []
    ra: list[dict] = []
    cho_mo_ta = False
    for d in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(\S+)\s+·\s+(\S+)\s+·\s+(\S+)", d)
        if m:
            ra.append({"ma": m.group(1), "loai": m.group(2), "muc": m.group(3), "mo_ta": ""})
            cho_mo_ta = True
        elif cho_mo_ta and d.strip() and not d.startswith("-"):
            ra[-1]["mo_ta"] = d.strip()
            cho_mo_ta = False
    return ra


def l_thong_tin(a, lot):
    """Số liệu cho bảng điều khiển SN_QL: chỉ ĐỌC các file của lô (không tính, không ghi). Thiếu file → «Chưa có»."""
    from sannen import thong_tin as _tt
    tt = _tt.thong_tin(lot)
    if getattr(a, "json", False):
        # Hợp đồng với palette C# (cad/dotnet): đủ số liệu có cấu trúc + dòng chữ đã định dạng + cảnh báo + việc cần làm.
        return {**tt, "nhom": _tt.dong_hien_thi(tt), "bien_dong": _tt.dong_bien(tt),
                "canh_bao": l_canh_bao(a, lot)[0], "viec_can_lam": _viec_can_lam(lot)}, ""
    return {"lo": tt["lo"], "buoc": tt["buoc"], "buoc_ke_tiep": tt["buoc_ke_tiep"], "cong": tt["cong"],
            "canh_bao_cu": tt["canh_bao_cu"], "nhom": _tt.dong_hien_thi(tt)}, ""


def l_luoi_doc(a, lot):
    if (lot.process_dir / "grid.json").exists():
        return _luoi_doc(lot), ""
    if not getattr(a, "cho_phep_chua_co", False):
        raise Loi("Chưa có grid.json — chạy luoi trước")
    cfg = doc_lot(lot.lot_yaml)
    cl = cfg.get("luoi") or {}
    kt = float(cl.get("kich_thuoc_o_m", 20.0) or 20.0)
    goc = float(cl.get("goc_xoay_do", 0.0) or 0.0) if not isinstance(cl.get("goc_xoay_do"), str) else 0.0
    gl = [0.0, 0.0]
    dt_lo = 0.0
    hb = None
    if (lot.process_dir / "lo.json").exists():
        lo_d = io_out.doc_json(lot.process_dir / "lo.json")
        dt_lo = float(lo_d.get("tong", {}).get("dt_hieu_dung_m2", 0.0))
        hb = lo_d.get("hop_bao")
    # Khi chưa tạo lưới (chưa có grid.json): cột/hàng/nx/ny để trống để chỉ hiển thị sau khi người dùng quét lô & tạo lưới
    return {"kich_thuoc": kt, "goc_xoay_do": goc, "goc_luoi": gl,
            "cot": "", "hang": "",
            "nx": 0, "ny": 0, "ngoai_suy_m": float(cl.get("ngoai_suy_m", 0.0) or 0.0),
            "ngoai_suy_kieu": cl.get("ngoai_suy_kieu", "gan_nhat"), "dt_o": 0.0, "dt_lo": dt_lo, "so_o": 0,
            "hop_bao": hb}, ""


def _kw_luoi_sua(a) -> dict:
    kw: dict = {}
    for ten, v in (("chi_so", a.chi_so), ("sau", a.sau), ("kich_thuoc", a.kich_thuoc), ("dx", a.dx), ("dy", a.dy),
                   ("goc_do", a.goc), ("cot", a.cot), ("hang", a.hang), ("o", a.o),
                   ("ngoai_suy_m", a.ngoai_suy), ("ngoai_suy_kieu", a.kieu)):
        if v is not None:
            kw[ten] = v
    if a.den:
        kw["den"] = _en(a.den, "--den")
    if a.goc_luoi:
        kw["goc_luoi"] = _en(a.goc_luoi, "--goc-luoi")
    return kw


def l_luoi_sua(a, lot):
    if not a.lenh_sua:
        raise Loi("Thiếu --lenh")
    if not (lot.process_dir / "grid.json").exists() and a.lenh_sua != "dat":
        raise Loi("Chưa có grid.json — chạy luoi trước")
    st_cu = luoi_sua.trang_thai(lot) if (lot.process_dir / "grid.json").exists() else {
        "kich_thuoc_o_m": float((doc_lot(lot.lot_yaml).get("luoi") or {}).get("kich_thuoc_o_m", 20.0)),
        "goc_xoay_do": 0.0, "goc_luoi": [0.0, 0.0], "cot_m": [20.0], "hang_m": [20.0],
        "ngoai_suy_m": 0.0, "ngoai_suy_kieu": "gan_nhat"
    }
    moi = luoi_sua.ap_dung(st_cu, a.lenh_sua, **_kw_luoi_sua(a))       # lỗi mẫu/chỉ số: chưa đổi gì
    lsp = None if a.khong_tinh else (Path(a.lsp) if a.lsp else (None if a.json else _lsp(a)))
    chi_luoi = getattr(a, "chi_luoi", False)
    gd = GiaoDich(lot)
    try:
        r = luoi_sua.ghi_tuy_chinh(lot, moi, a.ly_do or f"lệnh {a.lenh_sua}")
        if not a.khong_tinh:
            if chi_luoi and (lot.process_dir / "surface_moc.json").exists() and (lot.process_dir / "lo.json").exists():
                _tinh_lai(lot, chi_luoi=True)
                if lsp is not None:
                    _ve_lsp(lot, lsp, ["luoi", "nhan"])
            elif chi_luoi:
                # Chưa dựng bề mặt/biên lô mà người dùng đã vẽ khung lưới chữ nhật lên CAD trước (như DD_TAOLUOI của SNVN)
                if lsp is not None:
                    cfg = doc_lot(lot.lot_yaml)
                    be = BackendLisp()
                    be.cad_purge_sn(str(cfg["ma_lo"]), int(cfg["dot"]), xem_truoc=False, loai=("luoi",))
                    be.cad_draw_grid(str(cfg["ma_lo"]), int(cfg["dot"]), "khung-luoi", moi, xem_truoc=False)
                    be.luu(lsp)
            else:
                _tinh_lai(lot, chi_luoi=False)
                if lsp is not None:
                    _ve_lsp(lot, lsp, ["luoi", "nhan", "o", "ranh"])
    except Exception:
        gd.khoi_phuc()
        raise
    du = _luoi_doc(lot) if (not a.khong_tinh and (lot.process_dir / "grid.json").exists()) else {
        "kich_thuoc": moi["kich_thuoc_o_m"], "goc_xoay_do": moi["goc_xoay_do"], "goc_luoi": moi["goc_luoi"],
        "cot": luoi_sua.dinh_dang(moi["cot_m"]), "hang": luoi_sua.dinh_dang(moi["hang_m"]),
        "nx": len(moi["cot_m"]), "ny": len(moi["hang_m"]), "ngoai_suy_m": moi.get("ngoai_suy_m", 0.0),
        "ngoai_suy_kieu": moi.get("ngoai_suy_kieu", "gan_nhat"), "dt_o": 0.0, "dt_lo": 0.0, "so_o": 0
    }
    if not a.khong_tinh:
        q = lot.process_dir / "qc_luoi.json"
        du["canh_bao"] = [f["mo_ta"] for f in io_out.doc_json(q).get("phat_hien", []) if f.get("muc") == "canh_bao"] if q.exists() else []
        du["cat_hieu_chinh"] = r["da_cat_hieu_chinh_dinh"]
    return du, ("Đã tạo/cập nhật lưới" if chi_luoi else ("Đã áp dụng và tính lại" if not a.khong_tinh else "Đã ghi lưới tùy chỉnh (chưa tính lại)"))


def l_luoi_ve_lai_lot_yaml(a, lot):
    lsp = Path(a.lsp) if a.lsp else (None if a.json else _lsp(a))
    gd = GiaoDich(lot)
    try:
        luoi_sua.xoa_tuy_chinh(lot)
        _tinh_lai(lot)
        if lsp is not None:
            _ve_lsp(lot, lsp, ["luoi", "nhan", "o", "ranh"])
    except Exception:
        gd.khoi_phuc()
        raise
    return _luoi_doc(lot), "Đã bỏ lưới tùy chỉnh, quay về lot.yaml và tính lại"


def l_luoi_xoa(a, lot):
    """Xóa lưới hiện tại của lô (grid.json, qc_luoi.json, grid_adjusted.json, volume.json, luoi_tuy_chinh.yaml)."""
    da_xoa: list[str] = []
    for ten in ("grid.json", "qc_luoi.json", "grid_adjusted.json", "volume.json", "qc_volume.json"):
        p = lot.process_dir / ten
        if p.is_file():
            p.unlink()
            da_xoa.append(ten)
    tc = lot.root / luoi_sua.FILE_TUY_CHINH
    if tc.is_file():
        tc.unlink()
        da_xoa.append(tc.name)
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · xoa-luoi (CAD) · Người xóa lưới hiện tại ({len(da_xoa)} file)\n")
    a_doc = argparse.Namespace(cho_phep_chua_co=True)
    du, _ = l_luoi_doc(a_doc, lot)
    return du, f"Đã xóa lưới ({len(da_xoa)} file số liệu lưới) và xóa đối tượng lưới trên bản vẽ"


def l_luoi_import_dxf(a, lot):
    """Import thông số lưới ô vuông/chữ nhật từ file DXF hoặc file JSON các đoạn thẳng trên CAD."""
    from sannen import dxfio as _dxfio
    if not a.tu_file:
        raise Loi("Thiếu --tu-file (đường dẫn file .dxf hoặc .json chứa đường lưới)")
    try:
        kq = _dxfio.doc_luoi_dxf(Path(a.tu_file), getattr(a, "layer_luoi", None))
    except Exception as e:
        raise Loi(f"Không import được lưới từ file: {e}")
    cot_str = luoi_sua.dinh_dang(kq["cot_m"])
    hang_str = luoi_sua.dinh_dang(kq["hang_m"])
    st_cu = luoi_sua.trang_thai(lot) if (lot.process_dir / "grid.json").exists() else {
        "kich_thuoc_o_m": float(kq.get("kich_thuoc_o_m", 20.0)),
        "goc_xoay_do": 0.0, "goc_luoi": [0.0, 0.0], "cot_m": [20.0], "hang_m": [20.0],
        "ngoai_suy_m": 0.0, "ngoai_suy_kieu": "gan_nhat"
    }
    dt_lo = 0.0
    if (lot.process_dir / "lo.json").exists():
        dt_lo = float(io_out.doc_json(lot.process_dir / "lo.json").get("tong", {}).get("dt_hieu_dung_m2", 0.0))
    du_doc = {
        "kich_thuoc": float(kq.get("kich_thuoc_o_m", st_cu["kich_thuoc_o_m"])),
        "goc_xoay_do": float(kq["goc_xoay_do"]),
        "goc_luoi": [float(kq["goc_luoi"][0]), float(kq["goc_luoi"][1])],
        "cot": cot_str, "hang": hang_str,
        "nx": len(kq["cot_m"]), "ny": len(kq["hang_m"]),
        "ngoai_suy_m": float(st_cu.get("ngoai_suy_m", 0.0)),
        "ngoai_suy_kieu": str(st_cu.get("ngoai_suy_kieu", "gan_nhat")),
        "dt_o": 0.0, "dt_lo": dt_lo, "so_o": 0
    }
    if getattr(a, "chi_doc", False):
        return du_doc, f"Đã nhận diện lưới từ file: {du_doc['nx']} cột ({cot_str}) × {du_doc['ny']} hàng ({hang_str})"
    moi = {**st_cu, "kich_thuoc_o_m": du_doc["kich_thuoc"], "goc_xoay_do": du_doc["goc_xoay_do"],
           "goc_luoi": du_doc["goc_luoi"], "cot_m": list(kq["cot_m"]), "hang_m": list(kq["hang_m"])}
    lsp = None if a.khong_tinh else (Path(a.lsp) if a.lsp else (None if a.json else _lsp(a)))
    gd = GiaoDich(lot)
    try:
        r = luoi_sua.ghi_tuy_chinh(lot, moi, a.ly_do or f"import lưới từ {Path(a.tu_file).name}")
        if not a.khong_tinh:
            _tinh_lai(lot)
            if lsp is not None:
                _ve_lsp(lot, lsp, ["luoi", "nhan", "o", "ranh"])
    except Exception:
        gd.khoi_phuc()
        raise
    du = _luoi_doc(lot) if not a.khong_tinh else du_doc
    if not a.khong_tinh:
        q = lot.process_dir / "qc_luoi.json"
        du["canh_bao"] = [f["mo_ta"] for f in io_out.doc_json(q).get("phat_hien", []) if f.get("muc") == "canh_bao"] if q.exists() else []
        du["cat_hieu_chinh"] = r["da_cat_hieu_chinh_dinh"]
    return du, f"Đã import lưới ({du_doc['nx']} cột × {du_doc['ny']} hàng)" + (" và tính lại" if not a.khong_tinh else "")


_TEN_HOP_LE = re.compile(r"^[\w\-. ]{1,40}$", re.UNICODE)


def l_mat_cat(a, lot):
    if not (a.a and a.b):
        raise Loi("Cần --a E,N --b E,N (và --goc-ve E,N nếu muốn tự chọn chỗ đặt biểu đồ)")
    ten = a.ten or "MC1"
    if not _TEN_HOP_LE.match(ten):
        raise Loi("Tên mặt cắt chỉ gồm chữ, số, gạch nối, dấu chấm, khoảng trắng (≤ 40 ký tự)")
    pa, pb = _en(a.a, "--a"), _en(a.b, "--b")
    kq = matcat.thuc_hien(lot, pa, pb, float(a.buoc or 1.0), ten)
    ty_le = float(a.ty_le_dung or 5.0)
    try:
        ent, gv, mac_dinh = ke_hoach.bo_cuc_mat_cat(lot, kq, ty_le, _en(a.goc_ve, "--goc-ve") if a.goc_ve else None,
                                                    a.trai_x, a.duoi_y)
    except ValueError as e:
        raise Loi(str(e))
    vung = bo_cuc.hop_bao_ent(ent[3:])
    if a.lsp or not a.json:
        cfg = doc_lot(lot.lot_yaml)
        ma_lo, dot, hs = str(cfg["ma_lo"]), int(cfg["dot"]), str(kq["hash_dau_vao"] or "")[:16]
        be = BackendLisp()
        be.cad_purge_sn(ma_lo, dot, xem_truoc=False, loai=("mat_cat",), ex=[f"ten={ten}"])   # vẽ lại cùng tên → không nhân đôi
        be.ve_ent(ma_lo, dot, hs, "mat_cat", "SN-MATCAT", ent, False, ten=ten)
        be.luu(_lsp(a))
    return {"chieu_dai": kq["chieu_dai_m"], "dien_tich_dao": kq["dien_tich_dao_m2"],
            "dien_tich_dap": kq["dien_tich_dap_m2"], "doan_thieu": kq["doan_thieu_du_lieu_m"],
            "csv": str(lot.output_dir / f"matcat_{ten}.csv"), "goc_ve": [gv[0], gv[1]], "mac_dinh": mac_dinh,
            "vung": [vung[0], vung[1], vung[2], vung[3]]}, \
        f"Mặt cắt {ten}: L = {kq['chieu_dai_m']:.2f} m" + (
            f" — biểu đồ tự đặt dưới kết quả của lô tại ({gv[0]:.1f}; {gv[1]:.1f})" if mac_dinh else "")


def l_bang(a, lot):
    loai = a.loai
    if loai not in ("tong", "tong-hop", "o"):
        raise Loi("--loai phải là tong, tong-hop hoặc o")
    if not a.goc_ve:
        raise Loi("Thiếu --goc-ve E,N")
    gv = _en(a.goc_ve, "--goc-ve")
    try:
        nc = ve.ngu_canh(lot.root)
    except FileNotFoundError as e:
        raise Loi(str(e))
    vol = nc["vol"]
    if loai == "o":
        cfg = doc_lot(lot.lot_yaml)
        pj = lot.root.parent.parent / "project.yaml"
        du_an = (yaml.safe_load(pj.read_text(encoding="utf-8")) or {}) if pj.exists() else {}
        kt = xuat.kiem_khop(vol, nguong(cfg))
        ent = bo_cuc.bang_ent(xuat.tao_bang_in_cad(cfg, du_an, vol, kt), gv)
    else:
        tieu, hang = bo_cuc.hang_bang_tong(vol, loai)
        ent = bo_cuc.bang_don_gian_ent(tieu, hang, gv)
    be = BackendLisp()
    be.cad_purge_sn(nc["ma_lo"], nc["dot"], xem_truoc=False, loai=("bang",), ex=[f"kieu={loai}"])
    be.ve_ent(nc["ma_lo"], nc["dot"], nc["hash_tv"], "bang", "SN-BANG", ent, False, kieu=loai)
    be.luu(_lsp(a))
    return {"kieu": loai, "so_doi_tuong": len(ent)}, f"Bảng «{loai}» đã sinh lệnh vẽ"


def l_xem3d(a, lot):
    """Sinh trình xem 3D HTML (verb `xem3d` của lõi) và mở bằng trình duyệt mặc định.
    Nếu chưa có surface_moc.json / surface_do.json nhưng đã có dữ liệu điểm thì tự động chạy nhap/mat để tạo bề mặt TIN trước."""
    ps = lot.process_dir
    if not (ps / "surface_moc.json").exists() and not (ps / "surface_do.json").exists():
        if not (ps / "points_moc.csv").exists() and not (ps / "points_do.csv").exists():
            _cli(lot, "nhap", "--xac-nhan-anh-xa")
        co_diem = any(
            (ps / f"points_{n}.csv").is_file() and sum(1 for _ in (ps / f"points_{n}.csv").open(encoding="utf-8")) > 3
            for n in ("moc", "do")
        )
        if co_diem:
            ok_c1, _ = cong.cong_da_duyet(lot, 1)
            if not ok_c1 and not cong.viec_chan(lot, 1):
                cong.duyet_cong({"lot": str(lot.root), "cong": 1, "nguoi_duyet": "Người dùng CAD",
                                 "bang_chung": "Người dùng bấm Tạo & Xem 3D HTML trong AutoCAD"})
            _cli(lot, "mat", "--be-mat", "ca-hai")
    ma, ra = _cli(lot, "xem3d", "--mo")
    dong = [d.strip() for d in ra.splitlines() if d.strip()]
    if ma != 0:
        raise Loi("Không dựng được trình xem 3D: " + (" ".join(dong[-3:]) if dong else
                                                      f"verb xem3d báo mã thoát {ma} (lõi chưa có verb này hoặc tham số sai)"))
    file = next((d for d in reversed(dong) if d.lower().endswith(".html")), dong[-1] if dong else "")
    if file.startswith("Đã tạo trình xem 3D:"):
        file = file.split("Đã tạo trình xem 3D:", 1)[1].strip()
    return {"file": file}, f"Đã mở trình xem 3D: {file}"


def _ket_qua_cli(ma: int, ra: str):
    du = {"ma_thoat": ma, "van_ban": ra}
    if ma > 1:
        raise Loi("Lõi dừng (mã thoát %d) — xem nội dung chi tiết" % ma, du)
    return du, ("" if ma == 0 else "Xong nhưng còn việc chặn hoặc chưa nhận — đọc nội dung")


def l_chay(a, lot):
    if a.verb not in VERB_CHO_PHEP:
        raise Loi(f"--verb phải là một trong: {', '.join(VERB_CHO_PHEP)}")
    ma, ra = _cli(lot, a.verb, *(a.them.split() if a.them else []))
    return _ket_qua_cli(ma, ra)


def l_dong_bo(a, lot):
    if not a.tu_file or not Path(a.tu_file).is_file():
        raise Loi("Thiếu --tu-file hoặc không thấy file CSV nhãn đỉnh do CAD xuất")
    ma, ra = _cli(lot, "luoi", "--resync", "--tu-file", str(a.tu_file), *(["--chap-nhan"] if a.chap_nhan else []))
    return _ket_qua_cli(ma, ra)


def l_hieuchinh_nhieu(a, lot):
    if not a.tu_file or not Path(a.tu_file).is_file():
        raise Loi("Thiếu --tu-file hoặc không thấy file CSV (ma,z,be_mat,ly_do)")
    lsp = Path(a.lsp) if a.lsp else (None if a.json else _lsp(a))
    ma, ra = _cli(lot, "hieuchinh", "--tu-file", str(a.tu_file), *(["--ly-do", a.ly_do] if a.ly_do else []))
    if ma >= 2:
        raise Loi("Hiệu chỉnh đỉnh bị từ chối: " + " ".join(ra.strip().splitlines()[-3:]))
    co_vol = (lot.process_dir / "volume.json").exists()
    if co_vol and not getattr(a, "chi_luoi", False):
        sweep = "sweep" in io_out.doc_json(lot.process_dir / "volume.json")
        ma2, ra2 = _cli(lot, "tinh", *(["--sweep"] if sweep else []))
        if ma2 >= 1:
            raise Loi("Đã ghi hiệu chỉnh nhưng tính lại bị chặn: " + _chan(lot, "qc_volume.json", ra2))
        du = _ve_lsp(lot, lsp, ["nhan", "o"]) if lsp is not None else {}
    else:
        du = _ve_lsp(lot, lsp, ["nhan"]) if lsp is not None else {}
    return {"ma_thoat": ma, "van_ban": ra, "da_ve": du}, "Đã hiệu chỉnh cao độ mắt lưới và cập nhật chênh cao" + (" (đã sinh lệnh vẽ lại nhãn)" if lsp else "")


def l_canh_bao(a, lot):
    thu_tu = {"chan": 0, "canh_bao": 1, "thong_tin": 2}
    ra = []
    for ten in QC_FILES:
        p = lot.process_dir / ten
        if not p.exists():
            continue
        for f in io_out.doc_json(p).get("phat_hien", []):
            vt = f.get("vi_tri") or [None, None]
            ra.append({"ma": f.get("ma"), "muc": f.get("muc"), "loai": f.get("loai"), "mo_ta": f.get("mo_ta"),
                       "e": vt[0], "n": vt[1], "nguon": ten})
    ra.sort(key=lambda x: thu_tu.get(x["muc"], 3))          # sort ổn định: chặn trước, giữ thứ tự gốc trong từng mức
    return ra, f"{len(ra)} phát hiện"


def l_o_tai(a, lot):
    if a.e is None or a.n is None:
        raise Loi("Cần --e E --n N")
    gp, vp = lot.process_dir / "grid.json", lot.process_dir / "volume.json"
    if not gp.exists():
        raise Loi("Chưa có grid.json — chạy luoi trước")
    g_doc = io_out.doc_json(gp)
    ts = g_doc["tham_so"]
    th = math.radians(ts["goc_xoay_do"])
    dx, dy = float(a.e) - ts["goc_luoi"][0], float(a.n) - ts["goc_luoi"][1]
    u, v = dx * math.cos(th) + dy * math.sin(th), -dx * math.sin(th) + dy * math.cos(th)

    def chi_so(x, ds):
        t = 0.0
        for k, w in enumerate(ds):
            t += w
            if x < t - 1e-12 or (k == len(ds) - 1 and x <= t + 1e-9):
                return k if x >= -1e-9 else None
        return None
    i, j = chi_so(u, ts["cot_m"]), chi_so(v, ts["hang_m"])
    if i is None or j is None:
        raise Loi("Điểm nằm ngoài lưới")
    ma = _luoi.ma_o(i, j)
    if vp.exists():
        o = next((c for c in io_out.doc_json(vp)["o"] if c["ma"] == ma), None)
        if o is None:
            raise Loi(f"Điểm nằm trong lưới (ô {ma}) nhưng ngoài lô — ô này không có diện tích trong lô")
        return {"ma": ma, "kl_dao": o["kl_dao_m3"], "kl_dap": o["kl_dap_m3"], "dt": o["dt_huu_hieu_m2"],
                "thieu_du_lieu": bool(o["thieu_du_lieu"])}, ""
    o_g = next((c for c in g_doc.get("o", []) if c["ma"] == ma), None)
    return {"ma": ma, "kl_dao": 0.0, "kl_dap": 0.0, "dt": o_g["dt_huu_hieu_m2"] if o_g else 0.0,
            "thieu_du_lieu": bool(o_g["thieu_du_lieu"]) if o_g else False}, ""


def _ntc_mac_dinh_trong() -> dict:
    """Khi người dùng làm việc trên AutoCAD (hoặc vừa bấm Làm mới): khởi tạo nguồn trống để KHÔNG tự động nạp dữ liệu ví dụ của lot.yaml."""
    return {
        "be_mat_moc": {"nguon": "chua_khai_bao"},
        "be_mat_do": {"nguon": "chua_khai_bao"},
        "bien_lo": {"nguon": "chua_khai_bao"},
        "dut_gay": {"nguon": "chua_khai_bao"},
        "bo_diem": [],
    }


def l_khoi_tao_be_mat(a, lot):
    """Nhận cấu hình khởi tạo thủ công từ CAD/Excel (điểm mốc/đo, breakline, biên lô), ghi nguon_tuy_chinh.yaml,
    chạy nhap + mat + lo để khởi tạo bề mặt TIN và chuẩn hóa biên lô."""
    import shutil
    from datetime import datetime
    ntc_p = lot.root / "nguon_tuy_chinh.yaml"
    co_file_tuy_chinh = any(getattr(a, k, None) for k in ("file_moc", "file_do", "file_dut_gay", "file_bien_lo", "file_loai_tru"))
    if ntc_p.exists():
        ntc = yaml.safe_load(ntc_p.read_text(encoding="utf-8")) or {}
    elif co_file_tuy_chinh:
        ntc = _ntc_mac_dinh_trong()
    else:
        ntc = {}
    if co_file_tuy_chinh:
        for k_m, v_m in _ntc_mac_dinh_trong().items():
            ntc.setdefault(k_m, v_m)
    lot.process_dir.mkdir(parents=True, exist_ok=True)

    for nhan in ("moc", "do"):
        nguon = getattr(a, f"nguon_{nhan}", None)
        file_p = getattr(a, f"file_{nhan}", None)
        if not nguon or not file_p:
            continue
        src = Path(file_p)
        if nguon in ("cad_chon", "csv_diem"):
            if not src.is_file():
                raise Loi(f"Không thấy file điểm {nhan} từ AutoCAD: {src}")
            dst = lot.process_dir / f"cad_chon_{nhan}.csv"
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            ntc[f"be_mat_{nhan}"] = {"nguon": "cad_chon", "file": f"10_process/cad_chon_{nhan}.csv"}
        elif nguon in ("excel", "csv"):
            # Nếu file nằm ngoài 00_input/, copy vào 10_process/ hoặc nếu nằm trong 00_input/ thì dùng tên file
            if src.is_file():
                in_p = lot.input_dir / src.name
                if in_p.is_file() and in_p.resolve() == src.resolve():
                    rel_f = src.name
                else:
                    # RULES 3: không ghi vào 00_input/, lưu bản sao vào 10_process/ nếu file ngoài 00_input/
                    # hoặc nếu bang_in đọc từ 00_input, kiểm tra xem file có trong 00_input không
                    if (lot.input_dir / src.name).is_file():
                        rel_f = src.name
                    else:
                        dst = lot.process_dir / f"excel_{nhan}{src.suffix.lower()}"
                        shutil.copy2(src, dst)
                        rel_f = f"../10_process/{dst.name}"
            else:
                rel_f = str(file_p)
            d_bm = {"nguon": nguon, "file": rel_f}
            sh_ten = getattr(a, f"sheet_{nhan}", None)
            if sh_ten:
                d_bm["sheet"] = sh_ten
            ntc[f"be_mat_{nhan}"] = d_bm
        elif nguon in ("dxf_layer", "dxf"):
            d_bm = {"nguon": "dxf_layer", "layer": getattr(a, f"layer_{nhan}", None) or ("*" if nguon == "dxf" else ("SN-DIEM-MOC" if nhan == "moc" else "SN-DIEM-DO"))}
            if file_p and file_p != "-":
                src = Path(file_p)
                if src.is_file():
                    try:
                        rel_f = str(src.resolve().relative_to(lot.input_dir.resolve()))
                    except ValueError:
                        try:
                            rel_f = "../" + str(src.resolve().relative_to(lot.root.resolve())).replace("\\", "/")
                        except ValueError:
                            dst = lot.process_dir / f"dxf_{nhan}{src.suffix.lower()}"
                            shutil.copy2(src, dst)
                            rel_f = f"../10_process/{dst.name}"
                    d_bm["file"] = rel_f
                else:
                    d_bm["file"] = str(file_p)
            ntc[f"be_mat_{nhan}"] = d_bm

    if getattr(a, "file_dut_gay", None):
        src = Path(a.file_dut_gay)
        if not src.is_file():
            raise Loi(f"Không thấy file breakline từ AutoCAD: {src}")
        dst = lot.process_dir / "cad_chon_dut_gay.json"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        ntc["dut_gay"] = {"nguon": "cad_chon", "file": "10_process/cad_chon_dut_gay.json"}

    if getattr(a, "file_bien_lo", None):
        src = Path(a.file_bien_lo)
        if not src.is_file():
            raise Loi(f"Không thấy file biên lô từ AutoCAD: {src}")
        dst = lot.process_dir / "cad_chon_bien_lo.json"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        ntc["bien_lo"] = {"nguon": "cad_chon", "file": "10_process/cad_chon_bien_lo.json"}

    if getattr(a, "file_loai_tru", None):
        src = Path(a.file_loai_tru)
        if src.is_file():
            dst = lot.process_dir / "cad_chon_loai_tru.json"
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            ntc["loai_tru"] = {"nguon": "cad_chon", "file": "10_process/cad_chon_loai_tru.json"}

    ntc_p.write_text("# Nguồn dữ liệu do NGƯỜI chọn thủ công từ AutoCAD / Excel — ghi đè lot.yaml.\n"
                     + yaml.safe_dump(ntc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · khoi-tao-be-mat (CAD) · Người khởi tạo dữ liệu bề mặt/breakline/biên lô thủ công\n")

    # Bước 1: chạy nhap (với --xac-nhan-anh-xa nếu người đã chọn file Excel trực tiếp trong hộp thoại)
    nhap_args = ["nhap"] + (["--xac-nhan-anh-xa"] if getattr(a, "xac_nhan_anh_xa", False) else [])
    ma_nhap, ra_nhap = _cli(lot, *nhap_args)
    if ma_nhap >= 2:
        raise Loi("Nhập dữ liệu dừng: " + " ".join(ra_nhap.strip().splitlines()[-4:]), {"van_ban": ra_nhap, "ma_thoat": ma_nhap})

    # Nếu chỉ lưu nguồn và chạy nhap (hoặc chưa yêu cầu dựng TIN ngay)
    if getattr(a, "chi_nhap", False):
        ra_lo_nhanh = ""
        if getattr(a, "file_bien_lo", None) or getattr(a, "file_loai_tru", None):
            ok_c1_n, _ = cong.cong_da_duyet(lot, 1)
            if not ok_c1_n and not cong.viec_chan(lot, 1):
                cong.duyet_cong({"lot": str(lot.root), "cong": 1, "nguoi_duyet": getattr(a, "nguoi", None) or "Người dùng CAD",
                                 "bang_chung": "Người dùng chọn biên lô thủ công trong AutoCAD"})
            if cong.cong_da_duyet(lot, 1)[0]:
                _, ra_lo_nhanh = _cli(lot, "lo")
                # Nếu đã có bề mặt TIN trước đó thì tự động cắt/dựng lại TIN theo phạm vi đường bao vừa chọn
                ps = lot.process_dir
                co_moc, co_do = (ps / "surface_moc.json").exists(), (ps / "surface_do.json").exists()
                if co_moc or co_do:
                    bm_cat = "ca-hai" if (co_moc and co_do) else ("moc" if co_moc else "do")
                    _cli(lot, "mat", "--be-mat", bm_cat)
                    if a.lsp:
                        _ve_3d_va_nguon(lot, Path(a.lsp), bm_cat, _dang(a), ve_nguon=False)
        if a.lsp and (getattr(a, "file_moc", None) or getattr(a, "file_do", None)):
            chon_bm = []
            if getattr(a, "file_moc", None) and getattr(a, "nguon_moc", None) not in ("cad_chon", "csv_diem"):
                chon_bm.append("moc")
            if getattr(a, "file_do", None) and getattr(a, "nguon_do", None) not in ("cad_chon", "csv_diem"):
                chon_bm.append("do")
            if chon_bm:
                _ve_diem_nguon_cad(lot, Path(a.lsp), chon_bm)
        return {"ma_thoat": ma_nhap, "van_ban": (ra_nhap + "\n" + ra_lo_nhanh).strip(), "nguon": ntc}, "Đã nạp dữ liệu đầu vào"

    # Người chủ động bấm "Khởi tạo bề mặt" trong CAD → nếu cổng 1 chưa duyệt và không có việc chặn ở cổng 1,
    # ghi nhận người duyệt cổng 1 thông qua hành động bấm nút khởi tạo bề mặt (nếu còn việc chặn thì dừng báo rõ).
    ok_c1, _ = cong.cong_da_duyet(lot, 1)
    if not ok_c1:
        chan1 = cong.viec_chan(lot, 1)
        if chan1:
            raise Loi("Dữ liệu đầu vào có việc CHẶN, cần xử lý trước khi dựng bề mặt: " + " | ".join(chan1),
                      {"van_ban": ra_nhap, "ma_thoat": ma_nhap})
        cong.duyet_cong({"lot": str(lot.root), "cong": 1, "nguoi_duyet": getattr(a, "nguoi", None) or "Người dùng CAD",
                         "bang_chung": "Người dùng khởi tạo bề mặt thủ công trong AutoCAD"})

    be_mat = getattr(a, "be_mat", None) or "ca-hai"
    ma_mat, ra_mat = _cli(lot, "mat", "--be-mat", be_mat)
    if ma_mat >= 2:
        raise Loi("Dựng bề mặt TIN dừng: " + " ".join(ra_mat.strip().splitlines()[-3:]),
                  {"van_ban": ra_nhap + "\n" + ra_mat, "ma_thoat": ma_mat})

    ra_lo = ""
    ma_lo = 0
    if (lot.process_dir / "boundary.geojson").exists():
        b_feats = json.loads((lot.process_dir / "boundary.geojson").read_text(encoding="utf-8")).get("features", [])
        if b_feats:
            ma_lo, ra_lo = _cli(lot, "lo")
            if ma_lo >= 2:
                raise Loi("Chuẩn hóa biên lô dừng: " + " ".join(ra_lo.strip().splitlines()[-3:]),
                          {"van_ban": ra_nhap + "\n" + ra_mat + "\n" + ra_lo, "ma_thoat": ma_lo})

    if a.lsp:
        try:
            nc = ve.ngu_canh(lot.root)
            be = BackendLisp()
            chon = ["moc", "do"] if be_mat == "ca-hai" else [be_mat]
            be.cad_purge_sn(nc["ma_lo"], nc["dot"], xem_truoc=False, loai=("mat_3d", "qc"))
            ve.ve_mat_3d(be, nc, chon, dang=_dang(a))
            be.luu(Path(a.lsp))
        except Exception:
            pass

    vb_gop = "\n".join(x.strip() for x in (ra_nhap, ra_mat, ra_lo) if x.strip())
    return {"ma_thoat": max(ma_nhap, ma_mat, ma_lo), "van_ban": vb_gop, "nguon": ntc}, \
        "Đã khởi tạo bề mặt thành công — sẵn sàng cho Agent rà soát, chuẩn hóa và tạo nhiều phương án"


def l_duyet(a, lot):
    van_ban, loi = cong.duyet_cong({"lot": str(lot.root), "cong": a.cong, "nguoi_duyet": a.nguoi or "",
                                          "bang_chung": a.bang_chung or ""})
    if loi:
        raise Loi(van_ban)
    return None, van_ban


def l_xoa_du_lieu_cu(a, lot):
    """Xóa sạch dữ liệu xử lý/kết quả cũ đã có từ trước (10_process, 20_output, cấu hình ghi đè và cổng duyệt), giữ nguyên 00_input/."""
    da_xoa: list[str] = []
    for d in (lot.process_dir, lot.output_dir):
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.name == ".gitkeep":
                    continue
                if p.is_file():
                    p.unlink()
                    da_xoa.append(p.name)
    for ten in ("nguon_tuy_chinh.yaml", luoi_sua.FILE_TUY_CHINH):
        p = lot.root / ten
        if p.is_file():
            p.unlink()
            da_xoa.append(ten)
    cong_p = lot.log_dir / "cong.json"
    if cong_p.is_file():
        cong_p.unlink()
        da_xoa.append("cong.json")
    # Ghi nguon_tuy_chinh.yaml ở trạng thái "chua_khai_bao" để khi người dùng khai báo mới trên CAD sẽ KHÔNG bị dính dữ liệu mẫu từ lot.yaml
    ntc_p = lot.root / "nguon_tuy_chinh.yaml"
    ntc_p.write_text("# Nguồn dữ liệu phiên làm việc CAD mới (trống cho tới khi người dùng chọn dữ liệu trên CAD/Excel).\n"
                     + yaml.safe_dump(_ntc_mac_dinh_trong(), allow_unicode=True, sort_keys=False), encoding="utf-8")
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")
    with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
        f.write(f"- {luc} · lam-moi (CAD) · Xóa dữ liệu xử lý cũ ({len(da_xoa)} file) để khởi tạo lại từ đầu\n")
    return {"so_file_xoa": len(da_xoa), "da_xoa": da_xoa}, f"Đã xóa {len(da_xoa)} file dữ liệu cũ — lô đã sạch để khởi tạo mới"


def _ve_diem_nguon_cad(lot: Lot, lsp_p: Path, chon: list[str], be: BackendLisp | None = None) -> dict:
    """Chèn trực quan toàn bộ điểm đã import từ Excel/CSV/DXF (và đường bao/breakline từ DXF nếu có) vào vùng CAD đang mở
    để người dùng kiểm tra ngay bằng mắt trên bản vẽ."""
    import csv as _csv
    cfg = doc_lot(lot.lot_yaml)
    ma_lo, dot = str(cfg["ma_lo"]), int(cfg["dot"])
    ps = lot.process_dir
    qi = io_out.doc_json(ps / "qc_input.json") if (ps / "qc_input.json").is_file() else {}
    hash_tv = str(qi.get("hash_dau_vao") or "import")[:16]
    luu_rieng = be is None
    if be is None:
        be = BackendLisp()
    min_e, min_n, max_e, max_n = 1e30, 1e30, -1e30, -1e30
    so_diem_ve = 0
    for n in chon:
        lop_d = "SN-DIEM-MOC" if n == "moc" else "SN-DIEM-DO"
        mau_d = 3 if n == "moc" else 2
        p_csv = ps / f"points_{n}.csv"
        if not p_csv.is_file():
            continue
        ent_d = []
        with p_csv.open(encoding="utf-8", newline="") as f:
            for r in _csv.DictReader(f):
                e_v, n_v, z_v = float(r["easting"]), float(r["northing"]), float(r["z"])
                min_e, max_e = min(min_e, e_v), max(max_e, e_v)
                min_n, max_n = min(min_n, n_v), max(max_n, n_v)
                ent_d.append(("point", e_v, n_v, z_v, mau_d))
                ent_d.append(("text3d", f"{z_v:.2f}", e_v + 0.35, n_v + 0.15, z_v, 0.7, mau_d))
                so_diem_ve += 1
        if ent_d:
            be._lop_da_khai.add(lop_d)
            be.dong.append(f"(snv:lop \"{lop_d}\" {mau_d} nil)")
            be.dong.append(f"(snv:bat \"{lop_d}\" T)")
            be.cad_purge_sn(ma_lo, dot, xem_truoc=False, loai=(f"diem_{n}",))
            be.ve_ent(ma_lo, dot, hash_tv, f"diem_{n}", lop_d, ent_d, False)
    p_dg = ps / "breaklines.geojson"
    if p_dg.is_file():
        feats = json.loads(p_dg.read_text(encoding="utf-8")).get("features", [])
        ent_dg = []
        for ft in feats:
            coords = ft.get("geometry", {}).get("coordinates", [])
            if len(coords) >= 2:
                ent_dg.append(("pl", [(c[0], c[1]) for c in coords], False, 1))
        if ent_dg:
            be._lop_da_khai.add("SN-DUTGAY")
            be.dong.append("(snv:lop \"SN-DUTGAY\" 1 nil)")
            be.dong.append("(snv:bat \"SN-DUTGAY\" T)")
            be.cad_purge_sn(ma_lo, dot, xem_truoc=False, loai=("dut_gay_mcp",))
            be.ve_ent(ma_lo, dot, hash_tv, "dut_gay_mcp", "SN-DUTGAY", ent_dg, False)
    p_bien = ps / "boundary.geojson"
    if p_bien.is_file():
        feats = json.loads(p_bien.read_text(encoding="utf-8")).get("features", [])
        ent_b = []
        for ft in feats:
            coords = (ft.get("geometry", {}).get("coordinates") or [[]])[0]
            if len(coords) >= 3:
                pts = [(c[0], c[1]) for c in coords]
                if len(pts) > 1 and pts[0] == pts[-1]:
                    pts = pts[:-1]
                for px, py in pts:
                    min_e, max_e = min(min_e, px), max(max_e, px)
                    min_n, max_n = min(min_n, py), max(max_n, py)
                ent_b.append(("pl", pts, True, 5))
        if ent_b:
            be._lop_da_khai.add("SN-BIENLO")
            be.dong.append("(snv:lop \"SN-BIENLO\" 5 nil)")
            be.dong.append("(snv:bat \"SN-BIENLO\" T)")
            be.cad_purge_sn(ma_lo, dot, xem_truoc=False, loai=("bien_lo_mcp",))
            be.ve_ent(ma_lo, dot, hash_tv, "bien_lo_mcp", "SN-BIENLO", ent_b, False)
    if luu_rieng:
        if min_e <= max_e and min_n <= max_n:
            pad_x = max((max_e - min_e) * 0.1, 10.0)
            pad_y = max((max_n - min_n) * 0.1, 10.0)
            be.dong.append(
                f"(vl-catch-all-apply '(lambda () (command \"_.ZOOM\" \"_W\" "
                f"(list {min_e - pad_x:.3f} {min_n - pad_y:.3f}) (list {max_e + pad_x:.3f} {max_n + pad_y:.3f}))) nil)"
            )
        be.luu(lsp_p)
    return {"so_diem_ve": so_diem_ve}


def _ve_mat_3d_cat_bien(lot: Lot, be, nc: dict, chon: list[str], dang: str = "polyface") -> dict:
    """Khi vẽ mặt 3D trên CAD hoặc tạo kế hoạch 3D: nếu lô có đường bao (boundary.geojson) thì chỉ vẽ các tam giác
    nằm trong phạm vi đường bao (và ngoài vùng loại trừ) để lưới tam giác trên CAD không tràn ra ngoài đường bao."""
    from sannen.mat import vong_ngoai, vong_loai_tru, cat_tin_theo_bien
    from sannen.tin import Tin
    bien = vong_ngoai(lot)
    lt = vong_loai_tru(lot)
    if not bien:
        return ve.ve_mat_3d(be, nc, chon, dang=dang)
    kq: dict[str, dict] = {}
    for nhan in chon:
        s = io_out.doc_json(nc["ps"] / f"surface_{nhan}.json")
        tin = Tin.from_dict(s)
        cat_tin_theo_bien(tin, bien, lt)
        d = s["diem"]
        tot = [[d[a], d[b], d[c]] for (a, b, c), l in zip(tin.tris, tin.loai) if l == 0]
        xau = [[d[a], d[b], d[c]] for (a, b, c), l in zip(tin.tris, tin.loai) if l != 0]
        kq[f"mat_{nhan}"] = be.cad_draw_3dface(nc["ma_lo"], nc["dot"], nc["hash_tv"], nhan, tot, "mat", xem_truoc=False, dang=dang)
        if xau:
            kq[f"qc_{nhan}"] = be.cad_draw_3dface(nc["ma_lo"], nc["dot"], nc["hash_tv"], nhan, xau, "qc", xem_truoc=False, dang=dang)
    return kq


def _ve_3d_va_nguon(lot: Lot, lsp_p: Path, be_mat: str = "ca-hai", dang: str = "polyface", ve_nguon: bool = False) -> dict:
    """Vẽ mặt 3D Mesh (cắt theo phạm vi đường bao nếu có, và tùy chọn vẽ các điểm nguồn/đứt gãy từ 10_process lên CAD)."""
    cfg = doc_lot(lot.lot_yaml)
    ma_lo, dot = str(cfg["ma_lo"]), int(cfg["dot"])
    ps = lot.process_dir
    chon = ["moc", "do"] if be_mat == "ca-hai" else [be_mat]
    for n in chon:
        if not (ps / f"surface_{n}.json").exists():
            raise Loi(f"Chưa có surface_{n}.json — cần tạo TIN trước")
    s0 = io_out.doc_json(ps / f"surface_{chon[0]}.json")
    hash_tv = str((s0.get("sinh_tu") or {}).get("hash_dau_vao") or "")[:16]
    nc = {"lot": lot, "ps": ps, "ma_lo": ma_lo, "dot": dot, "hash_tv": hash_tv}
    be = BackendLisp()
    be.cad_purge_sn(ma_lo, dot, xem_truoc=False, loai=("mat_3d", "qc"))
    kq = _ve_mat_3d_cat_bien(lot, be, nc, chon, dang=dang)
    if ve_nguon:
        _ve_diem_nguon_cad(lot, lsp_p, chon, be=be)
    be.bat_lop("SN-3DF-MOC", dot, "moc" in chon)
    be.bat_lop("SN-3DF-DO", dot, "do" in chon)
    be.bat_lop("SN-QC", dot, True)
    be.luu(lsp_p)
    return _dem(kq)


def l_tin_sua(a, lot):
    """Hiệu chỉnh mô hình TIN (MHTN/MHTK):
      --lenh lat-canh  --be-mat moc|do --e E --n N
      --lenh xoa-diem  --be-mat moc|do --e E --n N
      --lenh them-diem --be-mat moc|do --e E --n N --z Z
      --lenh xoa-tam-giac --be-mat moc|do --e E --n N
      --lenh tao-lai   --be-mat moc|do|ca-hai
    """
    from sannen.geom import orient2d
    lenh = a.lenh_sua
    if lenh not in ("lat-canh", "xoa-diem", "them-diem", "xoa-tam-giac", "tao-lai"):
        raise Loi("--lenh phải là lat-canh, xoa-diem, them-diem, xoa-tam-giac hoặc tao-lai")
    bm = a.be_mat or "moc"
    if lenh != "tao-lai" and bm not in ("moc", "do"):
        raise Loi("--be-mat phải là moc hoặc do")
    ps = lot.process_dir
    lot.log_dir.mkdir(parents=True, exist_ok=True)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M")

    if lenh in ("lat-canh", "xoa-tam-giac"):
        sp = ps / f"surface_{bm}.json"
        if not sp.exists():
            raise Loi(f"Chưa có surface_{bm}.json — hãy Tạo TIN cho bề mặt {bm.upper()} trước")
        sd = io_out.doc_json(sp)
        diem = sd["diem"]
        tris = [list(t) for t in sd["tam_giac"]]
        loai = list(sd.get("loai_tam_giac") or [0] * len(tris))
        rb = {tuple(sorted(e_)) for e_ in sd.get("canh_rang_buoc", [])}

        if lenh == "xoa-tam-giac":
            from sannen.geom import cat_hcn, dien_tich_co_dau, giao_doan, trong_da_giac
            xoa_idx: set[int] = set()
            mo_ta_log = ""
            if getattr(a, "a", None) and getattr(a, "b", None):
                e1, n1 = _en(a.a, "--a")
                e2, n2 = _en(a.b, "--b")
                kieu_q = (getattr(a, "kieu", None) or "crossing").lower()
                if kieu_q == "fence":
                    p1, p2 = (e1, n1), (e2, n2)
                    for idx, (u, v, w) in enumerate(tris):
                        pa, pb, pc = (diem[u][0], diem[u][1]), (diem[v][0], diem[v][1]), (diem[w][0], diem[w][1])
                        tri = [pa, pb, pc]
                        if (trong_da_giac(p1, tri) or trong_da_giac(p2, tri)
                                or giao_doan(p1, p2, pa, pb) is not None
                                or giao_doan(p1, p2, pb, pc) is not None
                                or giao_doan(p1, p2, pc, pa) is not None):
                            xoa_idx.add(idx)
                    mo_ta_log = f"đường cắt ({e1:.2f},{n1:.2f})→({e2:.2f},{n2:.2f})"
                else:
                    x0, x1 = min(e1, e2), max(e1, e2)
                    y0, y1 = min(n1, n2), max(n1, n2)
                    la_window = (kieu_q == "window") or (not getattr(a, "kieu", None) and e2 >= e1)
                    for idx, (u, v, w) in enumerate(tris):
                        pa, pb, pc = (diem[u][0], diem[u][1]), (diem[v][0], diem[v][1]), (diem[w][0], diem[w][1])
                        if la_window:
                            if all(x0 <= px <= x1 and y0 <= py <= y1 for px, py in (pa, pb, pc)):
                                xoa_idx.add(idx)
                        else:
                            tri = [pa, pb, pc]
                            if dien_tich_co_dau(tri) < 0:
                                tri = tri[::-1]
                            if abs(dien_tich_co_dau(cat_hcn(tri, x0, y0, x1, y1))) > 1e-9:
                                xoa_idx.add(idx)
                    mo_ta_log = f"quét vùng ({x0:.2f},{y0:.2f})..({x1:.2f},{y1:.2f})"
            elif a.e is not None and a.n is not None:
                pe, pn = float(a.e), float(a.n)
                best_i, best_d = None, 1e30
                for idx, (u, v, w) in enumerate(tris):
                    pa, pb, pc = (diem[u][0], diem[u][1]), (diem[v][0], diem[v][1]), (diem[w][0], diem[w][1])
                    if orient2d(pa, pb, (pe, pn)) >= -1e-6 and orient2d(pb, pc, (pe, pn)) >= -1e-6 and orient2d(pc, pa, (pe, pn)) >= -1e-6:
                        best_i, best_d = idx, 0.0
                        break
                    cx, cy = (pa[0] + pb[0] + pc[0]) / 3.0, (pa[1] + pb[1] + pc[1]) / 3.0
                    d_c = math.hypot(cx - pe, cy - pn)
                    if d_c < best_d:
                        best_i, best_d = idx, d_c
                if best_i is not None:
                    xoa_idx.add(best_i)
                mo_ta_log = f"tại ({pe:.3f}, {pn:.3f})"
            else:
                raise Loi("Cần --e E --n N (pick điểm) hoặc --a E1,N1 --b E2,N2 (quét vùng chọn nhiều tam giác)")
            if not xoa_idx:
                raise Loi("Không có tam giác nào trong vùng quét chọn để xóa")
            if len(xoa_idx) >= len(tris):
                raise Loi("Không thể xóa toàn bộ tam giác của bề mặt TIN (cần giữ lại ít nhất 1 tam giác)")
            so_xoa = len(xoa_idx)
            sd["tam_giac"] = [t for i, t in enumerate(tris) if i not in xoa_idx]
            sd["loai_tam_giac"] = [l for i, l in enumerate(loai) if i not in xoa_idx]
            sd.setdefault("thong_ke", {})["so_tam_giac"] = len(sd["tam_giac"])
            io_out.ghi_json(lot, f"surface_{bm}.json", sd)
            with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
                f.write(f"- {luc} · xoa-tam-giac ({bm.upper()}) · Xóa {so_xoa} tam giác ({mo_ta_log})\n")
            if a.lsp:
                _ve_3d_va_nguon(lot, Path(a.lsp), bm, _dang(a))
            return {"be_mat": bm, "so_xoa": so_xoa, "so_tam_giac": len(sd["tam_giac"])}, \
                f"Đã xóa {so_xoa} tam giác khỏi {bm.upper()} (còn {len(sd['tam_giac'])} tam giác)"

        if a.e is None or a.n is None:
            raise Loi("Cần --e E --n N (tọa độ điểm click trên bản vẽ)")
        pe, pn = float(a.e), float(a.n)

        # lenh == "lat-canh": tìm cạnh nội bộ (chia sẻ bởi đúng 2 tam giác) gần điểm (pe, pn) nhất
        canh_map: dict[tuple[int, int], list[int]] = {}
        for idx, (u, v, w) in enumerate(tris):
            for e1, e2 in ((u, v), (v, w), (w, u)):
                k = (e1, e2) if e1 < e2 else (e2, e1)
                canh_map.setdefault(k, []).append(idx)
        best_k, best_dist = None, 1e30
        for (u, v), ds_t in canh_map.items():
            if len(ds_t) != 2:
                continue
            ax, ay = diem[u][0], diem[u][1]
            bx, by = diem[v][0], diem[v][1]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((pe - ax) * dx + (pn - ay) * dy) / l2))
            qx, qy = ax + t * dx, ay + t * dy
            dist = math.hypot(pe - qx, pn - qy)
            if dist < best_dist:
                best_k, best_dist = (u, v), dist
        if best_k is None:
            raise Loi("Không tìm thấy cạnh chung của 2 tam giác để lật")
        if best_k in rb:
            raise Loi("Cạnh này là đường đứt gãy cưỡng bức (Breakline) — không được phép lật!")
        t1, t2 = canh_map[best_k]
        u, v = best_k
        c1 = next(x for x in tris[t1] if x != u and x != v)
        c2 = next(x for x in tris[t2] if x != u and x != v)
        p_u, p_v = (diem[u][0], diem[u][1]), (diem[v][0], diem[v][1])
        p_c1, p_c2 = (diem[c1][0], diem[c1][1]), (diem[c2][0], diem[c2][1])
        if not (orient2d(p_c1, p_c2, p_u) * orient2d(p_c1, p_c2, p_v) < 0 and orient2d(p_u, p_v, p_c1) * orient2d(p_u, p_v, p_c2) < 0):
            raise Loi("Tứ giác chứa cạnh này bị lõm — lật cạnh sẽ làm hai tam giác chồng đè lên nhau!")
        # Tạo 2 tam giác mới (c1, c2, u) và (c2, c1, v) đảm bảo ngược chiều kim đồng hồ (orient2d > 0)
        nt1 = [c1, c2, u] if orient2d(p_c1, p_c2, p_u) > 0 else [c2, c1, u]
        nt2 = [c2, c1, v] if orient2d(p_c2, p_c1, p_v) > 0 else [c1, c2, v]
        tris[t1], tris[t2] = nt1, nt2
        sd["tam_giac"] = tris
        io_out.ghi_json(lot, f"surface_{bm}.json", sd)
        with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
            f.write(f"- {luc} · lat-canh ({bm.upper()}) · Lật cạnh ({u}-{v}) → ({c1}-{c2}) tại ({pe:.3f}, {pn:.3f})\n")
        if a.lsp:
            _ve_3d_va_nguon(lot, Path(a.lsp), bm, _dang(a))
        return {"be_mat": bm, "canh_cu": list(best_k), "canh_moi": [c1, c2]}, \
            f"Đã lật cạnh tam giác trên {bm.upper()} từ đỉnh ({u}–{v}) sang ({c1}–{c2})"

    ntc_p = lot.root / "nguon_tuy_chinh.yaml"
    ntc = (yaml.safe_load(ntc_p.read_text(encoding="utf-8")) or {}) if ntc_p.exists() else _ntc_mac_dinh_trong()
    for k_m, v_m in _ntc_mac_dinh_trong().items():
        ntc.setdefault(k_m, v_m)
    if not ntc_p.exists():
        ntc_p.write_text("# Nguồn dữ liệu phiên làm việc CAD (không dùng dữ liệu mẫu từ lot.yaml).\n"
                         + yaml.safe_dump(ntc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cfg_goc = doc_lot(lot.lot_yaml)

    if lenh == "xoa-diem":
        if a.e is None or a.n is None:
            raise Loi("Cần --e E --n N (tọa độ điểm cần xóa)")
        p_csv = ps / f"points_{bm}.csv"
        if not p_csv.is_file():
            raise Loi(f"Chưa có points_{bm}.csv — chạy nhập dữ liệu trước")
        import csv as _csv
        pe, pn = float(a.e), float(a.n)
        best_id, best_z, best_d = None, 0.0, 1e30
        with p_csv.open(encoding="utf-8", newline="") as f:
            for r in _csv.DictReader(f):
                d_p = math.hypot(float(r["easting"]) - pe, float(r["northing"]) - pn)
                if d_p < best_d:
                    best_id, best_z, best_d = r["id"], float(r["z"]), d_p
        if best_id is None:
            raise Loi(f"Bề mặt {bm.upper()} không có điểm nào để xóa")
        bo_ds = [str(x) for x in (cfg_goc.get("bo_diem") or [])]
        if best_id not in bo_ds:
            bo_ds.append(best_id)
        ntc["bo_diem"] = bo_ds
        # Nếu là điểm từng thêm tay trong them_diem thì loại luôn
        if isinstance(ntc.get("them_diem"), dict) and bm in ntc["them_diem"]:
            ntc["them_diem"][bm] = [x for x in ntc["them_diem"][bm] if str(x.get("id")) != best_id]
        ntc_p.write_text("# Nguồn dữ liệu & hiệu chỉnh điểm do NGƯỜI chọn từ AutoCAD — ghi đè lot.yaml.\n"
                         + yaml.safe_dump(ntc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
            f.write(f"- {luc} · xoa-diem ({bm.upper()}) · Loại bỏ điểm {best_id} (Z={best_z:.3f} m, cách điểm chọn {best_d:.2f} m)\n")
        thong_bao_sua = f"Đã loại bỏ điểm {best_id} (Z={best_z:.3f} m) khỏi {bm.upper()} và tạo lại lưới TIN"

    elif lenh == "them-diem":
        if a.e is None or a.n is None or a.z is None:
            raise Loi("Cần --e E --n N --z Z (tọa độ và cao độ điểm thêm vào TIN)")
        pe, pn, pz = float(a.e), float(a.n), float(a.z)
        td = ntc.get("them_diem")
        if not isinstance(td, dict):
            td = {}
        ds_bm = list(td.get(bm) or [])
        ma_moi = f"THEM-{bm.upper()}-{len(ds_bm)+1:04d}"
        ds_bm.append({"id": ma_moi, "e": round(pe, 4), "n": round(pn, 4), "z": round(pz, 4), "code": "cad_them"})
        td[bm] = ds_bm
        ntc["them_diem"] = td
        ntc_p.write_text("# Nguồn dữ liệu & hiệu chỉnh điểm do NGƯỜI chọn từ AutoCAD — ghi đè lot.yaml.\n"
                         + yaml.safe_dump(ntc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with (lot.log_dir / "decisions.md").open("a", encoding="utf-8") as f:
            f.write(f"- {luc} · them-diem ({bm.upper()}) · Thêm điểm {ma_moi} ({pe:.3f}, {pn:.3f}, Z={pz:.3f} m)\n")
        thong_bao_sua = f"Đã thêm điểm {ma_moi} (Z={pz:.3f} m) vào {bm.upper()} và tạo lại lưới TIN"

    else:
        thong_bao_sua = f"Đã tạo lại lưới tam giác TIN ({bm})"

    bm_chay = bm if bm in ("moc", "do") else "ca-hai"
    # Dự phòng thông minh: nếu nguon_tuy_chinh.yaml của bề mặt đang là chua_khai_bao nhưng người dùng vừa chọn/import file trong 10_process/ hoặc %TEMP%
    ds_check = ("moc", "do") if bm_chay == "ca-hai" else (bm_chay,)
    da_khoi_phuc = False
    for nb in ds_check:
        b_cfg = ntc.get(f"be_mat_{nb}") or {}
        if b_cfg.get("nguon") in (None, "chua_khai_bao", "trong", "none"):
            for cand_p, cand_ng in (
                (ps / f"cad_chon_{nb}.csv", {"nguon": "cad_chon", "file": f"10_process/cad_chon_{nb}.csv"}),
                (ps / f"dxf_{nb}.dxf", {"nguon": "dxf_layer", "layer": "*", "file": f"../10_process/dxf_{nb}.dxf"}),
                (ps / f"excel_{nb}.xlsx", {"nguon": "excel", "file": f"../10_process/excel_{nb}.xlsx"}),
                (ps / f"excel_{nb}.xls", {"nguon": "excel", "file": f"../10_process/excel_{nb}.xls"}),
                (ps / f"excel_{nb}.csv", {"nguon": "csv", "file": f"../10_process/excel_{nb}.csv"}),
            ):
                if cand_p.is_file():
                    ntc[f"be_mat_{nb}"] = cand_ng
                    da_khoi_phuc = True
                    break
            else:
                import os as _os, shutil as _sh
                tmp_csv = Path(_os.environ.get("SANNEN_TMP") or _os.environ.get("TEMP") or r"C:\Temp") / f"sn_cad_chon_{nb}.csv"
                if tmp_csv.is_file():
                    dst_csv = ps / f"cad_chon_{nb}.csv"
                    _sh.copy2(tmp_csv, dst_csv)
                    ntc[f"be_mat_{nb}"] = {"nguon": "cad_chon", "file": f"10_process/cad_chon_{nb}.csv"}
                    da_khoi_phuc = True
    if da_khoi_phuc:
        ntc_p.write_text("# Nguồn dữ liệu & hiệu chỉnh điểm do NGƯỜI chọn từ AutoCAD — ghi đè lot.yaml.\n"
                         + yaml.safe_dump(ntc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # Chạy lại nhap + mat để dựng lại TIN
    ma_nhap, ra_nhap = _cli(lot, "nhap", "--xac-nhan-anh-xa")
    if ma_nhap >= 2:
        raise Loi("Nhập lại dữ liệu dừng: " + " ".join(ra_nhap.strip().splitlines()[-3:]))
    ok_c1, _ = cong.cong_da_duyet(lot, 1)
    if not ok_c1:
        chan1 = cong.viec_chan(lot, 1)
        if chan1:
            raise Loi("Dữ liệu đầu vào có việc CHẶN cần xử lý trước khi tạo TIN: " + " | ".join(chan1))
        cong.duyet_cong({"lot": str(lot.root), "cong": 1, "nguoi_duyet": "Người dùng CAD",
                         "bang_chung": "Người dùng hiệu chỉnh / tạo lại lưới TIN trong AutoCAD"})
    # Nếu tạo lại riêng 1 bề mặt (moc hoặc do), đảm bảo không còn file surface của bề mặt kia nếu bề mặt kia chưa khai báo điểm
    for n_check in ("moc", "do"):
        p_pts = ps / f"points_{n_check}.csv"
        p_surf = ps / f"surface_{n_check}.json"
        if p_surf.is_file() and (not p_pts.is_file() or sum(1 for _ in p_pts.open(encoding="utf-8")) <= 1):
            p_surf.unlink()
    bm_chay = bm if bm in ("moc", "do") else "ca-hai"
    ma_mat, ra_mat = _cli(lot, "mat", "--be-mat", bm_chay)
    if ma_mat >= 2:
        raise Loi("Tạo lại TIN dừng: " + " ".join(ra_mat.strip().splitlines()[-3:]))
    if a.lsp:
        try:
            _ve_3d_va_nguon(lot, Path(a.lsp), bm_chay, _dang(a))
        except Exception:
            pass
    return {"be_mat": bm_chay, "ma_thoat": max(ma_nhap, ma_mat),
            "van_ban": (ra_nhap + "\n" + ra_mat).strip()}, thong_bao_sua


def l_nap_tu_mcp(a, lot):
    """Đồng bộ dữ liệu đầu vào đã được AI Agent (Claude/ChatGPT/Antigravity) đọc & kiểm soát qua MCP vào bản vẽ AutoCAD đang mở:
    nạp điểm, dựng lưới TIN, tạo 3D Mesh + trình xem 3D Web HTML."""
    ps = lot.process_dir
    if not (ps / "points_moc.csv").exists() or not (ps / "points_do.csv").exists():
        ma_nhap, ra_nhap = _cli(lot, "nhap", "--xac-nhan-anh-xa")
        if ma_nhap >= 2:
            raise Loi("Chưa nạp được dữ liệu đầu vào từ MCP: " + " ".join(ra_nhap.strip().splitlines()[-3:]))
    ok_c1, _ = cong.cong_da_duyet(lot, 1)
    if not ok_c1:
        chan1 = cong.viec_chan(lot, 1)
        if chan1:
            raise Loi("Dữ liệu đầu vào từ Agent còn việc CHẶN chưa duyệt ở Cổng 1: " + " | ".join(chan1))
        cong.duyet_cong({"lot": str(lot.root), "cong": 1, "nguoi_duyet": "Người dùng CAD (Đồng bộ MCP)",
                         "bang_chung": "Người dùng bấm Nhận & Tạo TIN từ Agent (MCP) trên AutoCAD"})
    bm = a.be_mat or "ca-hai"
    ma_mat, ra_mat = _cli(lot, "mat", "--be-mat", bm)
    if ma_mat >= 2:
        raise Loi("Dựng lưới TIN từ dữ liệu MCP dừng: " + " ".join(ra_mat.strip().splitlines()[-3:]))
    if (ps / "boundary.geojson").exists() and not (ps / "lo.json").exists():
        _cli(lot, "lo")
    _cli(lot, "xem3d")
    da_ve = {}
    if a.lsp:
        da_ve = _ve_3d_va_nguon(lot, Path(a.lsp), bm, _dang(a), ve_nguon=True)
    return {"be_mat": bm, "da_ve": da_ve}, \
        "Đã nhận dữ liệu đã kiểm soát từ Agent (MCP), đẩy vào bản vẽ CAD, dựng lưới TIN, tạo 3D Mesh và HTML 3D View!"


LENH = {"trang-thai": l_trang_thai, "ve": l_ve, "ve-ke-hoach": l_ve_ke_hoach, "tin3d": l_tin3d, "tin3d-tat": l_tin3d_tat,
        "xem3d": l_xem3d,
        "luoi-doc": l_luoi_doc, "thong-tin": l_thong_tin,
        "luoi-sua": l_luoi_sua, "luoi-ve-lai-lot-yaml": l_luoi_ve_lai_lot_yaml, "luoi-import-dxf": l_luoi_import_dxf,
        "luoi-xoa": l_luoi_xoa,
        "mat-cat": l_mat_cat, "bang": l_bang,
        "chay": l_chay, "canh-bao": l_canh_bao, "o-tai": l_o_tai, "dong-bo": l_dong_bo,
        "hieuchinh-nhieu": l_hieuchinh_nhieu, "duyet": l_duyet, "khoi-tao-be-mat": l_khoi_tao_be_mat,
        "xoa-du-lieu-cu": l_xoa_du_lieu_cu, "tin-sua": l_tin_sua, "nap-tu-mcp": l_nap_tu_mcp}


# =========================================================================== điểm vào
def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sannen_cad.cau_noi")
    ap.add_argument("cmd", choices=sorted(LENH))
    ap.add_argument("--lot", required=True)
    ap.add_argument("--ra", required=True, help="file kết quả (s-expression AutoLISP; JSON nếu có --json)")
    ap.add_argument("--json", action="store_true", help="ghi kết quả dạng JSON UTF-8 (cho palette C#) thay vì s-expression")
    ap.add_argument("--lsp")
    ap.add_argument("--ke-hoach", help="file kế hoạch vẽ JSON (lệnh ve-ke-hoach); '-' = stdout")
    ap.add_argument("--che-do", help="ve-ke-hoach: ve (mặc định) | tin3d | mat-cat")
    ap.add_argument("--lop")
    ap.add_argument("--be-mat")
    ap.add_argument("--lenh", dest="lenh_sua")
    ap.add_argument("--chi-so", type=int)
    ap.add_argument("--sau", type=int)
    ap.add_argument("--kich-thuoc", type=float)
    ap.add_argument("--den")
    ap.add_argument("--dx", type=float)
    ap.add_argument("--dy", type=float)
    ap.add_argument("--goc", type=float)
    ap.add_argument("--cot")
    ap.add_argument("--hang")
    ap.add_argument("--o", type=float)
    ap.add_argument("--goc-luoi")
    ap.add_argument("--ngoai-suy", type=float)
    ap.add_argument("--kieu")
    ap.add_argument("--ly-do")
    ap.add_argument("--khong-tinh", action="store_true")
    ap.add_argument("--cho-phep-chua-co", action="store_true", help="luoi-doc: trả thông số mặc định từ lot.yaml khi chưa có grid.json")
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--buoc", type=float)
    ap.add_argument("--ten")
    ap.add_argument("--goc-ve")
    ap.add_argument("--trai-x", type=float, help="mép trái (E) của kết quả lô trong bản vẽ — mặt cắt mặc định canh theo")
    ap.add_argument("--duoi-y", type=float, help="đáy (N) của kết quả lô trong bản vẽ — mặt cắt mặc định đặt dưới đó ≥ 30 m")
    ap.add_argument("--dang", help="dạng mặt 3D: polyface (mặc định) hoặc 3dface")
    ap.add_argument("--ty-le-dung", type=float)
    ap.add_argument("--loai")
    ap.add_argument("--verb")
    ap.add_argument("--them")
    ap.add_argument("--e", type=float)
    ap.add_argument("--n", type=float)
    ap.add_argument("--z", type=float)
    ap.add_argument("--tu-file")
    ap.add_argument("--chap-nhan", action="store_true")
    ap.add_argument("--cong", type=int)
    ap.add_argument("--nguoi")
    ap.add_argument("--bang-chung")
    ap.add_argument("--nguon-moc")
    ap.add_argument("--file-moc")
    ap.add_argument("--sheet-moc")
    ap.add_argument("--layer-moc")
    ap.add_argument("--nguon-do")
    ap.add_argument("--file-do")
    ap.add_argument("--sheet-do")
    ap.add_argument("--layer-do")
    ap.add_argument("--file-dut-gay")
    ap.add_argument("--file-bien-lo")
    ap.add_argument("--file-loai-tru")
    ap.add_argument("--xac-nhan-anh-xa", action="store_true")
    ap.add_argument("--chi-nhap", action="store_true")
    ap.add_argument("--chi-luoi", action="store_true", help="luoi-sua: chỉ đặt/cắt lưới và nội suy cao độ nút lưới, chưa chạy tính đào đắp")
    ap.add_argument("--chi-doc", action="store_true", help="luoi-import-dxf: chỉ đọc thông số lưới từ file, không ghi lô")
    ap.add_argument("--layer-luoi", help="luoi-import-dxf: tên layer chứa lưới trong file DXF")
    return ap


def _sach(o):
    """Chuẩn bị cho JSON chặt: NaN/Inf → null, tuple → list, khoá → chuỗi (JavaScriptSerializer của .NET không đọc NaN)."""
    if isinstance(o, dict):
        return {str(k): _sach(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sach(v) for v in o]
    if isinstance(o, float) and (o != o or o in (math.inf, -math.inf)):
        return None
    return o


def mo_rong_args_file(argv: list[str]) -> list[str]:
    """`--args-file F`: đọc đối số từ file, MỖI DÒNG MỘT đối số (dòng trống bỏ qua).

    Kênh an toàn cho chữ Việt từ AutoLISP: `(open ... "w")` ghi theo bảng mã ANSI nên làm hỏng chữ có dấu, và dòng lệnh
    cmd.exe cũng vậy. LISP ghi file bằng Scripting.FileSystemObject (CreateTextFile path :vlax-true :vlax-true →
    UTF-16LE có BOM); UTF-8 (có/không BOM) cũng được chấp nhận.
    """
    if "--args-file" not in argv:
        return list(argv)
    i = argv.index("--args-file")
    raw = Path(argv[i + 1]).read_bytes()
    txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    return list(argv[:i]) + [d for d in txt.splitlines() if d != ""] + list(argv[i + 2:])


def main(argv: list[str] | None = None) -> int:
    try:
        a = _parser().parse_args(mo_rong_args_file(sys.argv[1:] if argv is None else argv))
    except SystemExit as e:                       # tham số sai: argparse đã in lỗi ra stderr
        return int(e.code or 2)
    ok, tb, du = False, "", None
    if a.lsp:
        Path(a.lsp).unlink(missing_ok=True)       # lỗi thì KHÔNG để lại file vẽ cũ cho LISP nạp nhầm
    try:
        lot = _lot(a)
        du, tb = LENH[a.cmd](a, lot)
        ok = True
    except (Loi, luoi_sua.SuaLuoiLoi, _luoi.LuoiLoi, matcat.MatCatLoi) as e:
        tb, du = str(e), getattr(e, "du_lieu", None)
    except Exception as e:                        # cầu nối không được sập: báo cho người, không traceback
        tb = f"{type(e).__name__}: {e}"
    ra = Path(a.ra)
    ra.parent.mkdir(parents=True, exist_ok=True)
    if a.json:
        ra.write_bytes(json.dumps(_sach({"ok": ok, "thong_bao": tb, "du_lieu": du}), ensure_ascii=False).encode("utf-8"))
        return 0
    noi_dung = sx({"ok": ok, "thong_bao": tb, "du_lieu": du})
    if ra.suffix.lower() == ".lsp":
        # AutoLISP `open ... "r"` đọc UTF-8 thành rác (đo trên AutoCAD 2022), còn `(load)` thì đọc UTF-8 đúng:
        # ghi dạng file LISP, người dùng `(load ra)` rồi lấy biến toàn cục *sn-ra*.
        noi_dung = "(setq *sn-ra* '" + noi_dung + ")"
    ra.write_bytes((noi_dung + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
