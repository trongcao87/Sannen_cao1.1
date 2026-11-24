"""Cầu nối giữa AutoLISP (menu SAN NỀN trong AutoCAD) và lõi tính.

    python -X utf8 -m sannen_cad.cau_noi <lệnh> --lot <thư mục lô> --ra <file kết quả> [--lsp <file vẽ>] ...

LISP không phân tích được JSON, nên MỖI lệnh ghi vào `--ra` MỘT s-expression AutoLISP đọc được bằng `(read)`:

    (("ok" . T) ("thong_bao" . "chuỗi") ("du_lieu" . ...))

Lỗi thì ok = nil và thong_bao nói đúng nguyên nhân bằng tiếng Việt (không traceback). Khi cần vẽ vào bản vẽ,
lệnh ghi thêm file `--lsp` (BackendLisp) để LISP `(load)`. Mọi con số vẫn do lõi tính (RULES 1) — LISP chỉ hiển thị.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path

import yaml

from sannen import cong, io_out, luoi as _luoi, luoi_sua, matcat, mcp_server, xuat
from sannen.config import doc_lot, nguong
from sannen.paths import Lot

from . import bo_cuc, ve
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
    return {"kich_thuoc": ts["kich_thuoc_o_m"], "goc_xoay_do": ts["goc_xoay_do"], "goc_luoi": ts["goc_luoi"],
            "cot": luoi_sua.dinh_dang(ts["cot_m"]), "hang": luoi_sua.dinh_dang(ts["hang_m"]),
            "nx": len(ts["cot_m"]), "ny": len(ts["hang_m"]), "ngoai_suy_m": ts["ngoai_suy_m"],
            "ngoai_suy_kieu": ts["ngoai_suy_kieu"], "dt_o": tong["dt_o_m2"], "dt_lo": tong["dt_lo_m2"], "so_o": tong["so_o"]}


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


def _tinh_lai(lot: Lot) -> None:
    """luoi rồi tinh (giữ --sweep nếu volume.json hiện có sweep). Mã ≥ 1 ở bước nào thì ném Loi."""
    sweep = False
    vp = lot.process_dir / "volume.json"
    if vp.exists():
        sweep = "sweep" in io_out.doc_json(vp)
    ma, ra = _cli(lot, "luoi")
    if ma >= 1:
        raise Loi("Lưới không dùng được: " + _chan(lot, "qc_luoi.json", ra))
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


def l_tin3d(a, lot):
    chon = {"moc": ["moc"], "do": ["do"], "ca-hai": ["moc", "do"]}.get(a.be_mat)
    if chon is None:
        raise Loi("--be-mat phải là moc, do hoặc ca-hai")
    try:
        nc = ve.ngu_canh(lot.root)
    except FileNotFoundError as e:
        raise Loi(str(e))
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
    if not (lot.process_dir / "grid.json").exists():
        raise Loi("Chưa có grid.json — chạy luoi trước")
    return _luoi_doc(lot), ""


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
    if not (lot.process_dir / "grid.json").exists():
        raise Loi("Chưa có grid.json — chạy luoi trước")
    moi = luoi_sua.ap_dung(luoi_sua.trang_thai(lot), a.lenh_sua, **_kw_luoi_sua(a))       # lỗi mẫu/chỉ số: chưa đổi gì
    lsp = None if a.khong_tinh else _lsp(a)
    gd = GiaoDich(lot)
    try:
        r = luoi_sua.ghi_tuy_chinh(lot, moi, a.ly_do or f"lệnh {a.lenh_sua}")
        if not a.khong_tinh:
            _tinh_lai(lot)
            _ve_lsp(lot, lsp, ["luoi", "nhan", "o", "ranh"])
    except Exception:
        gd.khoi_phuc()
        raise
    du = _luoi_doc(lot) if not a.khong_tinh else luoi_sua.trang_thai(lot)
    if not a.khong_tinh:
        q = lot.process_dir / "qc_luoi.json"
        du["canh_bao"] = [f["mo_ta"] for f in io_out.doc_json(q).get("phat_hien", []) if f.get("muc") == "canh_bao"] if q.exists() else []
        du["cat_hieu_chinh"] = r["da_cat_hieu_chinh_dinh"]
    return du, ("Đã áp dụng và tính lại" if not a.khong_tinh else "Đã ghi lưới tùy chỉnh (chưa tính lại)")


def l_luoi_ve_lai_lot_yaml(a, lot):
    lsp = _lsp(a)
    gd = GiaoDich(lot)
    try:
        luoi_sua.xoa_tuy_chinh(lot)
        _tinh_lai(lot)
        _ve_lsp(lot, lsp, ["luoi", "nhan", "o", "ranh"])
    except Exception:
        gd.khoi_phuc()
        raise
    return _luoi_doc(lot), "Đã bỏ lưới tùy chỉnh, quay về lot.yaml và tính lại"


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
        if a.goc_ve:                                        # người chọn điểm đặt: luôn được ưu tiên
            gv, mac_dinh = _en(a.goc_ve, "--goc-ve"), False
        else:                                               # mặc định: DƯỚI toàn bộ kết quả của lô + đệm ≥ 30 m
            trai_x, duoi_y = a.trai_x, a.duoi_y
            if trai_x is None or duoi_y is None:            # LISP không đo được bản vẽ → dùng hộp bao lô + bảng in
                hb = io_out.doc_json(lot.process_dir / "lo.json")["hop_bao"]
                bp = lot.output_dir / "bang_in_cad.json"
                tx, dy = bo_cuc.duoi_mac_dinh_lot(hb, io_out.doc_json(bp) if bp.exists() else None)
                trai_x = tx if trai_x is None else trai_x
                duoi_y = dy if duoi_y is None else duoi_y
            gv, mac_dinh = bo_cuc.goc_mat_cat_mac_dinh(kq, ty_le, float(trai_x), float(duoi_y)), True
        ent = bo_cuc.mat_cat_ent(kq, gv, ty_le)
    except ValueError as e:
        raise Loi(str(e))
    vung = bo_cuc.hop_bao_ent(ent[3:])
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
    """Sinh trình xem 3D HTML (verb `xem3d` của lõi) và mở bằng trình duyệt mặc định."""
    ma, ra = _cli(lot, "xem3d", "--mo")
    dong = [d.strip() for d in ra.splitlines() if d.strip()]
    if ma != 0:
        raise Loi("Không dựng được trình xem 3D: " + (" ".join(dong[-3:]) if dong else
                                                      f"verb xem3d báo mã thoát {ma} (lõi chưa có verb này hoặc tham số sai)"))
    file = next((d for d in reversed(dong) if d.lower().endswith(".html")), dong[-1] if dong else "")
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
    lsp = _lsp(a)
    ma, ra = _cli(lot, "hieuchinh", "--tu-file", str(a.tu_file), *(["--ly-do", a.ly_do] if a.ly_do else []))
    if ma >= 2:
        raise Loi("Hiệu chỉnh đỉnh bị từ chối: " + " ".join(ra.strip().splitlines()[-3:]))
    sweep = "sweep" in io_out.doc_json(lot.process_dir / "volume.json") if (lot.process_dir / "volume.json").exists() else False
    ma2, ra2 = _cli(lot, "tinh", *(["--sweep"] if sweep else []))
    if ma2 >= 1:
        raise Loi("Đã ghi hiệu chỉnh nhưng tính lại bị chặn: " + _chan(lot, "qc_volume.json", ra2))
    du = _ve_lsp(lot, lsp, ["nhan", "o"])
    return {"ma_thoat": ma, "van_ban": ra, "da_ve": du}, "Đã hiệu chỉnh đỉnh, tính lại và sinh lệnh vẽ lại nhãn"


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
    if not (gp.exists() and vp.exists()):
        raise Loi("Chưa có grid.json/volume.json — chạy luoi và tinh trước")
    ts = io_out.doc_json(gp)["tham_so"]
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
    o = next((c for c in io_out.doc_json(vp)["o"] if c["ma"] == ma), None)
    if o is None:
        raise Loi(f"Điểm nằm trong lưới (ô {ma}) nhưng ngoài lô — ô này không có diện tích trong lô")
    return {"ma": ma, "kl_dao": o["kl_dao_m3"], "kl_dap": o["kl_dap_m3"], "dt": o["dt_huu_hieu_m2"],
            "thieu_du_lieu": bool(o["thieu_du_lieu"])}, ""


def l_duyet(a, lot):
    van_ban, loi = cong.duyet_cong({"lot": str(lot.root), "cong": a.cong, "nguoi_duyet": a.nguoi or "",
                                          "bang_chung": a.bang_chung or ""})
    if loi:
        raise Loi(van_ban)
    return None, van_ban


LENH = {"trang-thai": l_trang_thai, "ve": l_ve, "tin3d": l_tin3d, "tin3d-tat": l_tin3d_tat, "xem3d": l_xem3d,
        "luoi-doc": l_luoi_doc, "thong-tin": l_thong_tin,
        "luoi-sua": l_luoi_sua, "luoi-ve-lai-lot-yaml": l_luoi_ve_lai_lot_yaml, "mat-cat": l_mat_cat, "bang": l_bang,
        "chay": l_chay, "canh-bao": l_canh_bao, "o-tai": l_o_tai, "dong-bo": l_dong_bo,
        "hieuchinh-nhieu": l_hieuchinh_nhieu, "duyet": l_duyet}


# =========================================================================== điểm vào
def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sannen_cad.cau_noi")
    ap.add_argument("cmd", choices=sorted(LENH))
    ap.add_argument("--lot", required=True)
    ap.add_argument("--ra", required=True, help="file kết quả (s-expression AutoLISP; JSON nếu có --json)")
    ap.add_argument("--json", action="store_true", help="ghi kết quả dạng JSON UTF-8 (cho palette C#) thay vì s-expression")
    ap.add_argument("--lsp")
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
    ap.add_argument("--tu-file")
    ap.add_argument("--chap-nhan", action="store_true")
    ap.add_argument("--cong", type=int)
    ap.add_argument("--nguoi")
    ap.add_argument("--bang-chung")
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
