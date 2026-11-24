"""Giai đoạn 2 — TIN. Điều kiện qua cửa: sai số nội suy so mặt giải tích ≈ 0;
không cạnh nào cắt qua đứt gãy."""
from __future__ import annotations
import random
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import tin as T                                   # noqa: E402
from sannen.geom import Goc, orient2d, incircle, giao_doan    # noqa: E402

E0, N0 = 445000.0, 1113000.0


def mat_phang(e, n):
    return 0.3 * (e - E0) - 0.2 * (n - N0) + 5.0


def diem_phang(so=300, seed=1, rong=100.0, cao=80.0):
    r = random.Random(seed)
    d = [(E0 + r.uniform(0, rong), N0 + r.uniform(0, cao)) for _ in range(so)]
    d += [(E0, N0), (E0 + rong, N0), (E0, N0 + cao), (E0 + rong, N0 + cao)]
    return [(e, n, mat_phang(e, n)) for e, n in d]


def dung(*a, **kw):
    # tắt bộ lọc tam giác rác ở mép để kiểm riêng độ chính xác nội suy; QC có test riêng
    kw.setdefault("goc_det_do", 0.0)
    return T.dung_tin(*a, **kw)


def goc_cua(d):
    return Goc.trong_tam([(e, n) for e, n, _ in d])


def canh_cua(tin):
    s = set()
    for a, b, c in tin.tris:
        for e in ((a, b), (b, c), (c, a)):
            s.add(tuple(sorted(e)))
    return s


# ---------------------------------------------------------------- vị từ
def test_vi_tu_chinh_xac_voi_so_lon():
    # ba điểm gần thẳng hàng ở toạ độ VN-2000 THÔ: float thường dễ sai dấu, vị từ chính xác thì không
    a, b = (445000.0, 1113000.0), (445001.0, 1113001.0)
    c = (445002.0, 1113002.0)
    assert orient2d(a, b, c) == 0
    assert orient2d(a, b, (445002.0, 1113002.0000000002)) > 0
    assert incircle((0, 0), (1, 0), (0, 1), (1, 1)) == 0       # bốn điểm đồng viên
    assert incircle((0, 0), (1, 0), (0, 1), (0.5, 0.5)) > 0


# ---------------------------------------------------------------- nghiệm giải tích
def test_noi_suy_mat_phang_sai_so_bang_khong():
    d = diem_phang()
    tin, bc = dung(goc_cua(d), d)
    r = random.Random(99)
    for _ in range(500):
        e, n = E0 + r.uniform(1, 99), N0 + r.uniform(1, 79)
        assert tin.z_tai(e, n) == pytest.approx(mat_phang(e, n), abs=1e-7)
    assert tin.z_tai(E0 - 10, N0) is None                         # ngoài TIN thì None, không bịa
    # diện tích tam giác phủ đúng hình chữ nhật (bao lồi) — không chồng chéo, không hở
    assert sum(tin.dien_tich_tam_giac(i) for i in range(len(tin.tris))) == pytest.approx(100 * 80, rel=1e-9)


def test_tinh_chat_delaunay():
    d = diem_phang(200, seed=3)
    tin, _ = dung(goc_cua(d), d)
    kenh = {}
    for i, (a, b, c) in enumerate(tin.tris):
        for e in ((a, b), (b, c), (c, a)):
            kenh.setdefault(tuple(sorted(e)), []).append(i)
    P = lambda k: (tin.x[k], tin.y[k])
    for e, ts in kenh.items():
        if len(ts) != 2:
            continue
        t1, t2 = (tin.tris[i] for i in ts)
        o = next(v for v in t2 if v not in e)
        a, b, c = t1
        assert incircle(P(a), P(b), P(c), P(o)) <= 1e-9, (e,)


def test_dao_thu_tu_va_dich_toan_bo_khong_doi_ket_qua():
    d = diem_phang(150, seed=4)
    t1, _ = dung(goc_cua(d), d)
    r = random.Random(5)
    d2 = list(d)
    r.shuffle(d2)
    t2, _ = dung(goc_cua(d2), d2)
    assert t1.tris == t2.tris and t1.x == t2.x                    # bất biến số 3: y hệt từng bit
    # dịch toàn bộ 10 km: mặt phẳng dịch theo, nội suy tại điểm tương ứng vẫn khớp
    dx, dy = 10_000.0, -7_000.0
    d3 = [(e + dx, n + dy, z) for e, n, z in d]
    t3, _ = dung(goc_cua(d3), d3)
    for e, n in ((E0 + 30, N0 + 20), (E0 + 77, N0 + 51)):
        assert t3.z_tai(e + dx, n + dy) == pytest.approx(t1.z_tai(e, n), abs=1e-6)


def test_gop_diem_trung_lay_trung_binh():
    d = diem_phang(60, seed=6)
    d2 = d + [(d[0][0], d[0][1], d[0][2] + 0.2)]                  # cùng chỗ, lệch 20 cm
    tin, bc = dung(goc_cua(d2), d2)
    assert bc.so_gop == 1 and bc.lech_gop_max_m == pytest.approx(0.2)
    assert tin.z_tai(d[0][0], d[0][1]) == pytest.approx(d[0][2] + 0.1, abs=1e-6)


# ---------------------------------------------------------------- đứt gãy
def nep(e, n):
    """Mặt gấp nếp dọc E = E0+50: hai nửa mặt phẳng khác nhau."""
    return 0.5 * abs(e - (E0 + 50)) + 0.1 * (n - N0)


def diem_nep(so=300, seed=7):
    r = random.Random(seed)
    d = [(E0 + r.uniform(0, 100), N0 + r.uniform(0, 80)) for _ in range(so)]
    d += [(E0, N0), (E0 + 100, N0), (E0, N0 + 80), (E0 + 100, N0 + 80)]
    return [(e, n, nep(e, n)) for e, n in d]


def dut_gay_nep():
    # đường nếp có đỉnh KHÔNG trùng điểm đo; ép buộc phải lật cạnh
    return [[(E0 + 50, N0 + y, nep(E0 + 50, N0 + y)) for y in (0, 17, 33, 52, 80)]]


def test_dut_gay_khong_canh_nao_cat_qua_va_noi_suy_chinh_xac():
    d = diem_nep()
    dg = dut_gay_nep()
    tin, bc = dung(goc_cua(d + dg[0]), d, dg)
    assert bc.so_doan_ep == 4 and not bc.xung_dot
    # mọi đoạn đứt gãy là một chuỗi cạnh có thật của TIN
    canh = canh_cua(tin)
    xy = {(round(e, 3), round(n, 3)): i for i, (e, n, _) in enumerate(tin.to_dict()["diem"])}
    ids = [xy[(round(e, 3), round(n, 3))] for e, n, _ in dg[0]]
    for a, b in zip(ids, ids[1:]):
        assert tuple(sorted((a, b))) in canh
    # không cạnh nào của TIN cắt thật sự qua đoạn đứt gãy
    P = lambda k: (tin.x[k], tin.y[k])
    for a, b in canh:
        for u, v in zip(ids, ids[1:]):
            assert giao_doan(P(a), P(b), P(u), P(v)) is None
    # nhờ ép đứt gãy, nội suy khớp mặt gấp nếp tuyệt đối
    r = random.Random(11)
    for _ in range(400):
        e, n = E0 + r.uniform(1, 99), N0 + r.uniform(1, 79)
        assert tin.z_tai(e, n) == pytest.approx(nep(e, n), abs=1e-7), (e - E0, n - N0)


def test_khong_co_dut_gay_thi_sai_so_lon_hon():
    """Đối chứng: bỏ đứt gãy thì sai số nội suy vượt xa — chứng tỏ test trên có sức nặng."""
    d = diem_nep()
    tin, _ = dung(goc_cua(d), d)
    r = random.Random(11)
    sai = max(abs(tin.z_tai(E0 + r.uniform(1, 99), N0 + r.uniform(1, 79)) - 0) for _ in range(1))
    r = random.Random(11)
    loi = 0.0
    for _ in range(400):
        e, n = E0 + r.uniform(1, 99), N0 + r.uniform(1, 79)
        loi = max(loi, abs(tin.z_tai(e, n) - nep(e, n)))
    assert loi > 0.05


def test_dut_gay_cat_nhau_lech_cao_thi_bao_loi():
    d = diem_phang(120, seed=8)
    dg = [[(E0 + 10, N0 + 10, 4.0), (E0 + 90, N0 + 70, 4.0)],
          [(E0 + 10, N0 + 70, 9.0), (E0 + 90, N0 + 10, 9.0)]]      # cắt nhau, lệch 5 m
    tin, bc = dung(goc_cua(d), d, dg)
    assert any(x["loai"] == "dut_gay_cat_nhau_lech_cao" for x in bc.xung_dot)
    dg[1] = [(E0 + 10, N0 + 70, 4.0), (E0 + 90, N0 + 10, 4.0)]     # cùng cao độ: hợp lệ
    tin, bc = dung(goc_cua(d), d, dg)
    assert not bc.xung_dot and bc.so_doan_ep == 4                  # mỗi đoạn tách đôi tại giao điểm


def test_dut_gay_lech_diem_do_bi_bao():
    d = diem_phang(80, seed=9)
    e, n, z = d[10]
    dg = [[(e, n, z + 0.5), (E0 + 5, N0 + 5, mat_phang(E0 + 5, N0 + 5))]]
    _, bc = dung(goc_cua(d), d, dg)
    assert any(x["loai"] == "dut_gay_lech_diem_do" for x in bc.xung_dot)


# ---------------------------------------------------------------- QC bề mặt
def test_tam_giac_qua_lon_bi_danh_dau_thieu_du_lieu():
    r = random.Random(12)
    d = []
    for _ in range(400):                       # đo dày, có một khoảng trống 40×40 m ở giữa
        e, n = E0 + r.uniform(0, 100), N0 + r.uniform(0, 100)
        if 30 < e - E0 < 70 and 30 < n - N0 < 70:
            continue
        d.append((e, n, mat_phang(e, n)))
    tin, bc = dung(goc_cua(d), d)
    assert bc.thieu_du_lieu, "khoảng trống phải bị đánh dấu"
    ra = tin.tra(E0 + 50, N0 + 50)
    assert ra is not None and ra[1] == T.LOAI_THIEU_DU_LIEU
    ra2 = tin.tra(E0 + 10, N0 + 10)
    assert ra2 is not None and ra2[1] == T.LOAI_TOT


def test_tam_giac_det_o_mep_bi_loai():
    d = diem_phang(100, seed=13)
    d.append((E0 + 50, N0 - 0.05, mat_phang(E0 + 50, N0 - 0.05)))    # điểm sát mép tạo tam giác dẹt
    d.append((E0 + 52, N0 - 0.05, mat_phang(E0 + 52, N0 - 0.05)))
    tin, bc = dung(goc_cua(d), d, goc_det_do=5.0)
    assert bc.rac, "tam giác rác ở mép phải bị loại và báo"


def test_toan_ven_json():
    d = diem_nep(100, seed=14)
    dg = dut_gay_nep()
    tin, _ = dung(goc_cua(d), d, dg)
    t2 = T.Tin.from_dict(tin.to_dict())
    assert t2.tris == tin.tris and t2.rang_buoc == tin.rang_buoc
    assert t2.z_tai(E0 + 20, N0 + 20) == pytest.approx(tin.z_tai(E0 + 20, N0 + 20), abs=1e-3)  # JSON làm tròn 0,1 mm


def test_thoi_gian_5000_diem():
    d = diem_phang(5000, seed=15, rong=300, cao=300)
    t0 = time.perf_counter()
    tin, _ = dung(goc_cua(d), d)
    giay = time.perf_counter() - t0
    print(f"\nTIN 5000 điểm: {giay:.2f} s, {len(tin.tris)} tam giác")
    assert giay < 20
