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
    assert {"sannen_trang_thai", "sannen_doc_viec", "sannen_duyet_cong", "sannen_ghi_quyet_dinh"} | {
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
