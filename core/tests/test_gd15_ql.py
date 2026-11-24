"""Bảng điều khiển trung tâm SN_QL (giai đoạn 15).

  (a) LÕI `sannen.thong_tin`: đúng số liệu trên lô giải tích, thiếu file thì «Chưa có», deterministic, chỉ ĐỌC (không ghi
      gì ra đĩa), phát hiện «kết quả cũ» (lưới đổi, hiệu chỉnh đỉnh, cổng mất hiệu lực).
  (b) CẦU NỐI `thong-tin` qua sannen_cad.cau_noi (s-expression cho LISP; lô sai thì lỗi tiếng Việt).
  (c) LISP trong accoreconsole (cần AutoCAD 2022): ánh xạ nhóm→layer, đếm đối tượng của ĐÚNG lô (kể cả khi layer đang tắt),
      bật/tắt layer đúng và khôi phục đúng trạng thái, không đụng layer ngoài SN-*, không tắt layer hiện hành;
      cầu nối thật → bước/cổng/số liệu; lệnh c:SN_QL không sập khi không mở được hộp thoại.
  (d) TĨNH: bảng nhóm khớp convention, DCL sn_ql hợp lệ (ASCII, key khớp, callback có định nghĩa, mã done_dialog được xử lý).
Hộp thoại sn_ql chỉ HIỂN THỊ được trên AutoCAD có giao diện — accoreconsole không có load_dialog.
"""
from __future__ import annotations
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(ROOT / "cad"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sannen import cli, luoi_sua, mcp_server, thong_tin                    # noqa: E402
from sannen.paths import Lot                                                # noqa: E402
from sannen_cad import cau_noi as CN                                        # noqa: E402
from sannen_cad.backend import LAYER_KET_QUA, ten_layer                     # noqa: E402
from sannen_cad.ve import TAT_CA                                            # noqa: E402
from lot_giai_tich import E0, chay_het, hcn, tao                            # noqa: E402
from test_gd12_lisp import (ACC, DCL, LISP_DIR, LSP, chay_acc, doc_hop_thoai, kiem_tra_tat_ca_ok,  # noqa: E402
                            lisp_chuoi, mo_dau, moi_truong, tao_cau_noi_gia)

LSP_TXT = LSP.read_text(encoding="utf-8")


# ======================================================================================== dựng lô
@pytest.fixture(scope="module")
def lot_goc(tmp_path_factory) -> Lot:
    """Lô giải tích đã chạy đủ nhap → mat → lo → luoi → tinh (CHỈ ĐỌC trong các test; cần sửa thì copy)."""
    p = tmp_path_factory.mktemp("ql") / "lot"
    lot = tao(p, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, lambda e, n: 10.0 + 0.02 * (e - E0 - 50), so_diem=900)
    chay_het(lot)
    return lot


@pytest.fixture()
def lot_ban_sao(lot_goc, tmp_path) -> Lot:
    dich = tmp_path / "ban_sao"
    shutil.copytree(lot_goc.root, dich)
    return Lot(dich)


def chup(lot: Lot) -> dict:
    return {str(p.relative_to(lot.root)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(lot.root.rglob("*")) if p.is_file()}


def doc(lot: Lot, ten: str) -> dict:
    return json.loads((lot.process_dir / ten).read_text(encoding="utf-8"))


# ======================================================================================== (a) LÕI
def test_thong_tin_dung_so_lieu_lo_giai_tich(lot_goc):
    tt = thong_tin.thong_tin(lot_goc)
    sl = tt["so_lieu"]
    mo = doc(lot_goc, "surface_moc.json")
    assert tt["lo"] == {"ma_lo": "GT-01", "dot": 1, "thu_muc": "lot"}
    assert tt["buoc"] == {"nhap": True, "mat": True, "lo": True, "luoi": True, "tinh": True, "xuat": False}
    assert tt["buoc_ke_tiep"] == "xuat"
    assert sl["moc"]["so_dinh"] == len(mo["diem"]) == 950 and sl["moc"]["so_tam_giac"] == len(mo["tam_giac"])
    assert sl["moc"]["so_tam_giac_thieu"] == 0
    zs = [p[2] for p in mo["diem"]]
    assert sl["moc"]["z_min"] == min(zs) and sl["moc"]["z_max"] == max(zs)
    assert sl["moc"]["z_tb"] == pytest.approx(sum(zs) / len(zs))
    assert sl["moc"]["dien_tich_phu_m2"] == mo["thong_ke"]["dien_tich_phu_m2"]
    assert sl["do"]["z_max"] > sl["do"]["z_min"]                            # mặt đo dốc 0,02
    assert sl["do"]["so_canh_rang_buoc"] == 0 and sl["do"]["xung_dot_dut_gay"] == 0
    g = sl["luoi"]
    assert (g["nx"], g["ny"], g["so_o"]) == (5, 3, 15) and g["cot"] == "5x20" and g["hang"] == "3x20"
    assert g["dt_o_m2"] == pytest.approx(6000.0) and g["dt_lo_m2"] == pytest.approx(6000.0) and abs(g["chenh_dt_m2"]) < 1e-6
    assert g["so_o_thieu"] == 0 and g["tuy_chinh"] is False and g["so_dinh"] == 24
    v = doc(lot_goc, "volume.json")
    k = sl["khoiluong"]
    assert k["nop_dao"] == v["so_nop"]["dao_m3"] and k["kiem_dap"] == v["so_kiem"]["dap_m3"]
    assert k["chenh_dao_pct"] == v["chenh_nop_kiem"]["dao_pct"]
    assert k["so_o_lech_lon"] == sum(1 for c in v["o"] if c["o_lech_lon"]) == g["so_o_lech_lon"]
    assert sl["ranh"]["so_doan"] == len(v["ranh_dao_dap"]) > 0 and sl["ranh"]["chieu_dai_m"] == pytest.approx(60.0, abs=0.01)
    assert sl["matcat"]["co"] is False and sl["bang"]["co"] is False         # chưa tạo mặt cắt / chưa xuất
    assert sl["qc"]["so_tam_giac_thieu"] == 0
    assert tt["canh_bao_cu"] == []                                           # vừa chạy xong: không có kết quả cũ
    assert {n for n in thong_tin.NHOM} == set(thong_tin.dong_hien_thi(tt))   # đủ mọi nhóm của hộp thoại


def test_dong_hien_thi_chu_viet_va_chua_co_khi_thieu_file(lot_goc, tmp_path):
    # lô chỉ mới `nhap`: mọi mục sau đó phải nói «Chưa có», không lỗi
    lot = tao(tmp_path / "moi_nhap", [hcn(0, 0, 100, 60)], lambda e, n: 10.0, lambda e, n: 10.0, so_diem=400)
    cli.main(["nhap", "--lot", str(lot.root)])
    tt = thong_tin.thong_tin(lot)
    assert tt["buoc"]["nhap"] and not tt["buoc"]["mat"] and tt["buoc_ke_tiep"] == "mat"
    dong = thong_tin.dong_hien_thi(tt)
    for k in ("moc", "do", "qc", "luoi", "nhan", "o", "khoiluong", "ranh", "matcat", "bang"):
        assert dong[k] and "Chưa có" in dong[k][0][1], f"{k}: {dong[k]}"
    assert dong["nguon"][0][0].startswith("Điểm mốc / đo") and "dxf" in " ".join(v for _, v in dong["nguon"])
    assert all(tt["cong"][c]["da_duyet"] is False for c in "123")
    # lô đủ: chuỗi có dấu, không giá trị rỗng/None
    full = thong_tin.dong_hien_thi(thong_tin.thong_tin(lot_goc))
    for k, ds in full.items():
        for nhan, gt in ds:
            assert isinstance(nhan, str) and isinstance(gt, str) and gt != "" and "None" not in gt, (k, nhan, gt)
    kl = dict(map(tuple, full["khoiluong"]))
    assert "SỐ NỘP — đào (m³)" in kl and "SỐ KIỂM (lăng trụ) — đào (m³)" in kl and "%" in kl["Chênh nộp − kiểm: đào"]


def test_thong_tin_deterministic_va_chi_doc(lot_goc):
    truoc = chup(lot_goc)
    a, b = thong_tin.thong_tin(lot_goc), thong_tin.thong_tin(lot_goc)
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)
    assert json.dumps(thong_tin.dong_hien_thi(a), ensure_ascii=False) == json.dumps(thong_tin.dong_hien_thi(b), ensure_ascii=False)
    assert chup(lot_goc) == truoc, "thong_tin không được ghi hay sửa file nào"


def test_mat_cat_va_bang_hien_trong_thong_tin(lot_ban_sao):
    lot = lot_ban_sao
    from sannen import matcat
    matcat.thuc_hien(lot, (E0 + 10, 1113030.0), (E0 + 90, 1113030.0), 1.0, "MC1")
    matcat.thuc_hien(lot, (E0 + 50, 1113005.0), (E0 + 50, 1113055.0), 1.0, "MC2")
    cli.main(["xuat", "--lot", str(lot.root)])
    tt = thong_tin.thong_tin(lot)
    mc = tt["so_lieu"]["matcat"]
    assert [m["ten"] for m in mc["ds"]] == ["MC1", "MC2"]
    assert mc["ds"][0]["chieu_dai_m"] == pytest.approx(80.0) and mc["ds"][0]["dao_m2"] > 0 and mc["ds"][0]["dap_m2"] > 0
    ct = dict(map(tuple, thong_tin.dong_hien_thi(tt)["matcat"]))
    assert ct["Số mặt cắt đã tạo"] == "2" and "[MC1] chiều dài (m)" in ct
    b = tt["so_lieu"]["bang"]
    assert b["co"] and b["so_dong"] == 15 and b["so_khoi"] >= 1


def test_phat_hien_ket_qua_cu(lot_ban_sao):
    lot = lot_ban_sao
    assert thong_tin.thong_tin(lot)["canh_bao_cu"] == []
    # 1) người đổi kích thước một cột (luoi_tuy_chinh.yaml) nhưng chưa chạy lại luoi/tinh
    st = luoi_sua.ap_dung(luoi_sua.trang_thai(lot), "doi_cot", chi_so=1, kich_thuoc=25.0)
    luoi_sua.ghi_tuy_chinh(lot, st, "thử")
    cu = thong_tin.thong_tin(lot)["canh_bao_cu"]
    assert any("Lưới đã đổi" in c and "cột" in c for c in cu), cu
    # chạy lại luoi + tinh → hết cảnh báo lưới cũ
    cli.main(["luoi", "--lot", str(lot.root)])
    cu = thong_tin.thong_tin(lot)["canh_bao_cu"]
    assert any("volume.json" in c for c in cu), cu                           # lưới mới nhưng khối lượng còn của lưới cũ
    cli.main(["tinh", "--lot", str(lot.root)])
    assert thong_tin.thong_tin(lot)["canh_bao_cu"] == []
    # 2) hiệu chỉnh đỉnh sau khi tính
    ma, _ = mcp_server._chay_cli(["hieuchinh", "--lot", str(lot.root), "--dinh", "D02-02", "--z", "9.5", "--be-mat-hc", "do"])
    assert ma <= 1
    cu = thong_tin.thong_tin(lot)["canh_bao_cu"]
    assert any("hiệu chỉnh" in c.lower() and "tinh" in c for c in cu), cu
    cli.main(["tinh", "--lot", str(lot.root)])
    assert thong_tin.thong_tin(lot)["canh_bao_cu"] == []
    assert thong_tin.thong_tin(lot)["so_lieu"]["luoi"]["so_hieu_chinh"] == 1


def test_cong_duyet_mat_hieu_luc_hien_thanh_canh_bao(lot_ban_sao):
    lot = lot_ban_sao
    kq, loi = mcp_server.duyet_cong({"lot": str(lot.root), "cong": 1, "nguoi_duyet": "QS", "bang_chung": "Đồng ý dữ liệu"})
    assert not loi, kq
    tt = thong_tin.thong_tin(lot)
    assert tt["cong"]["1"]["da_duyet"] is True and tt["canh_bao_cu"] == []
    with (lot.process_dir / "points_moc.csv").open("a", encoding="utf-8") as f:     # dữ liệu đổi sau khi duyệt
        f.write("")                                                                  # byte không đổi → vẫn hợp lệ
    with (lot.process_dir / "points_moc.csv").open("a", encoding="utf-8") as f:
        f.write("X1,1113000.0000,445000.0000,10.0000,\n")
    tt = thong_tin.thong_tin(lot)
    assert tt["cong"]["1"]["da_duyet"] is False
    assert any("Cổng 1" in c and "mất hiệu lực" in c for c in tt["canh_bao_cu"]), tt["canh_bao_cu"]


# ======================================================================================== (b) CẦU NỐI
def test_cau_noi_thong_tin(lot_goc, tmp_path):
    truoc = chup(lot_goc)
    ra = tmp_path / "ra.txt"
    assert CN.main(["thong-tin", "--lot", str(lot_goc.root), "--ra", str(ra)]) == 0
    s = ra.read_text(encoding="utf-8")
    assert s.startswith('(("ok" . T) ("thong_bao" . "")') and s.count("(") == s.count(")")
    for mau in ('("ma_lo" . "GT-01")', '("buoc_ke_tiep" . "xuat")', '("xuat")', '("Số đỉnh" "950")', '("Số cột × hàng" "5 × 3")',
                '("canh_bao_cu")', '("SỐ NỘP — đào (m³)"', '("matcat" ("Trạng thái" "Chưa có'):
        assert mau in s, mau
    for k in thong_tin.NHOM:
        assert f'("{k}" ("' in s, k
    assert chup(lot_goc) == truoc
    ra2 = tmp_path / "ra2.txt"
    CN.main(["thong-tin", "--lot", str(lot_goc.root), "--ra", str(ra2)])
    assert ra2.read_bytes() == ra.read_bytes()                               # deterministic
    # lô sai → lỗi tiếng Việt, không traceback
    ra3 = tmp_path / "ra3.txt"
    CN.main(["thong-tin", "--lot", str(tmp_path / "khong_co"), "--ra", str(ra3)])
    s3 = ra3.read_text(encoding="utf-8")
    assert s3.startswith('(("ok")') and "không phải thư mục lô" in s3 and "Traceback" not in s3


# ======================================================================================== (d) TĨNH
def _bang_nhom() -> list[tuple]:
    khoi = LSP_TXT.split("(setq *sn-ql-nhom*")[1].split("(setq *sn-ql-ve*")[0]
    return re.findall(r'\(\s*"(\w+)"\s+"([^"]+)"\s+(nil|"[\w\-]+")\s+(nil|"[^"]+")\s+(T|nil)\s*\)', khoi)


def test_bang_nhom_khop_convention_va_loi():
    bang = _bang_nhom()
    khoa = [b[0] for b in bang]
    assert tuple(khoa) == thong_tin.NHOM, "khoá nhóm LISP và lõi phải trùng thứ tự"
    goc = {b[3].strip('"') for b in bang if b[3] != "nil"}
    thieu = [l for l in LAYER_KET_QUA if l not in goc]
    assert not thieu, f"layer kết quả chưa thuộc nhóm nào của SN_QL: {thieu}"
    for ten in ("SN-DIEM-MOC", "SN-DIEM-DO", "SN-DUTGAY", "SN-BIENLO", "SN-LOAITRU", "SN-DONGMUC"):   # layer nguồn của convention
        assert ten in LSP_TXT.split("(setq *sn-ql-ve*")[0].split("(setq *sn-ql-nhom*")[1]
    ve = re.findall(r'\("(\w+)"\s+\.\s+"(\w+)"\)', LSP_TXT.split("(setq *sn-ql-ve*")[1].split("(setq *sn-ql-lenh*")[0])
    assert ve and {v for _, v in ve} <= set(TAT_CA) and {k for k, _ in ve} <= set(khoa)
    assert set(khoa) - {k for k, _ in ve} == {"matcat", "khoiluong", "nguon"}      # nhóm không vẽ lại được từ SN_QL


def test_dcl_sn_ql_hop_le_va_vua_man_hinh():
    d = doc_hop_thoai()["sn_ql"]
    tho = DCL.read_text(encoding="utf-8")
    assert all(ord(c) < 128 for c in tho)
    khoi = tho.split("sn_ql : dialog {")[1].split("\nsn_tin3d")[0]
    rong = [int(w) for w in re.findall(r"\bwidth\s*=\s*(\d+)", khoi)]
    assert max(rong) <= 126, "tile rộng hơn ~126 ký tự: không vừa màn hình 1366"
    cot = re.findall(r"list_box \{ key = \"(\w+)\"; width = (\d+); height = (\d+)", khoi)
    assert {c[0] for c in cot} == {"l_nhom", "l_ct"} and sum(int(c[1]) for c in cot) <= 128
    assert max(int(c[2]) for c in cot) <= 14 and "multiple_select = true" in khoi and "tabs =" in khoi
    nut = {k for k in d["khoa"] if k.startswith("b_")}
    assert nut == {"b_hien", "b_an", "b_chi", "b_hien_het", "b_an_het", "b_zoom", "b_tin3d", "b_xem3d", "b_luoi", "b_matcat",
                   "b_capdo", "b_canhbao", "b_bang", "b_tinh", "b_ve", "b_duyet", "b_lammoi", "b_dong"}
    # đủ các tile thông tin đầu hộp + ba dòng trạng thái
    for k in ("t_ten", "t_lo", "t_buoc", "t_cong", "t_cu", "t_cu2", "t_cot", "t_cttieu", "t_tt", "t_tt2", "t_tt3"):
        assert k in d["khoa"], k
    # mọi tile chữ / nút của sn_ql đều được LISP đặt chữ có dấu bằng set_tile (sn:vn / sn:vn-ds / sn:vn-dong)
    pt = LSP_TXT.split(";;; 19B.")[1].split(";;; 20. MENU")[0]
    for k in d["khoa"]:
        if k.startswith(("t_", "b_")) and k not in ("t_tt", "t_tt2", "t_tt3"):
            assert f'"{k}"' in pt, f"{k}: sn_ql không đặt chữ có dấu cho tile này"
    assert "(sn:tt " in pt and "sn:vn-dong" in pt


def test_sn_ql_callback_ma_done_dialog_va_lenh_dich():
    pt = LSP_TXT.split(";;; 19B.")[1].split(";;; 20. MENU")[0]
    ma = {int(m) for m in re.findall(r"\(done_dialog (\d+)\)", pt)} - {0}
    khoa_lenh = {int(k) for k in re.findall(r"\((\d+) \. \"SN_[A-Z0-9]+\"\)", pt)}
    xu_ly = khoa_lenh | {9, 11}                                              # 9 = vẽ lại, 11 = zoom (xử lý riêng sau khi đóng hộp)
    assert ma == xu_ly, f"mã done_dialog {sorted(ma)} ≠ mã được xử lý {sorted(xu_ly)}"
    co = set(re.findall(r"^\(defun\s+c:(SN[A-Z0-9_]*)\s*\(\)", LSP_TXT, re.M))
    dich = set(re.findall(r"\(\d+ \. \"(SN_[A-Z0-9]+)\"\)", pt))
    assert dich == {"SN_TIN3D", "SN_XEM3D", "SN_LUOI", "SN_MATCAT", "SN_CAPDO", "SN_CANHBAO", "SN_BANG", "SN_TINH", "SN_DUYET"}
    assert dich <= co and "SN_QL" in co
    # hộp mở lại sau mỗi nút (vòng lặp) và thoát khi người dùng đóng / ESC (mã 0)
    assert re.search(r"\(while \(and ma \(/= ma 0\)\)", pt)
    # menu thả xuống: mục đầu tiên là SN_QL; menu dòng lệnh SN có từ khoá Quanly
    menu = LSP_TXT.split("(setq *sn-menu*")[1]
    dau = menu.lstrip()
    assert dau.startswith("'((\"BẢNG ĐIỀU KHIỂN TRUNG TÂM") and '"SN_QL"' in dau.split("\n")[0]
    assert "(= k \"Quanly\") (c:SN_QL)" in LSP_TXT
    # lỗi cầu nối: chỉ ra file cấu hình sannen.cfg (sn:cfg-file)
    assert "(sn:cfg-file)" in pt and "python=, cad=, lot=" in pt
    # không đóng băng / xóa layer: hộp chỉ dùng sn:lop-bat (ON/OFF)
    assert "FREEZE" not in pt.upper() and "entdel" not in pt and "_.-LAYER" not in pt.upper()


# ======================================================================================== (c) LISP trong AutoCAD
def _dung_ban_ve() -> str:
    """Bản vẽ thử: lô L1 (đợt 1, đợt 3), lô L2, layer ngoài SN, dữ liệu nguồn, mặt 3D ở layer đã TẮT."""
    return r'''
(defun mk (pt lop lo dot loai)
  (sn:lop lop 2)
  (entmake (list '(0 . "POINT") (cons 8 lop) (cons 10 pt)
                 (list -3 (cons "SANNEN" (mapcar '(lambda (s) (cons 1000 s)) (list lo dot "h" loai)))))))
(defun mk0 (pt lop) (sn:lop lop 3) (entmake (list '(0 . "POINT") (cons 8 lop) (cons 10 pt))))
(foreach i '(1 2 3) (mk (list i 0.0 0.0) "SN-LUOI" "L1" "1" "luoi"))              ; L1 đợt 1 ×3
(foreach i '(1 2)   (mk (list i 1.0 0.0) "SN-LUOI" "L2" "1" "luoi"))              ; lô khác ×2 (cùng layer!)
(mk '(9.0 9.0 0.0) "SN-LUOI" "L1" "3" "luoi")                                     ; L1 nhưng đợt 3 nằm nhầm layer đợt 1
(mk '(5.0 5.0 0.0) "SN-LUOI-D03" "L1" "3" "luoi")                                 ; L1 đợt 3 đúng layer
(foreach i '(1 2 3 4) (mk (list i 2.0 0.0) "SN-LUOI-NHAN" "L1" "1" "nhan_dinh"))
(foreach i '(1 2)   (mk (list i 3.0 0.0) "SN-3DF-MOC" "L1" "1" "mat_3d"))
(mk '(1.0 4.0 0.0) "SN-3DF-DO" "L1" "1" "mat_3d")
(mk '(1.0 5.0 0.0) "SN-MATCAT" "L1" "1" "mat_cat")
(mk '(1.0 6.0 0.0) "SN-MATCAT" "L2" "1" "mat_cat")
(foreach i '(1 2 3 4) (mk0 (list i 7.0 0.0) "SN-DIEM-MOC"))
(mk0 '(1.0 8.0 0.0) "SN-DIEM-MOC-D03")
(mk0 '(1.0 9.0 0.0) "SN-DIEM-DO")
(foreach i '(1 2 3) (mk0 (list i 10.0 0.0) "BANVE-NHA-THAU"))
(setq *sn-ql-lo* "L1" *sn-ql-dot* 1)
(sn:lop-bat "SN-3DF-MOC" nil)                                                      ; mặt 3D tắt sẵn
(setq tt0 (mapcar '(lambda (l) (cons l (sn:ql-lop-tt l))) (append '("0" "BANVE-NHA-THAU") (sn:ql-lop-sn))))
(defun nh (k) (assoc k *sn-ql-nhom*))
(defun tt-l (l) (sn:ql-lop-tt l))
(defun cung-trang-thai (ds) (equal (mapcar '(lambda (l) (cons l (sn:ql-lop-tt l))) (mapcar 'car ds)) ds))
'''


def test_lisp_anh_xa_nhom_dem_dung_lo_bat_tat_khoi_phuc(tmp_path):
    if not ACC.exists():
        pytest.skip("Không có AutoCAD 2022 (accoreconsole.exe)")
    map_ky_vong = []
    for dot in (1, 3):
        for k, goc in (("moc", "SN-3DF-MOC"), ("do", "SN-3DF-DO"), ("qc", "SN-QC"), ("luoi", "SN-LUOI"),
                       ("nhan", "SN-LUOI-NHAN"), ("o", "SN-LUOI-O"), ("ranh", "SN-RANH-DAODAP")):
            map_ky_vong.append(f'(setq *sn-ql-dot* {dot}) (t! "map-{k}-{dot}" (= (sn:ql-mau-lop (nh "{k}")) "{ten_layer(goc, dot)}"))')
    ma = mo_dau() + _dung_ban_ve() + "\n".join(map_ky_vong) + r'''
(setq *sn-ql-dot* 1)
(t! "map-cod-dinh" (and (= (sn:ql-mau-lop (nh "matcat")) "SN-MATCAT") (= (sn:ql-mau-lop (nh "bang")) "SN-BANG")))
(setq *sn-ql-dot* 3) (t! "map-cod-dinh-dot3" (= (sn:ql-mau-lop (nh "matcat")) "SN-MATCAT")) (setq *sn-ql-dot* 1)
(t! "map-khoiluong-khong-layer" (null (sn:ql-mau-lop (nh "khoiluong"))))
(t! "lop-cua-luoi-dung-ten" (equal (sn:ql-lop-cua (nh "luoi")) '("SN-LUOI")))          ; không lẫn SN-LUOI-NHAN / SN-LUOI-D03
(t! "lop-cua-nguon" (= (length (sn:ql-lop-cua (nh "nguon"))) 3))                       ; SN-DIEM-MOC, SN-DIEM-MOC-D03, SN-DIEM-DO
(t! "lop-sn-khong-co-layer-ngoai" (and (member "SN-LUOI" (sn:ql-lop-sn)) (not (member "BANVE-NHA-THAU" (sn:ql-lop-sn))) (not (member "0" (sn:ql-lop-sn)))))
;; ---- đếm đúng lô / đúng đợt ----
(t! "dem-luoi-L1-dot1" (= (sn:ql-dem-nhom (nh "luoi") "L1" 1) 3))                     ; L2 (2 cái) và đợt 3 nằm nhầm KHÔNG bị đếm
(t! "dem-luoi-L2" (= (sn:ql-dem-nhom (nh "luoi") "L2" 1) 2))
(t! "dem-luoi-lo-la" (= (sn:ql-dem-nhom (nh "luoi") "L9" 1) 0))
(setq *sn-ql-dot* 3) (t! "dem-luoi-dot3" (= (sn:ql-dem-nhom (nh "luoi") "L1" 3) 1)) (setq *sn-ql-dot* 1)
(t! "dem-nhan" (= (sn:ql-dem-nhom (nh "nhan") "L1" 1) 4))
(t! "dem-moc-layer-dang-tat" (and (equal (tt-l "SN-3DF-MOC") "an") (= (sn:ql-dem-nhom (nh "moc") "L1" 1) 2)))
(t! "dem-do" (= (sn:ql-dem-nhom (nh "do") "L1" 1) 1))
(t! "dem-matcat-dung-lo" (and (= (sn:ql-dem-nhom (nh "matcat") "L1" 1) 1) (= (sn:ql-dem-nhom (nh "matcat") "L2" 1) 1)))
(t! "dem-nhom-chua-co-layer" (null (sn:ql-dem-nhom (nh "bang") "L1" 1)))                 ; chưa có layer SN-BANG → nil
(t! "dem-o-chua-co-layer" (null (sn:ql-dem-nhom (nh "o") "L1" 1)))
(t! "dem-nguon-theo-layer" (= (sn:ql-dem-nhom (nh "nguon") "L1" 1) 6))                  ; 4 + 1 (đợt 3) + 1: đếm mọi đối tượng trên layer nguồn
(t! "khoiluong-khong-dem" (null (sn:ql-dem-nhom (nh "khoiluong") "L1" 1)))
(t! "ss-nhom-chi-lo-nay" (= (sslength (sn:ql-ss-nhom (nh "luoi") "L1" 1)) 3))
(setq *sn-ql-dem* (list (cons "luoi" 3) (cons "bang" nil) (cons "khoiluong" nil)))
(t! "dong-luoi" (equal (sn:ql-dong-nhom (nh "luoi")) (strcat "Lưới ô" "\t" "3 đối tượng" "\t" "Hiện")))
(t! "dong-bang-chua-co" (equal (sn:ql-dong-nhom (nh "bang")) (strcat "Bảng in" "\t" "(chưa có lớp)" "\t" "Chưa có lớp")))
(t! "dong-khoiluong" (equal (sn:ql-dong-nhom (nh "khoiluong")) (strcat "Khối lượng (số liệu)" "\t" "—" "\t" "—")))
(t! "tt-moc-an" (equal (sn:ql-chu-tt (nh "moc")) "Ẩn"))
;; ---- bật / tắt: chỉ ON/OFF, khôi phục đúng, không đụng layer ngoài SN ----
(t! "tt-ban-dau" (and (= (sn:ql-trang-thai (nh "luoi")) "hien") (= (sn:ql-trang-thai (nh "moc")) "an") (= (sn:ql-trang-thai (nh "bang")) "khong")))
(setq so-dt0 (sslength (ssget "X" '((0 . "POINT")))))
(t! "tat-luoi" (= (sn:ql-bat-nhom (nh "luoi") nil) 1))
(t! "luoi-an" (and (= (tt-l "SN-LUOI") "an") (= (sn:ql-trang-thai (nh "luoi")) "an")))
(t! "tat-lan-hai-khong-doi" (= (sn:ql-bat-nhom (nh "luoi") nil) 0))
(t! "layer-khac-giu-nguyen" (and (= (tt-l "SN-LUOI-NHAN") "hien") (= (tt-l "BANVE-NHA-THAU") "hien") (= (tt-l "0") "hien") (= (tt-l "SN-3DF-MOC") "an")))
(t! "khong-dong-bang" (zerop (logand 1 (cdr (assoc 70 (tblsearch "LAYER" "SN-LUOI"))))))
(t! "khong-xoa-doi-tuong" (= (sslength (ssget "X" '((0 . "POINT")))) so-dt0))
(t! "dem-van-du-khi-an" (= (sn:ql-dem-nhom (nh "luoi") "L1" 1) 3))
(t! "bat-lai-luoi" (= (sn:ql-bat-nhom (nh "luoi") T) 1))
(t! "khoi-phuc-dung-trang-thai" (cung-trang-thai tt0))                                  ; layer 3D vốn tắt vẫn tắt, phần còn lại như cũ
;; ---- không tắt layer hiện hành ----
(setvar "CLAYER" "SN-LUOI")
(setq *sn-ql-bo-qua* nil)
(t! "khong-tat-layer-hien-hanh" (and (= (sn:ql-bat-ds '("SN-LUOI") nil) 0) (equal *sn-ql-bo-qua* '("SN-LUOI")) (= (tt-l "SN-LUOI") "hien")))
(setvar "CLAYER" "0")
;; ---- chỉ hiện nhóm này / hiện tất cả / ẩn tất cả ----
(setq *sn-ql-bo-qua* nil)
(sn:ql-chi-hien (list (nh "nhan")))
(t! "chi-hien-nhan" (and (= (tt-l "SN-LUOI-NHAN") "hien") (= (tt-l "SN-LUOI") "an") (= (tt-l "SN-MATCAT") "an") (= (tt-l "SN-DIEM-DO") "an")))
(t! "chi-hien-khong-dung-layer-ngoai" (and (= (tt-l "BANVE-NHA-THAU") "hien") (= (tt-l "0") "hien")))
(sn:ql-bat-ds (sn:ql-lop-sn) T)
(t! "hien-tat-ca-sn" (null (vl-remove-if '(lambda (l) (= (tt-l l) "hien")) (sn:ql-lop-sn))))
(sn:ql-bat-ds (sn:ql-lop-sn) nil)
(t! "an-tat-ca-sn" (null (vl-remove-if '(lambda (l) (= (tt-l l) "an")) (sn:ql-lop-sn))))
(t! "an-tat-ca-khong-dung-layer-ngoai" (and (= (tt-l "BANVE-NHA-THAU") "hien") (= (tt-l "0") "hien")))
(t! "van-con-du-doi-tuong" (= (sslength (ssget "X" '((0 . "POINT")))) so-dt0))
;; ---- chọn nhóm / vẽ lại ----
(t! "parse-chon" (and (equal (sn:ql-parse-chon "0 3 5") '(0 3 5)) (null (sn:ql-parse-chon "")) (null (sn:ql-parse-chon nil))))
(t! "nhom-chon" (equal (mapcar 'car (sn:ql-nhom-chon "0 3")) '("moc" "luoi")))
(t! "nhom-chon-ngoai-pham-vi" (equal (mapcar 'car (sn:ql-nhom-chon "1 99")) '("do")))
(t! "ve-nhom-gop-3d" (equal (sn:ql-ve-nhom (sn:ql-nhom-chon "0 1 2 3")) '("3d" "luoi")))
(t! "ve-nhom-matcat-khong-ve" (null (sn:ql-ve-nhom (sn:ql-nhom-chon "7 9 10"))))
(t! "lenh-co" (and (boundp 'c:SN_QL) (boundp 'c:SN_TIN3D) (boundp 'c:SN_DUYET)))
(t! "chu-ct-khi-thieu-so-lieu" (progn (setq *sn-ql-tt* nil *sn-ql-loi* "lỗi thử")
   (vl-some '(lambda (d) (and (vl-string-search "Chưa có — lỗi thử" d) (vl-string-search "\t" d))) (sn:ql-ct-dong (nh "moc")))))
(setq *sn-ql-tt* '(("nhom" ("moc" ("Số đỉnh" "950") ("Số tam giác" "1,776")))))
(setq ct (sn:ql-ct-dong (nh "moc")))
(t! "ct-co-layer-dem-hien-thi" (and (vl-string-search "SN-3DF-MOC" (car ct)) (vl-string-search "lô L1" (cadr ct)) (vl-string-search "Ẩn" (nth 2 ct))))
(t! "ct-co-so-lieu" (and (member (strcat "Số đỉnh" "\t" "950") ct) (member (strcat "Số tam giác" "\t" "1,776") ct)))
(t! "ct-khoiluong-khong-layer" (null (vl-some '(lambda (d) (vl-string-search "Lớp (layer)" d)) (sn:ql-ct-dong (nh "khoiluong")))))
'''
    txt, kq = chay_acc(tmp_path, ma, moi_truong(tmp_path))
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma) + [f"map-{k}-{d}" for d in (1, 3) for k in ("moc", "do", "qc", "luoi", "nhan", "o", "ranh")])


def test_lisp_cau_noi_that_buoc_cong_so_lieu_va_lenh_khong_sap(tmp_path, lot_goc):
    if not ACC.exists():
        pytest.skip("Không có AutoCAD 2022 (accoreconsole.exe)")
    lot = Lot(tmp_path / "lot_acad")
    shutil.copytree(lot_goc.root, lot.root)
    env = moi_truong(tmp_path, {"python": sys.executable, "cad": str(ROOT / "cad"), "lot": str(lot.root), "lisp": str(LISP_DIR)})
    ma = mo_dau() + r'''
(sn:ql-nap)
(t! "nap-ok" (and *sn-ql-tt* (null *sn-ql-loi*)))
(t! "buoc" (and (vl-string-search "[x] nhập" (sn:ql-buoc-chu *sn-ql-tt*)) (vl-string-search "[x] tính" (sn:ql-buoc-chu *sn-ql-tt*))
                (vl-string-search "[ ] xuất" (sn:ql-buoc-chu *sn-ql-tt*)) (vl-string-search "kế tiếp: xuất" (sn:ql-buoc-chu *sn-ql-tt*))))
(t! "cong" (and (vl-string-search "Cổng 1: chưa duyệt" (sn:ql-cong-chu *sn-ql-tt*)) (vl-string-search "Cổng 3: chưa duyệt" (sn:ql-cong-chu *sn-ql-tt*))))
(t! "cu-khong" (vl-string-search "khớp" (sn:ql-cu-chu *sn-ql-tt*)))
(t! "ma-lo" (= *sn-ql-lo* "GT-01"))
(defun nh (k) (assoc k *sn-ql-nhom*))
(t! "ct-luoi" (and (member (strcat "Số cột × hàng" "\t" "5 × 3") (sn:ql-ct-dong (nh "luoi")))
                   (vl-some '(lambda (d) (vl-string-search "Số ô trong lô\t15" d)) (sn:ql-ct-dong (nh "luoi")))))
(t! "ct-khoiluong" (vl-some '(lambda (d) (vl-string-search "SỐ NỘP — đào (m³)\t1,440.013" d)) (sn:ql-ct-dong (nh "khoiluong"))))
(t! "ct-bang-chua-co" (vl-some '(lambda (d) (vl-string-search "Chưa có" d)) (sn:ql-ct-dong (nh "bang"))))
(t! "chua-ve-dem-0" (and (null (cdr (assoc "luoi" *sn-ql-dem*))) (null (cdr (assoc "moc" *sn-ql-dem*)))))   ; bản vẽ trống: chưa có layer
;; vẽ thật rồi đếm
(setq kv (sn:chay "ve" "" T))
(t! "ve-ok" (and (sn:get "ok" kv) (sn:ap-lsp kv)))
(sn:ql-nap)
(setq vd (sn:get "du_lieu" kv))                                   ; số đối tượng cầu nối báo đã vẽ — SN_QL phải đếm khớp
(t! "dem-nhan-khop-ve" (and (> (sn:get "nhan_dinh" vd) 0) (= (cdr (assoc "nhan" *sn-ql-dem*)) (sn:get "nhan_dinh" vd))))
(t! "dem-o-15" (and (= (cdr (assoc "o" *sn-ql-dem*)) 15) (= (sn:get "nhan_o" vd) 15)))
(t! "dem-luoi-khop-ve" (and (> (sn:get "luoi" vd) 0) (= (cdr (assoc "luoi" *sn-ql-dem*)) (sn:get "luoi" vd))))
(t! "dem-ranh-khop-ve" (and (> (sn:get "ranh" vd) 0) (= (cdr (assoc "ranh" *sn-ql-dem*)) (sn:get "ranh" vd))))
(t! "dem-moc-polyface-1" (= (cdr (assoc "moc" *sn-ql-dem*)) 1))
(t! "dem-do-polyface-1" (= (cdr (assoc "do" *sn-ql-dem*)) 1))
(t! "moc-tat-mac-dinh" (= (sn:ql-trang-thai (assoc "moc" *sn-ql-nhom*)) "an"))
(t! "luoi-hien" (= (sn:ql-trang-thai (assoc "luoi" *sn-ql-nhom*)) "hien"))
(t! "dem-lo-khac-0" (= (sn:ql-dem-nhom (assoc "luoi" *sn-ql-nhom*) "LO-KHAC" 1) 0))
;; bật nhóm mốc: chỉ ON/OFF
(sn:ql-bat-nhom (assoc "moc" *sn-ql-nhom*) T)
(t! "moc-hien" (= (sn:ql-trang-thai (assoc "moc" *sn-ql-nhom*)) "hien"))
;; lệnh SN_QL không sập khi không mở được hộp thoại (accoreconsole không có DCL) và báo bằng tiếng Việt
(c:SN_QL)
(princ "\n@@sn-ql-chay=OK")
'''
    txt, kq = chay_acc(tmp_path, ma, env, timeout=400)
    kiem_tra_tat_ca_ok(kq, re.findall(r'\(t! "([^"]+)"', ma) + ["sn-ql-chay"])
    assert "Không nạp được sannen.dcl" in txt or "Không mở được hộp thoại" in txt or "Không thấy sannen.dcl" in txt


def test_lisp_ql_cau_noi_loi_van_mo_duoc_va_chi_cau_hinh(tmp_path):
    if not ACC.exists():
        pytest.skip("Không có AutoCAD 2022 (accoreconsole.exe)")
    lot = tmp_path / "lo_x"
    lot.mkdir()
    (lot / "lot.yaml").write_text("ma_lo: X\ndot: 1\n", encoding="utf-8")
    cad = tao_cau_noi_gia(tmp_path)                               # cầu nối giả không biết lệnh thong-tin → không trả kết quả
    env = moi_truong(tmp_path, {"python": sys.executable, "cad": str(cad), "lot": str(lot)})
    ma = mo_dau() + r'''
(sn:ql-nap)
(t! "loi-khong-crash" (and (null *sn-ql-tt*) (vl-string-search "không trả kết quả" *sn-ql-loi*)))
(defun nh (k) (assoc k *sn-ql-nhom*))
(t! "ct-chua-co" (vl-some '(lambda (d) (vl-string-search "Chưa có —" d)) (sn:ql-ct-dong (nh "luoi"))))
(t! "dem-van-chay" (and (assoc "luoi" *sn-ql-dem*) (null (cdr (assoc "luoi" *sn-ql-dem*)))))
(c:SN_QL)
(princ "\n@@xong=OK")
'''
    txt, kq = chay_acc(tmp_path, ma, env)
    kiem_tra_tat_ca_ok(kq, ["loi-khong-crash", "ct-chua-co", "dem-van-chay", "xong"])
