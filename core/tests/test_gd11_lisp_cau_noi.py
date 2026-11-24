"""Backend LISP + cầu nối `cau_noi` (menu SAN NỀN trong AutoCAD).

Ba tầng kiểm tra:
  (a) s-expression: bộ đọc nhỏ trong test + AutoLISP THẬT (accoreconsole) đọc lại bằng `(read)`;
  (b) từng lệnh cầu nối trên lô giải tích: cấu trúc, số liệu, lỗi, và nguyên tử (hỏng thì khôi phục nguyên trạng);
  (c) nạp file .lsp sinh ra vào AutoCAD 2022 chạy không giao diện, lưu DXF, đọc lại bằng ezdxf.
"""
from __future__ import annotations
import csv
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import ezdxf
import pytest

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE.parent / "cad"))
from sannen import cli                                                       # noqa: E402
from sannen_cad import cau_noi as CN                                         # noqa: E402
from sannen_cad.backend import NHOM_LOP                                      # noqa: E402
from sannen_cad.backend_dxf import BackendDXF                                # noqa: E402
from sannen_cad.backend_lisp import BackendLisp, ls                          # noqa: E402
from sannen_cad.ve import ve_ket_qua                                         # noqa: E402
from lot_giai_tich import E0, N0, chay_het, hcn, tao                         # noqa: E402

ACORE = Path(r"C:\Program Files\Autodesk\AutoCAD 2022\accoreconsole.exe")
can_acore = pytest.mark.skipif(not ACORE.exists(), reason="không thấy accoreconsole.exe (AutoCAD 2022)")

f_moc = lambda e, n: 10.0
f_do = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)       # dz đổi dấu giữa lô


# =========================================================================== bộ đọc s-expression
def doc_sx(txt: str):
    """Đọc s-expression do `sx()` sinh ra. (k . v) → tuple (k, v); (k a b) → list [k, a, b]; nil → None; T → True."""
    tok = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|\.(?=\s)|[^\s()"]+', txt)
    vi = [0]

    def atom(t):
        if t.startswith('"'):
            return re.sub(r"\\(.)", lambda m: "\n" if m[1] == "n" else m[1], t[1:-1])
        if t == "nil":
            return None
        if t == "T":
            return True
        return float(t) if re.search(r"[.eE]", t) else int(t)

    def parse():
        t = tok[vi[0]]
        vi[0] += 1
        if t != "(":
            return atom(t)
        ds = []
        while tok[vi[0]] != ")":
            ds.append(parse() if tok[vi[0]] != "." else (vi.__setitem__(0, vi[0] + 1) or "."))
        vi[0] += 1
        if len(ds) == 3 and ds[1] == ".":
            return (ds[0], ds[2])
        return ds or None
    return parse()


MISSING = object()


def tim(al, khoa):
    """Giá trị của `khoa` trong alist: (k . v) → v ; (k a b) → [a, b] ; (k) → []."""
    for it in al or []:
        if isinstance(it, tuple) and it[0] == khoa:
            return it[1]
        if isinstance(it, list) and it and it[0] == khoa:
            return it[1:]
    return MISSING


def chay_cn(tmp: Path, lot, cmd: str, *args: str, lsp: bool = False):
    """Chạy một lệnh cầu nối; trả (ok, thong_bao, du_lieu, đường dẫn lsp)."""
    ra = tmp / f"ra_{uuid.uuid4().hex[:8]}.txt"
    lsp_p = tmp / f"ve_{uuid.uuid4().hex[:8]}.lsp"
    argv = [cmd, "--lot", str(lot.root), "--ra", str(ra), *args] + (["--lsp", str(lsp_p)] if lsp else [])
    assert CN.main(argv) == 0
    al = doc_sx(ra.read_text(encoding="utf-8"))
    ok = tim(al, "ok") is True
    return ok, tim(al, "thong_bao"), tim(al, "du_lieu"), lsp_p


def can_bang(txt: str) -> int:
    """Độ sâu ngoặc cuối file LISP, bỏ qua chuỗi và chú thích — kiểm file sinh ra cân ngoặc."""
    d, i, n = 0, 0, len(txt)
    while i < n:
        c = txt[i]
        if c == '"':
            i += 1
            while txt[i] != '"':
                i += 2 if txt[i] == "\\" else 1
        elif c == ";":
            while i < n and txt[i] != "\n":
                i += 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            assert d >= 0, "thừa ngoặc đóng"
        i += 1
    return d


# =========================================================================== lô thử
@pytest.fixture(scope="module")
def lo(tmp_path_factory):
    l = tao(tmp_path_factory.mktemp("cn_lo"), [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=700)
    chay_het(l)
    assert cli.main(["xuat", "--lot", str(l.root)]) == 0              # có bang_in_cad.json cho `ve` vẽ bảng
    return l


@pytest.fixture
def lot_moi(tmp_path):
    l = tao(tmp_path / "lot", [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=600)
    chay_het(l)
    return l


@pytest.fixture(scope="module")
def tmp_m(tmp_path_factory):
    return tmp_path_factory.mktemp("cn_tmp")


# =========================================================================== (a) s-expression
KHO = {"ok": True, "chuoi": 'Lô "01" \\ đường\nDòng 2 — Đắp ứ ơ', "so": 1.5, "ds": [1, 2.5, "x"],
       "long": {"a": 1, "b": False}, "rong": [], "khong": None, "am": -3.25}


def test_sx_round_trip_bang_bo_doc_nho():
    al = doc_sx(CN.sx(KHO))
    assert tim(al, "ok") is True and tim(al, "chuoi") == KHO["chuoi"] and tim(al, "so") == 1.5
    assert tim(al, "ds") == [1, 2.5, "x"] and tim(al, "am") == -3.25
    assert tim(al, "khong") == [] and tim(al, "rong") == []
    assert tim(tim(al, "long"), "a") == 1 and tim(tim(al, "long"), "b") == []     # False → (k) → rỗng
    assert CN.sx(None) == "nil" and CN.sx([]) == "nil" and CN.sx(True) == "T"
    assert CN.sx(float("nan")) == "nil" and CN.sx(1e-7) == "0.0000001" and "e" not in CN.sx(123456789012.5)


@can_acore
def test_ra_lsp_nap_duoc_bang_autolisp_that_va_args_file_utf16(tmp_m):
    """Hai kênh chữ Việt đã đo trên AutoCAD 2022:
    Python → LISP: `--ra x.lsp` = (setq *sn-ra* '…) rồi (load). (`(open … "r" "UTF-8")` bị từ chối; "r" thường đọc UTF-8 thành rác.)
    LISP → Python: FileSystemObject.CreateTextFile(path, T, T) ghi UTF-16LE → `--args-file`."""
    ra = tmp_m / "kho_ra.lsp"
    ra.write_bytes(("(setq *sn-ra* '" + CN.sx(KHO) + ")\n").encode("utf-8"))
    outf, args_f, lsp = tmp_m / "kho_out.txt", tmp_m / "args_utf16.txt", tmp_m / "doc.lsp"
    lsp.write_text(f"""(vl-load-com)
(load "{ra.as_posix()}")
(setq o (open "{outf.as_posix()}" "w"))
(write-line (if (cdr (assoc "ok" *sn-ra*)) "OK" "NIL") o)
(write-line (vl-prin1-to-string (cdr (assoc "ds" *sn-ra*))) o)
(write-line (vl-prin1-to-string (cdr (assoc "long" *sn-ra*))) o)
(write-line (rtos (cdr (assoc "so" *sn-ra*)) 2 3) o)
(write-line (if (cdr (assoc "khong" *sn-ra*)) "CO" "KHONG") o)
(write-line (itoa (strlen (cdr (assoc "chuoi" *sn-ra*)))) o)
(close o)
(setq fso (vlax-create-object "Scripting.FileSystemObject"))
(setq f (vlax-invoke-method fso 'CreateTextFile "{args_f.as_posix()}" :vlax-true :vlax-true))
(vlax-invoke-method f 'WriteLine (cdr (assoc "chuoi" *sn-ra*)))
(vlax-invoke-method f 'Close)
(princ)
""", encoding="utf-8")
    _chay_acore(tmp_m, [lsp], luu_dxf=False)
    d = outf.read_text(encoding="ascii").splitlines()
    assert d == ["OK", '(1 2.5 "x")', '(("a" . 1) ("b"))', "1.500", "KHONG", str(len(KHO["chuoi"]))]   # độ dài đúng = không vỡ chữ Việt
    assert args_f.read_bytes()[:2] == b"\xff\xfe"                                                      # UTF-16LE có BOM
    assert mo_rong_args_file_doc(args_f) == KHO["chuoi"].split("\n")                                   # LISP ghi → Python đọc đúng


def mo_rong_args_file_doc(p: Path) -> list[str]:
    tmp = ["--args-file", str(p)]
    return CN.mo_rong_args_file(tmp)


def test_args_file_dua_chu_viet_vao_lenh(lot_moi, tmp_path):
    f = tmp_path / "args.txt"
    dong = ["duyet", "--lot", str(lot_moi.root), "--ra", str(tmp_path / "r.txt"), "--cong", "1",
            "--nguoi", "Nguyễn Văn Ạ", "--bang-chung", "Đồng ý — dữ liệu ổn \"tốt\""]
    for enc, ten in (("utf-16", "u16"), ("utf-8-sig", "u8bom"), ("utf-8", "u8")):
        g = tmp_path / f"{ten}.txt"
        g.write_bytes(("\n".join(dong) + "\n\n").encode(enc))
        assert CN.mo_rong_args_file(["--args-file", str(g)]) == dong
        assert CN.mo_rong_args_file(["x", "--args-file", str(g), "--y"]) == ["x", *dong, "--y"]
    f.write_bytes("\n".join(dong).encode("utf-16"))
    assert CN.main(["--args-file", str(f)]) == 0
    cong = json.loads((lot_moi.log_dir / "cong.json").read_text(encoding="utf-8"))
    assert cong["1"]["nguoi_duyet"] == "Nguyễn Văn Ạ" and cong["1"]["bang_chung"] == 'Đồng ý — dữ liệu ổn "tốt"'
    assert "Đồng ý — dữ liệu ổn" in (lot_moi.log_dir / "decisions.md").read_text(encoding="utf-8")


def test_ra_duoi_lsp_ghi_dang_setq(lo, tmp_m):
    ra = tmp_m / "kq.lsp"
    assert CN.main(["luoi-doc", "--lot", str(lo.root), "--ra", str(ra)]) == 0
    t = ra.read_bytes().decode("utf-8")
    assert t.startswith("(setq *sn-ra* '(") and can_bang(t) == 0 and not t.startswith("﻿")
    assert doc_sx(t[len("(setq *sn-ra* '"):-2]) is not None


# =========================================================================== backend LISP (đơn vị)
def test_backend_lisp_xem_truoc_khong_them_dong_nao():
    be = BackendLisp()
    n0 = len(be.dong)
    be.cad_draw_grid("L", 1, "h", {"goc_luoi": [0, 0], "goc_xoay_do": 0, "cot_m": [10], "hang_m": [10]}, xem_truoc=True)
    be.cad_purge_sn("L", 1, xem_truoc=True)
    be.cad_draw_3dface("L", 1, "h", "moc", [[[0, 0, 1], [1, 0, 1], [0, 1, 1]]], xem_truoc=True)
    be.cad_label_cells("L", 1, "h", [{"ma": "O01-01", "e": 1, "n": 1, "kl_dao_m3": 1, "kl_dap_m3": 2}], xem_truoc=True)
    assert len(be.dong) == n0 == 0


def test_backend_lisp_thoat_chuoi_layer_mot_lan_va_hau_to_dot():
    assert ls('Lô "A" \\ B\nC') == r'"Lô \"A\" \\ B\nC"'
    be = BackendLisp()
    lu = {"goc_luoi": [100.5, 200.25], "goc_xoay_do": 30, "cot_m": [10, 10], "hang_m": [10]}
    be.cad_draw_grid('01-"CGP"', 3, "h", lu, xem_truoc=False)
    be.cad_draw_grid('01-"CGP"', 3, "h", lu, xem_truoc=False)
    txt = be.noi_dung()
    assert txt.count('(snv:lop "SN-LUOI-D03"') == 1 and "SN-LUOI-D03" in txt         # đợt ≥ 2 có hậu tố; layer tạo 1 lần
    assert r'(snv:dat "01-\"CGP\""' in txt
    assert txt.endswith("(princ)\n") and can_bang(txt) == 0 and "\ufeff" not in txt


def test_backend_lisp_doc_khong_lam_duoc_thi_noi_that():
    be = BackendLisp()
    for f in (be.cad_doc_info, lambda: be.cad_read_points("x"), lambda: be.cad_read_polylines("x"),
              lambda: be.cad_export_dxf("x.dxf"), lambda: be.cad_read_grid_z("L")):
        with pytest.raises(NotImplementedError):
            f()


def test_backend_lisp_doc_csv_nhan_dinh(tmp_path):
    p = tmp_path / "nhan.csv"
    p.write_text("ma,be_mat,z\nD02-01,do,2.5\nD01-01,moc,\"1,25\"\n", encoding="utf-8-sig")
    z = BackendLisp(p).cad_read_grid_z("L")
    assert z == [{"ma": "D01-01", "be_mat": "moc", "z": 1.25}, {"ma": "D02-01", "be_mat": "do", "z": 2.5}]


def test_ve_lop_chi_ve_phan_duoc_chon_va_giu_mat_cat(lo, tmp_path):
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    ve_ket_qua(be, lo.root)
    be.ve_ent("GT-01", 1, "h", "mat_cat", "SN-MATCAT", [("doan", 0, 0, 5, 5)], False, ten="MC9")
    dem = lambda: {k: sum(1 for e in be.msp if e.dxf.layer == k) for k in ("SN-LUOI", "SN-LUOI-NHAN", "SN-LUOI-O", "SN-MATCAT")}
    d1 = dem()
    ve_ket_qua(be, lo.root)                                                  # vẽ lại TOÀN BỘ không xóa mặt cắt
    assert dem() == d1 and d1["SN-MATCAT"] == 1
    ve_ket_qua(be, lo.root, lop=["luoi"])                                    # chỉ lưới: nhãn, ô, mặt cắt nguyên vẹn
    assert dem() == d1
    be.cad_purge_sn("GT-01", 1, xem_truoc=False, loai=NHOM_LOP["nhan"])
    d2 = dem()
    assert d2["SN-LUOI-NHAN"] == 0 and d2["SN-LUOI"] == d1["SN-LUOI"] and d2["SN-LUOI-O"] == d1["SN-LUOI-O"]
    with pytest.raises(ValueError, match="Nhóm vẽ lạ"):
        ve_ket_qua(be, lo.root, lop=["luoi", "xyz"])


# =========================================================================== (b) từng lệnh cầu nối
def test_loi_chung_khong_phai_thu_muc_lo_van_ghi_ra(tmp_path):
    ra = tmp_path / "r.txt"
    assert CN.main(["trang-thai", "--lot", str(tmp_path), "--ra", str(ra)]) == 0
    al = doc_sx(ra.read_text(encoding="utf-8"))
    assert tim(al, "ok") != True and "thiếu lot.yaml" in tim(al, "thong_bao")    # noqa: E712
    assert tim(al, "du_lieu") == []


def test_trang_thai(lo, tmp_m):
    ok, tb, du, _ = chay_cn(tmp_m, lo, "trang-thai")
    assert ok and tim(du, "lot") == lo.root.name
    assert tim(tim(du, "buoc_da_chay"), "tinh") is True and tim(tim(du, "buoc_da_chay"), "xuat") is True
    assert tim(du, "buoc_ke_tiep") == []                                      # đã chạy hết các bước → None → ("buoc_ke_tiep")
    so_nop = tim(du, "so_nop")
    v = json.loads((lo.process_dir / "volume.json").read_text(encoding="utf-8"))
    assert tim(so_nop, "dao_m3") == pytest.approx(v["so_nop"]["dao_m3"], abs=1e-6)


def test_luoi_doc(lo, tmp_m):
    ok, _, du, _ = chay_cn(tmp_m, lo, "luoi-doc")
    assert ok and tim(du, "kich_thuoc") == 20 and tim(du, "cot") == "5x20" and tim(du, "hang") == "3x20"
    assert (tim(du, "nx"), tim(du, "ny"), tim(du, "so_o")) == (5, 3, 15)
    assert tim(du, "dt_o") == pytest.approx(6000, abs=1e-3) and tim(du, "dt_lo") == pytest.approx(6000, abs=1e-3)
    assert len(tim(du, "goc_luoi")) == 2 and tim(du, "ngoai_suy_kieu") == "gan_nhat"


def test_luoi_doc_chua_co_grid(tmp_path):
    l = tao(tmp_path / "x", [hcn(0, 0, 50, 50)], f_moc, f_do, so_diem=300)
    ok, tb, _, _ = chay_cn(tmp_path, l, "luoi-doc")
    assert not ok and "grid.json" in tb
    ok, tb, _, _ = chay_cn(tmp_path, l, "ve", lsp=True)
    assert not ok and "grid.json" in tb


def test_ve_va_tin3d_sinh_lsp_can_ngoac(lo, tmp_m):
    ok, tb, du, lsp = chay_cn(tmp_m, lo, "ve", lsp=True)
    assert ok and lsp.exists() and tim(du, "luoi") == 10 and tim(du, "nhan_o") == 15
    txt = lsp.read_text(encoding="utf-8")
    assert txt.startswith(";; Sinh tự động") and txt.endswith("(princ)\n") and can_bang(txt) == 0
    assert not txt.startswith("\ufeff") and "Đào" in txt
    ok, _, du, lsp = chay_cn(tmp_m, lo, "tin3d", "--be-mat", "do", lsp=True)
    assert ok and tim(du, "so_mat_moc") == 0 and tim(du, "so_mat_do") > 100
    t = lsp.read_text(encoding="utf-8")
    assert '(snv:bat "SN-3DF-DO" T)' in t and '(snv:bat "SN-3DF-MOC" nil)' in t and can_bang(t) == 0
    ok, tb, _, _ = chay_cn(tmp_m, lo, "tin3d", "--be-mat", "xyz", lsp=True)
    assert not ok and "moc, do hoặc ca-hai" in tb
    ok, tb, _, lsp = chay_cn(tmp_m, lo, "tin3d-tat", lsp=True)
    assert ok and lsp.read_text(encoding="utf-8").count("(snv:bat") == 2
    ok, tb, _, lsp = chay_cn(tmp_m, lo, "ve", "--lop", "luoi,xyz", lsp=True)
    assert not ok and "Nhóm vẽ lạ" in tb and not lsp.exists()                    # lỗi → không để lại file vẽ cũ


def test_mat_cat_cau_noi(lo, tmp_m):
    ok, tb, du, lsp = chay_cn(tmp_m, lo, "mat-cat", "--a", f"{E0},{N0 + 30}", "--b", f"{E0 + 100},{N0 + 30}",
                              "--buoc", "5", "--ten", "A-B", "--goc-ve", f"{E0},{N0 - 90}", lsp=True)
    assert ok and tim(du, "chieu_dai") == pytest.approx(100.0)
    assert tim(du, "dien_tich_dao") == pytest.approx(25.0, rel=1e-4) and tim(du, "dien_tich_dap") == pytest.approx(25.0, rel=1e-4)
    assert Path(tim(du, "csv")).exists() and (lo.process_dir / "matcat_A-B.json").exists()
    t = lsp.read_text(encoding="utf-8")
    assert '(snv:xoa "GT-01" "1" \'("mat_cat") \'("ten=A-B"))' in t and "MẶT CẮT A-B" in t and can_bang(t) == 0
    for args, loi in ((("--a", f"{E0},{N0}", "--b", f"{E0},{N0}", "--goc-ve", "0,0"), "trùng nhau"),
                      (("--a", "abc", "--b", "1,2", "--goc-ve", "0,0"), "dạng E,N"),
                      (("--a", f"{E0},{N0}", "--b", f"{E0 + 5},{N0}", "--goc-ve", "0,0", "--ten", 'a"b'), "Tên mặt cắt"),
                      (("--a", f"{E0 + 500},{N0 + 500}", "--b", f"{E0 + 600},{N0 + 500}", "--goc-ve", "0,0"), "không có đoạn nào nằm trong TIN")):
        ok, tb, _, _ = chay_cn(tmp_m, lo, "mat-cat", *args, lsp=True)
        assert not ok and loi in tb, (args, tb)


def test_bang_cau_noi(lo, tmp_m):
    for loai in ("tong", "tong-hop", "o"):
        ok, tb, du, lsp = chay_cn(tmp_m, lo, "bang", "--loai", loai, "--goc-ve", f"{E0},{N0 - 40}", lsp=True)
        assert ok and tim(du, "kieu") == loai and tim(du, "so_doi_tuong") > 8
        t = lsp.read_text(encoding="utf-8")
        assert f"kieu={loai}" in t and "BẢNG" in t and can_bang(t) == 0
    ok, tb, _, _ = chay_cn(tmp_m, lo, "bang", "--loai", "xyz", "--goc-ve", "0,0", lsp=True)
    assert not ok and "tong, tong-hop hoặc o" in tb
    ok, tb, _, _ = chay_cn(tmp_m, lo, "bang", "--loai", "tong", lsp=True)
    assert not ok and "--goc-ve" in tb


def test_o_tai(lo, tmp_m):
    ok, _, du, _ = chay_cn(tmp_m, lo, "o-tai", "--e", str(E0 + 10), "--n", str(N0 + 10))
    v = json.loads((lo.process_dir / "volume.json").read_text(encoding="utf-8"))
    o = next(c for c in v["o"] if c["ma"] == "O01-01")
    assert ok and tim(du, "ma") == "O01-01" and tim(du, "kl_dap") == pytest.approx(o["kl_dap_m3"])
    assert tim(du, "dt") == pytest.approx(400.0, abs=1e-3) and tim(du, "thieu_du_lieu") is not True
    ok, _, du, _ = chay_cn(tmp_m, lo, "o-tai", "--e", str(E0 + 99), "--n", str(N0 + 59))
    assert ok and tim(du, "ma") == "O05-03"
    for e, n in ((E0 - 50, N0 - 50), (E0 + 105, N0 + 10), (E0 + 10, N0 + 70)):
        ok, tb, _, _ = chay_cn(tmp_m, lo, "o-tai", "--e", str(e), "--n", str(n))
        assert not ok and "ngoài lưới" in tb


def test_canh_bao_va_chay(lo, tmp_m):
    ok, tb, du, _ = chay_cn(tmp_m, lo, "canh-bao")
    assert ok and tb.endswith("phát hiện") and isinstance(du, list)
    assert du, "lô thử có ít nhất vài thông báo (chú giải, tam giác dẹt...)"
    hang = {"chan": 0, "canh_bao": 1, "thong_tin": 2}
    muc = [tim(it, "muc") for it in du]
    assert all(m in hang for m in muc) and [hang[m] for m in muc] == sorted(hang[m] for m in muc)   # chặn trước
    assert all(isinstance(tim(it, "mo_ta"), str) and tim(it, "ma") for it in du)
    ok, _, du, _ = chay_cn(tmp_m, lo, "chay", "--verb", "xuat", "--them=--preview")
    assert ok and tim(du, "ma_thoat") == 0 and "XEM TRƯỚC" in tim(du, "van_ban")
    ok, tb, _, _ = chay_cn(tmp_m, lo, "chay", "--verb", "rm")
    assert not ok and "một trong" in tb
    ok, tb, du, _ = chay_cn(tmp_m, lo, "chay", "--verb", "mat", "--them=--be-mat")       # tham số hỏng: argparse báo lỗi
    assert not ok and tim(du, "ma_thoat") == 2


# ---- các lệnh làm thay đổi lô: mỗi test một lô riêng ------------------------------------
def test_luoi_sua_thanh_cong(lot_moi, tmp_path):
    ok, tb, du, lsp = chay_cn(tmp_path, lot_moi, "luoi-sua", "--lenh", "chen_cot", "--sau", "2", "--kich-thuoc", "10",
                              "--ly-do", "thử chèn cột", lsp=True)
    assert ok, tb
    assert tim(du, "cot") == "2x20,1x10,3x20" and tim(du, "nx") == 6 and tim(du, "dt_o") == pytest.approx(6000, abs=1e-3)
    assert (lot_moi.root / "luoi_tuy_chinh.yaml").exists()
    assert "thử chèn cột" in (lot_moi.log_dir / "decisions.md").read_text(encoding="utf-8")
    t = lsp.read_text(encoding="utf-8")
    assert "(snv:xoa " in t and can_bang(t) == 0
    ok, tb, du, lsp = chay_cn(tmp_path, lot_moi, "luoi-ve-lai-lot-yaml", lsp=True)
    assert ok and tim(du, "cot") == "5x20" and not (lot_moi.root / "luoi_tuy_chinh.yaml").exists()


def test_luoi_sua_hong_thi_khoi_phuc_nguyen_trang(lot_moi, tmp_path):
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "luoi-sua", "--lenh", "chen_cot", "--sau", "2", "--kich-thuoc", "10", lsp=True)
    assert ok, tb
    ps = lot_moi.process_dir
    ten = ("grid.json", "volume.json", "qc_luoi.json", "qc_volume.json", "viec_can_lam.md")
    truoc = {t: (ps / t).read_bytes() for t in ten}
    tc, dec = lot_moi.root / "luoi_tuy_chinh.yaml", lot_moi.log_dir / "decisions.md"
    b_tc, b_dec = tc.read_bytes(), dec.read_bytes()
    # xóa cột cuối → 110 − 20 = 90 m < 100 m: lưới không phủ hết lô
    ok, tb, _, lsp = chay_cn(tmp_path, lot_moi, "luoi-sua", "--lenh", "xoa_cot", "--chi-so", "6", lsp=True)
    assert not ok and "Lưới không dùng được" in tb and "chưa phủ hết lô" in tb
    assert tc.read_bytes() == b_tc and dec.read_bytes() == b_dec                # yaml + nhật ký quyết định như cũ
    assert {t: (ps / t).read_bytes() for t in ten} == truoc                     # grid/volume/qc như cũ
    assert not lsp.exists()
    # lỗi mẫu / chỉ số: chưa ghi gì
    for args, loi in ((("--lenh", "dat", "--cot", "abc"), "không đúng dạng"),
                      (("--lenh", "doi_cot", "--chi-so", "99", "--kich-thuoc", "5"), "không có"),
                      (("--lenh", "doi_hang", "--chi-so", "1", "--kich-thuoc", "0"), "phải dương"),
                      (("--lenh", "bay"), "lạ"), ((), "Thiếu --lenh")):
        ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "luoi-sua", *args, lsp=True)
        assert not ok and loi in tb, (args, tb)
    assert tc.read_bytes() == b_tc and dec.read_bytes() == b_dec


def test_luoi_sua_cat_hieu_chinh_dinh_va_khoi_phuc_khi_hong(lot_moi, tmp_path):
    cli.main(["hieuchinh", "--lot", str(lot_moi.root), "--dinh", "D02-02", "--z", "99"])
    adj = lot_moi.process_dir / "grid_adjusted.json"
    b_adj = adj.read_bytes()
    ok, tb, du, _ = chay_cn(tmp_path, lot_moi, "luoi-sua", "--lenh", "xoa_cot", "--chi-so", "5", lsp=True)   # hỏng
    assert not ok and adj.exists() and adj.read_bytes() == b_adj                # hiệu chỉnh đỉnh còn nguyên
    assert not list(lot_moi.process_dir.glob("grid_adjusted.cu_*.json"))
    ok, tb, du, _ = chay_cn(tmp_path, lot_moi, "luoi-sua", "--lenh", "chen_cot", "--sau", "1", "--kich-thuoc", "5", lsp=True)
    assert ok and tim(du, "cat_hieu_chinh").startswith("grid_adjusted.cu_") and not adj.exists()


def test_dong_bo_va_hieuchinh_nhieu(lot_moi, tmp_path):
    csv_cad = tmp_path / "nhan.csv"
    z = json.loads((lot_moi.process_dir / "grid.json").read_text(encoding="utf-8"))["nut"]["D02-02"]["z_do"]
    csv_cad.write_text(f"ma,be_mat,z\nD02-02,do,{z + 0.25}\n", encoding="utf-8-sig")
    ok, tb, du, _ = chay_cn(tmp_path, lot_moi, "dong-bo", "--tu-file", str(csv_cad))
    assert ok and tim(du, "ma_thoat") == 1 and "KHÁC" in tim(du, "van_ban") and "Chưa nhận" in tim(du, "van_ban")
    assert not (lot_moi.process_dir / "grid_adjusted.json").exists()
    ok, tb, du, _ = chay_cn(tmp_path, lot_moi, "dong-bo", "--tu-file", str(csv_cad), "--chap-nhan")
    assert ok and (lot_moi.process_dir / "grid_adjusted.json").exists()
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "dong-bo", "--tu-file", str(tmp_path / "khong_co.csv"))
    assert not ok and "tu-file" in tb

    sua = tmp_path / "sua.csv"
    sua.write_text("ma,z,be_mat,ly_do\nD03-02,12.5,do,theo thiết kế\nD02-03,11.5,do,\n", encoding="utf-8")
    ok, tb, du, lsp = chay_cn(tmp_path, lot_moi, "hieuchinh-nhieu", "--tu-file", str(sua), "--ly-do", "nâng", lsp=True)
    assert ok, tb
    t = lsp.read_text(encoding="utf-8")
    assert "ma=D03-02" in t and "(snv:xoa-nhan" in t and can_bang(t) == 0
    adj = json.loads((lot_moi.process_dir / "grid_adjusted.json").read_text(encoding="utf-8"))["ghi_de"]
    assert {(g["ma"], g["z_moi"]) for g in adj} >= {("D03-02", 12.5), ("D02-03", 11.5)}
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "hieuchinh-nhieu", "--tu-file", str(sua), lsp=False)
    assert not ok and "--lsp" in tb
    sai = tmp_path / "sai.csv"
    sai.write_text("ma,z\nD99-99,1\n", encoding="utf-8")
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "hieuchinh-nhieu", "--tu-file", str(sai), lsp=True)
    assert not ok and "từ chối" in tb


def test_duyet_cong(lot_moi, tmp_path):
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "duyet", "--cong", "1", "--nguoi", "QS")
    assert not ok and "Agent không được tự duyệt" in tb
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "duyet", "--cong", "1", "--nguoi", "QS", "--bang-chung", "OK, dữ liệu dùng được")
    assert ok, tb
    cong = json.loads((lot_moi.log_dir / "cong.json").read_text(encoding="utf-8"))
    assert cong["1"]["duyet"] is True and cong["1"]["bang_chung"] == "OK, dữ liệu dùng được"


# =========================================================================== (c) AutoCAD thật
def _chay_acore(tmp: Path, lsp_list: list[Path], base: Path | None = None, luu_dxf: bool = True,
                ten_ra: str | None = None):
    """Nạp lần lượt các file .lsp vào AutoCAD 2022 (không giao diện), lưu DXF. Trả (doc ezdxf | None, log)."""
    ra = tmp / (ten_ra or f"ra_{uuid.uuid4().hex[:8]}.dxf")
    dong = [f'(load "{p.as_posix()}")' for p in lsp_list]
    if luu_dxf:
        dong += ["_.SAVEAS", "DXF", "16", ra.as_posix()]
    dong += ["_.QUIT", "Y"]
    scr = tmp / f"s_{uuid.uuid4().hex[:8]}.scr"
    scr.write_text("\n".join(dong) + "\n", encoding="ascii")
    args = [str(ACORE), "/s", str(scr), "/l", "en-US"] + (["/i", str(base)] if base else [])
    p = subprocess.run(args, capture_output=True, timeout=300)
    log = p.stdout.decode("utf-16-le", "ignore") if p.stdout[:2] in (b"\xff\xfe",) or b"\x00" in p.stdout[:40] \
        else p.stdout.decode("utf-8", "ignore")
    assert "; error" not in log.lower() and "bad argument" not in log.lower(), log[-1500:]
    if not luu_dxf:
        return None, log
    assert ra.exists(), log[-1500:]
    return ezdxf.readfile(ra), log


def dem_layer(doc, layer: str, loai_dxf: str | None = None) -> int:
    return sum(1 for e in doc.modelspace() if e.dxf.layer == layer and (loai_dxf is None or e.dxftype() == loai_dxf))


def so_mat_polyface(doc, layer: str) -> int:
    """Tổng số mặt (tam giác) của các POLYFACE trên một layer — menu CAD vẽ mặt 3D dạng polyface, mỗi bề mặt MỘT đối tượng."""
    return sum(sum(1 for _ in e.faces()) for e in doc.modelspace()
               if e.dxftype() == "POLYLINE" and e.dxf.layer == layer and e.is_poly_face_mesh)


def dem_tat_ca(doc) -> dict:
    d: dict[str, int] = {}
    for e in doc.modelspace():
        d[e.dxf.layer] = d.get(e.dxf.layer, 0) + 1
    return d


@pytest.fixture(scope="module")
def lsp_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("cn_lsp")


@can_acore
def test_acad_ve_day_du_layer_xdata_va_tieng_viet(lo, lsp_dir):
    ok, tb, du, lsp = chay_cn(lsp_dir, lo, "ve", lsp=True)
    assert ok, tb
    doc, _ = _chay_acore(lsp_dir, [lsp], base=lo.input_dir / "gt.dxf")
    g = json.loads((lo.process_dir / "grid.json").read_text(encoding="utf-8"))
    v = json.loads((lo.process_dir / "volume.json").read_text(encoding="utf-8"))
    ts = g["tham_so"]
    assert dem_layer(doc, "SN-LUOI") == ts["nx"] + 1 + ts["ny"] + 1
    assert dem_layer(doc, "SN-LUOI-O", "MTEXT") == len(g["o"])
    assert dem_layer(doc, "SN-RANH-DAODAP") == len(v["ranh_dao_dap"])
    so_nut = sum(1 for n in g["nut"].values() if n["z_moc"] is not None and n["z_do"] is not None)
    assert dem_layer(doc, "SN-LUOI-NHAN", "TEXT") == 3 * so_nut
    assert dem_layer(doc, "SN-BANG") > 20
    for nhan, ly in (("moc", "SN-3DF-MOC"), ("do", "SN-3DF-DO")):
        s = json.loads((lo.process_dir / f"surface_{nhan}.json").read_text(encoding="utf-8"))
        tot = sum(1 for l in (s.get("loai_tam_giac") or [0] * len(s["tam_giac"])) if l == 0)
        assert dem_layer(doc, ly) == 1 and dem_layer(doc, ly, "POLYLINE") == 1 and so_mat_polyface(doc, ly) == tot
        assert doc.layers.get(ly).is_off()                                    # mặt 3D tắt mặc định
    # nguồn nguyên vẹn
    goc = ezdxf.readfile(lo.input_dir / "gt.dxf")
    assert dem_layer(doc, "SN-DIEM-MOC", "POINT") == dem_layer(goc, "SN-DIEM-MOC", "POINT") > 100
    assert dem_layer(doc, "SN-BIENLO") == dem_layer(goc, "SN-BIENLO") == 1
    # mọi đối tượng kết quả mang dấu truy vết đọc được bởi backend DXF
    hs = str(v["hash_dau_vao"])[:16]
    ket_qua = [e for e in doc.modelspace() if e.dxf.layer.startswith("SN-") and e.dxf.layer not in ("SN-DIEM-MOC", "SN-DIEM-DO", "SN-BIENLO", "SN-LOAITRU", "SN-DUTGAY")]
    assert len(ket_qua) > 100
    for e in ket_qua:
        n = BackendDXF.doc_nhan(e)
        assert n and n["ma_lo"] == "GT-01" and n["dot"] == 1 and n["hash"] == hs, e.dxf.layer
    nhan = [BackendDXF.doc_nhan(e) for e in doc.modelspace() if e.dxf.layer == "SN-LUOI-NHAN"]
    assert {n["be_mat"] for n in nhan} == {"moc", "do", "dz"} and all(n["loai"] == "nhan_dinh" and n["ma"] for n in nhan)
    # tiếng Việt đúng
    mt = " ".join(e.text for e in doc.modelspace() if e.dxftype() == "MTEXT")
    assert "Đào" in mt and "Đắp" in mt
    tx = " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT" and e.dxf.layer == "SN-BANG")
    assert "BẢNG KHỐI LƯỢNG" in tx


@can_acore
def test_acad_nap_lan_hai_khong_nhan_doi(lo, lsp_dir):
    ok, tb, _, lsp = chay_cn(lsp_dir, lo, "ve", lsp=True)
    assert ok
    d1, _ = _chay_acore(lsp_dir, [lsp], base=lo.input_dir / "gt.dxf")
    c1 = dem_tat_ca(d1)
    d2, _ = _chay_acore(lsp_dir, [lsp, lsp, lsp], base=lo.input_dir / "gt.dxf")               # nạp 3 lần trong 1 phiên
    assert dem_tat_ca(d2) == c1
    ra1 = lsp_dir / "phien1.dxf"
    d1.saveas(ra1)
    d3, _ = _chay_acore(lsp_dir, [lsp], base=ra1)                                              # phiên sau, mở bản vẽ đã vẽ
    assert dem_tat_ca(d3) == c1


@can_acore
def test_acad_ve_tung_phan_va_purge_khong_dung_lo_khac(lo, lsp_dir):
    # một lô KHÁC cùng nằm trong bản vẽ: LISP tay đánh dấu "LO-KHAC" — không được bị xóa
    khac = lsp_dir / "lo_khac.lsp"
    be = BackendLisp()
    be.cad_draw_grid("LO-KHAC", 1, "h", {"goc_luoi": [E0, N0], "goc_xoay_do": 0, "cot_m": [10, 10], "hang_m": [10]}, xem_truoc=False)
    be.luu(khac)
    ok, _, _, ve_all = chay_cn(lsp_dir, lo, "ve", lsp=True)
    ok2, _, _, ve_luoi = chay_cn(lsp_dir, lo, "ve", "--lop", "luoi", lsp=True)
    assert ok and ok2
    doc_all, _ = _chay_acore(lsp_dir, [khac, ve_all], base=lo.input_dir / "gt.dxf")
    doc_lai, _ = _chay_acore(lsp_dir, [khac, ve_all, ve_luoi], base=lo.input_dir / "gt.dxf")
    assert dem_tat_ca(doc_lai) == dem_tat_ca(doc_all)
    lo_khac = [e for e in doc_lai.modelspace() if (BackendDXF.doc_nhan(e) or {}).get("ma_lo") == "LO-KHAC"]
    assert len(lo_khac) == 5                                                                    # 3 cột + 2 hàng đường lưới


@can_acore
def test_acad_tin3d_bat_tat_dung_be_mat(lo, lsp_dir):
    sinh = lambda *a: chay_cn(lsp_dir, lo, *a, lsp=True)[3]
    moc, do, tat = sinh("tin3d", "--be-mat", "moc"), sinh("tin3d", "--be-mat", "do"), sinh("tin3d-tat")
    base = lo.input_dir / "gt.dxf"
    d, _ = _chay_acore(lsp_dir, [moc], base=base)
    assert dem_layer(d, "SN-3DF-MOC", "POLYLINE") == 1 and so_mat_polyface(d, "SN-3DF-MOC") > 100 and dem_layer(d, "SN-3DF-DO") == 0
    assert not d.layers.get("SN-3DF-MOC").is_off()                                              # bật
    d, _ = _chay_acore(lsp_dir, [moc, do], base=base)                                           # đổi sang mặt đo
    assert dem_layer(d, "SN-3DF-MOC") == 0 and so_mat_polyface(d, "SN-3DF-DO") > 100       # mặt mốc cũ bị xóa
    assert d.layers.get("SN-3DF-MOC").is_off() and not d.layers.get("SN-3DF-DO").is_off()
    d, _ = _chay_acore(lsp_dir, [moc, do, tat], base=base)
    assert d.layers.get("SN-3DF-DO").is_off() and d.layers.get("SN-3DF-MOC").is_off()
    assert dem_layer(d, "SN-3DF-DO", "POLYLINE") == 1 and so_mat_polyface(d, "SN-3DF-DO") > 100  # tắt chứ không xóa
    d2, _ = _chay_acore(lsp_dir, [moc, sinh("tin3d", "--be-mat", "ca-hai")], base=base)
    assert not d2.layers.get("SN-3DF-MOC").is_off() and not d2.layers.get("SN-3DF-DO").is_off()
    assert so_mat_polyface(d2, "SN-3DF-MOC") > 100 and so_mat_polyface(d2, "SN-3DF-DO") > 100


@can_acore
def test_acad_mat_cat_cung_ten_ve_lai_khong_nhan_doi(lo, lsp_dir):
    ve = lambda ten, gv: chay_cn(lsp_dir, lo, "mat-cat", "--a", f"{E0},{N0 + 30}", "--b", f"{E0 + 100},{N0 + 30}", "--buoc", "10",
                                 "--ten", ten, "--goc-ve", gv, lsp=True)[3]
    mc1, mc2 = ve("MC1", f"{E0},{N0 - 90}"), ve("MC2", f"{E0 + 200},{N0 - 90}")
    base = lo.input_dir / "gt.dxf"
    d1, _ = _chay_acore(lsp_dir, [mc1], base=base)
    n1 = dem_layer(d1, "SN-MATCAT")
    assert n1 > 25
    d, _ = _chay_acore(lsp_dir, [mc1, mc1], base=base)
    assert dem_layer(d, "SN-MATCAT") == n1                                                      # cùng tên: thay, không nhân đôi
    d, _ = _chay_acore(lsp_dir, [mc1, mc2, mc1], base=base)
    assert dem_layer(d, "SN-MATCAT") == 2 * n1                                                  # tên khác: cộng thêm; vẽ lại MC1 không đụng MC2
    ten = {BackendDXF.doc_nhan(e)["ten"] for e in d.modelspace() if e.dxf.layer == "SN-MATCAT"}
    assert ten == {"MC1", "MC2"}
    assert all(BackendDXF.doc_nhan(e)["loai"] == "mat_cat" for e in d.modelspace() if e.dxf.layer == "SN-MATCAT")
    tx = [e.dxf.text for e in d.modelspace() if e.dxf.layer == "SN-MATCAT" and e.dxftype() == "TEXT"]
    assert any(t.startswith("MẶT CẮT MC1") for t in tx) and any("Cao độ mốc" in t for t in tx)
    dg = [e for e in d.modelspace() if e.dxf.layer == "SN-MATCAT" and e.dxftype() == "LWPOLYLINE" and e.dxf.color == 6]
    assert len(dg) == 2                                                                         # tuyến cắt A–B của mỗi mặt cắt trên mặt bằng


@can_acore
def test_acad_bang_cung_kieu_thay_khac_kieu_cong_them(lo, lsp_dir):
    ve = lambda loai: chay_cn(lsp_dir, lo, "bang", "--loai", loai, "--goc-ve", f"{E0},{N0 - 60}", lsp=True)[3]
    tong, th, o = ve("tong"), ve("tong-hop"), ve("o")
    base = lo.input_dir / "gt.dxf"
    d1, _ = _chay_acore(lsp_dir, [tong], base=base)
    n_tong = dem_layer(d1, "SN-BANG")
    d, _ = _chay_acore(lsp_dir, [tong, tong], base=base)
    assert dem_layer(d, "SN-BANG") == n_tong
    d, _ = _chay_acore(lsp_dir, [tong, th, o, tong], base=base)
    kieu = {BackendDXF.doc_nhan(e)["kieu"] for e in d.modelspace() if e.dxf.layer == "SN-BANG"}
    assert kieu == {"tong", "tong-hop", "o"}
    dt, _ = _chay_acore(lsp_dir, [th], base=base)
    do_, _ = _chay_acore(lsp_dir, [o], base=base)
    assert dem_layer(d, "SN-BANG") == n_tong + dem_layer(dt, "SN-BANG") + dem_layer(do_, "SN-BANG")
    t = " ".join(e.dxf.text for e in d.modelspace() if e.dxf.layer == "SN-BANG" and e.dxftype() == "TEXT")
    assert "Khối lượng đào" in t and "Diện tích lô" in t


@can_acore
def test_acad_chinh_luoi_roi_ve_lai_khong_con_luoi_cu(lot_moi, tmp_path):
    base = lot_moi.input_dir / "gt.dxf"
    _, _, _, ve_all = chay_cn(tmp_path, lot_moi, "ve", lsp=True)
    d1, _ = _chay_acore(tmp_path, [ve_all], base=base)
    ra1 = tmp_path / "da_ve.dxf"
    d1.saveas(ra1)
    n_nhan1 = dem_layer(d1, "SN-LUOI-NHAN")
    ok, tb, du, lsp = chay_cn(tmp_path, lot_moi, "luoi-sua", "--lenh", "chen_cot", "--sau", "2", "--kich-thuoc", "10", lsp=True)
    assert ok, tb
    d2, _ = _chay_acore(tmp_path, [lsp], base=ra1)                                              # mở bản vẽ ĐÃ VẼ, nạp lưới mới
    nx, ny = tim(du, "nx"), tim(du, "ny")
    assert (nx, ny) == (6, 3) and dem_layer(d2, "SN-LUOI") == nx + 1 + ny + 1                   # không còn đường lưới cũ
    assert dem_layer(d2, "SN-LUOI-O", "MTEXT") == len(json.loads((lot_moi.process_dir / "grid.json").read_text(encoding="utf-8"))["o"])
    g = json.loads((lot_moi.process_dir / "grid.json").read_text(encoding="utf-8"))
    so_nut = sum(1 for n in g["nut"].values() if n["z_moc"] is not None and n["z_do"] is not None)
    # đúng 3 nhãn (mốc, đo, chênh) cho mỗi nút CÓ ĐỦ cao độ — nút ở x=110 m ngoài vùng đo thì không có nhãn;
    # bằng đúng số này nghĩa là nhãn cũ đã bị xóa sạch, không nhân đôi
    assert dem_layer(d2, "SN-LUOI-NHAN") == 3 * so_nut and n_nhan1 == 3 * 24
    assert dem_layer(d2, "SN-3DF-MOC") == dem_layer(d1, "SN-3DF-MOC")                          # mặt 3D không bị vẽ lại/đụng tới


@can_acore
def test_acad_hieuchinh_cap_nhat_nhan_tai_cho(lot_moi, tmp_path):
    base = lot_moi.input_dir / "gt.dxf"
    _, _, _, ve_all = chay_cn(tmp_path, lot_moi, "ve", lsp=True)
    d1, _ = _chay_acore(tmp_path, [ve_all], base=base)
    ra1 = tmp_path / "da_ve.dxf"
    d1.saveas(ra1)
    sua = tmp_path / "sua.csv"
    sua.write_text("ma,z,be_mat,ly_do\nD03-02,12.5,do,thử\n", encoding="utf-8")
    ok, tb, _, lsp = chay_cn(tmp_path, lot_moi, "hieuchinh-nhieu", "--tu-file", str(sua), lsp=True)
    assert ok, tb
    d2, _ = _chay_acore(tmp_path, [lsp], base=ra1)
    assert dem_layer(d2, "SN-LUOI-NHAN") == dem_layer(d1, "SN-LUOI-NHAN")                       # cập nhật tại chỗ
    z = {(BackendDXF.doc_nhan(e)["ma"], BackendDXF.doc_nhan(e)["be_mat"]): e.dxf.text
         for e in d2.modelspace() if e.dxf.layer == "SN-LUOI-NHAN"}
    assert z[("D03-02", "do")] == "12.500"
    # CAD → hệ thống: đọc ngược nhãn từ DXF vừa lưu bằng backend DXF cho ra đúng 12.5
    rd = BackendDXF(ra1.parent / "da_ve.dxf", tmp_path / "x.dxf")
    assert rd.cad_read_grid_z("GT-01", 1)                                                       # nhãn cũ vẫn đọc được
    d2.saveas(tmp_path / "sau.dxf")
    assert {(x["ma"], x["be_mat"]): x["z"] for x in BackendDXF(tmp_path / "sau.dxf", tmp_path / "y.dxf").cad_read_grid_z("GT-01", 1)
            }[("D03-02", "do")] == 12.5
