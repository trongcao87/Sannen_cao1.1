"""Giai đoạn 7 — MCP server bọc CLI. Điều kiện qua cửa: agent chạy trọn một lô, dừng đúng 3 cổng."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
from sannen import mcp_server as M                                # noqa: E402
from sannen.mcp_stdio import xu_ly                                # noqa: E402
from lot_giai_tich import E0, N0, hcn, tao                        # noqa: E402

pytestmark = pytest.mark.cong_that                                # MCP + chốt của CLI đều thật

F_DO = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)


def tool(ten: str):
    return {c.ten: c for c in M.danh_sach_cong_cu()}[ten].ham


def goi(ten, **a):
    return tool(ten)(a)


def lot_moi(tmp_path):
    return tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, [hcn(30, 20, 60, 40)], so_diem=1500)


# ------------------------------------------------------------------ giao thức
def test_giao_thuc_initialize_list_call():
    bang = {c.ten: c for c in M.danh_sach_cong_cu()}
    r = xu_ly({"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {}}}, "x", "1", bang)
    assert r["result"]["protocolVersion"] == "2024-11-05" and "tools" in r["result"]["capabilities"]
    assert xu_ly({"jsonrpc": "2.0", "method": "notifications/initialized"}, "x", "1", bang) is None
    r = xu_ly({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, "x", "1", bang)
    ten = {t["name"] for t in r["result"]["tools"]}
    assert {"sannen_trang_thai", "sannen_doc_viec", "sannen_duyet_cong", "sannen_ghi_quyet_dinh",
            "sannen_thong_tin", "sannen_canh_bao", "sannen_ra_soat_phuong_an", "sannen_ve"} | {
        f"sannen_{v}" for v in ("nhap", "mat", "lo", "luoi", "hieuchinh", "tinh", "xuat")} == ten
    for t in r["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object" and "lot" in t["inputSchema"]["required"]
    loi = xu_ly({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "khong_co"}}, "x", "1", bang)
    assert loi["error"]["code"] == -32602
    loi = xu_ly({"jsonrpc": "2.0", "id": 4, "method": "foo"}, "x", "1", bang)
    assert loi["error"]["code"] == -32601


def test_cong_cu_loi_khong_lam_sap_may_chu(tmp_path):
    bang = {c.ten: c for c in M.danh_sach_cong_cu()}
    r = xu_ly({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
               "params": {"name": "sannen_trang_thai", "arguments": {"lot": str(tmp_path / "khong_co")}}}, "x", "1", bang)
    assert r["result"]["isError"] is True and "lot.yaml" in r["result"]["content"][0]["text"]


def test_tien_trinh_con_stdio_that(tmp_path):
    """Chạy `python -m sannen.mcp_server` như một MCP client thật: dòng JSON vào, dòng JSON ra."""
    l = lot_moi(tmp_path)
    yc = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
          {"jsonrpc": "2.0", "method": "notifications/initialized"},
          {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
           "params": {"name": "sannen_trang_thai", "arguments": {"lot": str(l.root)}}}]
    p = subprocess.run([sys.executable, "-X", "utf8", "-m", "sannen.mcp_server"], cwd=CORE, text=True,
                       encoding="utf-8", input="\n".join(json.dumps(x) for x in yc) + "\n",
                       capture_output=True, timeout=60)
    ra = [json.loads(x) for x in p.stdout.splitlines()]
    assert len(ra) == 2 and ra[0]["id"] == 1 and ra[1]["id"] == 2        # thông báo không có phản hồi
    tt = json.loads(ra[1]["result"]["content"][0]["text"])
    assert tt["buoc_ke_tiep"] == "nhap" and tt["cong"]["1"]["da_duyet"] is False


# ------------------------------------------------------------------ ba cổng
def test_agent_chay_tron_mot_lo_va_bi_chan_dung_ba_cong(tmp_path):
    l = lot_moi(tmp_path)
    lot = str(l.root)
    tu_choi = 0

    def chay(ten, **a):
        nonlocal tu_choi
        van_ban, loi = goi(ten, lot=lot, **a)
        if van_ban.startswith("TỪ CHỐI"):
            tu_choi += 1
        return van_ban, loi

    assert json.loads(goi("sannen_trang_thai", lot=lot)[0])["buoc_ke_tiep"] == "nhap"
    # xem trước luôn được chạy, không cần duyệt
    t, loi = chay("sannen_nhap")
    assert not t.startswith("TỪ CHỐI") and "XEM TRƯỚC" in t
    t, _ = chay("sannen_nhap", preview=False)
    assert "Đã ghi 7 file" in t and "CỔNG 1" in t

    # ---- cổng 1
    t, loi = chay("sannen_mat", preview=False)
    assert t.startswith("TỪ CHỐI") and "Cổng 1" in t and loi
    t, loi = goi("sannen_duyet_cong", lot=lot, cong=1, nguoi_duyet="QS A", bang_chung="")
    assert loi and "Agent không được tự duyệt" in t                      # không có bằng chứng thì không duyệt
    t, loi = goi("sannen_duyet_cong", lot=lot, cong=1, nguoi_duyet="QS A", bang_chung="OK, dữ liệu dùng được")
    assert not loi
    assert not chay("sannen_mat", preview=False)[1] and not chay("sannen_lo", preview=False)[1]

    # ---- cổng 2
    t, loi = chay("sannen_luoi", preview=False)
    assert t.startswith("TỪ CHỐI") and "Cổng 2" in t
    t, loi = chay("sannen_tinh", preview=False)
    assert t.startswith("TỪ CHỐI")
    goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS A", bang_chung="Bề mặt ổn, đặt lưới 20 m")
    assert not chay("sannen_luoi", preview=False)[1]
    assert not chay("sannen_tinh", preview=False, sweep=False)[1]

    # ---- cổng 3
    t, loi = chay("sannen_xuat", preview=False)
    assert t.startswith("TỪ CHỐI") and "Cổng 3" in t
    t, loi = chay("sannen_xuat")                                          # xem trước vẫn chạy
    assert not t.startswith("TỪ CHỐI")
    goi("sannen_duyet_cong", lot=lot, cong=3, nguoi_duyet="QS A", bang_chung="Số liệu chấp nhận")
    t, loi = chay("sannen_xuat", preview=False)
    assert not loi and (l.output_dir / "phieu_truy_vet.json").exists()

    assert tu_choi >= 3                                                   # đúng ba cổng đã chặn
    dec = (l.log_dir / "decisions.md").read_text(encoding="utf-8")
    assert dec.count("duyệt:") == 3 and "Số liệu chấp nhận" in dec         # mỗi cổng một dòng có nguyên văn
    tt = json.loads(goi("sannen_trang_thai", lot=lot)[0])
    assert tt["buoc_ke_tiep"] is None and all(c["da_duyet"] for c in tt["cong"].values())
    assert "so_nop" in tt


def chuan_bi_den_cong2(tmp_path):
    l = lot_moi(tmp_path)
    lot = str(l.root)
    goi("sannen_nhap", lot=lot, preview=False)
    goi("sannen_duyet_cong", lot=lot, cong=1, nguoi_duyet="QS", bang_chung="ok")
    goi("sannen_mat", lot=lot, preview=False)
    goi("sannen_lo", lot=lot, preview=False)
    return l, lot


def test_phe_duyet_mat_hieu_luc_khi_ket_qua_doi(tmp_path):
    l, lot = chuan_bi_den_cong2(tmp_path)
    t, loi = goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="ok")
    assert not loi
    with (l.process_dir / "surface_moc.json").open("a", encoding="utf-8") as f:
        f.write(" ")                                                      # kết quả đã duyệt bị đổi
    t, loi = goi("sannen_luoi", lot=lot, preview=False)
    assert loi and t.startswith("TỪ CHỐI") and "mất hiệu lực" in t


def test_khong_duyet_duoc_khi_con_viec_chan(tmp_path):
    l, lot = chuan_bi_den_cong2(tmp_path)
    p = l.process_dir / "qc_surface.json"
    q = json.loads(p.read_text(encoding="utf-8"))
    q["phat_hien"].append({"ma": "M-99", "muc": "chan", "mo_ta": "đứt gãy mâu thuẫn"})
    p.write_text(json.dumps(q), encoding="utf-8")
    t, loi = goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="ok")
    assert loi and "CHẶN" in t and "M-99" in t
    assert not (l.log_dir / "cong.json").exists() or "2" not in json.loads(
        (l.log_dir / "cong.json").read_text(encoding="utf-8"))


def test_hieuchinh_sau_cong_3_lam_mat_hieu_luc_cong_3(tmp_path):
    l, lot = chuan_bi_den_cong2(tmp_path)
    goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="ok")
    goi("sannen_luoi", lot=lot, preview=False)
    goi("sannen_tinh", lot=lot, preview=False)
    goi("sannen_duyet_cong", lot=lot, cong=3, nguoi_duyet="QS", bang_chung="ok")
    goi("sannen_hieuchinh", lot=lot, preview=False, dinh="D02-02", z=12.0)
    t, loi = goi("sannen_xuat", lot=lot, preview=False)
    assert t.startswith("TỪ CHỐI") and "mất hiệu lực" in t
    goi("sannen_tinh", lot=lot, preview=False)                             # tính lại với đỉnh mới
    t, _ = goi("sannen_xuat", lot=lot, preview=False)
    assert t.startswith("TỪ CHỐI")                                         # vẫn phải duyệt lại số mới
    goi("sannen_duyet_cong", lot=lot, cong=3, nguoi_duyet="QS", bang_chung="ok lần hai")
    t, loi = goi("sannen_xuat", lot=lot, preview=False)
    assert not loi and "Đã ghi" in t


def test_chay_lai_giu_nguyen_phe_duyet_nho_deterministic(tmp_path):
    """Chạy lại mat/lo ra kết quả y hệt thì phê duyệt cổng 2 còn nguyên — không bắt người duyệt lại vô cớ."""
    l, lot = chuan_bi_den_cong2(tmp_path)
    goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="ok")
    goi("sannen_mat", lot=lot, preview=False)
    goi("sannen_lo", lot=lot, preview=False)
    assert M.cong_da_duyet(l, 2)[0] is True


def test_preview_khong_can_cong_va_ghi_quyet_dinh(tmp_path):
    l = lot_moi(tmp_path)
    lot = str(l.root)
    t, _ = goi("sannen_mat", lot=lot)                                      # preview, chưa nhap, chưa duyệt gì
    assert not t.startswith("TỪ CHỐI")
    t, loi = goi("sannen_ghi_quyet_dinh", lot=lot, ma_viec="V-03", lua_chon="b", ghi_chu="bỏ điểm P00012")
    assert not loi
    assert "V-03 → b — bỏ điểm P00012" in (l.log_dir / "decisions.md").read_text(encoding="utf-8")
    assert goi("sannen_ghi_quyet_dinh", lot=lot, ma_viec="V-03")[1] is True


def test_nhap_excel_chua_xac_nhan_thi_dung_o_mcp(tmp_path):
    """Qua MCP, ánh xạ cột đề xuất không tự thành xác nhận: agent nhận mã 2 và phải hỏi người."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import make_fixture
    from sannen.paths import Lot
    l = Lot(tmp_path)
    l.ensure()
    l.lot_yaml.write_text("ma_lo: X\ndot: 1\nhe_toa_do: VN-2000\nphuong_phap_chinh_thuc: luoi_o_vuong\n"
                          "be_mat_moc: {nguon: excel, file: moc.xlsx}\nbe_mat_do: {nguon: excel, file: do.xlsx}\n"
                          "luoi: {kich_thuoc_o_m: 20, goc_xoay_do: 0}\n", encoding="utf-8")
    make_fixture.tao_xlsx(l.input_dir / "moc.xlsx", 150)
    make_fixture.tao_xlsx(l.input_dir / "do.xlsx", 150, seed=3, cai_loi=False)
    t, loi = goi("sannen_nhap", lot=str(l.root), preview=False)
    assert loi and "[mã thoát 2" in t and "CẦN NGƯỜI XÁC NHẬN" in t
    t, loi = goi("sannen_nhap", lot=str(l.root), preview=False, xac_nhan_anh_xa=True)
    assert not loi


def test_thong_tin_canh_bao_va_ve_y_dinh(tmp_path):
    """Ba công cụ MCP gộp theo ý định (Bước 3): sannen_thong_tin, sannen_canh_bao, sannen_ve."""
    l = lot_moi(tmp_path)
    lot = str(l.root)
    assert not goi("sannen_nhap", lot=lot, preview=False)[1]
    assert not goi("sannen_duyet_cong", lot=lot, cong=1, nguoi_duyet="QS", bang_chung="OK")[1]
    assert not goi("sannen_mat", lot=lot, preview=False)[1]
    assert not goi("sannen_lo", lot=lot, preview=False)[1]
    assert not goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="OK")[1]
    assert not goi("sannen_luoi", lot=lot, preview=False)[1]
    assert not goi("sannen_tinh", lot=lot, preview=False, sweep=False)[1]

    t, loi = goi("sannen_thong_tin", lot=lot)
    assert not loi
    tt = json.loads(t)
    assert tt["lo"]["ma_lo"] == "GT-01" and tt["so_lieu"]["khoiluong"]["co"] is True

    t, loi = goi("sannen_canh_bao", lot=lot)
    assert not loi and "phat_hien" in json.loads(t)

    # sannen_ve mặc định preview=True: không ghi file
    t, loi = goi("sannen_ve", lot=lot, lop=["luoi", "nhan"])
    assert not loi
    v = json.loads(t)
    assert v["preview"] is True and v["tom_tat"]["so_doi_tuong"] > 0
    assert not (l.output_dir / "ke_hoach_ve.json").exists()

    # preview=False: ghi file kế hoạch JSON
    t, loi = goi("sannen_ve", lot=lot, che_do="bang", loai="tong", preview=False)
    assert not loi and (l.output_dir / "ke_hoach_ve.json").exists()
    assert not loi


def test_agent_chi_chay_ra_soat_va_phuong_an_khi_be_mat_da_khoi_tao(tmp_path):
    """Agent chỉ chạy bước rà soát, chuẩn hóa và tạo nhiều phương án khi người dùng đã khởi tạo bề mặt thành công."""
    l = lot_moi(tmp_path)
    lot = str(l.root)
    # 1. Chưa khởi tạo bề mặt → TỪ CHỐI
    t, loi = goi("sannen_ra_soat_phuong_an", lot=lot)
    assert loi and t.startswith("TỪ CHỐI") and "CHƯA khởi tạo xong hai bề mặt" in t

    # 2. Mới chạy nhap, chưa dựng bề mặt → vẫn TỪ CHỐI
    goi("sannen_nhap", lot=lot, preview=False)
    t, loi = goi("sannen_ra_soat_phuong_an", lot=lot)
    assert loi and t.startswith("TỪ CHỐI")

    # 3. Người dùng khởi tạo bề mặt thành công (qua cau_noi khoi-tao-be-mat)
    sys.path.insert(0, str(CORE.parent / "cad"))
    from sannen_cad import cau_noi as CN
    ra = tmp_path / "kt_ra.json"
    assert CN.main(["khoi-tao-be-mat", "--lot", lot, "--json", "--ra", str(ra)]) == 0
    kq = json.loads(ra.read_text(encoding="utf-8"))
    assert kq["ok"] is True and "khởi tạo bề mặt thành công" in kq["thong_bao"]

    # 4. Bề mặt đã khởi tạo → Agent chạy rà soát, chuẩn hóa, quét phương án thành công
    tt = json.loads(goi("sannen_trang_thai", lot=lot)[0])
    assert tt["be_mat_da_khoi_tao"] is True and tt["san_sang_agent_ra_soat"] is True
    t, loi = goi("sannen_ra_soat_phuong_an", lot=lot, preview=True)
    assert not loi and "RÀ SOÁT CHẤT LƯỢNG BỀ MẶT & BIÊN LÔ" in t

    # Duyệt cổng 2 → chạy chính thức đặt lưới + quét ma trận phương án (--sweep)
    goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="Đã khởi tạo bề mặt ổn, chạy rà soát và phương án")
    t, loi = goi("sannen_ra_soat_phuong_an", lot=lot, preview=False)
    assert not loi and "SWEEP:" in t and (l.process_dir / "volume.json").exists()
    vol = json.loads((l.process_dir / "volume.json").read_text(encoding="utf-8"))
    assert "sweep" in vol and len(vol["sweep"]["A"]) >= 8 and len(vol["sweep"]["B"]) >= 5


def test_luoi_import_dxf_va_day_tu_chat_mcp(tmp_path):
    """Import lưới từ file DXF/JSON hoặc đẩy cấu hình cột/hàng từ cửa sổ Chat qua MCP."""
    import ezdxf
    l, lot = chuan_bi_den_cong2(tmp_path)
    goi("sannen_duyet_cong", lot=lot, cong=2, nguoi_duyet="QS", bang_chung="Duyệt bề mặt để đặt lưới từ DXF/MCP")

    # 1. Tạo file DXF chứa lưới 4 cột (25m) × 3 hàng (20m) tại gốc (E0, N0)
    dxf_luoi = tmp_path / "luoi_mau.dxf"
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("SN-LUOI")
    for i in range(5):
        x = E0 + i * 25.0
        msp.add_line((x, N0), (x, N0 + 60.0), dxfattribs={"layer": "SN-LUOI"})
    for j in range(4):
        y = N0 + j * 20.0
        msp.add_line((E0, y), (E0 + 100.0, y), dxfattribs={"layer": "SN-LUOI"})
    doc.saveas(dxf_luoi)

    # 2. Import lưới qua MCP sannen_luoi (tu_file_dxf)
    t, loi = goi("sannen_luoi", lot=lot, preview=False, tu_file_dxf=str(dxf_luoi))
    assert not loi and (l.root / "luoi_tuy_chinh.yaml").exists()
    g = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert g["tham_so"]["cot_m"] == [25.0] * 4 and g["tham_so"]["hang_m"] == [20.0] * 3

    # 3. Đẩy cấu hình cột/hàng tùy chỉnh từ Chat qua MCP (cot="5x20", hang="3x20")
    t, loi = goi("sannen_luoi", lot=lot, preview=False, cot="5x20", hang="3x20")
    assert not loi
    g2 = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert g2["tham_so"]["cot_m"] == [20.0] * 5 and g2["tham_so"]["hang_m"] == [20.0] * 3

    # 4. Cầu nối luoi-import-dxf --chi-doc cho hộp thoại AutoCAD SN_LUOI
    sys.path.insert(0, str(CORE.parent / "cad"))
    from sannen_cad import cau_noi as CN
    ra = tmp_path / "imp_ra.json"
    assert CN.main(["luoi-import-dxf", "--lot", lot, "--tu-file", str(dxf_luoi), "--chi-doc", "--json", "--ra", str(ra)]) == 0
    kq = json.loads(ra.read_text(encoding="utf-8"))
    assert kq["ok"] is True and kq["du_lieu"]["cot"] == "4x25" and kq["du_lieu"]["hang"] == "3x20"
