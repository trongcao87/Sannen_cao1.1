"""Giai đoạn 14 — mặt 3D dạng POLYFACE MESH (một đối tượng/bề mặt), chỗ đặt mặt cắt, osnap, hộp thoại tiếng Việt.

Tầng kiểm chứng:
  (a) backend DXF (ezdxf): 1 polyface/bề mặt, số mặt = số tam giác tốt, vẽ hai lần không nhân đôi, purge sạch đúng lô,
      chia khối khi vượt giới hạn đỉnh;
  (b) backend LISP + cầu nối: file .lsp sinh ra đúng dạng, chia khối, `dang=3dface` giữ lối cũ, 13 công cụ MCP vẫn đủ;
  (c) AutoCAD 2022 THẬT không giao diện (accoreconsole): nạp polyface bằng entmake, đếm POLYLINE/mặt, XDATA, purge,
      ẩn/khôi phục layer, osnap, hộp bao, view.
Hộp thoại DCL, VSCURRENT và menu thả xuống cần GIAO DIỆN — chỉ kiểm tĩnh được (xem test_gd12_lisp.py).
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import ezdxf
import pytest

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE.parent / "cad"))
from sannen_cad import bo_cuc                                                # noqa: E402
from sannen_cad import cau_noi as CN                                         # noqa: E402
from sannen_cad.backend import TEN_CONG_CU, chia_polyface                    # noqa: E402
from sannen_cad.backend_dxf import BackendDXF                                # noqa: E402
from sannen_cad.backend_lisp import BackendLisp                              # noqa: E402
from sannen_cad.mcp_cad_server import _MO_TA, tao_cong_cu                    # noqa: E402
from sannen_cad.ve import ve_ket_qua                                         # noqa: E402
from lot_giai_tich import E0, N0, chay_het, hcn, tao                         # noqa: E402
from test_gd11_lisp_cau_noi import (ACORE, _chay_acore, can_acore, can_bang, chay_cn, dem_layer,   # noqa: E402
                                    doc_sx, so_mat_polyface, tim)
from test_gd12_lisp import chay_acc, mo_dau, moi_truong   # noqa: E402

f_moc = lambda e, n: 10.0
f_do = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)


@pytest.fixture(scope="module")
def lo(tmp_path_factory):
    l = tao(tmp_path_factory.mktemp("pf_lo"), [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=700)
    chay_het(l)
    return l


@pytest.fixture
def lot_moi(tmp_path):
    l = tao(tmp_path / "lot", [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=600)
    chay_het(l)
    return l


def kiem_tra_tat_ca_ok(kq: dict, ten: list[str]):
    """Như test_gd12 nhưng chịu được ký tự `_` dính sau OK (echo lệnh của console)."""
    sai = [k for k in ten if not str(kq.get(k)).startswith("OK")]
    assert not sai, f"Không đạt: {sai} (nhận được: { {k: kq.get(k) for k in ten} })"


def tam_giac_tot_xau(lot, nhan):
    s = json.loads((lot.process_dir / f"surface_{nhan}.json").read_text(encoding="utf-8"))
    d, loai = s["diem"], s.get("loai_tam_giac") or [0] * len(s["tam_giac"])
    tot = sum(1 for l in loai if l == 0)
    return tot, len(loai) - tot


def luoi_tam_giac(n: int, z=lambda i, j: 0.0):
    """Lưới n×n ô, mỗi ô 2 tam giác → (n+1)² đỉnh, 2n² mặt."""
    ds = []
    for i in range(n):
        for j in range(n):
            a, b, c, d = (i, j, z(i, j)), (i + 1, j, z(i + 1, j)), (i + 1, j + 1, z(i + 1, j + 1)), (i, j + 1, z(i, j + 1))
            ds += [[a, b, c], [a, c, d]]
    return ds


def polyface_cua(doc, layer):
    return [e for e in doc.modelspace() if e.dxftype() == "POLYLINE" and e.dxf.layer == layer]


# =========================================================================== (a) backend DXF
def test_chia_polyface_dung_dinh_dung_gioi_han():
    tg = luoi_tam_giac(200)                                  # 201² = 40401 đỉnh > 30000 → buộc phải chia
    khoi = chia_polyface(tg)
    assert len(khoi) >= 2 and all(len(d) <= 30000 for d, _ in khoi)
    assert sum(len(m) for _, m in khoi) == len(tg) == 2 * 200 * 200            # không mất, không thừa mặt
    for d, m in khoi:                                                          # chỉ số hợp lệ, không đỉnh mồ côi
        assert all(0 <= k < len(d) for f in m for k in f)
        assert {k for f in m for k in f} == set(range(len(d)))
    assert len(chia_polyface(luoi_tam_giac(50))) == 1                          # 51² = 2601 đỉnh: một khối
    assert chia_polyface([]) == []


def test_dxf_mot_polyface_moi_be_mat_so_mat_bang_tam_giac_tot(lo, tmp_path):
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    kq = ve_ket_qua(be, lo.root, lop=["3d"], dang="polyface")
    doc = be.doc
    for nhan, ly in (("moc", "SN-3DF-MOC"), ("do", "SN-3DF-DO")):
        tot, xau = tam_giac_tot_xau(lo, nhan)
        pf = polyface_cua(doc, ly)
        assert len(pf) == 1 and pf[0].is_poly_face_mesh, ly                    # MỘT đối tượng cho cả bề mặt
        assert sum(1 for _ in pf[0].faces()) == tot == kq[f"mat_{nhan}"]["so_mat"]
        assert kq[f"mat_{nhan}"]["so_polyface"] == 1 and kq[f"mat_{nhan}"]["dang"] == "polyface"
        assert doc.layers.get(ly).is_off()                                     # mặt 3D vẫn tắt mặc định
        n = BackendDXF.doc_nhan(pf[0])
        assert n["loai"] == "mat_3d" and n["be_mat"] == nhan and n["ma_lo"] == "GT-01" and int(n["so_mat"]) == tot
        if xau:
            qc = polyface_cua(doc, "SN-QC")
            assert qc and sum(sum(1 for _ in e.faces()) for e in qc) >= xau
    assert doc.layers.get("SN-3DF-MOC").color == 3 and doc.layers.get("SN-3DF-DO").color == 2   # mốc xanh lá, đo vàng
    assert not [e for e in doc.modelspace() if e.dxftype() == "3DFACE"]       # không còn 3DFACE rời


def test_dxf_ve_hai_lan_khong_nhan_doi_va_purge_sach(lo, tmp_path):
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    ve_ket_qua(be, lo.root, lop=["3d"], dang="polyface")
    d1 = {e.dxf.layer: 0 for e in be.msp}
    for e in be.msp:
        d1[e.dxf.layer] += 1
    ve_ket_qua(be, lo.root, lop=["3d"], dang="polyface")                       # RULES 5: purge cũ rồi vẽ lại
    d2 = {e.dxf.layer: 0 for e in be.msp}
    for e in be.msp:
        d2[e.dxf.layer] += 1
    assert d1 == d2 and d1["SN-3DF-MOC"] == 1 and d1["SN-3DF-DO"] == 1
    # lô khác trong cùng bản vẽ: không được đụng
    be.cad_draw_3dface("LO-KHAC", 1, "h", "moc", luoi_tam_giac(3), "mat", xem_truoc=False, dang="polyface")
    assert len(polyface_cua(be.doc, "SN-3DF-MOC")) == 2
    r = be.cad_purge_sn("GT-01", 1, xem_truoc=False, loai=("mat_3d", "qc"))
    assert r["so_xoa"] >= 2
    con = polyface_cua(be.doc, "SN-3DF-MOC")
    assert len(con) == 1 and BackendDXF.doc_nhan(con[0])["ma_lo"] == "LO-KHAC"
    assert not polyface_cua(be.doc, "SN-3DF-DO")
    be.cad_purge_sn("LO-KHAC", 1, xem_truoc=False)
    assert not [e for e in be.msp if e.dxftype() in ("POLYLINE", "3DFACE")]


def test_dxf_xem_truoc_khong_ghi_va_dang_3dface_van_chay(lo, tmp_path):
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    tg = luoi_tam_giac(4)
    r = be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=True, dang="polyface")
    assert not r["da_ghi"] and not [e for e in be.msp if e.dxf.layer == "SN-3DF-MOC"] and r["so_polyface"] == 1
    r = be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=False)     # mặc định = lối cũ
    assert len([e for e in be.msp if e.dxftype() == "3DFACE"]) == len(tg) and "so_polyface" not in r
    with pytest.raises(ValueError, match="dang phải"):
        be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=True, dang="mesh")


def test_dxf_chia_khoi_khi_qua_gioi_han_va_noi_ro(tmp_path, lo):
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    be.toi_da_dinh = 500                                                       # hạ giới hạn để thử nhanh; có thử giới hạn thật bên dưới
    tg = luoi_tam_giac(40)                                                     # 41² = 1681 đỉnh → ≥ 4 khối
    r = be.cad_draw_3dface("L", 1, "h", "do", tg, "mat", xem_truoc=False, dang="polyface")
    pf = polyface_cua(be.doc, "SN-3DF-DO")
    assert len(pf) == r["so_polyface"] >= 4 and "chia thành" in r["ghi_chu"] and "500" in r["ghi_chu"]
    assert sum(sum(1 for _ in e.faces()) for e in pf) == len(tg)
    assert all(len(e.vertices) - sum(1 for _ in e.faces()) <= 500 for e in pf)
    khoi = [BackendDXF.doc_nhan(e)["khoi"] for e in pf]
    assert sorted(khoi) == sorted(f"{i}/{len(pf)}" for i in range(1, len(pf) + 1))
    be.cad_purge_sn("L", 1, xem_truoc=False, loai=("mat_3d",))                 # purge xóa MỌI khối
    assert not polyface_cua(be.doc, "SN-3DF-DO")


def test_dxf_gioi_han_that_30000_dinh(tmp_path, lo):
    be = BackendDXF(lo.input_dir / "gt.dxf", tmp_path / "a.dxf")
    tg = luoi_tam_giac(190, lambda i, j: (i * 7 + j * 3) % 5 * 0.1)           # 191² = 36481 đỉnh
    r = be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=False, dang="polyface")
    pf = polyface_cua(be.doc, "SN-3DF-MOC")
    assert len(pf) == r["so_polyface"] == 2
    assert all(len(e.vertices) - sum(1 for _ in e.faces()) <= 30000 for e in pf)
    assert sum(sum(1 for _ in e.faces()) for e in pf) == len(tg)
    be.luu()
    doc = ezdxf.readfile(be.ra)                                                # lưu/đọc lại được, vẫn hai khối
    assert len(polyface_cua(doc, "SN-3DF-MOC")) == 2


# =========================================================================== (b) backend LISP + cầu nối + MCP
def test_mcp_van_13_cong_cu_va_co_tham_so_dang():
    assert len(TEN_CONG_CU) == 13 and set(_MO_TA) == set(TEN_CONG_CU)
    mo_ta, tp, bb = _MO_TA["cad_draw_3dface"]
    assert tp["dang"]["enum"] == ["polyface", "3dface"] and "dang" not in bb      # tùy chọn, mặc định cũ
    assert len(tao_cong_cu(BackendLisp())) == 13


def test_backend_lisp_polyface_sinh_lenh_dung_dang():
    be = BackendLisp()
    tg = luoi_tam_giac(2)
    r = be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=False, dang="polyface")
    t = be.noi_dung()
    assert t.count("(snv:pf ") == 1 and t.count("(snv:pk)") == 1 and t.count("(snv:pm ") == len(tg) == 8
    assert t.count("(snv:pd ") == 9 and "(snv:pf 9 8 \"SN-3DF-MOC\")" in t and '"khoi=1/1"' in t and '"so_mat=8"' in t
    assert "(snv:f " not in t and can_bang(t) == 0
    assert r["so_polyface"] == 1 and "(snv:mau \"SN-3DF-MOC\" 3)" in t
    be2 = BackendLisp()
    be2.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=False)         # lối cũ
    assert be2.noi_dung().count("(snv:f ") == len(tg) and "(snv:pf " not in be2.noi_dung()
    be3 = BackendLisp()
    be3.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=True, dang="polyface")
    assert be3.dong == []                                                      # xem trước: không thêm dòng nào


def test_backend_lisp_chia_khoi_va_ghi_chu():
    be = BackendLisp()
    be.toi_da_dinh = 100
    tg = luoi_tam_giac(20)                                                     # 441 đỉnh
    r = be.cad_draw_3dface("L", 1, "h", "moc", tg, "mat", xem_truoc=False, dang="polyface")
    t = be.noi_dung()
    n = r["so_polyface"]
    assert n >= 5 and t.count("(snv:pf ") == n == t.count("(snv:pk)") and "chia thành" in r["ghi_chu"]
    assert t.count("(snv:pm ") == len(tg)
    for i in range(1, n + 1):
        assert f'"khoi={i}/{n}"' in t


def test_cau_noi_tin3d_polyface_mac_dinh_va_3dface_theo_yeu_cau(lo, tmp_path):
    ok, tb, du, lsp = chay_cn(tmp_path, lo, "tin3d", "--be-mat", "ca-hai", lsp=True)
    assert ok and tim(du, "dang") == "polyface" and tim(du, "so_polyface") >= 2 and "polyface" in tb
    t = lsp.read_text(encoding="utf-8")
    assert t.count("(snv:pf ") == tim(du, "so_polyface") and "(snv:f " not in t and can_bang(t) == 0
    ok, tb, du, lsp = chay_cn(tmp_path, lo, "tin3d", "--be-mat", "do", "--dang", "3dface", lsp=True)
    t = lsp.read_text(encoding="utf-8")
    assert ok and "(snv:pf " not in t and t.count("(snv:f ") == tim(du, "so_mat_do")
    ok, tb, _, _ = chay_cn(tmp_path, lo, "tin3d", "--be-mat", "do", "--dang", "mesh", lsp=True)
    assert not ok and "polyface hoặc 3dface" in tb
    ok, tb, du, lsp = chay_cn(tmp_path, lo, "ve", lsp=True)                     # menu SN_VE cũng vẽ polyface
    assert ok and lsp.read_text(encoding="utf-8").count("(snv:pf ") >= 2


# =========================================================================== SN_MATCAT: chỗ đặt mặc định
MC = lambda lo_, ten, *them: chay_cn(Path(lo_.root).parent, lo_, "mat-cat", "--a", f"{E0},{N0 + 30}", "--b", f"{E0 + 100},{N0 + 30}",
                                     "--buoc", "10", "--ten", ten, *them, lsp=True)


def test_mat_cat_mac_dinh_tranh_bang_va_cach_it_nhat_30m(lo):
    hb = json.loads((lo.process_dir / "lo.json").read_text(encoding="utf-8"))["hop_bao"]
    ok, tb, du, lsp = MC(lo, "MD1")                                            # không --goc-ve, không đo bản vẽ: dùng hộp bao lô + bảng
    assert ok, tb
    vung = tim(du, "vung")
    assert tim(du, "mac_dinh") is True and "tự đặt dưới" in tb
    bp = lo.output_dir / "bang_in_cad.json"
    duoi = hb[1]
    if bp.exists():                                                            # bảng in đặt tại (xmin, ymin − 20) và kéo dài xuống
        duoi = min(duoi, bo_cuc.hop_bao_ent(bo_cuc.bang_ent(json.loads(bp.read_text(encoding="utf-8")), (hb[0], hb[1] - 20.0)))[1])
    assert vung[3] <= duoi - 30.0 + 1e-6, (vung, duoi)                         # đỉnh biểu đồ thấp hơn mọi thứ ≥ 30 m
    assert vung[0] == pytest.approx(hb[0], abs=1e-3)                           # canh trái theo hộp bao
    # LISP đo được bản vẽ → truyền --trai-x/--duoi-y: ưu tiên số đo thực (kể cả số ÂM, dạng =)
    ok, tb, du, _ = MC(lo, "MD2", "--trai-x=-123.5", "--duoi-y=-5000")
    v = tim(du, "vung")
    assert ok and v[3] <= -5030.0 + 1e-6 and v[0] == pytest.approx(-123.5, abs=1e-3)
    # người chọn điểm → dùng đúng điểm đó, không phải mặc định
    ok, tb, du, lsp = MC(lo, "MD3", "--goc-ve", f"{E0 + 5},{N0 - 77}")
    assert ok and tim(du, "mac_dinh") is not True and tim(du, "goc_ve") == pytest.approx([E0 + 5, N0 - 77])
    assert "MẶT CẮT MD3" in lsp.read_text(encoding="utf-8")


def test_mat_cat_mac_dinh_xep_xuong_khi_co_nhieu_bieu_do(lo):
    """Biểu đồ thứ hai (tên khác) tính hộp bao gồm cả biểu đồ thứ nhất do LISP đo → nằm dưới nó, không chồng."""
    ok, _, d1, _ = MC(lo, "XA", "--trai-x", "0", "--duoi-y", "0")
    ok2, _, d2, _ = MC(lo, "XB", "--trai-x", "0", "--duoi-y=" + str(tim(d1, "vung")[1]))
    assert ok and ok2 and tim(d2, "vung")[3] <= tim(d1, "vung")[1] - 30.0 + 1e-6


def test_goc_mat_cat_mac_dinh_ham_thuan():
    kq = {"tram": [{"ly_trinh": 0.0, "z_moc": 10.0, "z_do": 11.0}, {"ly_trinh": 50.0, "z_moc": 10.0, "z_do": 9.0}],
          "chieu_dai_m": 50.0, "ten": "T", "a": [0.0, 0.0], "b": [50.0, 0.0],
          "dien_tich_dao_m2": 1.0, "dien_tich_dap_m2": 1.0, "doan_thieu_du_lieu_m": 0.0}
    gx, gy = bo_cuc.goc_mat_cat_mac_dinh(kq, 5.0, trai_x=1000.0, duoi_y=2000.0)
    hb = bo_cuc.hop_bao_ent(bo_cuc.mat_cat_ent(kq, (gx, gy), 5.0)[3:])
    assert hb[0] == pytest.approx(1000.0) and hb[3] == pytest.approx(2000.0 - 30.0)


# =========================================================================== SN_XEM3D (cầu nối dựng dòng lệnh)
def test_xem3d_cau_noi_goi_verb_xem3d_voi_mo(lot_moi, tmp_path, monkeypatch):
    goi = []

    def gia(lot, *argv):
        goi.append(argv)
        return 0, "Đã sinh trình xem 3D\n" + str(tmp_path / "xem3d.html") + "\n"
    monkeypatch.setattr(CN, "_cli", gia)
    ok, tb, du, _ = chay_cn(tmp_path, lot_moi, "xem3d")
    assert ok and goi == [("xem3d", "--mo")] and tim(du, "file").endswith("xem3d.html") and "xem3d.html" in tb

    monkeypatch.setattr(CN, "_cli", lambda lot, *a: (3, "verb chưa cài\n"))
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "xem3d")
    assert not ok and "Không dựng được trình xem 3D" in tb and "verb chưa cài" in tb
    monkeypatch.setattr(CN, "_cli", lambda lot, *a: (2, ""))
    ok, tb, _, _ = chay_cn(tmp_path, lot_moi, "xem3d")
    assert not ok and "mã thoát 2" in tb


def test_lisp_xem3d_goi_cau_noi_va_menu():
    lsp = (Path(__file__).resolve().parents[2] / "cad" / "lisp" / "sannen.lsp").read_text(encoding="utf-8")
    assert '(sn:chay "xem3d" "" nil)' in lsp and "(defun c:SN_XEM3D ()" in lsp
    assert '"SN_XEM3D"' in lsp.split("(setq *sn-menu*")[1].split("(defun sn:dung-menu")[0]       # có trong menu thả xuống
    assert "Xem3d" in lsp and "(c:SN_XEM3D)" in lsp                                             # và menu dòng lệnh SN
    assert "xem3d" in CN.LENH


# =========================================================================== osnap (tĩnh)
def test_lisp_moi_lan_chon_diem_deu_qua_sn_lay_diem():
    lsp = (Path(__file__).resolve().parents[2] / "cad" / "lisp" / "sannen.lsp").read_text(encoding="utf-8")
    ngoai = re.sub(r"\(defun sn:lay-diem .*?\n\n", "", lsp, flags=re.S)
    assert "(getpoint" not in ngoai, "còn getpoint trần — osnap Intersection trên đám 3D dày sẽ treo"
    assert lsp.count("(sn:lay-diem ") >= 9
    assert "(logior osm 16384)" in lsp and '(setvar "OSMODE" osm)' in lsp and "đã tạm tắt osnap" in lsp


# =========================================================================== (c) AutoCAD thật (accoreconsole)
@can_acore
def test_acad_polyface_mot_polyline_moi_be_mat_xdata_purge_va_ve_hai_lan(lo, tmp_path):
    ok, tb, du, lsp = chay_cn(tmp_path, lo, "tin3d", "--be-mat", "ca-hai", lsp=True)
    assert ok, tb
    doc, _ = _chay_acore(tmp_path, [lsp], base=lo.input_dir / "gt.dxf")
    for nhan, ly in (("moc", "SN-3DF-MOC"), ("do", "SN-3DF-DO")):
        tot, _ = tam_giac_tot_xau(lo, nhan)
        assert dem_layer(doc, ly) == 1 and dem_layer(doc, ly, "POLYLINE") == 1
        assert so_mat_polyface(doc, ly) == tot
        pf = polyface_cua(doc, ly)[0]
        n = BackendDXF.doc_nhan(pf)                                            # XDATA "SANNEN" gắn trên POLYLINE
        assert n["ma_lo"] == "GT-01" and n["loai"] == "mat_3d" and n["be_mat"] == nhan and int(n["so_mat"]) == tot
    # nạp ba lần trong một phiên và ở phiên sau: vẫn đúng 1 polyface/bề mặt
    d3, _ = _chay_acore(tmp_path, [lsp, lsp, lsp], base=lo.input_dir / "gt.dxf")
    assert dem_layer(d3, "SN-3DF-MOC", "POLYLINE") == 1 and dem_layer(d3, "SN-3DF-DO", "POLYLINE") == 1
    ra1 = tmp_path / "p1.dxf"
    doc.saveas(ra1)
    d4, _ = _chay_acore(tmp_path, [lsp], base=ra1)
    assert dem_layer(d4, "SN-3DF-MOC", "POLYLINE") == 1 and so_mat_polyface(d4, "SN-3DF-MOC") == so_mat_polyface(doc, "SN-3DF-MOC")
    # mặt 3D còn tắt/bật đúng, màu mới
    assert not doc.layers.get("SN-3DF-MOC").is_off() and doc.layers.get("SN-3DF-MOC").color == 3
    assert doc.layers.get("SN-3DF-DO").color == 2
    # backend DXF đọc được dấu truy vết của polyface do AutoCAD vẽ và purge xóa sạch
    be = BackendDXF(ra1, tmp_path / "x.dxf")
    r = be.cad_purge_sn("GT-01", 1, xem_truoc=False, loai=("mat_3d", "qc"))
    assert r["so_xoa"] >= 2 and not [e for e in be.msp if e.dxftype() == "POLYLINE"]


@can_acore
def test_acad_chi_dat_mot_be_mat_roi_doi_sang_mat_kia(lo, tmp_path):
    sinh = lambda *a: chay_cn(tmp_path, lo, *a, lsp=True)[3]
    moc, do = sinh("tin3d", "--be-mat", "moc"), sinh("tin3d", "--be-mat", "do")
    d, _ = _chay_acore(tmp_path, [moc, do], base=lo.input_dir / "gt.dxf")
    assert dem_layer(d, "SN-3DF-MOC") == 0 and dem_layer(d, "SN-3DF-DO", "POLYLINE") == 1     # đổi mặt: purge mặt cũ
    assert d.layers.get("SN-3DF-MOC").is_off() and not d.layers.get("SN-3DF-DO").is_off()


@can_acore
def test_acad_chia_khoi_polyface_that(tmp_path):
    be = BackendLisp()
    be.toi_da_dinh = 300
    tg = luoi_tam_giac(30)                                                     # 961 đỉnh → nhiều khối
    r = be.cad_draw_3dface("LK", 1, "h", "moc", tg, "mat", xem_truoc=False, dang="polyface")
    f = tmp_path / "k.lsp"
    be.luu(f)
    d, _ = _chay_acore(tmp_path, [f])
    assert dem_layer(d, "SN-3DF-MOC", "POLYLINE") == r["so_polyface"] >= 4 and so_mat_polyface(d, "SN-3DF-MOC") == len(tg)


@can_acore
def test_acad_lisp_bbox_polyface_bo_mat_ao_va_hop_bao_lo(tmp_path):
    be = BackendLisp()
    be.cad_draw_3dface("LB", 1, "h", "moc", [[[100, 200, 5], [110, 200, 5], [100, 220, 6]], [[110, 200, 5], [110, 220, 6], [100, 220, 6]]],
                       "mat", xem_truoc=False, dang="polyface")
    be.cad_draw_grid("LB", 1, "h", {"goc_luoi": [100, 200], "goc_xoay_do": 0, "cot_m": [10], "hang_m": [20]}, xem_truoc=False)
    be.ve_ent("LB", 1, "h", "mat_cat", "SN-MATCAT", [("doan", 90, -50, 95, -60)], False, ten="T1")
    be.ve_ent("LB", 1, "h", "mat_cat", "SN-MATCAT", [("doan", 80, -300, 85, -310)], False, ten="T2")
    be.ve_ent("KHAC", 1, "h", "bang", "SN-BANG", [("doan", 0, -999, 1, -1000)], False)
    f = tmp_path / "b.lsp"
    be.luu(f)
    ma = mo_dau() + f'(load "{f.as_posix()}")\n' + r'''
(setq e (ssname (ssget "X" '((0 . "POLYLINE"))) 0))
(setq bb (sn:bbox e))
(t! "bbox-polyface" (and (equal (car (car bb)) 100.0 1e-6) (equal (cadr (car bb)) 200.0 1e-6)
                         (equal (car (cadr bb)) 110.0 1e-6) (equal (cadr (cadr bb)) 220.0 1e-6)))
(setq h (sn:hop-bao-lo "LB" "T2"))        ; không tính mặt 3D, không tính mặt cắt T2, không tính lô KHAC
(t! "hbl-x" (and (equal (car (car h)) 90.0 1e-6) (equal (car (cadr h)) 110.0 1e-6)))
(t! "hbl-y" (and (equal (cadr (car h)) -60.0 1e-6) (equal (cadr (cadr h)) 220.0 1e-6)))
(setq h2 (sn:hop-bao-lo "LB" "T1"))        ; bỏ T1 thì T2 tính
(t! "hbl-y2" (equal (cadr (car h2)) -310.0 1e-6))
(t! "hbl-rong" (null (sn:hop-bao-lo "KHONG-CO" "x")))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    assert kq, txt[-2500:]
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))


@can_acore
def test_acad_chi_hien_3d_tat_bat_layer_va_khoi_phuc_dung(tmp_path):
    ma = mo_dau() + r'''
(sn:lop "A" 1) (sn:lop "B" 2) (sn:lop "SN-3DF-MOC" 3) (sn:lop "SN-QC" 6) (sn:lop "SN-LUOI" 8)
(sn:lop-bat "B" nil)                                   ; B đã tắt từ trước — KHÔNG được bật lại khi khôi phục
(defun on-p (n) (>= (cdr (assoc 62 (entget (tblobjname "LAYER" n)))) 0))
(setq *sn-lop-an* nil)
(setq n (sn:chi-hien-3d))
(t! "chi-hien-bat-3d" (and (on-p "SN-3DF-MOC") (on-p "SN-QC")))
(t! "tat-lop-khac" (and (not (on-p "A")) (not (on-p "SN-LUOI"))))
(t! "b-van-tat" (not (on-p "B")))
(t! "layer-0-va-clayer" (equal (strcase (getvar "CLAYER")) "0"))
(t! "dem" (and (= n (length *sn-lop-an*)) (member "A" *sn-lop-an*) (member "SN-LUOI" *sn-lop-an*) (not (member "B" *sn-lop-an*))))
(t! "khong-xoa-khong-bang" (and (tblsearch "LAYER" "A") (zerop (logand 1 (cdr (assoc 70 (tblsearch "LAYER" "A")))))))
(t! "lop-3d-p" (and (sn:lop-3d-p "SN-3DF-DO-D02") (sn:lop-3d-p "SN-QC") (not (sn:lop-3d-p "SN-LUOI"))))
;; chạy lần hai khi đã ẩn: không ghi đè danh sách cũ bằng danh sách rỗng
(sn:chi-hien-3d)
(t! "lan-hai-giu-danh-sach" (and (member "A" *sn-lop-an*) (member "SN-LUOI" *sn-lop-an*)))
;; danh sách lưu trong CHÍNH bản vẽ: mất biến vẫn khôi phục được
(setq *sn-lop-an* nil)
(t! "doc-tu-ban-ve" (and (member "A" (sn:doc-lop-an)) (member "SN-LUOI" *sn-lop-an*)))
(setq k (sn:khoi-phuc-lop))
(t! "khoi-phuc-dung" (and (on-p "A") (on-p "SN-LUOI") (not (on-p "B")) (= k n)))
(t! "danh-sach-sach" (and (null *sn-lop-an*) (null (sn:doc-lop-an))))
;; layer bị xóa giữa chừng thì bỏ qua, không lỗi
(sn:chi-hien-3d)
(setq *sn-lop-an* (append *sn-lop-an* (list "KHONG-CO"))) (sn:luu-lop-an)
(setq k2 (vl-catch-all-apply 'sn:khoi-phuc-lop nil))
(t! "layer-khong-ton-tai" (and (not (vl-catch-all-error-p k2)) (on-p "A") (= k2 2)))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))


@can_acore
def test_acad_osnap_tam_tat_roi_khoi_phuc_ke_ca_khi_loi(tmp_path):
    f = tmp_path / "t.lsp"
    f.write_text(mo_dau() + r'''
(setvar "OSMODE" 183)
(setq *sn-da-bao-osnap* nil)
(princ "\n@@truoc=OK")
''', encoding="utf-8")
    scr = tmp_path / "t.scr"
    # dòng 1 nạp; dòng 2 gọi sn:lay-diem → getpoint nhận điểm từ dòng kế tiếp; dòng 4 ép LỖI (base không phải điểm)
    scr.write_text("\n".join([
        f'(load "{f.as_posix()}")',
        '(setq p (sn:lay-diem "\\nChon diem: " nil))',
        "10,20",
        '(princ (strcat "\\n@@diem=" (if (equal p (list 10.0 20.0 0.0) 1e-9) "OK" "FAIL") "\\n@@osm1=" (itoa (getvar "OSMODE"))))',
        '(setq q (sn:lay-diem "\\nLoi: " "khong-phai-diem"))',
        '(princ (strcat "\\n@@loi=" (if (null q) "OK" "FAIL") "\\n@@osm2=" (itoa (getvar "OSMODE"))))',
        '(setvar "OSMODE" 16384)',
        '(setq r (sn:lay-diem "\\nChon: " nil))',
        "1,2",
        '(princ (strcat "\\n@@osm3=" (itoa (getvar "OSMODE"))))',
        "_.QUIT", "Y", ""]), encoding="utf-8")
    import subprocess
    p = subprocess.run([str(ACORE), "/s", str(scr), "/l", "en-US"], capture_output=True, timeout=180, stdin=subprocess.DEVNULL)
    b = p.stdout
    txt = b.decode("utf-16-le", "replace") if b"\x00" in b[:400] else b.decode("utf-8", "replace")
    kq = {}
    for k, v in re.findall(r"@@([\w:\-]+)=([\w\-]+)", txt):
        kq.setdefault(k, v)
    assert kq.get("diem") == "OK" and kq.get("osm1") == "183", txt[-1200:]       # chọn xong: OSMODE như cũ
    assert kq.get("loi") == "OK" and kq.get("osm2") == "183"                     # lỗi giữa chừng: vẫn khôi phục
    assert kq.get("osm3") == "16384"                                             # osnap vốn đã tắt: giữ nguyên
    assert "osnap" in txt                                                        # dòng lệnh nói rõ đã tạm tắt osnap


@can_acore
def test_acad_wrap_dong_dai_khong_bi_cat(tmp_path):
    ma = mo_dau() + r'''
(setq s "Mặt 3D tắt sẵn trong bản vẽ; nút Hiển thị sẽ vẽ (nếu chưa có), bật lớp, đổi góc nhìn và lưu view SN_TIN3D rất dài dòng thêm nữa")
(setq ds (sn:wrap s 40))
(t! "wrap-dong-ngan" (apply 'and (mapcar '(lambda (d) (<= (strlen d) 40)) ds)))
(t! "wrap-du-chu" (= (apply 'strcat (mapcar '(lambda (d) (strcat d " ")) ds)) (strcat s " ")))
(t! "wrap-nhieu-dong" (> (length ds) 2))
(t! "wrap-rong" (null (sn:wrap "" 40)))
(t! "wrap-1-dong" (equal (sn:wrap "ngắn" 40) '("ngắn")))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma))


@can_acore
def test_acad_view_va_zoom_polyface_khong_treo(lo, tmp_path):
    """-VIEW (SWISO, Save) và ZOOM Object lên polyface chạy được trong accoreconsole; VSCURRENT thì KHÔNG (cần giao diện)."""
    ok, tb, du, lsp = chay_cn(tmp_path, lo, "tin3d", "--be-mat", "ca-hai", lsp=True)
    ma = mo_dau() + f'(load "{lsp.as_posix()}")\n' + r'''
(sn:xem-3d "1" "0" "ca")
(t! "view-da-luu" (not (null (tblsearch "VIEW" "SN_TIN3D"))))
(sn:xem-3d "1" "0" "ca")                    ; lưu lại lần hai: thay, không lỗi
(t! "view-hai-lan" (not (null (tblsearch "VIEW" "SN_TIN3D"))))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path), timeout=120)
    assert str(kq.get("view-da-luu")).startswith("OK") and str(kq.get("view-hai-lan")).startswith("OK"), txt[-1500:]   # (echo của lệnh có thể dính "_" sau OK)
