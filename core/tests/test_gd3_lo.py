"""Giai đoạn 3 — lo. Điều kiện qua cửa: diện tích khớp lệnh AREA dưới 0,01 %."""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import ezdxf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, lo                                   # noqa: E402
from sannen.geom import Goc                                  # noqa: E402
from sannen.paths import Lot                                 # noqa: E402

E0, N0 = 445000.0, 1113000.0
LOT = """
ma_lo: LO-01
dot: 1
he_toa_do: VN-2000
phuong_phap_chinh_thuc: luoi_o_vuong
be_mat_moc: {nguon: dxf_layer, layer: SN-DIEM-MOC}
be_mat_do:  {nguon: dxf_layer, layer: SN-DIEM-DO}
luoi: {kich_thuoc_o_m: 20, goc_xoay_do: 0}
"""


def tao_lot(tmp: Path, bien=(), loai_tru=(), extra_yaml="") -> Lot:
    """bien / loai_tru: danh sách đa giác, mỗi đỉnh (e, n) hoặc (e, n, bulge)."""
    l = Lot(tmp)
    l.ensure()
    l.lot_yaml.write_text(LOT + extra_yaml, encoding="utf-8")
    doc = ezdxf.new("R2018")
    for ly in ("SN-DIEM-MOC", "SN-DIEM-DO", "SN-BIENLO", "SN-LOAITRU"):
        doc.layers.add(ly)
    msp = doc.modelspace()
    for ring, ly in [(b, "SN-BIENLO") for b in bien] + [(b, "SN-LOAITRU") for b in loai_tru]:
        pts = [(p[0], p[1], 0, 0, p[2] if len(p) > 2 else 0) for p in ring]
        msp.add_lwpolyline(pts, format="xyseb", close=True, dxfattribs={"layer": ly})
    for i in range(5):
        msp.add_point((E0 + i, N0 + i, 1.0), dxfattribs={"layer": "SN-DIEM-MOC"})
        msp.add_point((E0 + i, N0 + i, 2.0), dxfattribs={"layer": "SN-DIEM-DO"})
    doc.saveas(l.input_dir / "x.dxf")
    cli.main(["nhap", "--lot", str(l.root)])
    return l


def hcn(x0, y0, x1, y1):
    return [(E0 + x0, N0 + y0), (E0 + x1, N0 + y0), (E0 + x1, N0 + y1), (E0 + x0, N0 + y1)]


def doc(l: Lot) -> dict:
    return json.loads((l.process_dir / "lo.json").read_text(encoding="utf-8"))


def qc_lo(l: Lot) -> list[dict]:
    return json.loads((l.process_dir / "qc_lo.json").read_text(encoding="utf-8"))["phat_hien"]


def test_dien_tich_khop_va_tru_loai_tru(tmp_path):
    l = tao_lot(tmp_path, [hcn(0, 0, 154, 90)], [hcn(40, 30, 70, 55)])
    assert cli.main(["lo", "--lot", str(l.root)]) == 0
    d = doc(l)
    assert d["tong"]["dt_bien_lo_m2"] == pytest.approx(154 * 90, rel=1e-9)
    assert d["tong"]["dt_loai_tru_m2"] == pytest.approx(30 * 25, rel=1e-9)
    assert d["tong"]["dt_hieu_dung_m2"] == pytest.approx(154 * 90 - 750, rel=1e-9)


def test_chuan_chieu_ngoai_nguoc_kim_loai_tru_thuan_kim(tmp_path):
    ngoai_cw = hcn(0, 0, 100, 60)[::-1]                    # cố ý đưa vào thuận chiều kim
    lo_ccw = hcn(10, 10, 20, 20)                           # cố ý ngược chiều kim
    l = tao_lot(tmp_path, [ngoai_cw], [lo_ccw])
    cli.main(["lo", "--lot", str(l.root)])
    L = lo.doc_lo(l)
    assert L.dien_tich() == pytest.approx(100 * 60 - 100, rel=1e-9)   # tổng đại số tự trừ lỗ
    from sannen.geom import dien_tich_co_dau
    assert dien_tich_co_dau(L.ngoai[0]) > 0 > dien_tich_co_dau(L.lo[0])


def test_cung_tron_phai_bung_ban_nguyet(tmp_path):
    """Bán nguyệt bán kính 50 (bulge = 1): π·50²/2. Nối thẳng qua bulge sẽ ra 0."""
    r = 50.0
    l = tao_lot(tmp_path, [[(E0, N0, 1.0), (E0 + 2 * r, N0, 0.0)]])
    cli.main(["lo", "--lot", str(l.root)])
    a = doc(l)["tong"]["dt_bien_lo_m2"]
    assert a == pytest.approx(math.pi * r * r / 2, rel=5e-6)       # ≪ ngưỡng 0,01 % (1e-4)


@pytest.mark.parametrize("bulge, r_cung", [(0.5, None), (-0.3, None), (1.0, None), (2.0, None)])
def test_cung_nho_van_khop_nghiem_giai_tich(tmp_path, bulge, r_cung):
    """Hình chữ nhật 100×60 có cạnh đáy là cung: diện tích = 6000 ± diện tích viên phân."""
    theta = 4 * math.atan(abs(bulge))
    r = 100 / (2 * math.sin(theta / 2))
    vien_phan = r * r / 2 * (theta - math.sin(theta))
    mong_doi = 6000 + math.copysign(vien_phan, bulge)
    l = tao_lot(tmp_path, [[(E0, N0, bulge), (E0 + 100, N0), (E0 + 100, N0 + 60), (E0, N0 + 60)]])
    cli.main(["lo", "--lot", str(l.root)])
    assert doc(l)["tong"]["dt_bien_lo_m2"] == pytest.approx(mong_doi, rel=5e-6)


def test_doi_chieu_area_dung_va_lech(tmp_path):
    y = "\ndien_tich_area_cad_m2:\n  bien_lo: [13860.0]\n  loai_tru: [750.0]\n"
    l = tao_lot(tmp_path, [hcn(0, 0, 154, 90)], [hcn(40, 30, 70, 55)], y)
    assert cli.main(["lo", "--lot", str(l.root)]) == 0
    assert doc(l)["bien_lo"][0]["dien_tich_area_cad_m2"] == 13860.0
    # lệch 0,05 % > 0,01 % -> dừng
    l.lot_yaml.write_text(LOT + y.replace("13860.0", "13867.0"), encoding="utf-8")
    assert cli.main(["lo", "--lot", str(l.root)]) == 1
    assert any(p["loai"] == "area_lech" and p["muc"] == "chan" for p in qc_lo(l))


def test_bien_tu_cat_bi_chan_co_vi_tri(tmp_path):
    no = [(E0, N0), (E0 + 100, N0 + 100), (E0 + 100, N0), (E0, N0 + 100)]      # hình nơ
    l = tao_lot(tmp_path, [no])
    assert cli.main(["lo", "--lot", str(l.root)]) == 1
    p = next(p for p in qc_lo(l) if p["loai"] == "tu_cat")
    assert p["vi_tri"] == pytest.approx([E0 + 50, N0 + 50], abs=1e-3)


def test_loai_tru_ra_ngoai_bien_bi_chan(tmp_path):
    l = tao_lot(tmp_path, [hcn(0, 0, 100, 100)], [hcn(90, 90, 120, 120)])
    assert cli.main(["lo", "--lot", str(l.root)]) == 1
    assert any(p["loai"] == "loai_tru_ra_ngoai" for p in qc_lo(l))


def test_hai_vung_loai_tru_chong_nhau_bi_chan(tmp_path):
    l = tao_lot(tmp_path, [hcn(0, 0, 100, 100)], [hcn(10, 10, 40, 40), hcn(30, 30, 60, 60)])
    assert cli.main(["lo", "--lot", str(l.root)]) == 1
    assert any(p["loai"] == "loai_tru_chong_nhau" for p in qc_lo(l))


def test_tich_phan_trong_o_co_lo(tmp_path):
    """Ô [0,50]² chứa lỗ [10,30]²: ∫1 = 2500−400; ∫x = 62500−8000 (nghiệm giải tích)."""
    l = tao_lot(tmp_path, [hcn(0, 0, 100, 100)], [hcn(10, 10, 30, 30)])
    cli.main(["lo", "--lot", str(l.root)])
    goc = Goc(E0, N0)
    L = lo.doc_lo(l, goc)
    o = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
    assert L.dien_tich_trong(o) == pytest.approx(2100.0, rel=1e-12)
    assert L.tich_phan_trong(o, lambda x, y: x) == pytest.approx(54500.0, rel=1e-12)
    assert L.tich_phan_trong(o, lambda x, y: 3.0 + 0.5 * x - 0.25 * y) == pytest.approx(
        3 * 2100 + 0.5 * 54500 - 0.25 * (62500 - 8000), rel=1e-12)
    assert L.trong(60.0, 60.0) and not L.trong(20.0, 20.0) and not L.trong(150.0, 10.0)


def test_cat_o_vat_ranh_lo_lom(tmp_path):
    """Lô hình chữ L (lõm): diện tích phần giao với ô khớp tính tay."""
    chu_l = [(E0, N0), (E0 + 100, N0), (E0 + 100, N0 + 40), (E0 + 40, N0 + 40),
             (E0 + 40, N0 + 100), (E0, N0 + 100)]
    l = tao_lot(tmp_path, [chu_l])
    cli.main(["lo", "--lot", str(l.root)])
    L = lo.doc_lo(l, Goc(E0, N0))
    assert L.dien_tich() == pytest.approx(100 * 40 + 40 * 60, rel=1e-12)
    o = [(30.0, 30.0), (70.0, 30.0), (70.0, 70.0), (30.0, 70.0)]     # ô vắt qua chỗ lõm
    # phần thuộc chữ L: x∈[30,70],y∈[30,40] (400) + x∈[30,40],y∈[40,70] (300)
    assert L.dien_tich_trong(o) == pytest.approx(700.0, rel=1e-12)


def test_lo_dung_khi_dau_vao_doi(tmp_path, capsys):
    l = tao_lot(tmp_path, [hcn(0, 0, 100, 100)])
    with (l.input_dir / "x.dxf").open("ab") as f:
        f.write(b"\n")
    assert cli.main(["lo", "--lot", str(l.root)]) == 2
