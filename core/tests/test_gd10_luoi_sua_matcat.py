"""Menu CAD: hiệu chỉnh lưới kiểu SNVN và mặt cắt địa hình — phần lõi (không cần AutoCAD)."""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, luoi_sua as S, matcat                      # noqa: E402
from sannen.config import doc_lot                                  # noqa: E402
from lot_giai_tich import E0, N0, chay_den, chay_het, hcn, tao     # noqa: E402

f_moc = lambda e, n: 10.0
f_do = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)       # dz đổi dấu giữa lô


# ------------------------------------------------------------------ mẫu Số×KT
@pytest.mark.parametrize("mau, mong", [
    ("10x20,5x15", [20.0] * 10 + [15.0] * 5), ("5x20 , 5 x 15 , 5x20", [20.0] * 5 + [15.0] * 5 + [20.0] * 5),
    ("20", [20.0]), ("3×12.5;2×10", [12.5] * 3 + [10.0] * 2), ("2X5", [5.0, 5.0])])
def test_phan_tich_mau_so_x_kich_thuoc(mau, mong):
    assert S.phan_tich(mau) == mong


@pytest.mark.parametrize("xau", ["", "abc", "0x20", "3x0", "3x-2", "3x2,x", "3*20"])
def test_mau_sai_bi_tu_choi_noi_ro_cho_sai(xau):
    with pytest.raises(S.SuaLuoiLoi):
        S.phan_tich(xau)


def test_dinh_dang_gon_va_khu_hoi():
    ds = [20.0] * 10 + [15.0] * 5
    assert S.dinh_dang(ds) == "10x20,5x15" and S.phan_tich(S.dinh_dang(ds)) == ds
    assert S.dinh_dang([12.5, 12.5, 10.0]) == "2x12.5,1x10"


# ------------------------------------------------------------------ các phép hiệu chỉnh
def st0():
    return {"kich_thuoc_o_m": 20, "goc_xoay_do": 0.0, "goc_luoi": [1000.0, 2000.0],
            "cot_m": [20.0] * 4, "hang_m": [20.0] * 3}


def test_doi_chen_xoa_hang_cot():
    s = S.ap_dung(st0(), "doi_cot", chi_so=2, kich_thuoc=30)
    assert s["cot_m"] == [20, 30, 20, 20] and s["goc_luoi"] == [1000, 2000]
    s = S.ap_dung(s, "chen_cot", sau=2, kich_thuoc=10)
    assert s["cot_m"] == [20, 30, 10, 20, 20]
    s = S.ap_dung(s, "xoa_hang", chi_so=3)
    assert s["hang_m"] == [20, 20]
    s = S.ap_dung(st0(), "chen_cot", sau=0, kich_thuoc=5)         # chèn trước cột đầu: gốc lùi để ô cũ đứng yên
    assert s["cot_m"][0] == 5 and s["goc_luoi"] == pytest.approx([995.0, 2000.0])
    g = S.ap_dung({**st0(), "goc_xoay_do": 90.0}, "chen_hang", sau=0, kich_thuoc=5)   # lưới xoay 90°: trục v = -x
    assert g["goc_luoi"] == pytest.approx([1000.0 + 5.0, 2000.0], abs=1e-9)


def test_chi_so_sai_bao_dung_cho():
    with pytest.raises(S.SuaLuoiLoi, match="Cột 9 không có: lưới có 4 cột"):
        S.ap_dung(st0(), "doi_cot", chi_so=9, kich_thuoc=10)
    with pytest.raises(S.SuaLuoiLoi, match="Kích thước phải dương"):
        S.ap_dung(st0(), "doi_hang", chi_so=1, kich_thuoc=0)
    with pytest.raises(S.SuaLuoiLoi, match="chỉ còn 1"):
        S.ap_dung({**st0(), "cot_m": [20.0]}, "xoa_cot", chi_so=1)


def test_di_chuyen_va_xoay_quanh_tam():
    s = S.ap_dung(st0(), "di_chuyen", dx=5, dy=-3)
    assert s["goc_luoi"] == [1005.0, 1997.0]
    s = S.ap_dung(st0(), "di_chuyen", den=(1.0, 2.0))
    assert s["goc_luoi"] == [1.0, 2.0]
    a = st0()
    tam = lambda t: (t["goc_luoi"][0] + (math.cos(math.radians(t["goc_xoay_do"])) * sum(t["cot_m"])
                                          - math.sin(math.radians(t["goc_xoay_do"])) * sum(t["hang_m"])) / 2,
                     t["goc_luoi"][1] + (math.sin(math.radians(t["goc_xoay_do"])) * sum(t["cot_m"])
                                          + math.cos(math.radians(t["goc_xoay_do"])) * sum(t["hang_m"])) / 2)
    b = S.ap_dung(a, "xoay", goc_do=30)
    assert b["goc_xoay_do"] == 30 and tam(b) == pytest.approx(tam(a), abs=1e-9)   # tâm lưới đứng yên


# ------------------------------------------------------------------ vào lõi thật
def _lot(tmp_path, **kw):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do, so_diem=1500, **kw)
    chay_het(l)
    return l


def test_ghi_tuy_chinh_ghi_de_luoi_va_tinh_lai_khop(tmp_path):
    l = _lot(tmp_path)
    s0 = S.trang_thai(l)
    assert s0["cot_m"] == [20.0] * 5 and s0["hang_m"] == [20.0] * 3
    s = S.ap_dung(s0, "dat", cot="1x10,4x22.5", hang="3x20")              # 10 + 90 = 100 m: phủ đúng lô
    r = S.ghi_tuy_chinh(l, s, "người hiệu chỉnh cột trong CAD")
    assert (l.root / S.FILE_TUY_CHINH).exists() and r["da_cat_hieu_chinh_dinh"] is None
    assert doc_lot(l.lot_yaml)["luoi"]["cot_m"] == [10.0, 22.5, 22.5, 22.5, 22.5]     # lot.yaml KHÔNG bị sửa
    assert "kich_thuoc_o_m: 20" in (l.root / "lot.yaml").read_text(encoding="utf-8").replace("{kich_thuoc_o_m: 20", "kich_thuoc_o_m: 20")
    assert cli.main(["luoi", "--lot", str(l.root)]) == 0
    assert cli.main(["tinh", "--lot", str(l.root)]) == 0
    g = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert g["tham_so"]["cot_m"] == [10.0, 22.5, 22.5, 22.5, 22.5] and g["tong"]["dt_o_m2"] == pytest.approx(6000, abs=1e-6)
    v = json.loads((l.process_dir / "volume.json").read_text(encoding="utf-8"))
    assert v["so_kiem"]["rong_m3"] == pytest.approx(0.0, abs=0.5)         # lăng trụ không phụ thuộc lưới
    assert "lưới 5 cột × 3 hàng" in (l.log_dir / "decisions.md").read_text(encoding="utf-8")
    assert S.xoa_tuy_chinh(l) and not (l.root / S.FILE_TUY_CHINH).exists()


def test_luoi_khong_phu_het_lo_bi_chan_noi_ro(tmp_path):
    l = _lot(tmp_path)
    S.ghi_tuy_chinh(l, S.ap_dung(S.trang_thai(l), "xoa_cot", chi_so=5), "xóa cột cuối")
    assert cli.main(["luoi", "--lot", str(l.root)]) == 1
    q = json.loads((l.process_dir / "qc_luoi.json").read_text(encoding="utf-8"))
    p = next(p for p in q["phat_hien"] if p["loai"] == "tong_o_khac_dt_lo")
    assert p["muc"] == "chan" and "chưa phủ hết lô" in p["mo_ta"]


def test_doi_hinh_hoc_luoi_cat_hieu_chinh_dinh_cu_khong_xoa(tmp_path):
    l = _lot(tmp_path)
    cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", "D02-02", "--z", "99"])
    assert (l.process_dir / "grid_adjusted.json").exists()
    r = S.ghi_tuy_chinh(l, S.ap_dung(S.trang_thai(l), "chen_cot", sau=1, kich_thuoc=10), "chèn cột")
    assert r["da_cat_hieu_chinh_dinh"] and (l.process_dir / r["da_cat_hieu_chinh_dinh"]).exists()
    assert not (l.process_dir / "grid_adjusted.json").exists()           # mã đỉnh đã đổi nghĩa → không dùng nữa
    assert "cất tại grid_adjusted.cu_" in (l.log_dir / "decisions.md").read_text(encoding="utf-8")


def test_xuat_tu_choi_so_cu_khi_luoi_doi_ma_chua_tinh_lai(tmp_path, capsys):
    l = _lot(tmp_path)
    S.ghi_tuy_chinh(l, S.ap_dung(S.trang_thai(l), "dat", cot="5x20", hang="3x20", goc_luoi=[E0 - 1, N0 - 1]), "dời gốc")
    cli.main(["luoi", "--lot", str(l.root)])
    assert cli.main(["xuat", "--lot", str(l.root)]) == 2
    assert "Lưới (grid.json) đã đổi" in capsys.readouterr().out


# ------------------------------------------------------------------ mặt cắt
def test_mat_cat_dien_tich_dung_giai_tich(tmp_path):
    """dz = 0,02(x−50) + 0,01(y−30). Tuyến y = 30, x∈[0,100]: dz = 0,02(x−50), đổi dấu tại x = 50.
    Diện tích đào = đắp = ½·50·1 = 25 m²."""
    l = _lot(tmp_path)
    kq = matcat.thuc_hien(l, (E0, N0 + 30), (E0 + 100, N0 + 30), buoc=5.0, ten="A-B")
    assert kq["chieu_dai_m"] == pytest.approx(100.0)
    assert kq["dien_tich_dao_m2"] == pytest.approx(25.0, rel=1e-4) and kq["dien_tich_dap_m2"] == pytest.approx(25.0, rel=1e-4)
    assert kq["doan_thieu_du_lieu_m"] == 0
    s0, s1 = kq["tram"][0], kq["tram"][-1]
    assert (s0["z_moc"], s1["z_moc"]) == (pytest.approx(10.0), pytest.approx(10.0))
    assert s0["z_do"] == pytest.approx(9.0, abs=1e-3) and s1["z_do"] == pytest.approx(11.0, abs=1e-3)
    assert s0["ly_trinh"] == 0 and s1["ly_trinh"] == pytest.approx(100.0)
    csv_ = (l.output_dir / "matcat_A-B.csv").read_text(encoding="utf-8-sig").splitlines()
    assert csv_[0].startswith("ly_trinh_m;E;N") and len(csv_) == len(kq["tram"]) + 1
    assert (l.process_dir / "matcat_A-B.json").exists()


def test_mat_cat_xien_va_dung_o_giao_cat_tam_giac(tmp_path):
    """Tuyến chéo: diện tích vẫn đúng tích phân giải tích dù các điểm chia không đều."""
    l = _lot(tmp_path)
    a, b = (E0 + 10, N0 + 5), (E0 + 90, N0 + 55)
    kq = matcat.thuc_hien(l, a, b, buoc=1000.0, ghi=False)        # buoc cực lớn: chỉ còn giao điểm tam giác
    L = math.hypot(80, 50)
    # dz dọc tuyến là hàm tuyến tính của lý trình: dz(t) = dz0 + (dz1-dz0)·t
    dz0 = 0.02 * (10 - 50) + 0.01 * (5 - 30)
    dz1 = 0.02 * (90 - 50) + 0.01 * (55 - 30)
    t0 = dz0 / (dz0 - dz1)
    dao = 0.5 * abs(dz0) * t0 * L
    dap = 0.5 * abs(dz1) * (1 - t0) * L
    assert kq["dien_tich_dao_m2"] == pytest.approx(dao, rel=1e-5) and kq["dien_tich_dap_m2"] == pytest.approx(dap, rel=1e-5)
    assert len(kq["tram"]) > 10                                    # có nhiều giao điểm tam giác, không chỉ 2 đầu mút


def test_mat_cat_ngoai_tin_bao_doan_thieu(tmp_path):
    l = _lot(tmp_path)
    kq = matcat.thuc_hien(l, (E0 - 60, N0 + 30), (E0 + 40, N0 + 30), buoc=5.0, ghi=False)   # 60 − 8 m đầu nằm ngoài TIN
    assert kq["doan_thieu_du_lieu_m"] == pytest.approx(52.0, abs=0.5)
    assert any(s["dz"] is None for s in kq["tram"])


def test_mat_cat_tuyen_suy_bien(tmp_path):
    l = _lot(tmp_path)
    with pytest.raises(matcat.MatCatLoi, match="trùng nhau"):
        matcat.thuc_hien(l, (E0 + 5, N0 + 5), (E0 + 5, N0 + 5), ghi=False)
    with pytest.raises(matcat.MatCatLoi, match="dương"):
        matcat.thuc_hien(l, (E0, N0), (E0 + 10, N0), buoc=0, ghi=False)
