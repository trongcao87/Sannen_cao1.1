"""Giai đoạn 8 — lớp CAD (backend DXF). Điều kiện qua cửa: vẽ vào bản vẽ thật rồi purge sạch,
chạy hai lần không đè nhau."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import ezdxf
import pytest

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE.parent / "cad"))
from sannen import cli, dxfio                                       # noqa: E402
from sannen.mcp_stdio import xu_ly                                  # noqa: E402
from sannen_cad import mcp_cad_server                               # noqa: E402
from sannen_cad.backend import CONG_CU_GHI, LAYER_KET_QUA, TEN_CONG_CU   # noqa: E402
from sannen_cad.backend_com import BackendCOM                       # noqa: E402
from sannen_cad.backend_dxf import BackendDXF                       # noqa: E402
from sannen_cad.ve import ve_ket_qua                                # noqa: E402
from lot_giai_tich import E0, N0, chay_het, hcn, tao                # noqa: E402

F_DO = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)


@pytest.fixture
def lo(tmp_path):
    l = tao(tmp_path / "lot", [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, [hcn(30, 20, 60, 40)], so_diem=1500)
    chay_het(l, "--sweep")
    assert cli.main(["xuat", "--lot", str(l.root)]) == 0
    return l


def be_moi(l, ten="ra.dxf", vao=None):
    return BackendDXF(vao or (l.input_dir / "gt.dxf"), l.root.parent / ten)


def dem_theo_layer(doc) -> dict[str, int]:
    d: dict[str, int] = {}
    for e in doc.modelspace():
        d[e.dxf.layer] = d.get(e.dxf.layer, 0) + 1
    return d


def dem_nguon(doc) -> dict:
    return {k: v for k, v in dem_theo_layer(doc).items() if not k.startswith("SN-LUOI") and
            not k.startswith(("SN-3DF", "SN-QC", "SN-BANG", "SN-RANH"))}


# ------------------------------------------------------------------ hợp đồng
def test_dung_13_cong_cu_va_7_cong_cu_ghi():
    assert len(TEN_CONG_CU) == 13 and len(CONG_CU_GHI) == 7           # 5 đọc + 7 ghi + 1 điều hướng
    assert set(CONG_CU_GHI) <= set(TEN_CONG_CU)
    assert set(TEN_CONG_CU) == set(mcp_cad_server._MO_TA)
    from sannen_cad.backend import Backend
    assert {n for n in dir(Backend) if n.startswith("cad_")} == set(TEN_CONG_CU)


def test_tam_giac_thieu_du_lieu_len_layer_sn_qc(lo):
    be = be_moi(lo)
    be.cad_draw_3dface("GT-01", 1, "h", "do", [[[E0, N0, 1], [E0 + 5, N0, 1], [E0, N0 + 5, 1]]], "qc", xem_truoc=False)
    assert dem_theo_layer(be.doc)["SN-QC"] == 1
    assert be.doc.layers.get("SN-QC").is_off() is False                  # QC phải thấy ngay, khác mặt 3D


def test_ve_ra_du_layer_xrecord_va_giu_nguyen_nguon(lo):
    be = be_moi(lo)
    truoc = dem_nguon(be.doc)
    kq = ve_ket_qua(be, lo.root)
    doc = ezdxf.readfile(be.ra)
    theo = dem_theo_layer(doc)
    for ly in LAYER_KET_QUA:
        if ly in ("SN-QC", "SN-MATCAT"):        # QC: lô sạch không có tam giác thiếu dữ liệu; MATCAT: chỉ có khi người tạo mặt cắt
            assert theo.get(ly, 0) == 0
            continue
        assert theo.get(ly, 0) > 0, f"thiếu layer kết quả {ly}"
    assert dem_nguon(doc) == truoc                                     # nguồn nguyên vẹn
    vol = json.loads((lo.process_dir / "volume.json").read_text(encoding="utf-8"))
    g = json.loads((lo.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert theo["SN-LUOI-O"] == len(g["o"])
    assert theo["SN-LUOI"] == g["tham_so"]["nx"] + 1 + g["tham_so"]["ny"] + 1
    s_moc = json.loads((lo.process_dir / "surface_moc.json").read_text(encoding="utf-8"))
    assert theo["SN-3DF-MOC"] + theo.get("SN-QC", 0) >= len(s_moc["tam_giac"])
    assert theo["SN-RANH-DAODAP"] == len(vol["ranh_dao_dap"])
    assert doc.layers.get("SN-3DF-MOC").is_off() and doc.layers.get("SN-3DF-DO").is_off()   # tắt mặc định
    hash_tv = str(vol["hash_dau_vao"])[:16]
    for e in doc.modelspace():
        if e.dxf.layer in LAYER_KET_QUA:
            n = BackendDXF.doc_nhan(e)
            assert n and n["ma_lo"] == "GT-01" and n["dot"] == 1 and n["hash"] == hash_tv


def test_chay_hai_lan_khong_de_nhau(lo):
    be = be_moi(lo)
    ve_ket_qua(be, lo.root)
    m1 = dem_theo_layer(be.doc)
    ve_ket_qua(be, lo.root)                                             # lần hai trên cùng bản vẽ
    assert dem_theo_layer(be.doc) == m1
    # mở lại file kết quả rồi vẽ lần nữa (như người mở DWG đã vẽ và bảo agent vẽ lại)
    be2 = BackendDXF(be.ra, lo.root.parent / "ra2.dxf")
    ve_ket_qua(be2, lo.root)
    assert dem_theo_layer(be2.doc) == m1


def test_purge_sach_chi_xoa_ket_qua_cua_dung_lo_nay(lo):
    be = be_moi(lo)
    nguon = dem_nguon(be.doc)
    n_goc = sum(dem_theo_layer(be.doc).values())
    ve_ket_qua(be, lo.root)
    # một lô KHÁC cùng nằm trong bản vẽ
    be.cad_draw_grid("LO-KHAC", 1, "h", {"goc_luoi": [E0, N0], "goc_xoay_do": 0, "cot_m": [10], "hang_m": [10]},
                     xem_truoc=False)
    xem = be.cad_purge_sn("GT-01", 1, xem_truoc=True)                    # xem trước không xóa gì
    assert xem["so_xoa"] > 0 and xem["da_ghi"] is False
    tong_truoc = sum(dem_theo_layer(be.doc).values())
    be.cad_purge_sn("GT-01", 1, xem_truoc=False)
    theo = dem_theo_layer(be.doc)
    assert sum(theo.values()) == n_goc + 4                                # chỉ còn nguồn + 4 đường lưới lô khác
    assert dem_nguon(be.doc) == nguon
    assert theo["SN-LUOI"] == 4 and tong_truoc > n_goc + 4
    assert sum(1 for _ in be._doi_tuong_ket_qua("GT-01")) == 0


def test_nhieu_dot_dung_hau_to_layer_va_purge_theo_dot(lo):
    be = be_moi(lo)
    lu = {"goc_luoi": [E0, N0], "goc_xoay_do": 0, "cot_m": [10, 10], "hang_m": [10]}
    be.cad_draw_grid("GT-01", 1, "h1", lu, xem_truoc=False)
    be.cad_draw_grid("GT-01", 3, "h3", lu, xem_truoc=False)
    theo = dem_theo_layer(be.doc)
    assert theo["SN-LUOI"] == 5 and theo["SN-LUOI-D03"] == 5
    be.cad_purge_sn("GT-01", 3, xem_truoc=False)
    theo = dem_theo_layer(be.doc)
    assert theo["SN-LUOI"] == 5 and "SN-LUOI-D03" not in {k for k, v in theo.items() if v}


def test_xem_truoc_khong_ghi_gi(lo):
    be = be_moi(lo)
    truoc = dem_theo_layer(be.doc)
    kq = ve_ket_qua(be, lo.root, xem_truoc=True)
    assert dem_theo_layer(be.doc) == truoc and not be.ra.exists()
    assert kq["luoi"]["xem_truoc"] is True and kq["luoi"]["so_duong"] > 0


def test_khong_duoc_ghi_de_dxf_dau_vao(lo):
    with pytest.raises(ValueError, match="RULES 3"):
        BackendDXF(lo.input_dir / "gt.dxf", lo.input_dir / "gt.dxf")
    be = be_moi(lo)
    with pytest.raises(ValueError, match="RULES 3"):
        be.cad_export_dxf(str(lo.input_dir / "gt.dxf"))


# ------------------------------------------------------------------ vòng hiệu chỉnh bằng mắt
def test_sua_tay_nhan_trong_cad_roi_resync_ve_he_thong(lo, capsys):
    be = be_moi(lo)
    ve_ket_qua(be, lo.root)
    doc = ezdxf.readfile(be.ra)                                         # người mở bản vẽ, sửa tay một nhãn
    muc_tieu = None
    for e in doc.modelspace():
        if e.dxf.layer == "SN-LUOI-NHAN":
            n = BackendDXF.doc_nhan(e)
            if n["ma"] == "D03-02" and n["be_mat"] == "do":
                muc_tieu = e
                z_cu = float(e.dxf.text)
                e.dxf.text = f"{z_cu + 0.250:.3f}"
    assert muc_tieu is not None
    sua = lo.root.parent / "sua_tay.dxf"
    doc.saveas(sua)

    be2 = BackendDXF(sua, lo.root.parent / "ra3.dxf")
    z = {(x["ma"], x["be_mat"]): x["z"] for x in be2.cad_read_grid_z("GT-01", 1)}
    assert z[("D03-02", "do")] == pytest.approx(z_cu + 0.25, abs=1e-9)
    tep = lo.root.parent / "nhan_cad.json"
    tep.write_text(json.dumps([{"ma": m, "be_mat": b, "z": v} for (m, b), v in z.items()]), encoding="utf-8")

    capsys.readouterr()
    assert cli.main(["luoi", "--lot", str(lo.root), "--resync", "--tu-file", str(tep)]) == 1    # báo trước
    ra = capsys.readouterr().out
    assert "1 đỉnh trong bản vẽ KHÁC" in ra and "D03-02" in ra and "Chưa nhận" in ra           # chỉ đúng 1 đỉnh lệch
    assert "9.7000" in ra and "9.9500" in ra                                                    # số hệ thống và số bản vẽ
    assert cli.main(["luoi", "--lot", str(lo.root), "--resync", "--tu-file", str(tep), "--chap-nhan"]) == 0
    adj = json.loads((lo.process_dir / "grid_adjusted.json").read_text(encoding="utf-8"))["ghi_de"]
    assert len(adj) == 1 and adj[0]["ma"] == "D03-02" and adj[0]["z_moi"] == pytest.approx(z_cu + 0.25)
    # tính lại với đỉnh mới rồi vẽ lại: nhãn cập nhật, KHÔNG nhân đôi
    assert cli.main(["tinh", "--lot", str(lo.root)]) in (0, 1)
    n_truoc = sum(1 for _ in be2._doi_tuong_ket_qua("GT-01"))
    ve_ket_qua(be2, lo.root)
    assert sum(1 for _ in be2._doi_tuong_ket_qua("GT-01")) == n_truoc


def test_cap_nhat_nhan_dinh_tai_cho_khong_tao_trung(lo):
    be = be_moi(lo)
    nut = [{"ma": "D01-01", "e": E0, "n": N0, "z_moc": 1.0, "z_do": 2.0}]
    be.cad_set_vertex_z("GT-01", 1, "h", nut, xem_truoc=False)
    n1 = len(be.cad_read_grid_z("GT-01", 1))
    nut[0]["z_do"] = 2.5
    kq = be.cad_set_vertex_z("GT-01", 1, "h", nut, xem_truoc=False)
    assert kq["nhan_moi"] == 0 and kq["nhan_cap_nhat"] == 3
    z = {(x["ma"], x["be_mat"]): x["z"] for x in be.cad_read_grid_z("GT-01", 1)}
    assert z[("D01-01", "do")] == 2.5 and len(z) == n1 == 2


# ------------------------------------------------------------------ đi vòng lại lõi
def test_dxf_ket_qua_doc_lai_bang_nhap_khong_vo_layer_la(lo):
    be = be_moi(lo)
    ve_ket_qua(be, lo.root)
    goc = dxfio.doc(lo.input_dir / "gt.dxf")
    lai = dxfio.doc(be.ra)                                               # layer SN-LUOI*, SN-3DF*... đều hợp lệ
    assert len(lai.diem_moc) == len(goc.diem_moc) and len(lai.diem_do) == len(goc.diem_do)
    assert len(lai.bien_lo) == len(goc.bien_lo)


# ------------------------------------------------------------------ MCP CAD
def test_mcp_cad_phoi_dung_13_cong_cu_va_mac_dinh_xem_truoc(lo):
    be = be_moi(lo)
    bang = {c.ten: c for c in mcp_cad_server.tao_cong_cu(be)}
    assert list(bang) == list(TEN_CONG_CU)
    r = xu_ly({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "cad", "1", bang)
    assert len(r["result"]["tools"]) == 13
    assert all("[GHI" in t["description"] for t in r["result"]["tools"] if t["name"] in CONG_CU_GHI)
    luoi = {"goc_luoi": [E0, N0], "goc_xoay_do": 0, "cot_m": [10], "hang_m": [10]}
    truoc = dem_theo_layer(be.doc)
    r = xu_ly({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "cad_draw_grid", "arguments": {"ma_lo": "X", "dot": 1, "hash_tv": "h", "luoi": luoi}}}, "cad", "1", bang)
    assert json.loads(r["result"]["content"][0]["text"])["xem_truoc"] is True      # không nói gì → xem trước
    assert dem_theo_layer(be.doc) == truoc
    xu_ly({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "cad_draw_grid", "arguments": {"ma_lo": "X", "dot": 1, "hash_tv": "h", "luoi": luoi,
                                               "xem_truoc": False}}}, "cad", "1", bang)
    assert dem_theo_layer(be.doc)["SN-LUOI"] == 4
    info = json.loads(bang["cad_doc_info"].ham({})[0])
    assert info["lo_da_ve"] == {"X/đợt 1": 4} and info["so_doi_tuong_sn"] > 0
    pts = json.loads(bang["cad_read_points"].ham({"layer": "SN-DIEM-MOC"})[0])
    assert len(pts) > 1000 and len(pts[0]) == 3


def test_zoom_va_xuat_dxf(lo):
    be = be_moi(lo)
    assert be.cad_zoom_to(E0 + 10, N0 + 10, 30.0)["e"] == E0 + 10
    kq = be.cad_export_dxf(str(lo.root.parent / "xuat.dxf"))
    assert Path(kq["da_ghi"]).exists()


def test_backend_com_chua_cai_noi_that_thay_vi_gia_vo():
    with pytest.raises(NotImplementedError, match="AutoCAD 2022"):
        BackendCOM()
