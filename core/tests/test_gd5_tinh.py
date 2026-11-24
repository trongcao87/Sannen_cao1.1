"""Giai đoạn 5 — tinh. Điều kiện qua cửa: khớp nghiệm giải tích."""
from __future__ import annotations
import json
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli                                               # noqa: E402
from lot_giai_tich import E0, N0, chay_den, chay_het, hcn, tao       # noqa: E402

F_MOC_PHANG = lambda e, n: 10.0


def vol(l) -> dict:
    return json.loads((l.process_dir / "volume.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- ví dụ của SPEC
def test_o_vat_ranh_luoi_ra_0_con_lang_tru_ra_100_dao_100_dap(tmp_path):
    """Một ô 20×20 có chênh cao 4 góc −1,+1,+1,−1: lưới 0 m³, lăng trụ 100 đào + 100 đắp."""
    f_do = lambda e, n: 5.0 + 0.1 * (e - E0 - 10.0)
    l = tao(tmp_path, [hcn(0, 0, 20, 20)], lambda e, n: 5.0, f_do, so_diem=1200)
    v = chay_het(l)
    assert v["so_nop"]["so_o"] == 1 and v["so_nop"]["so_o_thieu"] == 0
    # points_*.csv lưu 0,1 mm nên lưới ra ±0,01 m³ chứ không đúng 0 tuyệt đối (so với 100 m³ của lăng trụ)
    assert v["so_nop"]["dao_m3"] == pytest.approx(0.0, abs=0.05)
    assert v["so_nop"]["dap_m3"] == pytest.approx(0.0, abs=0.05)
    assert v["so_kiem"]["dao_m3"] == pytest.approx(100.0, abs=2e-3)       # 2e-3: JSON 0,1 mm
    assert v["so_kiem"]["dap_m3"] == pytest.approx(100.0, abs=2e-3)
    assert v["o"][0]["o_lech_lon"] is True                                # phải bị cờ ô lệch lớn


# ---------------------------------------------------------------- nghiệm giải tích
F_DO_NGHIENG = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)    # dz đổi dấu giữa lô


def _lo_co_lo(tmp_path, **kw):
    return tao(tmp_path, [hcn(0, 0, 100, 60)], F_MOC_PHANG, F_DO_NGHIENG, [hcn(30, 20, 60, 40)],
               so_diem=2200, **kw)


def test_lang_tru_rong_dung_cong_thuc_dong_va_tong_khong_phu_thuoc_luoi(tmp_path):
    l = _lo_co_lo(tmp_path)
    v = chay_het(l)
    # ròng = ∫dz trên lô = A·dz(tâm lô) − A_lỗ·dz(tâm lỗ) = 6000·0 − 600·(−0,1) = +60
    assert v["so_kiem"]["rong_m3"] == pytest.approx(60.0, abs=5e-3)
    assert v["dt_dao_dap_thieu_tru_dt_lo_m2"] == pytest.approx(0.0, abs=1e-6)       # dòng 8 bảng tổng khớp
    ref = v["so_kiem"]
    # đổi hẳn lưới (17 m, xoay 33°): số kiểm lăng trụ không được đổi
    assert cli.main(["luoi", "--lot", str(l.root), "--o", "17", "--goc", "33"]) == 0
    cli.main(["tinh", "--lot", str(l.root)])
    v2 = vol(l)
    for k in ("dao_m3", "dap_m3", "dt_dao_m2", "dt_dap_m2"):
        assert v2["so_kiem"][k] == pytest.approx(ref[k], rel=1e-6), k


def test_lang_tru_gop_dao_dap_khop_tich_phan_so(tmp_path):
    """Đối chiếu độc lập: tích phân số (điểm giữa, bước 0,1 m) trên đúng lô, bỏ lỗ."""
    l = _lo_co_lo(tmp_path)
    v = chay_het(l)
    h = 0.1
    dao = dap = 0.0
    for i in range(1000):
        x = (i + 0.5) * h
        for j in range(600):
            y = (j + 0.5) * h
            if 30 < x < 60 and 20 < y < 40:
                continue
            dz = 0.02 * (x - 50) + 0.01 * (y - 30)
            if dz >= 0:
                dap += dz * h * h
            else:
                dao -= dz * h * h
    assert v["so_kiem"]["dao_m3"] == pytest.approx(dao, rel=3e-3)
    assert v["so_kiem"]["dap_m3"] == pytest.approx(dap, rel=3e-3)


def test_ranh_dao_dap_nam_dung_tren_duong_dz_bang_0(tmp_path):
    l = _lo_co_lo(tmp_path)
    v = chay_het(l)
    assert v["ranh_dao_dap"], "phải có ranh đào–đắp"
    dai = 0.0
    for (e0, n0), (e1, n1) in v["ranh_dao_dap"]:
        for e, n in ((e0, n0), (e1, n1), ((e0 + e1) / 2, (n0 + n1) / 2)):
            assert F_DO_NGHIENG(e, n) - 10.0 == pytest.approx(0.0, abs=2e-4)
        dai += math.hypot(e1 - e0, n1 - n0)
    # đường 2(x−50) + (y−30) = 0 đi từ (35,60) tới (65,0) dài √(30²+60²) = 67,082 m;
    # đoạn qua lỗ (55,20)→(45,40) dài √(10²+20²) = 22,361 m bị bỏ → còn 44,721 m
    assert dai == pytest.approx(math.hypot(30, 60) - math.hypot(10, 20), rel=2e-3)


def test_luoi_khop_lang_tru_khi_o_nguyen_va_chenh_cao_tuyen_tinh(tmp_path):
    f_do = lambda e, n: 11.0 + 0.01 * (e - E0)                      # dz = 1 + 0,01x > 0 khắp nơi
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], F_MOC_PHANG, f_do, so_diem=1800)
    v = chay_het(l)
    mong = 6000 * (1 + 0.01 * 50)
    assert v["so_nop"]["dap_m3"] == pytest.approx(mong, rel=1e-5)
    assert v["so_nop"]["dao_m3"] == 0
    assert v["so_kiem"]["dap_m3"] == pytest.approx(mong, rel=1e-5)
    assert not any(o["o_lech_lon"] for o in v["o"])


def test_nang_ha_cao_do_doi_tuyen_tinh_ca_hai_phuong_phap(tmp_path):
    lo, hi = tmp_path / "a", tmp_path / "b"
    lo.mkdir(); hi.mkdir()
    f = lambda e, n: 11.0 + 0.01 * (e - E0)
    va = chay_het(tao(lo, [hcn(0, 0, 100, 60)], F_MOC_PHANG, f, so_diem=1800))
    vb = chay_het(tao(hi, [hcn(0, 0, 100, 60)], F_MOC_PHANG, lambda e, n: f(e, n) + 0.5, so_diem=1800))
    for pp in ("so_nop", "so_kiem"):
        assert vb[pp]["rong_m3"] - va[pp]["rong_m3"] == pytest.approx(0.5 * 6000, rel=1e-6)


def test_doi_cho_mat_moc_va_mat_do_thi_dao_dap_hoan_doi(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    va = chay_het(tao(a, [hcn(0, 0, 100, 60)], F_MOC_PHANG, F_DO_NGHIENG, so_diem=1800))
    vb = chay_het(tao(b, [hcn(0, 0, 100, 60)], F_DO_NGHIENG, F_MOC_PHANG, so_diem=1800))
    for pp in ("so_nop", "so_kiem"):
        assert va[pp]["dao_m3"] == pytest.approx(vb[pp]["dap_m3"], rel=1e-6)
        assert va[pp]["dap_m3"] == pytest.approx(vb[pp]["dao_m3"], rel=1e-6)


def test_dich_toan_bo_du_lieu_khong_doi_ket_qua(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    va = chay_het(tao(a, [hcn(0, 0, 100, 60)], F_MOC_PHANG, F_DO_NGHIENG, so_diem=1500))
    dx, dy = 12_345.0, -9_876.0
    ve = lambda f: (lambda e, n: f(e - dx, n - dy))
    bien = [[(p[0] + dx, p[1] + dy) for p in hcn(0, 0, 100, 60)]]
    vb = chay_het(tao(b, bien, ve(F_MOC_PHANG), ve(F_DO_NGHIENG), so_diem=1500))
    for pp in ("so_nop", "so_kiem"):
        assert vb[pp]["dao_m3"] == pytest.approx(va[pp]["dao_m3"], rel=1e-5)
        assert vb[pp]["dap_m3"] == pytest.approx(va[pp]["dap_m3"], rel=1e-5)


# ---------------------------------------------------------------- hiệu chỉnh đỉnh đi vào số nộp
def test_hieuchinh_di_vao_so_nop_dung_giai_tich(tmp_path):
    f = lambda e, n: 11.0 + 0.01 * (e - E0)
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], F_MOC_PHANG, f, so_diem=1800)
    v0 = chay_het(l)
    g = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    ma = next(m for m, n in g["nut"].items() if n["i"] == 2 and n["j"] == 1)
    cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", ma, "--z", str(g["nut"][ma]["z_do"] + 2.0)])
    cli.main(["tinh", "--lot", str(l.root)])
    v1 = vol(l)
    # đỉnh trong chung 4 ô 20×20: mỗi ô +2/4·400 = 200 → +800 m³
    assert v1["so_nop"]["rong_m3"] - v0["so_nop"]["rong_m3"] == pytest.approx(800.0, rel=2e-5)
    assert v1["so_kiem"]["rong_m3"] == pytest.approx(v0["so_kiem"]["rong_m3"], rel=1e-9)   # số kiểm KHÔNG đổi
    assert v1["tham_so"]["so_hieu_chinh"] == 1


# ---------------------------------------------------------------- RULES 8, 12
def test_vung_thieu_du_lieu_khong_vao_so_nop_nhung_dong_dt_van_khop(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 100)], F_MOC_PHANG, F_DO_NGHIENG, so_diem=1400,
            khoang_trong=(30, 30, 70, 70))
    v = chay_het(l)
    assert v["so_nop"]["so_o_thieu"] > 0 and v["so_nop"]["dt_thieu_du_lieu_m2"] > 0
    assert v["dt_dao_dap_thieu_tru_dt_lo_m2"] == pytest.approx(0.0, abs=1e-6)
    assert any(o["thieu_du_lieu"] and o["kl_dao_m3"] == 0 == o["kl_dap_m3"] for o in v["o"])
    q = json.loads((l.process_dir / "qc_volume.json").read_text(encoding="utf-8"))
    assert any(p["loai"] == "o_thieu_du_lieu" for p in q["phat_hien"])


def test_khoi_luong_dao_di_phan_da_dap_dot_truoc_bi_canh_bao(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], F_MOC_PHANG, lambda e, n: 12.0, so_diem=1800)
    v = chay_het(l)                                              # đợt 1: đắp 2 m khắp lô
    (l.root / "dot1_volume.json").write_text(json.dumps(v), encoding="utf-8")
    l.lot_yaml.write_text(l.lot_yaml.read_text(encoding="utf-8")
                          + "\ndot_truoc: {volume_json: dot1_volume.json}\n", encoding="utf-8")
    # đợt 2: mặt đo lại thấp hơn mặt mốc 1 m → đào đi phần vừa đắp
    for f in l.input_dir.glob("*.dxf"):
        f.unlink()
    l2 = tao(tmp_path, [hcn(0, 0, 100, 60)], F_MOC_PHANG, lambda e, n: 9.0, so_diem=1800,
             extra_yaml="\ndot_truoc: {volume_json: dot1_volume.json}\n")
    chay_het(l2)
    q = json.loads((l2.process_dir / "qc_volume.json").read_text(encoding="utf-8"))
    am = [p for p in q["phat_hien"] if p["loai"] == "khoi_luong_am_giua_hai_dot"]
    assert am and "đảo chiều" in am[0]["mo_ta"]


# ---------------------------------------------------------------- sweep
def test_sweep_du_phuong_an_va_quy_tac_doc(tmp_path):
    l = _lo_co_lo(tmp_path)
    v = chay_het(l, "--sweep")
    s = v["sweep"]
    assert [r["ma"] for r in s["A"]] == [f"A{i}" for i in range(1, 9)]
    assert [r["ma"] for r in s["B"]] == [f"B{i}" for i in range(1, 6)]
    a8 = next(r for r in s["A"] if r["ma"] == "A8")
    assert a8["so_to_hop"] == 16 * 7 == len(s["A8_chi_tiet"])
    # B3 chính là số kiểm của lăng trụ
    b3 = next(r for r in s["B"] if r["ma"] == "B3")
    assert b3["dao"] == pytest.approx(v["so_kiem"]["dao_m3"], abs=1e-2)
    # ô 5 m sát lăng trụ hơn ô 10 m, ô 10 m sát hơn ô 20 m (sai số theo ô vắt ranh giảm dần)
    gross = lambda r: r["dao"] + r["dap"]
    a1 = next(r for r in s["A"] if r["ma"] == "A1")
    b1 = next(r for r in s["B"] if r["ma"] == "B1"); b2 = next(r for r in s["B"] if r["ma"] == "B2")
    assert abs(gross(b2) - gross(b3)) <= abs(gross(b1) - gross(b3)) + 1e-6 <= abs(gross(a1) - gross(b3)) + 2e-6
    # cận dưới nhỏ hơn hoặc bằng mọi phương án lưới, và được diễn giải đúng chữ
    assert s["doc"]["can_duoi_tong_dao_dap_m3"] <= gross(a1) + 1e-9
    assert "cận dưới" in s["doc"]["cau"] and "không đứng được" in s["doc"]["cau"]
    assert s["doc"]["phan_bi_trieu_tiet_m3"] >= 0


def test_sweep_khong_doi_so_nop(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    va = chay_het(_lo_co_lo(a))
    vb = chay_het(_lo_co_lo(b), "--sweep")
    assert va["so_nop"] == vb["so_nop"]                          # RULES 9: agent không tự đổi số nộp


def test_xem_truoc_khong_ghi(tmp_path):
    l = _lo_co_lo(tmp_path)
    chay_den(l, "luoi")
    assert cli.main(["tinh", "--lot", str(l.root), "--preview"]) == 0
    assert not (l.process_dir / "volume.json").exists()
