"""Palette .NET "SAN NỀN" (giai đoạn 16): bảng dọc dock được, nhiều tab — cad/dotnet/SanNenPalette.

  (a) TĨNH: file nguồn đủ; lệnh [CommandMethod]; sáu tab; mọi lệnh LISP mà nút gọi đều có trong sannen.lsp; ánh xạ nhóm→layer của
      C# khớp bảng LISP (*sn-ql-nhom*) và backend.LAYER_KET_QUA; script xây có BOM; cấu trúc lớp (Services/Models/Drawing/Ui);
      C# không đọc 10_process/ và không có phép tính nghiệp vụ.
  (b) BIÊN DỊCH: csc.exe (.NET Framework, C# 5) + DLL AutoCAD 2022 → 0 lỗi (bỏ qua có lý do nếu thiếu csc/AutoCAD).
  (c) HỢP ĐỒNG JSON: `thong-tin --json` parse được, có đủ khoá C# dùng, không đổi hành vi s-expression cũ, chỉ ĐỌC.
Hiển thị palette chỉ kiểm được trên AutoCAD có giao diện (cad/MENU.md: checklist).
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(ROOT / "cad"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sannen import matcat, thong_tin                                        # noqa: E402
from sannen_cad import cau_noi as CN                                        # noqa: E402
from sannen_cad.backend import LAYER_KET_QUA                                # noqa: E402
from lot_giai_tich import E0, chay_het, hcn, tao                            # noqa: E402

DOTNET = ROOT / "cad" / "dotnet"
NGUON = DOTNET / "SanNenPalette"
LSP_TXT = (ROOT / "cad" / "lisp" / "sannen.lsp").read_text(encoding="utf-8")
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
ACAD = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Autodesk" / "AutoCAD 2022"

TAB = ("QL ĐH", "Biên lô", "Lưới", "Mặt cắt", "Khối lượng", "Cảnh báo")
FILE_NGUON = ("LenhPalette.cs", "Models/BangNhom.cs", "Models/Json.cs", "Models/DuLieuPal.cs", "Services/PythonBridge.cs",
              "Services/CadLop.cs", "Services/CadLenh.cs", "Services/DieuPhoi.cs", "Drawing/DrawEngine.cs", "Ui/Mau.cs",
              "Ui/TabCoSo.cs", "Ui/QlDhTab.cs", "Ui/BienLoTab.cs", "Ui/LuoiTab.cs", "Ui/MatCatTab.cs", "Ui/KhoiLuongTab.cs",
              "Ui/CanhBaoTab.cs")


def cs(ten: str) -> str:
    return (NGUON / ten).read_text(encoding="utf-8-sig")


def tat_ca_cs() -> str:
    """Toàn bộ mã C# bỏ chú thích `//` (chú thích được phép nhắc tên file để giải thích)."""
    return re.sub(r"//[^\n]*", "", "\n".join(cs(f) for f in FILE_NGUON))


# ======================================================================================== (a) TĨNH
def test_file_nguon_va_script_xay():
    for f in FILE_NGUON:
        assert (NGUON / f).is_file(), f
    ps1 = DOTNET / "xay_palette.ps1"
    assert ps1.read_bytes()[:3] == b"\xef\xbb\xbf", "xay_palette.ps1 phải có BOM UTF-8 (Windows PowerShell 5.1 lỗi dấu tiếng Việt nếu thiếu)"
    t = ps1.read_text(encoding="utf-8-sig")
    assert "SanNenPalette.dll" in t and "acmgd.dll" in t and "accoremgd.dll" in t and "acdbmgd.dll" in t and "csc.exe" in t
    for f in FILE_NGUON:                                                     # csc đọc UTF-8: file có BOM cho chắc chữ có dấu
        assert (NGUON / f).read_bytes()[:3] == b"\xef\xbb\xbf", f"{f} thiếu BOM UTF-8"
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "cad/dotnet/bin/" in gi


def test_lenh_commandmethod_va_tab():
    t = cs("LenhPalette.cs")
    lenh = set(re.findall(r'CommandMethod\((?:"[A-Z_]+",\s*)?"(SN_[A-Z_]+)"', t))
    assert lenh == {"SN_PALETTE", "SN_PALETTE_MO", "SN_PALETTE_DONG"}
    assert "5A7E6D2C-3B1F-4E8A-9C44-7D1B0E52A6F3" in t and 'PaletteSet("SAN NỀN"' in t           # tên + GUID cố định
    assert "DockSides.Left" in t and "DockSides.Right" in t and "ShowAutoHideButton" in t
    assert "Size(340, 700)" in t
    ten_tab = []
    for f in ("QlDhTab", "BienLoTab", "LuoiTab", "MatCatTab", "KhoiLuongTab", "CanhBaoTab"):
        m = re.search(r'TenTab \{ get \{ return "([^"]+)"', cs(f"Ui/{f}.cs"))
        assert m, f
        ten_tab.append(m.group(1))
    assert tuple(ten_tab) == TAB


def test_lenh_lisp_ma_nut_goi_deu_ton_tai():
    goi = set()
    for f in FILE_NGUON:
        if f.startswith("Ui/") or f.startswith("Services/CadLenh"):
            goi |= set(re.findall(r'"(SN_[A-Z0-9_]+) ', cs(f)))
            goi |= set(re.findall(r'\) (SN_[A-Z0-9_]+) "', cs(f)))
    for ten in ("SN_LUOI", "SN_MATCAT", "SN_TINH", "SN_BANG", "SN_EXCEL", "SN_XEM3D", "SN_DUYET", "SN_CANHBAO", "SN_DICHLUOI",
                "SN_XOAYLUOI", "SN_VE", "SN_NHAP", "SN_LO", "SN_LUOIAPDUNG", "SN_XOAMATCAT"):
        assert ten in goi, f"palette không gọi {ten}?"
    co = set(re.findall(r"^\(defun\s+c:(SN[A-Z0-9_]*)\s*\(\)", LSP_TXT, re.M))
    assert goi <= co, f"lệnh palette gọi mà LISP chưa định nghĩa: {sorted(goi - co)}"
    # lệnh LISP mới: nạp DLL rồi gọi lệnh .NET tên khác (không đệ quy), có trong menu thả xuống và menu dòng lệnh SN
    assert "(defun c:SN_PALETTE ()" in LSP_TXT and '"_.NETLOAD"' in LSP_TXT and '"_.SN_PALETTE_MO"' in LSP_TXT
    assert "\\\\dotnet\\\\bin\\\\SanNenPalette.dll" in LSP_TXT and "xay_palette.ps1" in LSP_TXT and "TRUSTEDPATHS" in LSP_TXT
    menu = LSP_TXT.split("(setq *sn-menu*")[1].split("(defun sn:dung-menu")[0]
    dong = [d for d in menu.split("\n") if d.strip()]
    assert '"SN_QL"' in dong[0] and '"SN_PALETTE"' in dong[1], "SN_PALETTE phải nằm ngay dưới SN_QL"
    assert '(= k "Palette") (c:SN_PALETTE)' in LSP_TXT
    # lệnh ghi có xác nhận (RULES 4)
    ap = LSP_TXT.split("(defun sn:l-luoi-ap-dung")[1].split("(defun c:SN_LUOIAPDUNG")[0]
    assert "sn:xac-nhan" in ap and "sn:chay-ve" in ap
    xoa = LSP_TXT.split("(defun sn:l-xoamatcat")[1].split("(defun c:SN_XOAMATCAT")[0]
    assert "sn:xac-nhan" in xoa and '"mat_cat"' in xoa


def test_anh_xa_nhom_layer_csharp_khop_lisp_va_python():
    cs_bang = cs("Models/BangNhom.cs")
    re_cs = r'new NhomDef\("(\w+)",\s*"([^"]+)",\s*(null|"[\w\-]+"),\s*(null|"[^"]+"),\s*(true|false)\)'
    chinh = [m for m in re.findall(re_cs, cs_bang.split("public static readonly NhomDef[] Tat")[1].split("};")[0])]
    khoi = LSP_TXT.split("(setq *sn-ql-nhom*")[1].split("(setq *sn-ql-ve*")[0]
    lsp = re.findall(r'\(\s*"(\w+)"\s+"([^"]+)"\s+(nil|"[\w\-]+")\s+(nil|"[^"]+")\s+(T|nil)\s*\)', khoi)
    assert len(chinh) == len(lsp) == 11
    for c, l in zip(chinh, lsp):
        assert c[0] == l[0] and c[1] == l[1], (c, l)
        assert c[2].replace("null", "nil") == l[2] and c[3].replace("null", "nil") == l[3], (c, l)
        assert (c[4] == "true") == (l[4] == "T"), (c, l)
    # các layer kết quả của backend đều thuộc một nhóm của C#
    goc = {c[3].strip('"') for c in chinh if c[3] != "null"}
    assert set(LAYER_KET_QUA) <= goc
    # nhóm nguồn tách nhỏ: hợp các mẫu = mẫu của nhóm "nguon"
    con = re.findall(r'new NhomDef\("nguon_\w+",\s*"[^"]+",\s*"mau",\s*"([^"]+)",\s*false\)', cs_bang)
    mau_nguon = next(c[3].strip('"') for c in chinh if c[0] == "nguon")
    assert sorted(con) == sorted(mau_nguon.split(","))
    # quy tắc tên layer đợt n ≥ 2: gốc-Dnn (như backend.ten_layer)
    assert 'goc + "-D" + dot.ToString("00")' in cs_bang


def test_cau_truc_lop_va_nguyen_tac_mong():
    tong = tat_ca_cs()
    assert "namespace SanNen.Palette.Models" in cs("Models/BangNhom.cs") and "namespace SanNen.Palette.Drawing" in cs("Drawing/DrawEngine.cs")
    # lớp THUẦN (Models) không dùng API AutoCAD
    for f in ("Models/BangNhom.cs", "Models/Json.cs", "Models/DuLieuPal.cs"):
        assert "Autodesk" not in cs(f), f
    # C# không đọc 10_process / 20_output của lô và không tự tính khối lượng
    assert "10_process" not in tong and "20_output" not in tong and "volume.json" not in tong
    assert "Math.Sqrt" not in tong and "Math.Atan" not in tong
    # nút ghi chỉ qua lệnh LISP: không có chỗ palette tự ghi duyệt cổng hay file lô
    assert "decisions.md" not in tong and "luoi_tuy_chinh" not in tong.replace("luoi_tuy_chinh.yaml", "")
    # chỉ ON/OFF layer: không đóng băng/xoá layer, không đổi layer hiện hành
    cad = cs("Services/CadLop.cs")
    assert "IsOff" in cad and "IsFrozen =" not in cad and ".Erase(" not in cad and "Clayer =" not in cad
    assert "LockDocument()" in cad                                                 # sửa LayerTable có khoá tài liệu
    # mọi handler sự kiện AutoCAD bọc try/catch
    dp = cs("Services/DieuPhoi.cs")
    for h in ("DocMoi", "DocHuy", "DocDoi", "LenhXong"):
        thân = dp.split(f"static void {h}(")[1].split("\n        }\n")[0]
        assert "try" in thân and "catch" in thân, h
    # chạy nền + Invoke về luồng giao diện
    assert "ThreadPool.QueueUserWorkItem" in dp and "BeginInvoke" in dp
    # C# 5: không dùng cú pháp mới
    for mau in (r'(?<=[\s(=,+])\$"[^"\n]*\{', r"\?\.", r"\bnameof\(", r"\bout var\b", r"=> ", r"\bis \w+ \w+\)"):
        assert not re.search(mau, tong), f"cú pháp ngoài C# 5: {mau}"
    # tab hiển thị tiếng Việt có dấu và font ≥ 9pt
    assert "Segoe UI\", 9.5f" in cs("Ui/Mau.cs")


# ======================================================================================== (b) BIÊN DỊCH
@pytest.mark.skipif(not CSC.exists() or not (ACAD / "acmgd.dll").exists(),
                    reason="cần csc.exe (.NET Framework 4.x) và AutoCAD 2022 (acmgd.dll) để biên dịch palette")
def test_bien_dich_sach(tmp_path):
    out = tmp_path / "SanNenPalette.dll"
    wpf = CSC.parent / "WPF"
    rsp = tmp_path / "a.rsp"
    dong = ["/nologo", "/target:library", "/codepage:65001", "/utf8output", f"/out:{out}"]
    dong += [f"/reference:{ACAD / d}" for d in ("acmgd.dll", "accoremgd.dll", "acdbmgd.dll")]
    dong += ["/reference:System.dll", "/reference:System.Core.dll", "/reference:System.Drawing.dll",
             "/reference:System.Windows.Forms.dll", "/reference:System.Web.Extensions.dll",
             f"/reference:{wpf / 'PresentationCore.dll'}", f"/reference:{wpf / 'WindowsBase.dll'}"]
    dong += [str(p) for p in sorted(NGUON.rglob("*.cs"))]
    rsp.write_text("\n".join(f'"{d}"' if " " in d or "\\" in d else d for d in dong), encoding="utf-8")
    r = subprocess.run([str(CSC), f"@{rsp}"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0 and out.exists(), r.stdout + r.stderr
    assert "error CS" not in r.stdout


# ======================================================================================== (c) HỢP ĐỒNG JSON
@pytest.fixture(scope="module")
def lot_mc(tmp_path_factory):
    p = tmp_path_factory.mktemp("pal") / "lot"
    lot = tao(p, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, lambda e, n: 10.0 + 0.02 * (e - E0 - 50), so_diem=900)
    chay_het(lot)
    matcat.thuc_hien(lot, (E0 + 10, 1113030.0), (E0 + 90, 1113030.0), 1.0, "MC1")
    return lot


def chup(lot) -> dict:
    return {str(p.relative_to(lot.root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(lot.root.rglob("*")) if p.is_file()}


def test_thong_tin_json_co_du_khoa_csharp_dung(lot_mc, tmp_path):
    truoc = chup(lot_mc)
    ra = tmp_path / "ra.json"
    assert CN.main(["thong-tin", "--lot", str(lot_mc.root), "--json", "--ra", str(ra)]) == 0
    d = json.loads(ra.read_text(encoding="utf-8"))                         # JSON chặt (không NaN)
    assert d["ok"] is True and d["thong_bao"] == ""
    du = d["du_lieu"]
    assert du["lo"]["ma_lo"] == "GT-01" and du["lo"]["dot"] == 1 and du["lo"]["thu_muc"] == "lot"
    for n in ("1", "2", "3"):
        assert {"da_duyet", "viec_chan"} <= set(du["cong"][n])
    assert isinstance(du["canh_bao_cu"], list) and isinstance(du["canh_bao"], list) and isinstance(du["viec_can_lam"], list)
    for k in ("luoi", "khoiluong", "matcat"):
        assert all(len(r) == 2 for r in du["nhom"][k])
    assert du["bien_dong"] and all(len(r) == 2 for r in du["bien_dong"])
    b = du["so_lieu"]["bien"]
    assert b["co"] and b["so_dinh"] >= 4 and b["chu_vi_m"] == pytest.approx(320.0, rel=1e-6) and len(b["hop_bao"]) == 4
    assert b["dien_tich_m2"] == pytest.approx(6000.0, rel=1e-6) and b["so_vung_loai_tru"] == 0
    mc = du["so_lieu"]["matcat"]["ds"]
    assert [m["ten"] for m in mc] == ["MC1"] and len(mc[0]["a"]) == 2 and len(mc[0]["b"]) == 2
    for k in ("ten", "chieu_dai_m", "dao_m2", "dap_m2", "thieu_m"):
        assert k in mc[0]
    lu = du["so_lieu"]["luoi"]
    assert isinstance(lu["cot"], str) and isinstance(lu["hang"], str) and "ngoai_suy_m" in lu
    # mọi khoá C# đọc đều có trong JSON: so khớp chuỗi trong mã C# với dữ liệu
    cs_dto = cs("Models/DuLieuPal.cs") + cs("Ui/BienLoTab.cs") + cs("Ui/LuoiTab.cs") + cs("Ui/CanhBaoTab.cs")
    for khoa in ("ma_lo", "dot", "thu_muc", "da_duyet", "viec_chan", "canh_bao_cu", "canh_bao", "viec_can_lam", "bien_dong",
                 "ds", "ten", "chieu_dai_m", "dao_m2", "dap_m2", "thieu_m", "muc", "ma", "loai", "mo_ta", "nguon", "e", "n",
                 "hop_bao", "cot", "hang", "ngoai_suy_m", "nhom", "so_lieu", "cong"):
        assert f'"{khoa}"' in cs_dto, f"C# không dùng khoá {khoa}?"
    for nhom in ("luoi", "khoiluong"):                                      # tab Lưới / Khối lượng đọc nhóm này
        assert f'"{nhom}"' in cs("Ui/LuoiTab.cs") + cs("Ui/KhoiLuongTab.cs")
    assert chup(lot_mc) == truoc, "thong-tin --json không được ghi file nào của lô"


def test_json_khong_doi_hanh_vi_sexp_va_loi_tieng_viet(lot_mc, tmp_path):
    ra = tmp_path / "ra.txt"
    CN.main(["thong-tin", "--lot", str(lot_mc.root), "--ra", str(ra)])
    s = ra.read_text(encoding="utf-8")
    assert s.startswith('(("ok" . T)') and '("canh_bao" ' not in s and '("bien_dong"' not in s          # s-expression cũ giữ nguyên
    rj = tmp_path / "loi.json"
    assert CN.main(["thong-tin", "--lot", str(tmp_path / "khong_co"), "--json", "--ra", str(rj)]) == 0
    d = json.loads(rj.read_text(encoding="utf-8"))
    assert d["ok"] is False and "không phải thư mục lô" in d["thong_bao"] and d["du_lieu"] is None


def test_json_nan_thanh_null():
    assert CN._sach({"a": float("nan"), "b": [1.5, float("inf")], "c": (1, 2)}) == {"a": None, "b": [1.5, None], "c": [1, 2]}


def test_viec_can_lam_doc_tu_markdown(lot_mc):
    (lot_mc.process_dir / "viec_can_lam.md").write_text(
        "# Việc cần làm\n\n## L-01  ·  o_ngoai_suy  ·  canh_bao\n18 ô dùng cao độ ngoại suy.\n- Chọn: (a) giữ\n\n"
        "## T-02  ·  o_lech_lon  ·  chan\nÔ O01-01 lệch 67 %.\n", encoding="utf-8")
    try:
        v = CN._viec_can_lam(lot_mc)
        assert v == [{"ma": "L-01", "loai": "o_ngoai_suy", "muc": "canh_bao", "mo_ta": "18 ô dùng cao độ ngoại suy."},
                     {"ma": "T-02", "loai": "o_lech_lon", "muc": "chan", "mo_ta": "Ô O01-01 lệch 67 %."}]
    finally:
        (lot_mc.process_dir / "viec_can_lam.md").unlink()
