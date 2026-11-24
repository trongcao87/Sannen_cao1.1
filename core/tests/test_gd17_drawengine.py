"""Bước 2 của lộ trình kiến trúc tối ưu (_agent/KIEN-TRUC-TOI-UU.md §5): KẾ HOẠCH VẼ JSON + DrawEngine C#.

  (a) Python: `ve-ke-hoach` — lược đồ, deterministic, chỉ ĐỌC lô, số đối tượng khớp backend DXF; tin3d, mặt cắt, chia khối.
  (b) Biên dịch: SanNenDraw.dll chỉ tham chiếu accoremgd + acdbmgd (KHÔNG acmgd/WinForms); palette tham chiếu Draw — csc sạch.
  (c) accoreconsole THẬT (AutoCAD 2022 không giao diện): NETLOAD SanNenDraw.dll → SN_KEHOACH_NET / SN_VE_NET / SN_XOA_NET /
      SN_TIN3D_NET: đếm theo layer + XDATA, vẽ hai lần không nhân đôi, purge đúng lô/đợt, khớp XDATA do sannen.lsp (backend LISP) vẽ,
      LISP c:SN_VE/SN_XOA/SN_TIN3D chuyển sang _NET khi có DLL; 100.000 thực thể.
  (d) Tĩnh: XDATA cùng appid/cấu trúc, mọi *_NET được LISP và palette gọi, C# 5, không phụ thuộc giao diện.
Hiển thị palette (GUI) không kiểm được ở đây — xem cad/MENU.md.
"""
from __future__ import annotations
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import ezdxf
import pytest

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(ROOT / "cad"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sannen import matcat                                                   # noqa: E402
from sannen_cad import bo_cuc                                               # noqa: E402
from sannen_cad import cau_noi as CN                                        # noqa: E402
from sannen_cad import ke_hoach                                             # noqa: E402
from sannen_cad.backend import NHOM_LOP, chia_polyface                      # noqa: E402
from sannen_cad.backend_dxf import BackendDXF                               # noqa: E402
from sannen_cad.backend_lisp import BackendLisp                             # noqa: E402
from sannen_cad.ve import TAT_CA, ve_ket_qua                                # noqa: E402
from lot_giai_tich import E0, N0, chay_het, hcn, tao                        # noqa: E402
from test_gd11_lisp_cau_noi import ACORE, _chay_acore, can_acore            # noqa: E402
from test_gd12_lisp import chay_acc, mo_dau, moi_truong                     # noqa: E402

DOTNET = ROOT / "cad" / "dotnet"
NGUON_DRAW = DOTNET / "SanNenDraw"
NGUON_PAL = DOTNET / "SanNenPalette"
LSP_TXT = (ROOT / "cad" / "lisp" / "sannen.lsp").read_text(encoding="utf-8")
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
ACAD = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Autodesk" / "AutoCAD 2022"
can_csc = pytest.mark.skipif(not CSC.exists() or not (ACAD / "accoremgd.dll").exists(),
                             reason="cần csc.exe (.NET Framework 4.x) và AutoCAD 2022 (accoremgd.dll) để biên dịch SanNenDraw")
can_net = pytest.mark.skipif(not CSC.exists() or not ACORE.exists(), reason="cần csc.exe và accoreconsole.exe (AutoCAD 2022)")

f_moc = lambda e, n: 10.0
f_do = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)
NHOM_DEM = ("luoi", "nhan", "o", "ranh", "3d")


def cs(rel: str) -> str:
    return (NGUON_DRAW / rel).read_text(encoding="utf-8-sig")


def tat_ca_cs_draw() -> str:
    return re.sub(r"//[^\n]*", "", "\n".join(p.read_text(encoding="utf-8-sig") for p in sorted(NGUON_DRAW.rglob("*.cs"))))


@pytest.fixture(scope="module")
def lo(tmp_path_factory):
    l = tao(tmp_path_factory.mktemp("gd17_lo") / "lot", [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=700)
    chay_het(l)
    return l


def chup(lot) -> dict:
    return {str(p.relative_to(lot.root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(lot.root.rglob("*")) if p.is_file()}


def ke_hoach_cn(tmp: Path, lot, *args: str, ten: str = "kh.json") -> tuple[bool, str, dict | None, dict | None]:
    """Chạy lệnh cầu nối `ve-ke-hoach`; trả (ok, thông báo, dữ liệu tóm tắt, kế hoạch)."""
    ra, kh = tmp / f"ra_{ten}", tmp / ten
    kh.unlink(missing_ok=True)
    assert CN.main(["ve-ke-hoach", "--lot", str(lot.root), "--json", "--ra", str(ra), "--ke-hoach", str(kh), *args]) == 0
    d = json.loads(ra.read_text(encoding="utf-8"))
    return d["ok"], d["thong_bao"], d["du_lieu"], (json.loads(kh.read_text(encoding="utf-8")) if kh.exists() else None)


# =========================================================================== (a) Python
def test_ke_hoach_luoc_do_va_chi_doc(lo, tmp_path):
    truoc = chup(lo)
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo)
    assert ok, tb
    assert chup(lo) == truoc, "ve-ke-hoach chỉ ĐỌC lô, không được ghi file nào"
    assert kh["phien_ban"] == 1 and kh["lenh"] == "ve" and kh["dinh_dang"] == {"chu_so_thap_phan": 4}
    tv = kh["truy_vet"]
    assert tv["ma_lo"] == "GT-01" and tv["dot"] == 1 and re.fullmatch(r"[0-9a-f]{16}", tv["hash_dau_vao"])
    assert tv["hash_dau_vao"] == json.loads((lo.process_dir / "volume.json").read_text(encoding="utf-8"))["hash_dau_vao"][:16]
    # xoa = đúng ánh xạ NHOM_LOP của backend
    assert [x["loai"] for x in kh["xoa"]] == [l for g in TAT_CA for l in NHOM_LOP[g]]
    ten_lop = {l["ten"] for l in kh["lop"]}
    assert {"SN-LUOI", "SN-LUOI-NHAN", "SN-LUOI-O", "SN-RANH-DAODAP", "SN-3DF-MOC", "SN-3DF-DO"} <= ten_lop
    mau = {l["ten"]: (l["mau"], l["tat"]) for l in kh["lop"]}
    assert mau["SN-3DF-MOC"] == (3, True) and mau["SN-3DF-DO"] == (2, True) and mau["SN-LUOI"] == (8, False)   # layer-convention
    kieu_ok = {"polyface", "3dface", "polyline", "text", "mtext"}
    theo_loai: dict[str, int] = {}
    for d in kh["doi_tuong"]:
        assert d["kieu"] in kieu_ok and d["lop"] in ten_lop and d["loai"]
        theo_loai[d["loai"]] = theo_loai.get(d["loai"], 0) + 1
        if d["kieu"] == "polyface":
            nv = len(d["dinh"])
            assert d["mat"] and all(0 <= i < nv for m in d["mat"] for i in m) and any(x.startswith("be_mat=") for x in d["ex"])
        if d["kieu"] == "text":
            assert len(d["diem"]) == 2 and d["cao"] > 0 and d["noi_dung"] != ""
        if d["kieu"] == "polyline":
            assert len(d["diem"]) >= 2 and isinstance(d["dong"], bool)
    assert kh["tom_tat"]["so_doi_tuong"] == len(kh["doi_tuong"]) == du["so_doi_tuong"]
    assert kh["tom_tat"]["theo_loai"] == theo_loai == du["theo_loai"]
    # toạ độ VN-2000 giữ ≥ 4 chữ số thập phân (không bị cắt về 2-3 số)
    s = json.loads((lo.process_dir / "surface_moc.json").read_text(encoding="utf-8"))
    pf = next(d for d in kh["doi_tuong"] if d["kieu"] == "polyface" and "be_mat=moc" in d["ex"])
    ds = set(map(tuple, pf["dinh"]))
    p0 = s["diem"][s["tam_giac"][0][0]]
    assert (round(p0[0], 4), round(p0[1], 4), round(p0[2], 4)) in ds


def test_ke_hoach_deterministic_hai_lan_cung_byte(lo, tmp_path):
    ke_hoach_cn(tmp_path, lo, ten="a.json")
    ke_hoach_cn(tmp_path, lo, ten="b.json")
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
    assert (tmp_path / "a.json").read_bytes()[:3] != b"\xef\xbb\xbf"                  # UTF-8 không BOM
    json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))                       # JSON chặt (không NaN)


def test_ke_hoach_khop_so_doi_tuong_voi_backend_dxf(lo, tmp_path):
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo)
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    ve_ket_qua(be, lo.root, dang="polyface")
    dem_dxf = collections.Counter()
    for e in be.msp:
        if e.dxf.layer.startswith("SN-") and BackendDXF.doc_nhan(e):
            dem_dxf[e.dxf.layer] += 1
    assert dict(dem_dxf) == kh["tom_tat"]["theo_lop"]
    loai_dxf = collections.Counter(BackendDXF.doc_nhan(e)["loai"] for e in be.msp if BackendDXF.doc_nhan(e))
    assert dict(loai_dxf) == kh["tom_tat"]["theo_loai"]
    for nhan, ly in (("moc", "SN-3DF-MOC"), ("do", "SN-3DF-DO")):                      # polyface: số đỉnh, số mặt
        pdx = [e for e in be.msp if e.dxftype() == "POLYLINE" and e.dxf.layer == ly][0]
        pk = [d for d in kh["doi_tuong"] if d["kieu"] == "polyface" and d["lop"] == ly][0]
        assert sum(1 for _ in pdx.faces()) == len(pk["mat"]) and int(BackendDXF.doc_nhan(pdx)["so_mat"]) == len(pk["mat"])


def test_ke_hoach_chon_nhom_va_xoa_dung_nhom(lo, tmp_path):
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--lop", "luoi,o")
    assert ok and [x["loai"] for x in kh["xoa"]] == ["luoi", "nhan_o", "cong_o"]
    assert {d["loai"] for d in kh["doi_tuong"]} == {"luoi", "nhan_o"}
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--lop", "3d", "--dang", "3dface")
    assert ok and {d["kieu"] for d in kh["doi_tuong"]} == {"3dface"} and all(len(d["p"]) == 3 for d in kh["doi_tuong"])
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--lop", "khong_co")
    assert not ok and "Nhóm vẽ lạ" in tb and not (tmp_path / "kh.json").exists() or kh is None
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--che-do", "kieu_la")
    assert not ok and "--che-do phải là" in tb


def test_ke_hoach_tin3d_bat_tat_lop_va_chi_xoa_mat_3d(lo, tmp_path):
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--che-do", "tin3d", "--be-mat", "moc")
    assert ok, tb
    assert kh["lenh"] == "tin3d" and [x["loai"] for x in kh["xoa"]] == ["mat_3d", "qc"]
    assert [(d["lop"], d["kieu"]) for d in kh["doi_tuong"] if d["loai"] == "mat_3d"] == [("SN-3DF-MOC", "polyface")]
    hl = {h["ten"]: h["bat"] for h in kh["hien_lop"]}
    assert hl == {"SN-3DF-MOC": True, "SN-3DF-DO": False, "SN-QC": True}
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--che-do", "tin3d", "--be-mat", "xxx")
    assert not ok and "be_mat phải là" in tb


def test_ke_hoach_mat_cat_xoa_theo_ten(lo, tmp_path):
    matcat.thuc_hien(lo, (E0 + 10, 1113030.0), (E0 + 90, 1113030.0), 1.0, "MC1")
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--che-do", "mat-cat", "--ten", "MC1", "--goc-ve", "445000,1112900")
    assert ok, tb
    assert kh["lenh"] == "mat_cat" and kh["xoa"] == [{"loai": "mat_cat", "ex": ["ten=MC1"]}]
    assert {d["loai"] for d in kh["doi_tuong"]} == {"mat_cat"} and {d["lop"] for d in kh["doi_tuong"]} == {"SN-MATCAT"}
    assert all(d["ex"] == ["ten=MC1"] for d in kh["doi_tuong"])
    kq = json.loads((lo.process_dir / "matcat_MC1.json").read_text(encoding="utf-8"))
    assert len(kh["doi_tuong"]) == len(bo_cuc.mat_cat_ent(kq, (445000.0, 1112900.0), 5.0))        # đúng bố cục sẵn có
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--che-do", "mat-cat", "--ten", "KHONG_CO")
    assert not ok and "Chưa có matcat_KHONG_CO.json" in tb
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--che-do", "mat-cat")
    assert not ok and "--ten" in tb


def test_ke_hoach_thieu_ket_qua_bao_loi_tieng_viet(tmp_path):
    l = tao(tmp_path / "lot", [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=300)           # chưa chạy luoi/tinh
    ok, tb, du, kh = ke_hoach_cn(tmp_path, l)
    assert not ok and "Chưa có grid.json" in tb and kh is None


def test_ke_hoach_chia_khoi_polyface_va_xdata_ex(tmp_path):
    be = ke_hoach.BackendKeHoach()
    be.toi_da_dinh = 500
    n = 40                                                                               # 41² = 1681 đỉnh > 500 → chia khối
    tg = []
    for i in range(n):
        for j in range(n):
            tg += [[(i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0)], [(i, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0)]]
    be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=False, dang="polyface")
    kh = be.ke_hoach()
    pf = kh["doi_tuong"]
    assert len(pf) >= 4 and all(len(d["dinh"]) <= 500 for d in pf)
    assert sum(len(d["mat"]) for d in pf) == len(tg)
    assert [d["ex"][2] for d in pf] == [f"khoi={i}/{len(pf)}" for i in range(1, len(pf) + 1)]
    with pytest.raises(ValueError):
        be.cad_draw_3dface("L-KHAC", 1, "h", "moc", tg[:2], "mat", xem_truoc=False, dang="polyface")   # một kế hoạch = một lô


# =========================================================================== (d) tĩnh
def test_xay_script_va_nguon_co_bom_va_khong_phu_thuoc_giao_dien():
    for p in [NGUON_DRAW / f for f in ("Json.cs", "CauNoiPython.cs", "KeHoach.cs", "DrawEngine.cs", "LenhDraw.cs")]:
        assert p.read_bytes()[:3] == b"\xef\xbb\xbf", f"{p.name} thiếu BOM UTF-8"
    for ps in ("xay_draw.ps1", "xay_palette.ps1"):
        assert (DOTNET / ps).read_bytes()[:3] == b"\xef\xbb\xbf", f"{ps} thiếu BOM"
    d = (DOTNET / "xay_draw.ps1").read_text(encoding="utf-8-sig")
    assert "accoremgd.dll" in d and "acdbmgd.dll" in d and "SanNenDraw.dll" in d and "SanNenDraw.new.dll" in d
    assert "acmgd" not in d.replace("KHÔNG acmgd.dll", "") and "System.Windows.Forms" not in d and "PresentationCore" not in d
    p = (DOTNET / "xay_palette.ps1").read_text(encoding="utf-8-sig")
    assert p.index("xay_draw.ps1") < p.index("/out:") and "SanNenDraw.dll" in p and "$drawDll" in p      # Draw trước, palette tham chiếu
    tong = tat_ca_cs_draw()
    for xau in ("System.Windows.Forms", "System.Drawing", "Autodesk.AutoCAD.Windows", "Autodesk.AutoCAD.ApplicationServices.Application",
                "PresentationCore", "PaletteSet"):
        assert xau not in tong, f"SanNenDraw không được dùng {xau} (phải chạy được trong accoreconsole)"
    assert "Core.Application" in tong                                                    # dùng bản accoremgd, không phải acmgd
    # C# 5
    for mau in (r'(?<=[\s(=,+])\$"[^"\n]*\{', r"\?\.", r"\bnameof\(", r"\bout var\b", r"=> ", r"\bis \w+ \w+\)"):
        assert not re.search(mau, tong), f"cú pháp ngoài C# 5: {mau}"
    # C# không đọc 10_process / không tự tính
    assert "10_process" not in tong and "20_output" not in tong and "volume.json" not in tong
    assert "Math.Sqrt" not in tong and "Math.Atan" not in tong


def test_xdata_csharp_cung_appid_va_cau_truc_voi_lisp():
    de = cs("DrawEngine.cs")
    assert 'AppId = "SANNEN"' in de and "ExtendedDataRegAppName" in de and "ExtendedDataAsciiString" in de
    assert "RegAppTable" in de                                                           # đăng ký appid như `(regapp "SANNEN")`
    # thứ tự trường: mã lô, đợt, hash, loại, rồi "k=v" — giống backend_lisp.snv:dat
    assert "new string[] { kh.MaLo, kh.Dot.ToString(), kh.Hash, null }" in de and "tienTo[3] = d.Loai" in de
    bl = (ROOT / "cad" / "sannen_cad" / "backend_lisp.py").read_text(encoding="utf-8")
    assert "(append (list lo dot hs loai) ex)" in bl and '(regapp "SANNEN")' in bl
    # đọc lại bằng cùng quy ước với palette (CadLop.Quet): ít nhất 4 chuỗi
    assert "s.Count >= 4" in de
    # purge chỉ xóa đối tượng KHỚP lô (và đợt), không xóa lô khác
    assert "if (s[0] != lo) return false;" in de and "s[1] != dot.Value.ToString()" in de
    # vẽ trong MỘT transaction, mở ModelSpace một lần
    assert de.count("StartTransaction()") == 2 and de.count("SymbolUtilityServices.GetBlockModelSpaceId") == 2   # Ve + Xoa
    assert "LockDocument()" in de


def test_moi_lenh_net_duoc_lisp_va_palette_goi_dung():
    lenh = set(re.findall(r'CommandMethod\("SANNEN_DRAW",\s*"(SN_[A-Z0-9_]+)"', cs("LenhDraw.cs")))
    assert lenh == {"SN_VE_NET", "SN_KEHOACH_NET", "SN_XOA_NET", "SN_XOA_NET_Y", "SN_TIN3D_NET"}
    for ten in ("SN_VE_NET", "SN_XOA_NET", "SN_TIN3D_NET"):
        assert f'"_.{ten}"' in LSP_TXT, f"sannen.lsp không gọi {ten}"
    assert '"_.NETLOAD" dll' in LSP_TXT and "dotnet\\\\bin\\\\SanNenDraw.dll" in LSP_TXT and "SANNEN_KHONG_NET" in LSP_TXT
    for ham, goi in (("(defun sn:ve ", "sn:nap-draw"), ("(defun sn:l-xoa ", "sn:nap-draw"), ("(defun sn:l-tin3d ", "sn:nap-draw")):
        than = LSP_TXT.split(ham)[1].split("\n(defun ")[0]
        assert goi in than, ham
    # còn nhánh LISP cũ khi thiếu DLL
    assert 'sn:chay-ve "ve" ""' in LSP_TXT and "sn:xoa-ket-qua lo nil nil" in LSP_TXT and 'sn:chay-ve "tin3d"' in LSP_TXT
    # palette đổi nút sang lệnh _NET khi có DLL
    cl = (NGUON_PAL / "Services" / "CadLenh.cs").read_text(encoding="utf-8-sig")
    assert "SN_VE_NET" in cl and "SN_TIN3D_NET" in cl and "CoDraw()" in cl and 'SanNenDraw.dll' in cl
    assert "CadLenh.VeLai()" in (NGUON_PAL / "Ui" / "LuoiTab.cs").read_text(encoding="utf-8-sig")
    assert "CadLenh.Xem3D()" in (NGUON_PAL / "Ui" / "QlDhTab.cs").read_text(encoding="utf-8-sig")
    # palette tham chiếu SanNenDraw cho J / CauHinh (không còn bản chép)
    assert "class CauHinh" not in (NGUON_PAL / "Services" / "PythonBridge.cs").read_text(encoding="utf-8-sig")
    assert "SanNen.Draw.J" in (NGUON_PAL / "Models" / "Json.cs").read_text(encoding="utf-8-sig")


# =========================================================================== (b) biên dịch
def bien_dich(out: Path, nguon: Path, tham_chieu: list[str], tmp: Path):
    rsp = tmp / (out.stem + ".rsp")
    dong = ["/nologo", "/target:library", "/codepage:65001", "/utf8output", f"/out:{out}"] + [f"/reference:{r}" for r in tham_chieu]
    dong += [str(p) for p in sorted(nguon.rglob("*.cs"))]
    rsp.write_text("\n".join(f'"{d}"' if " " in d or "\\" in d else d for d in dong), encoding="utf-8")
    r = subprocess.run([str(CSC), f"@{rsp}"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert r.returncode == 0 and out.exists(), r.stdout + r.stderr
    assert "error CS" not in r.stdout
    return r


REF_DRAW = ["accoremgd.dll", "acdbmgd.dll"]
REF_SYS = ["System.dll", "System.Core.dll", "System.Web.Extensions.dll"]


@pytest.fixture(scope="session")
def dll_draw(tmp_path_factory):
    if not CSC.exists() or not (ACAD / "accoremgd.dll").exists():
        pytest.skip("cần csc.exe và AutoCAD 2022")
    t = tmp_path_factory.mktemp("dll_draw")                                              # đường dẫn ASCII: .scr của accoreconsole là ASCII
    out = t / "SanNenDraw.dll"
    bien_dich(out, NGUON_DRAW, [str(ACAD / d) for d in REF_DRAW] + REF_SYS, t)
    return out


@can_csc
def test_bien_dich_draw_sach_chi_voi_accoremgd_acdbmgd(dll_draw):
    assert dll_draw.exists() and dll_draw.stat().st_size > 10000
    # không dính acmgd.dll / WinForms: đọc danh sách assembly tham chiếu trong metadata
    raw = dll_draw.read_bytes()
    for ten in (b"acmgd", b"System.Windows.Forms", b"PresentationCore", b"System.Drawing"):
        assert ten not in raw, f"SanNenDraw.dll tham chiếu {ten!r}"
    assert b"accoremgd" in raw.lower() and b"acdbmgd" in raw.lower()


@can_csc
def test_bien_dich_palette_tham_chieu_draw_sach(dll_draw, tmp_path):
    if not (ACAD / "acmgd.dll").exists():
        pytest.skip("cần acmgd.dll")
    wpf = CSC.parent / "WPF"
    d2 = tmp_path / "SanNenDraw.dll"
    shutil.copy2(dll_draw, d2)
    ref = [str(d2)] + [str(ACAD / d) for d in ("acmgd.dll", "accoremgd.dll", "acdbmgd.dll")] + REF_SYS + [
        "System.Drawing.dll", "System.Windows.Forms.dll", str(wpf / "PresentationCore.dll"), str(wpf / "WindowsBase.dll")]
    bien_dich(tmp_path / "SanNenPalette.dll", NGUON_PAL, ref, tmp_path)


# =========================================================================== (c) accoreconsole
def chay_console(tmp: Path, dll: Path, lenh: list[str], base: Path | None = None, env: dict | None = None,
                 luu: str | None = "ra.dxf", nap: bool = True, timeout: int = 900) -> tuple[str, "ezdxf.document.Drawing | None"]:
    """NETLOAD SanNenDraw.dll rồi chạy các dòng `lenh` (mỗi dòng = một lần Enter trong script), lưu DXF, thoát."""
    dong = (["_.NETLOAD", dll.as_posix()] if nap else []) + list(lenh)
    if luu:
        dong += ["_.SAVEAS", "DXF", "16", (tmp / luu).as_posix()]
    dong += ["_.QUIT", "Y"]
    scr = tmp / "s.scr"
    scr.write_text("\n".join(dong) + "\n", encoding="ascii")
    if luu:
        (tmp / luu).unlink(missing_ok=True)
    e = {**os.environ, **(env or {})}
    p = subprocess.run([str(ACORE), "/s", str(scr), "/l", "en-US"] + (["/i", str(base)] if base else []),
                       capture_output=True, timeout=timeout, env=e)
    log = p.stdout.decode("utf-16-le", "ignore") if b"\x00" in p.stdout[:40] else p.stdout.decode("utf-8", "ignore")
    assert "Cannot load assembly" not in log and "Unknown command" not in log, log[-2500:]
    if not luu:
        return log, None
    assert (tmp / luu).exists(), log[-2500:]
    return log, ezdxf.readfile(tmp / luu)


def xdata(e) -> tuple[str, ...]:
    return tuple(t.value for t in e.get_xdata("SANNEN")) if e.has_xdata("SANNEN") else ()


def dau_vet(doc) -> collections.Counter:
    """(layer, kiểu, XDATA, chữ) của mọi đối tượng SANNEN trong bản vẽ — so khớp C# với LISP."""
    c: collections.Counter = collections.Counter()
    for e in doc.modelspace():
        x = xdata(e)
        if not x:
            continue
        chu = e.dxf.text if e.dxftype() == "TEXT" else (e.text if e.dxftype() == "MTEXT" else "")
        c[(e.dxf.layer, e.dxftype(), x, chu)] += 1
    return c


def dem_layer(doc) -> dict:
    d: dict[str, int] = {}
    for e in doc.modelspace():
        if xdata(e):
            d[e.dxf.layer] = d.get(e.dxf.layer, 0) + 1
    return d


def kq_json(tmp: Path) -> dict:
    return json.loads((tmp / "sn_draw_kq.json").read_text(encoding="utf-8"))


@can_net
def test_acad_ke_hoach_ve_hai_lan_khong_nhan_doi_va_khop_xdata_lisp(lo, dll_draw, tmp_path):
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--dang", "polyface", ten="kh.json")
    assert ok, tb
    env = {"SANNEN_TMP": str(tmp_path)}
    log, doc = chay_console(tmp_path, dll_draw, ["SN_KEHOACH_NET", (tmp_path / "kh.json").as_posix()], env=env, luu="mot.dxf")
    assert dem_layer(doc) == kh["tom_tat"]["theo_lop"]                                   # khớp kế hoạch theo layer
    k = kq_json(tmp_path)
    assert k["lenh"] == "SN_KEHOACH_NET" and k["tong_ve"] == len(kh["doi_tuong"]) and k["ve"] == kh["tom_tat"]["theo_loai"]
    assert k["tong_xoa"] == 0 and k["ms_tong"] >= 0
    # mặt 3D: đúng MỘT polyface/bề mặt, số mặt đúng, layer tắt + màu theo quy ước
    for ly, be in (("SN-3DF-MOC", "moc"), ("SN-3DF-DO", "do")):
        pf = [e for e in doc.modelspace() if e.dxf.layer == ly]
        assert len(pf) == 1 and pf[0].dxftype() == "POLYLINE" and pf[0].is_poly_face_mesh
        ref = next(d for d in kh["doi_tuong"] if d["lop"] == ly)
        assert sum(1 for _ in pf[0].faces()) == len(ref["mat"]) and len(list(pf[0].vertices)) - len(ref["mat"]) == len(ref["dinh"])
        assert doc.layers.get(ly).is_off()
    assert doc.layers.get("SN-3DF-MOC").dxf.color == -3 or doc.layers.get("SN-3DF-MOC").color == 3
    assert doc.layers.get("SN-LUOI").color == 8 and not doc.layers.get("SN-LUOI").is_off()
    # chạy LẦN HAI trong CÙNG phiên (kế hoạch có `xoa` → purge nhóm sắp vẽ trước): số đối tượng không đổi
    log, doc2 = chay_console(tmp_path, dll_draw, ["SN_KEHOACH_NET", (tmp_path / "kh.json").as_posix(),
                                                  "SN_KEHOACH_NET", (tmp_path / "kh.json").as_posix()], env=env, luu="hai.dxf")
    assert dem_layer(doc2) == kh["tom_tat"]["theo_lop"]
    k2 = kq_json(tmp_path)
    assert k2["tong_xoa"] == len(kh["doi_tuong"]) and k2["xoa"] == kh["tom_tat"]["theo_loai"] and k2["tong_ve"] == len(kh["doi_tuong"])
    # KHỚP XDATA / layer / chữ với đối tượng do file .lsp (BackendLisp trong AutoCAD thật) vẽ
    be = BackendLisp()
    ve_ket_qua(be, lo.root, dang="polyface")
    lsp = be.luu(tmp_path / "lisp" / "ve.lsp")
    doc_lisp, _ = _chay_acore(tmp_path, [lsp], base=None, ten_ra="lisp.dxf")
    a, b = dau_vet(doc), dau_vet(doc_lisp)
    assert a == b, {"chi_C#": list((a - b).items())[:3], "chi_LISP": list((b - a).items())[:3]}
    for ly in kh["tom_tat"]["theo_lop"]:
        la, lb = doc.layers.get(ly), doc_lisp.layers.get(ly)
        assert (la.dxf.color, la.is_off()) == (lb.dxf.color, lb.is_off()), ly


@can_net
def test_acad_xoa_dung_lo_dot_khong_dung_lo_khac(lo, dll_draw, tmp_path):
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, "--lop", "luoi,nhan,o,ranh,3d")
    base = json.loads(json.dumps(kh))
    khac = json.loads(json.dumps(kh))
    khac["truy_vet"]["ma_lo"] = "LO-KHAC"                                                 # lô khác cùng bản vẽ
    dot2 = json.loads(json.dumps(kh))
    dot2["truy_vet"]["dot"] = 2                                                          # cùng lô, đợt khác
    for k in (khac, dot2):                                                               # đợt 2: layer có hậu tố -D02 như backend.ten_layer
        if k is dot2:
            for l in k["lop"]:
                l["ten"] += "-D02"
            for d in k["doi_tuong"]:
                d["lop"] += "-D02"
            for h in k["hien_lop"]:
                h["ten"] += "-D02"
    for ten, k in (("a.json", base), ("b.json", khac), ("c.json", dot2)):
        (tmp_path / ten).write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
    cfg = tmp_path / "sannen.cfg"
    cfg.write_text(f"python={sys.executable}\ncad={ROOT / 'cad'}\nlot={lo.root}\n", encoding="utf-8")        # lô cấu hình: GT-01, đợt 1
    env = {"SANNEN_CFG": str(cfg), "SANNEN_TMP": str(tmp_path)}
    ve3 = ["SN_KEHOACH_NET", (tmp_path / "a.json").as_posix(), "SN_KEHOACH_NET", (tmp_path / "b.json").as_posix(),
           "SN_KEHOACH_NET", (tmp_path / "c.json").as_posix()]
    n = kh["tom_tat"]["so_doi_tuong"]
    # (1) SN_XOA_NET trả lời No → không xóa gì
    _, doc = chay_console(tmp_path, dll_draw, ve3 + ["SN_XOA_NET", "No"], env=env, luu="no.dxf")
    assert sum(dem_layer(doc).values()) == 3 * n
    # (2) trả lời Yes → chỉ xóa GT-01 đợt 1
    _, doc = chay_console(tmp_path, dll_draw, ve3 + ["SN_XOA_NET", "Yes"], env=env, luu="yes.dxf")
    k = kq_json(tmp_path)
    assert k["lenh"] == "SN_XOA_NET" and k["tong_xoa"] == n and k["tong_ve"] == 0
    con = collections.Counter((xdata(e)[0], xdata(e)[1]) for e in doc.modelspace() if xdata(e))
    assert con == {("LO-KHAC", "1"): n, ("GT-01", "2"): n}
    # (3) SN_XOA_NET_Y: không hỏi
    _, doc = chay_console(tmp_path, dll_draw, ve3 + ["SN_XOA_NET_Y"], env=env, luu="y.dxf")
    con = collections.Counter((xdata(e)[0], xdata(e)[1]) for e in doc.modelspace() if xdata(e))
    assert con == {("LO-KHAC", "1"): n, ("GT-01", "2"): n}
    # bản vẽ sạch hẳn của lô cấu hình: không còn polyface của GT-01 đợt 1
    assert not [e for e in doc.modelspace() if e.dxf.layer in ("SN-3DF-MOC", "SN-3DF-DO") and xdata(e)[:2] == ("GT-01", "1")]
    # lô không có trong cấu hình / bản vẽ trống → báo, không lỗi
    log, doc = chay_console(tmp_path, dll_draw, ["SN_XOA_NET"], env=env, luu="trong.dxf")
    assert "Bản vẽ không có đối tượng kết quả SN của lô GT-01 đợt 1" in log and not dem_layer(doc)


@can_net
def test_acad_sn_ve_net_qua_python_va_tin3d_net(lo, dll_draw, tmp_path):
    cfg = tmp_path / "sannen.cfg"
    cfg.write_text(f"python={sys.executable}\ncad={ROOT / 'cad'}\nlot={lo.root}\n", encoding="utf-8")
    env = {"SANNEN_CFG": str(cfg), "SANNEN_TMP": str(tmp_path)}
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, ten="mong_doi.json")
    truoc = chup(lo)
    # SN_VE_NET: Enter ở câu hỏi nhóm = tất cả; chạy HAI lần liên tiếp trong cùng phiên
    log, doc = chay_console(tmp_path, dll_draw, ["SN_VE_NET", "", "SN_VE_NET", ""], env=env, luu="ve.dxf")
    assert dem_layer(doc) == kh["tom_tat"]["theo_lop"], log[-1500:]
    k = kq_json(tmp_path)
    assert k["lenh"] == "SN_VE_NET" and k["tong_xoa"] == len(kh["doi_tuong"]) and k["tong_ve"] == len(kh["doi_tuong"])
    # nhóm cụ thể: chỉ vẽ lại lưới → các nhóm khác nguyên vẹn
    log, doc = chay_console(tmp_path, dll_draw, ["SN_VE_NET", "", "SN_VE_NET", "luoi"], env=env, luu="luoi.dxf")
    assert dem_layer(doc) == kh["tom_tat"]["theo_lop"]
    k = kq_json(tmp_path)
    assert k["ve"] == {"luoi": kh["tom_tat"]["theo_loai"]["luoi"]} and k["xoa"] == k["ve"]
    # nhóm sai chính tả: báo, không vẽ gì thêm
    log, doc = chay_console(tmp_path, dll_draw, ["SN_VE_NET", "", "SN_VE_NET", "khong co"], env=env, luu="sai.dxf")
    assert dem_layer(doc) == kh["tom_tat"]["theo_lop"]
    # SN_TIN3D_NET: Mốc → chỉ polyface mốc; layer mốc BẬT, đo TẮT; có view SN_TIN3D
    log, doc = chay_console(tmp_path, dll_draw, ["SN_TIN3D_NET", "Moc"], env=env, luu="t3d.dxf")
    pf = [e for e in doc.modelspace() if e.dxftype() == "POLYLINE" and xdata(e)]
    assert [e.dxf.layer for e in pf] == ["SN-3DF-MOC"] and pf[0].is_poly_face_mesh
    assert not doc.layers.get("SN-3DF-MOC").is_off()
    assert "SN_TIN3D" in [v.dxf.name for v in doc.views], log[-1200:]
    # lặp lại, lần này Cả hai (Enter = mặc định): view cũ thay thế, không nhân đôi polyface
    log, doc = chay_console(tmp_path, dll_draw, ["SN_TIN3D_NET", "Moc", "SN_TIN3D_NET", ""], env=env, luu="t3d2.dxf")
    pf = sorted(e.dxf.layer for e in doc.modelspace() if e.dxftype() == "POLYLINE" and xdata(e))
    assert pf == ["SN-3DF-DO", "SN-3DF-MOC"]
    assert [v.dxf.name for v in doc.views].count("SN_TIN3D") == 1
    assert not doc.layers.get("SN-3DF-DO").is_off() and not doc.layers.get("SN-3DF-MOC").is_off()
    assert chup(lo) == truoc, "ve-ke-hoach không được ghi vào lô khi vẽ từ CAD"


@can_net
def test_acad_lisp_chuyen_sang_net_khi_co_dll_va_lui_ve_lisp_khi_khong(lo, dll_draw, tmp_path):
    """c:SN_VE / c:SN_XOA / c:SN_TIN3D ưu tiên bản _NET khi có DLL; SANNEN_KHONG_NET → LISP cũ, CÙNG kết quả."""
    cad = tmp_path / "cad"
    (cad / "dotnet" / "bin").mkdir(parents=True)
    shutil.copytree(ROOT / "cad" / "sannen_cad", cad / "sannen_cad", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(dll_draw, cad / "dotnet" / "bin" / "SanNenDraw.dll")
    cfg = {"python": sys.executable, "cad": str(cad), "lot": str(lo.root)}
    ok, tb, du, kh = ke_hoach_cn(tmp_path, lo, ten="mong_doi.json")
    n = kh["tom_tat"]["theo_lop"]
    ma = mo_dau() + r'''
(t! "co-dll" (not (null (sn:draw-dll))))
(sn:ve)
(t! "ve-net" (> (sslength (ssget "X" '((-3 ("SANNEN"))))) 20))
(princ)
'''
    # (1) có DLL → _NET: kết quả ghi bởi DrawEngine (sn_draw_kq.json xuất hiện)
    env = moi_truong(tmp_path, cfg)
    txt, kq = chay_acc(tmp_path, ma, env, timeout=600)
    assert kq.get("co-dll") == "OK" and kq.get("ve-net") == "OK", txt[-1500:]
    assert kq_json(tmp_path)["lenh"] == "SN_VE_NET"
    (tmp_path / "sn_draw_kq.json").unlink()
    # (2) SANNEN_KHONG_NET=1 → LISP cũ (không có DrawEngine): kết quả vẽ y hệt, KHÔNG có sn_draw_kq.json
    env2 = moi_truong(tmp_path, cfg, SANNEN_KHONG_NET="1")
    txt, kq = chay_acc(tmp_path, ma.replace('(t! "co-dll" (not (null (sn:draw-dll))))', '(t! "co-dll" (null (sn:draw-dll)))'), env2, timeout=600)
    assert kq.get("co-dll") == "OK" and kq.get("ve-net") == "OK", txt[-1500:]
    assert not (tmp_path / "sn_draw_kq.json").exists()
    # (3) c:SN_XOA qua _NET: hỏi Yes/No của C#
    scr = tmp_path / "x.scr"
    f = tmp_path / "x.lsp"
    f.write_text(mo_dau() + '(sn:ve)\n', encoding="utf-8")
    ra = tmp_path / "xoa.dxf"
    scr.write_text(f'(load "{f.as_posix()}")\n(c:SN_XOA)\nYes\n_.SAVEAS\nDXF\n16\n{ra.as_posix()}\n_.QUIT\nY\n', encoding="ascii")
    subprocess.run([str(ACORE), "/s", str(scr), "/l", "en-US"], capture_output=True, timeout=600, env={**os.environ, **env})
    assert ra.exists()
    d = ezdxf.readfile(ra)
    assert dem_layer(d) == {}, "SN_XOA (qua SN_XOA_NET, trả lời Yes) phải xóa sạch kết quả của lô"
    assert kq_json(tmp_path)["lenh"] == "SN_XOA_NET" and kq_json(tmp_path)["tong_xoa"] == sum(n.values())


@can_net
def test_acad_100000_thuc_the_mot_transaction(dll_draw, tmp_path):
    """Hiệu năng: 100.000 thực thể (polyline, text, + một polyface 20.000 đỉnh) trong một transaction; vẽ lần hai purge rồi vẽ lại."""
    ds = []
    for i in range(60000):
        x = 445000.0 + (i % 300) * 1.0
        y = 1113000.0 + (i // 300) * 1.0
        ds.append({"kieu": "polyline", "loai": "luoi", "lop": "SN-LUOI", "diem": [[x, y], [x + 0.9, y]], "dong": False})
    for i in range(39999):
        x = 445000.0 + (i % 300) * 1.0
        y = 1113300.0 + (i // 300) * 1.0
        ds.append({"kieu": "text", "loai": "nhan_dinh", "lop": "SN-LUOI-NHAN", "ex": [f"ma=D{i:05d}", "be_mat=moc"],
                   "diem": [x + 0.3, y + 0.3], "noi_dung": f"{10 + (i % 7) * 0.123:.3f}", "cao": 0.5})
    n = 200
    dinh = [[445000.0 + i, 1113600.0 + j, 10.0 + 0.001 * i] for i in range(n + 1) for j in range(100)]          # 20.100 đỉnh
    mat = []
    for i in range(n):
        for j in range(99):
            a, b, c, d = i * 100 + j, (i + 1) * 100 + j, (i + 1) * 100 + j + 1, i * 100 + j + 1
            mat += [[a, b, c], [a, c, d]]
    ds.append({"kieu": "polyface", "loai": "mat_3d", "lop": "SN-3DF-MOC", "ex": ["be_mat=moc", f"so_mat={len(mat)}", "khoi=1/1"],
               "dinh": dinh, "mat": mat})
    assert len(ds) == 100000
    kh = {"phien_ban": 1, "lenh": "ve", "dinh_dang": {"chu_so_thap_phan": 4},
          "truy_vet": {"ma_lo": "GT-01", "dot": 1, "hash_dau_vao": "0123456789abcdef"},
          "xoa": [{"loai": "luoi"}, {"loai": "nhan_dinh"}, {"loai": "mat_3d"}],
          "lop": [{"ten": "SN-LUOI", "mau": 8, "tat": False, "dat_mau": False}, {"ten": "SN-LUOI-NHAN", "mau": 3, "tat": False, "dat_mau": False},
                  {"ten": "SN-3DF-MOC", "mau": 3, "tat": True, "dat_mau": True}],
          "doi_tuong": ds, "hien_lop": [],
          "tom_tat": {"so_doi_tuong": 100000, "theo_loai": {"luoi": 60000, "nhan_dinh": 39999, "mat_3d": 1}, "theo_lop": {}}}
    p = tmp_path / "lon.json"
    t0 = time.time()
    p.write_bytes((json.dumps(kh, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    env = {"SANNEN_TMP": str(tmp_path)}
    t1 = time.time()
    log, doc = chay_console(tmp_path, dll_draw, ["SN_KEHOACH_NET", p.as_posix()], env=env, luu="lon.dxf", timeout=1800)
    t2 = time.time()
    k = kq_json(tmp_path)
    assert k["tong_ve"] == 100000 and k["ve"] == {"luoi": 60000, "nhan_dinh": 39999, "mat_3d": 1}
    dem = collections.Counter(e.dxf.layer for e in doc.modelspace())
    assert dem == {"SN-LUOI": 60000, "SN-LUOI-NHAN": 39999, "SN-3DF-MOC": 1}
    # lần hai trong cùng phiên: purge 100.000 rồi vẽ lại 100.000 — không nhân đôi
    log, doc2 = chay_console(tmp_path, dll_draw, ["SN_KEHOACH_NET", p.as_posix(), "SN_KEHOACH_NET", p.as_posix()], env=env, luu="lon2.dxf",
                             timeout=1800)
    k2 = kq_json(tmp_path)
    assert k2["tong_xoa"] == 100000 and k2["tong_ve"] == 100000
    assert collections.Counter(e.dxf.layer for e in doc2.modelspace()) == dem
    print(f"\n[100.000 thực thể] vẽ lần 1: {k['ms_ve']} ms (một transaction); lần 2 purge {k2['ms_xoa']} ms + vẽ {k2['ms_ve']} ms; "
          f"cả lệnh {k2['ms_tong']} ms; accoreconsole cả phiên (nạp + đọc JSON + lưu DXF) {t2 - t1:.1f} s; tạo JSON {t1 - t0:.1f} s, "
          f"{p.stat().st_size / 1e6:.1f} MB")
    assert k["ms_ve"] < 120000 and k2["ms_xoa"] < 120000, "vẽ/xóa 100.000 thực thể phải dưới 2 phút"
