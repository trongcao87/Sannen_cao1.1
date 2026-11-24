"""Menu CAD "SAN NỀN" — AutoLISP + DCL.

Hai tầng kiểm chứng:
  (a) TĨNH, luôn chạy: cân bằng ngoặc/nháy/ngoặc nhọn, khoá ô DCL trùng với LISP, hàm gọi lại có định nghĩa.
  (b) ĐỘNG, cần AutoCAD 2022 (accoreconsole.exe, chạy không giao diện): nạp sannen.lsp, đọc cấu hình UTF-8,
      gọi cầu nối (một cầu nối GIẢ viết ngay trong test), xóa kết quả theo XDATA, xuất CSV cho lõi.
Hộp thoại DCL và menu thả xuống cần GIAO DIỆN — accoreconsole không có (load_dialog trả -1, không có đối tượng
AutoCAD COM) nên hai phần đó chỉ được kiểm bằng (a) và đọc code.
"""
from __future__ import annotations
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LISP_DIR = ROOT / "cad" / "lisp"
LSP = LISP_DIR / "sannen.lsp"
DCL = LISP_DIR / "sannen.dcl"
ACC = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Autodesk" / "AutoCAD 2022" / "accoreconsole.exe"
CAC_LENH_BAT_BUOC = [
    "SN_LOT", "SN_TRANGTHAI", "SN_NHAP", "SN_MAT", "SN_LO", "SN_LUOITINH", "SN_TINH", "SN_VE", "SN_XOA",
    "SN_TIN3D", "SN_XEM3D", "SN_LUOI", "SN_DOICOT", "SN_CHENCOT", "SN_XOACOT", "SN_DOIHANG", "SN_CHENHANG", "SN_XOAHANG",
    "SN_DICHLUOI", "SN_XOAYLUOI", "SN_CAPDO", "SN_NANGCD", "SN_SUADINH", "SN_MATCAT", "SN_BANG", "SN_EXCEL",
    "SN_CANHBAO", "SN_CONGO", "SN_DONGBO", "SN_DUYET", "SN_MENU", "SN"]
HOP_THOAI = ["sn_tin3d", "sn_luoi", "sn_capdo", "sn_matcat", "sn_bang", "sn_canhbao", "sn_duyet"]


# ======================================================================================== (a) TĨNH
def bo_chuoi_chu_thich(ma: str) -> str:
    """Bỏ chú thích `;` và nội dung chuỗi "…" (có \\" thoát) để đếm ngoặc; trả mã đã làm sạch, báo lỗi nháy lẻ."""
    ra, i, n = [], 0, len(ma)
    while i < n:
        c = ma[i]
        if c == ";":                                  # chú thích đến hết dòng (ngoài chuỗi)
            while i < n and ma[i] != "\n":
                i += 1
            continue
        if c == '"':
            i += 1
            while i < n and ma[i] != '"':
                i += 2 if ma[i] == "\\" else 1
            if i >= n:
                raise AssertionError("Chuỗi không đóng nháy")
            ra.append('""')
            i += 1
            continue
        ra.append(c)
        i += 1
    return "".join(ra)


def test_lsp_can_bang_ngoac_va_nhay():
    ma = bo_chuoi_chu_thich(LSP.read_text(encoding="utf-8"))
    sau = 0
    for dong, d in enumerate(ma.split("\n"), 1):
        sau += d.count("(") - d.count(")")
    assert sau == 0, f"Lệch ngoặc đơn: dư {sau} dấu mở"
    # từng hàm cấp cao nhất phải tự cân: mỗi `(defun` ở đầu dòng bắt đầu khi độ sâu = 0
    sau, lech = 0, []
    for dong, d in enumerate(ma.split("\n"), 1):
        if re.match(r"^\(defun\s", d) and sau != 0:
            lech.append(dong)
        sau += d.count("(") - d.count(")")
    assert not lech, f"Hàm bắt đầu khi ngoặc chưa cân (hàm trước thiếu/thừa ngoặc) tại dòng {lech[:5]}"


def test_lsp_khong_trung_ten_ham():
    ten = re.findall(r"^\(defun\s+([^\s(]+)", LSP.read_text(encoding="utf-8"), re.M)
    trung = sorted({t for t in ten if ten.count(t) > 1})
    assert not trung, f"Trùng (defun): {trung} — định nghĩa sau ghi đè định nghĩa trước mà không báo"


def test_lsp_co_du_lenh_bat_buoc():
    co = set(re.findall(r"^\(defun\s+c:(SN[A-Z0-9_]*)\s*\(\)", LSP.read_text(encoding="utf-8"), re.M))
    thieu = [c for c in CAC_LENH_BAT_BUOC if c not in co]
    assert not thieu, f"Thiếu lệnh: {thieu}"


def doc_hop_thoai() -> dict[str, dict]:
    """sannen.dcl → {tên hộp thoại: {'khoa': [...], 'loai': [...], 'thuoc_tinh': [...]}} (đếm cả ngoặc nhọn)."""
    ma = re.sub(r"//[^\n]*", "", DCL.read_text(encoding="utf-8"))
    ma = bo_chuoi_chu_thich(ma.replace(";", ","))  # DCL kết thúc thuộc tính bằng `;` — dùng dấu khác để khỏi bị coi là chú thích
    assert ma.count("{") == ma.count("}"), "Lệch ngoặc nhọn trong DCL"
    goc = re.sub(r"//[^\n]*", "", DCL.read_text(encoding="utf-8"))
    ra = {}
    for m in re.finditer(r"^(\w+)\s*:\s*dialog\s*\{", goc, re.M):
        i, sau = m.end(), 1
        while sau and i < len(goc):
            sau += {"{": 1, "}": -1}.get(goc[i], 0)
            i += 1
        khoi = goc[m.end():i - 1]
        ra[m.group(1)] = {"khoa": re.findall(r'\bkey\s*=\s*"([^"]+)"', khoi),
                          "loai": re.findall(r":\s*([a-z_]+)\s*\{", khoi),
                          "thuoc_tinh": re.findall(r"\b([a-z_]+)\s*=\s*", khoi)}
    return ra


def test_dcl_cac_hop_thoai_va_khoa_duy_nhat():
    ds = doc_hop_thoai()
    assert set(ds) == set(HOP_THOAI)
    cho_phep_loai = {"text", "boxed_column", "boxed_radio_column", "row", "column", "edit_box", "popup_list",
                     "list_box", "radio_button", "toggle", "button"}
    cho_phep_tt = {"key", "label", "value", "width", "height", "edit_width", "is_default", "is_cancel",
                   "multiple_select"}
    for ten, d in ds.items():
        trung = {k for k in d["khoa"] if d["khoa"].count(k) > 1}
        assert not trung, f"{ten}: key trùng {trung}"
        assert set(d["loai"]) <= cho_phep_loai, f"{ten}: loại tile lạ {set(d['loai']) - cho_phep_loai}"
        assert set(d["thuoc_tinh"]) <= cho_phep_tt, f"{ten}: thuộc tính lạ {set(d['thuoc_tinh']) - cho_phep_tt}"
        assert any(k == "b_dong" for k in d["khoa"]), f"{ten}: thiếu nút Đóng"
        assert d["thuoc_tinh"].count("is_cancel") == 1, f"{ten}: phải có đúng một nút is_cancel"


def test_dcl_nhan_khong_dau_de_chac_chan_hien_thi():
    """DCL không chắc đọc UTF-8 → toàn file phải ASCII; chữ có dấu do sannen.lsp đặt lại bằng set_tile."""
    ma = DCL.read_text(encoding="utf-8")
    kytu = sorted({c for c in ma if ord(c) > 127})
    assert not kytu, f"sannen.dcl còn ký tự ngoài ASCII: {kytu}"


def test_dcl_chu_hien_thi_deu_do_lisp_dat_co_dau():
    """Hộp thoại hiện CHỮ CÓ DẤU: DCL chỉ ASCII, mọi chữ hiển thị đến từ set_tile của sannen.lsp.
    - tile `text` phải được LISP đặt (key xuất hiện trong sannen.lsp) — không tile chữ nào bị bỏ trống;
    - toggle / edit_box / popup_list / boxed_column KHÔNG có nhãn riêng (set_tile không đổi được nhãn của chúng): label = "";
    - không còn radio_button (nhãn không đổi được) — nhóm lựa chọn là popup_list do LISP nạp danh sách có dấu;
    - dòng ghi chú dài là nhiều tile text xếp dọc (t_tt, t_tt2, t_tt3) để không bị cắt cụt."""
    dcl = re.sub(r"//[^\n]*", "", DCL.read_text(encoding="utf-8"))
    lsp = LSP.read_text(encoding="utf-8")
    assert "radio_button" not in dcl and "boxed_radio_column" not in dcl
    thieu = []
    for loai, than in re.findall(r":\s*(text|toggle|edit_box|popup_list|boxed_column|button)\s*\{([^{}]*)", dcl):
        khoa = re.search(r'key\s*=\s*"([^"]+)"', than)
        nhan = re.search(r'label\s*=\s*"([^"]*)"', than)
        if loai in ("toggle", "edit_box", "popup_list", "boxed_column"):
            assert nhan is not None and nhan.group(1) == "", f"{loai} {khoa and khoa.group(1)} còn nhãn ASCII trong DCL: {nhan and nhan.group(1)}"
        if loai in ("text", "button") and khoa and f'"{khoa.group(1)}"' not in lsp:
            thieu.append(khoa.group(1))
    assert not thieu, f"Tile chữ/nút không được sannen.lsp đặt chữ có dấu: {thieu}"
    for ten, d in doc_hop_thoai().items():
        if "t_tt" in d["khoa"]:
            assert "t_tt2" in d["khoa"], f"{ten}: ghi chú chỉ một dòng — dễ bị cắt cụt"
    # sn:tt phải trải ghi chú lên cả ba dòng
    assert "(sn:vn-dong '(\"t_tt\" \"t_tt2\" \"t_tt3\")" in lsp


def test_dcl_cu_phap_moi_thuoc_tinh_ket_thuc_bang_cham_phay():
    """Không có AutoCAD giao diện để load_dialog → kiểm cú pháp tối thiểu: mọi `thuộc_tính = giá_trị` kết thúc bằng `;`,
    mọi tile là `: loại { ... }`, chuỗi đóng nháy."""
    dcl = re.sub(r"//[^\n]*", "", DCL.read_text(encoding="utf-8"))
    for m in re.finditer(r'\b[a-z_]+\s*=\s*(?:"[^"\n]*"|[\w.]+)(?!\s*[;"\w.])', dcl):
        raise AssertionError(f"thiếu dấu ; sau «{m.group(0)}»")
    for m in re.finditer(r'\b([a-z_]+)\s*=\s*(?:"[^"\n]*"|[\w.]+)\s*(.)', dcl):
        assert m.group(2) == ";", f"thuộc tính {m.group(1)} không kết thúc bằng ;"
    assert dcl.count('"') % 2 == 0
    dich = re.findall(r"^(\w+)\s*:\s*dialog\s*\{", dcl, re.M)
    assert dich == HOP_THOAI


def test_dcl_moi_hop_thoai_co_tieu_de_day_du_dau_trong_tile():
    lsp = LSP.read_text(encoding="utf-8")
    for ten, d in doc_hop_thoai().items():
        assert "t_ten" in d["khoa"], f"{ten}: thiếu tile tiêu đề t_ten (thanh tiêu đề DCL chỉ ASCII)"
    assert lsp.count('("t_ten" . "') >= len(HOP_THOAI)


def test_khoa_o_trong_lisp_deu_co_trong_dcl():
    lsp = LSP.read_text(encoding="utf-8")
    dung = set(re.findall(r'"([ebtrplgn]_[a-z0-9_]+)"', lsp))
    co = {k for d in doc_hop_thoai().values() for k in d["khoa"]}
    thieu = sorted(dung - co)
    assert not thieu, f"LISP dùng key không có trong sannen.dcl: {thieu}"
    # và mỗi hộp thoại mà LISP mở phải có hàm khởi tạo được định nghĩa
    ham = set(re.findall(r"^\(defun\s+(\S+)", lsp, re.M))
    for ten, khoi in re.findall(r"\(sn:mo-dlg\s+\"(\w+)\"\s+'(\S+?)\)", lsp):
        assert ten in HOP_THOAI, f"mở hộp thoại không có trong DCL: {ten}"
        assert khoi in ham, f"hàm khởi tạo {khoi} của {ten} chưa định nghĩa"
    mo = {t for t, _ in re.findall(r"\(sn:mo-dlg\s+\"(\w+)\"\s+'(\S+?)\)", lsp)}
    assert mo == set(HOP_THOAI), f"Hộp thoại chưa được lệnh nào mở: {set(HOP_THOAI) - mo}"


def test_callback_cua_hop_thoai_deu_co_dinh_nghia():
    lsp = LSP.read_text(encoding="utf-8")
    ham = set(re.findall(r"^\(defun\s+(\S+)", lsp, re.M))
    for khoa, chuoi in re.findall(r'\(action_tile\s+"([a-z0-9_]+)"\s+"((?:[^"\\]|\\.)*)"\)', lsp):
        for f in re.findall(r"['(](sn:[A-Za-z0-9\-:>]+)", chuoi):
            assert f in ham, f"action_tile {khoa} gọi hàm chưa định nghĩa: {f}"
    # mọi nút của DCL (trừ Đóng/hủy) phải có action_tile tương ứng trong LISP
    co_action = set(re.findall(r'\(action_tile\s+"([a-z0-9_]+)"', lsp))
    for ten, d in doc_hop_thoai().items():
        nut = {k for k in d["khoa"] if k.startswith("b_")}
        assert nut <= co_action, f"{ten}: nút chưa gán hành động: {sorted(nut - co_action)}"


def test_doi_so_chu_va_so_am_dung_dang_khoa_bang_gia_tri():
    """argparse từ chối `--them "--preview"` và `--dx -5`: LISP phải truyền `--khoá=giá trị` cho chữ và số có thể âm."""
    lsp = LSP.read_text(encoding="utf-8")
    cu = re.findall(r'--(?:ly-do|ten|nguoi|bang-chung|cot|hang|them|dx|dy|goc)\s"\s*\(', lsp)
    assert not cu, f"Còn đối số dạng `--khoá \"…\"`: {cu}"
    assert '--them=" (sn:q "--preview")' in lsp


def test_muc_menu_tro_toi_lenh_co_dinh_nghia():
    lsp = LSP.read_text(encoding="utf-8")
    macro = set(re.findall(r'\("[^"]+"\s+"(SN_[A-Z0-9]+)"\)', lsp))
    co = set(re.findall(r"^\(defun\s+c:(SN[A-Z0-9_]*)\s*\(\)", lsp, re.M))
    assert macro and macro <= co, f"Mục menu trỏ tới lệnh chưa có: {sorted(macro - co)}"
    # mọi lệnh của menu phải xuất hiện trong menu (không có lệnh mồ côi)
    mo_coi = {c for c in CAC_LENH_BAT_BUOC} - macro - {"SN", "SN_MENU", "SN_NHAP"}
    assert not (mo_coi - {"SN_LUOITINH"}), f"Lệnh không có trong menu thả xuống: {sorted(mo_coi)}"


# ======================================================================================== (b) ĐỘNG
def _giai_ma(b: bytes) -> str:
    if b"\x00" in b[:400]:
        return b.decode("utf-16-le", errors="replace")
    return b.decode("utf-8", errors="replace")


def chay_acc(tmp: Path, lisp: str, env: dict | None = None, timeout: int = 180) -> tuple[str, dict]:
    """Chạy `lisp` (UTF-8) trong accoreconsole trên bản vẽ trống. Trả (toàn bộ output, {tên: giá trị} của dòng @@tên=giá trị)."""
    f = tmp / "t.lsp"
    f.write_text(lisp, encoding="utf-8")
    scr = tmp / "t.scr"
    scr.write_text(f'(load "{f.as_posix()}")\n_.QUIT\nY\n', encoding="ascii")
    e = {**os.environ, **(env or {})}
    p = subprocess.run([str(ACC), "/s", str(scr), "/l", "en-US"], capture_output=True, env=e, timeout=timeout)
    txt = _giai_ma(p.stdout)
    # `princ` trả lại chuỗi nên console in LẶP một lần nữa → lấy lần xuất hiện ĐẦU TIÊN của mỗi marker
    kq: dict = {}
    for k, v in re.findall(r"@@([\w:\-]+)=([\w\-]+)", txt):
        kq.setdefault(k, v)
    return txt, kq


def lisp_chuoi(duong: Path | str) -> str:
    """Đường dẫn Windows → literal chuỗi LISP (gấp đôi dấu `\\`)."""
    return str(duong).replace("\\", "\\\\")


def mo_dau(**them) -> str:
    return ('(defun t! (n ok) (princ (strcat "\\n@@" n "=" (if ok "OK" "FAIL"))) (princ))\n'
            f'(load "{LSP.as_posix()}")\n')


@pytest.fixture(scope="module")
def can_acad():
    if not ACC.exists():
        pytest.skip("Không có AutoCAD 2022 (accoreconsole.exe) — bỏ qua tầng động")


def moi_truong(tmp: Path, cfg: dict | None = None, **them) -> dict:
    env = {"SANNEN_CFG": str(tmp / "sannen.cfg"), "SANNEN_TMP": str(tmp)}
    if cfg is not None:
        (tmp / "sannen.cfg").write_text("".join(f"{k}={v}\n" for k, v in cfg.items()), encoding="utf-8")
    env.update(them)
    return env


def kiem_tra_tat_ca_ok(kq: dict, ten: list[str]):
    sai = [t for t in ten if kq.get(t) != "OK"]
    assert not sai, f"Không đạt: {sai} (nhận được: { {t: kq.get(t) for t in ten} })"


def test_nap_khong_loi_va_du_lenh(can_acad, tmp_path):
    ds = " ".join(f"c:{c}" for c in CAC_LENH_BAT_BUOC)
    ma = mo_dau() + f'(foreach s (quote ({ds})) (princ (strcat "\\n@@" (vl-symbol-name s) "=" (if (boundp s) "OK" "KHONG"))))\n(t! "nap" T)\n'
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    assert kq.get("nap") == "OK", txt[-1500:]
    thieu = [c for c in CAC_LENH_BAT_BUOC if kq.get(f"C:{c}") != "OK"]
    assert not thieu, f"Lệnh chưa được định nghĩa sau khi nạp: {thieu}"
    assert "error" not in txt.lower().replace("*error*", ""), txt[-1500:]


def test_tien_ich_chuoi_so_toan(can_acad, tmp_path):
    ma = mo_dau() + r'''
(t! "g1" (= (sn:g 20.0) "20"))
(t! "g2" (= (sn:g 12.5) "12.5"))
(t! "g3" (= (sn:g 0.1234567) "0.123457"))
(t! "g4" (= (sn:g -3.0) "-3"))
(t! "so1" (equal (sn:so " 12.5 ") 12.5 1e-9))
(t! "so2" (null (sn:so "abc")))
(t! "so3" (null (sn:so "")))
(t! "en" (= (sn:en '(445012.3456789 1113045.1)) "445012.3457,1113045.1000"))
(t! "thay" (= (sn:thay "a,b,c" "," ";") "a;b;c"))
(t! "thay2" (= (sn:thay "aaa" "a" "aa") "aaaaaa"))
(t! "thay3" (= (sn:thay "xyz" "q" "!") "xyz"))
(t! "chia" (equal (sn:chia "a|b||c" "|") '("a" "b" "" "c")))
(t! "chia2" (equal (sn:chia "abc" "|") '("abc")))
(t! "q" (= (sn:q "x\"y\\") "\"x'y\""))
(t! "viet" (= (sn:cat-dong "Đào\nđắp\r") "Đào đắp "))
(t! "so-o1" (= (sn:so-o 100.0 20.0) 5))
(t! "so-o2" (= (sn:so-o 101.0 20.0) 6))
(t! "so-o3" (= (sn:so-o 0.5 20.0) 1))
(t! "so-o4" (= (sn:so-o 100.0000000001 20.0) 5))
(t! "mau" (= (sn:mau-kt 5 20.0) "5x20"))
(t! "mau2" (= (sn:mau-kt 3 12.5) "3x12.5"))
(t! "ij" (equal (sn:ma-o->ij "O03-02") '(3 2)))
(t! "ij2" (equal (sn:ma-o->ij "O12-105") '(12 105)))
(t! "ij3" (null (sn:ma-o->ij "xyz")))
(t! "dat1" (equal (sn:dat "a" 2 '(("a" . 1) ("b" . 3))) '(("a" . 2) ("b" . 3))))
(t! "dat2" (equal (sn:dat "c" 9 '(("a" . 1))) '(("a" . 1) ("c" . 9))))
(t! "vs1" (= (sn:vs nil) "không"))
(t! "vs2" (= (sn:vs 2.5) "2.5"))
(t! "vs3" (= (sn:vs 7) "7"))
(t! "vs4" (= (sn:vs T) "có"))
;; hộp bao của một đa tuyến → số cột/hàng cần (như SNVN: chọn vùng)
(entmake (list '(0 . "LWPOLYLINE") '(100 . "AcDbEntity") '(8 . "0") '(100 . "AcDbPolyline") '(90 . 4) '(70 . 1)
               '(10 10.0 20.0) '(10 110.0 20.0) '(10 110.0 70.0) '(10 10.0 70.0)))
(setq bb (vl-catch-all-apply 'sn:bbox (list (entlast))))
(t! "bbox-ok" (not (vl-catch-all-error-p bb)))
(if (not (vl-catch-all-error-p bb))
  (progn
    (t! "bbox1" (and (equal (car (car bb)) 10.0 1e-6) (equal (cadr (car bb)) 20.0 1e-6)))
    (t! "bbox2" (and (equal (car (cadr bb)) 110.0 1e-6) (equal (cadr (cadr bb)) 70.0 1e-6)))
    (t! "bbox3" (and (= (sn:so-o (- (car (cadr bb)) (car (car bb))) 20.0) 5)
                     (= (sn:so-o (- (cadr (cadr bb)) (cadr (car bb))) 20.0) 3)))))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    ten = [m for m in re.findall(r'\(t! "([^"]+)"', ma)]
    kiem_tra_tat_ca_ok(kq, ten)


def test_cau_hinh_utf8_doc_ghi_khong_bom(can_acad, tmp_path):
    lot = tmp_path / "Dự án KĐT" / "Lô 01"
    lot.mkdir(parents=True)
    (lot / "lot.yaml").write_text("# chú thích\nma_lo: 01-CGP  # mã lô\ndot: 2\nbe_mat_moc:\n  dot: 99\n", encoding="utf-8")
    cfg = {"python": r"C:\Python 3\python.exe", "cad": r"C:\Kho CAD", "lot": str(lot)}
    env = moi_truong(tmp_path, cfg)
    ma = mo_dau() + r'''
(t! "lot" (= (sn:cfg "lot") "''' + lisp_chuoi(lot) + r'''"))
(t! "py" (= (sn:cfg "python") "C:\\Python 3\\python.exe"))
(t! "khong-co" (null (sn:cfg "khong_co")))
(t! "malo" (= (sn:ma-lo) "01-CGP"))
(t! "dot" (= (sn:dot) 2))
(sn:ghi-cfg "lot" "D:\\Lô mới\\Đào đắp")
(sn:ghi-cfg "lisp" "E:\\x")
(setq *sn-cfg* nil)
(t! "ghi1" (= (sn:cfg "lot") "D:\\Lô mới\\Đào đắp"))
(t! "ghi2" (= (sn:cfg "python") "C:\\Python 3\\python.exe"))
(t! "ghi3" (= (sn:cfg "lisp") "E:\\x"))
'''
    txt, kq = chay_acc(tmp_path, ma, env)
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))
    byte = (tmp_path / "sannen.cfg").read_bytes()
    assert not byte.startswith(b"\xef\xbb\xbf"), "sannen.cfg không được có BOM"
    dong = byte.decode("utf-8").splitlines()
    assert "lot=D:\\Lô mới\\Đào đắp" in dong and "lisp=E:\\x" in dong and len(dong) == 4


def tao_cau_noi_gia(tmp: Path) -> Path:
    """Gói sannen_cad GIẢ: ghi s-expression cố định (có chữ Việt, nháy, backslash) vào --ra."""
    g = tmp / "cad_gia" / "sannen_cad"
    g.mkdir(parents=True)
    (g / "__init__.py").write_text("", encoding="utf-8")
    (g / "cau_noi.py").write_text('''
import sys
a = sys.argv[1:]
lenh = a[0]
def lay(k):
    return a[a.index(k) + 1] if k in a else None
ra, lsp = lay("--ra"), lay("--lsp")
if lenh == "echo":
    s = '(("ok" . T) ("thong_bao" . "Xin chào \\\\"bạn\\\\" \\\\\\\\ ok") ("du_lieu" . (("args" . "%s") ("n" . 3) ("x" . 2.5) ("ds" 1 2 3))))' % "|".join(a).replace("\\\\", "\\\\\\\\").replace('"', '\\\\"')
    open(ra, "w", encoding="utf-8").write(s)
    if lsp:
        open(lsp, "w", encoding="utf-8").write('(setq *gia-da-ve* 42) (princ)')
elif lenh == "loi":
    open(ra, "w", encoding="utf-8").write('(("ok") ("thong_bao" . "Không có lưới — chạy luoi trước"))')
elif lenh == "hong":
    open(ra, "w", encoding="utf-8").write('(("ok" . T) ("thong_bao" . ')
elif lenh == "sap":
    raise RuntimeError("cầu nối gãy giữa chừng")
elif lenh == "trang-thai":
    # đúng hình dạng cầu nối thật: alist lồng là ("khoá" cặp cặp …), không phải ("khoá" . alist)
    open(ra, "w", encoding="utf-8").write('(("ok" . T) ("thong_bao" . "") ("du_lieu" ("buoc_ke_tiep" . "mat") ("cong" ("1" ("da_duyet" . T)) ("2" ("da_duyet"))) ("so_nop" ("dao_m3" . 12.5) ("dap_m3" . 7.0))))')
''', encoding="utf-8")
    return tmp / "cad_gia"


def test_sn_chay_goi_cau_noi_gia_du_chu_viet_nhay_backslash(can_acad, tmp_path):
    lot = tmp_path / "Lô thử nghiệm đào đắp"
    lot.mkdir()
    (lot / "lot.yaml").write_text("ma_lo: X\n", encoding="utf-8")
    cad = tao_cau_noi_gia(tmp_path)
    env = moi_truong(tmp_path, {"python": sys.executable, "cad": str(cad), "lot": str(lot)})
    ma = mo_dau() + r'''
(setq kq (sn:chay "echo" "--x 1 --ten \"Lô A\"" T))
(t! "ok" (sn:get "ok" kq))
(t! "thong-bao" (= (sn:get "thong_bao" kq) "Xin chào \"bạn\" \\ ok"))
(setq d (sn:get "du_lieu" kq))
(t! "so" (= (sn:get "n" d) 3))
(t! "thuc" (equal (sn:get "x" d) 2.5 1e-9))
(t! "ds" (equal (sn:get "ds" d) '(1 2 3)))
(setq args (sn:get "args" d))
(t! "lot" (vl-string-search (strcat "--lot|''' + lisp_chuoi(lot) + r'''|") args))
(t! "tham-so" (vl-string-search "--x|1|--ten|Lô A|" args))
(t! "co-lsp" (and (sn:get "_lsp" kq) (vl-string-search "--lsp|" args)))
(t! "nap-lsp" (and (sn:ap-lsp kq) (= *gia-da-ve* 42)))
;; không yêu cầu lsp thì không có "_lsp" và không có --lsp
(setq kq2 (sn:chay "echo" "" nil))
(t! "khong-lsp" (and (sn:get "ok" kq2) (null (sn:get "_lsp" kq2)) (null (vl-string-search "--lsp|" (sn:get "args" (sn:get "du_lieu" kq2))))))
;; cầu nối báo lỗi / hỏng / gãy
(setq kq3 (sn:chay "loi" "" nil))
(t! "loi" (and (null (sn:get "ok" kq3)) (= (sn:get "thong_bao" kq3) "Không có lưới — chạy luoi trước")))
(setq kq4 (sn:chay "hong" "" nil))
(t! "hong" (and (null (sn:get "ok" kq4)) (vl-string-search "không trả kết quả" (sn:get "thong_bao" kq4))))
(setq kq5 (sn:chay "sap" "" nil))
(t! "sap" (and (null (sn:get "ok" kq5)) (vl-string-search "Nhật ký" (sn:get "thong_bao" kq5)) (vl-string-search "RuntimeError" (sn:get "thong_bao" kq5))))
;; chưa cấu hình → báo, không chạy
(setq *sn-cfg* (list (cons "python" "x")))
(setq kq6 (sn:chay "echo" "" nil))
(t! "chua-cau-hinh" (and (null (sn:get "ok" kq6)) (vl-string-search "Chưa cấu hình" (sn:get "thong_bao" kq6))))
'''
    txt, kq = chay_acc(tmp_path, ma, env)
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))


def test_lenh_trang_thai_in_ra_dong_lenh(can_acad, tmp_path):
    lot = tmp_path / "lo"
    lot.mkdir()
    (lot / "lot.yaml").write_text("ma_lo: X\n", encoding="utf-8")
    cad = tao_cau_noi_gia(tmp_path)
    env = moi_truong(tmp_path, {"python": sys.executable, "cad": str(cad), "lot": str(lot)})
    ma = mo_dau() + '(c:SN_TRANGTHAI)\n(princ "\\n@@xong=OK")\n'
    txt, kq = chay_acc(tmp_path, ma, env)
    assert kq.get("xong") == "OK"
    assert "buoc_ke_tiep: mat" in txt and "dao_m3: 12.5" in txt and "dap_m3: 7" in txt


def test_xoa_ket_qua_theo_xdata_dung_lo_dot_loai(can_acad, tmp_path):
    ma = mo_dau() + r'''
(sn:lop "SN-LUOI-NHAN" 3)
(defun mk (pt chu lo dot loai kv)
  (entmake (list '(0 . "TEXT") '(8 . "SN-LUOI-NHAN") (cons 10 pt) '(40 . 0.5) (cons 1 chu)
                 (list -3 (cons "SANNEN" (mapcar '(lambda (s) (cons 1000 s)) (append (list lo dot "h" loai) kv)))))))
(mk '(0.0 0.0 0.0) "2.500" "L1" "1" "nhan_dinh" '("ma=D01-01" "be_mat=do"))
(mk '(0.0 1.0 0.0) "1.250" "L1" "1" "nhan_dinh" '("ma=D01-01" "be_mat=moc"))
(mk '(0.0 2.0 0.0) "+1.250" "L1" "1" "nhan_dinh" '("ma=D01-01" "be_mat=dz"))
(mk '(5.0 0.0 0.0) "3.100" "L2" "1" "nhan_dinh" '("ma=D09-09" "be_mat=do"))
(mk '(6.0 0.0 0.0) "9.900" "L1" "3" "nhan_dinh" '("ma=D01-01" "be_mat=do"))
(entmake (list '(0 . "LINE") '(8 . "0") '(10 0.0 0.0 0.0) '(11 1.0 1.0 0.0)))          ; đối tượng của người, không dấu
(entmake (list '(0 . "LINE") '(8 . "SN-LUOI") '(10 0.0 0.0 0.0) '(11 1.0 0.0 0.0)))     ; layer SN nhưng không XDATA
(setq dem (lambda () (sslength (ssget "X" '((0 . "TEXT"))))))
(setq ds (sn:nhan-dinh-ds "L1" nil))
(t! "ds-gom-moc-do-khong-dz-khong-lo-khac" (= (length ds) 3))        ; L1: do + moc (đợt 1) + do (đợt 3); bỏ dz; bỏ L2
(t! "ds-ma" (= (car (car ds)) "D01-01"))
(t! "ds-z" (equal (caddr (car ds)) 2.5 1e-9))
(sn:csv-nhan "''' + lisp_chuoi(tmp_path / "n.csv") + r'''" ds)
(sn:csv-hieuchinh "''' + lisp_chuoi(tmp_path / "h.csv") + r'''" ds "do" '(lambda (z) (+ z 0.5)) "Nâng, thiết kế \"A\"")
(t! "xoa-dot3-loai-sai" (= (sn:xoa-ket-qua "L1" 3 '("luoi")) 0))                  ; sai loại → không xóa gì
(t! "xoa-dot3" (= (sn:xoa-ket-qua "L1" 3 '("nhan_dinh")) 1))
(t! "xoa-L1-con-lai" (= (sn:xoa-ket-qua "L1" nil nil) 3))                          ; 3 nhãn L1 đợt 1 (kể cả dz)
(t! "L2-con-nguyen" (= (sslength (ssget "X" '((-3 ("SANNEN"))))) 1))
(t! "doi-tuong-cua-nguoi-con" (= (sslength (ssget "X" '((0 . "LINE")))) 2))
(setq e (entlast))
;; cộng ô: MTEXT mang XDATA loai cong_o
(sn:mtext '(1.0 1.0) "O03-02 + O03-03\\PĐào 12.5\\PĐắp 3.0" 0.8 "SN-LUOI-O" '("L2" "1" "cong-o" "cong_o"))
(t! "mtext" (= (sslength (ssget "X" '((0 . "MTEXT") (-3 ("SANNEN"))))) 1))
(t! "xoa-cong-o" (= (sn:xoa-ket-qua "L2" nil '("cong_o")) 1))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))
    # CSV cho lõi: UTF-8 không BOM, đọc được bằng csv chuẩn
    nb = (tmp_path / "n.csv").read_bytes()
    assert not nb.startswith(b"\xef\xbb\xbf")
    hang = list(csv.DictReader((tmp_path / "n.csv").read_text(encoding="utf-8").splitlines()))
    assert {(r["ma"], r["be_mat"]) for r in hang} == {("D01-01", "do"), ("D01-01", "moc")} | {("D01-01", "do")}
    assert sorted(float(r["z"]) for r in hang) == [1.25, 2.5, 9.9]
    hb = (tmp_path / "h.csv").read_bytes()
    assert not hb.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(hb.decode("utf-8").splitlines()))
    assert [r["be_mat"] for r in rows] == ["do", "do"] and [float(r["z"]) for r in rows] == [3.0, 10.4]
    assert rows[0]["ly_do"] == "Nâng; thiết kế 'A'"                       # dấu phẩy và nháy kép trong lý do bị thay → CSV không vỡ


def test_thu_load_dialog_trong_accoreconsole(can_acad, tmp_path):
    """accoreconsole không có giao diện: nếu load_dialog hỗ trợ thì mọi hộp thoại phải mở được; không thì ghi nhận và bỏ qua."""
    ma = (mo_dau() + f'(setq id (load_dialog "{DCL.as_posix()}"))\n(princ (strcat "\\n@@id=" (itoa id)))\n'
          + "".join(f'(princ (strcat "\\n@@{h}=" (if (vl-catch-all-apply (quote new_dialog) (list "{h}" id)) "OK" "KHONG")))\n'
                    for h in HOP_THOAI))
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    if int(kq.get("id", "-1")) < 1:
        pytest.skip("accoreconsole không hỗ trợ hộp thoại (load_dialog = %s) — chỉ kiểm tĩnh được DCL" % kq.get("id"))
    assert all(kq.get(h) == "OK" for h in HOP_THOAI), kq


# ======================================================================================== (c) CẦU NỐI THẬT
CAU_NOI_THAT = ROOT / "cad" / "sannen_cad" / "cau_noi.py"


@pytest.mark.skipif(not CAU_NOI_THAT.exists(), reason="Chưa có cad/sannen_cad/cau_noi.py (tác tử cầu nối chưa xong)")
def test_cau_noi_that_trang_thai_luoi_doc_va_nap_file_ve(can_acad, tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lot_giai_tich import E0, N0, chay_het, hcn, tao
    lot = tao(tmp_path / "lot", [hcn(0, 0, 100, 60)], lambda e, n: 10.0,
              lambda e, n: 10.0 + 0.02 * (e - E0 - 50), so_diem=900)
    chay_het(lot)
    env = moi_truong(tmp_path, {"python": sys.executable, "cad": str(ROOT / "cad"), "lot": str(lot.root),
                                "lisp": str(LISP_DIR)})
    ma = mo_dau() + r'''
(setq kq (sn:chay "trang-thai" "" nil))
(t! "tt-ok" (sn:get "ok" kq))
(setq kl (sn:chay "luoi-doc" "" nil))
(t! "ld-ok" (sn:get "ok" kl))
(setq d (sn:get "du_lieu" kl))
(t! "ld-nx" (and (numberp (sn:get "nx" d)) (> (sn:get "nx" d) 0)))
(t! "ld-cot" (eq (type (sn:get "cot" d)) 'STR))
(t! "ld-dt" (equal (sn:get "dt_o" d) (sn:get "dt_lo" d) 1e-6))
(setq kv (sn:chay "ve" "" T))
(t! "ve-ok" (sn:get "ok" kv))
(t! "ve-lsp" (and (sn:get "_lsp" kv) (sn:ap-lsp kv)))
(t! "ve-co-doi-tuong" (> (sslength (ssget "X" '((-3 ("SANNEN"))))) 20))
(setq ds (sn:nhan-dinh-ds (sn:ma-lo) nil))
(t! "ve-co-nhan-dinh" (> (length ds) 4))
(t! "xoa" (> (sn:xoa-ket-qua (sn:ma-lo) nil nil) 20))
(t! "sach" (null (ssget "X" '((-3 ("SANNEN"))))))
;; chữ Việt, giá trị bắt đầu bằng `--`, số ÂM đi từ LISP sang lõi thật
(setq kc (sn:chay "chay" (strcat "--verb tinh --them=" (sn:q "--preview")) nil))
(t! "chay-preview" (and (sn:get "ok" kc) (sn:chay-duoc-p kc) (vl-string-search "XEM TRƯỚC" (sn:get "van_ban" (sn:get "du_lieu" kc)))))
(setq kd (sn:chay "duyet" (strcat "--cong 1 --nguoi=" (sn:q "Nguyễn Văn Ánh") " --bang-chung=" (sn:q "Đồng ý, dữ liệu dùng được")) nil))
(t! "duyet" (sn:get "ok" kd))
(setq km (sn:chay "luoi-sua" (strcat "--lenh di_chuyen --dx=-5.5 --dy=2 --ly-do=" (sn:q "Dời lưới sang trái 5,5 m")) T))
;; dời lưới −5,5 m làm lưới không phủ hết lô → lõi phải TỪ CHỐI (ok=nil) và nói rõ lý do bằng tiếng Việt
(t! "dich-luoi-tu-choi" (and (null (sn:get "ok" km)) (vl-string-search "Lưới không dùng được" (sn:get "thong_bao" km))))
(t! "dich-luoi-khong-ve" (null (sn:get "_lsp" km)))
'''
    txt, kq = chay_acc(tmp_path, ma, env, timeout=300)
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))
    dec = (lot.log_dir / "decisions.md").read_text(encoding="utf-8")
    assert "Nguyễn Văn Ánh" in dec and "Đồng ý, dữ liệu dùng được" in dec     # chữ Việt tới được lõi nguyên vẹn
    assert "Dời lưới sang trái 5,5 m" not in dec                                # lệnh bị từ chối thì không ghi nhật ký quyết định
    tc_file = lot.root / "luoi_tuy_chinh.yaml"
    assert not tc_file.exists() or "goc_luoi" not in tc_file.read_text(encoding="utf-8")   # và không để lại lưới hỏng
