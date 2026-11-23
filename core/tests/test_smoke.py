"""Điều kiện qua cửa giai đoạn 0: nhap chạy và đọc đúng số điểm."""
from __future__ import annotations
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import dxfio, qc, cli            # noqa: E402
from sannen.paths import Lot                 # noqa: E402
from sannen.config import NGUONG_MAC_DINH    # noqa: E402
import make_fixture                          # noqa: E402

LOT_YAML = """
ma_lo: MAU-01
dot: 1
he_toa_do: VN-2000
don_vi: m
phuong_phap_chinh_thuc: luoi_o_vuong
be_mat_moc: {nguon: dxf_layer, layer: SN-DIEM-MOC}
be_mat_do:  {nguon: dxf_layer, layer: SN-DIEM-DO}
luoi: {kich_thuoc_o_m: 20, goc_xoay_do: 0}
"""


@pytest.fixture
def lot(tmp_path: Path) -> Lot:
    l = Lot(tmp_path)
    l.ensure()
    l.lot_yaml.write_text(LOT_YAML, encoding="utf-8")
    make_fixture.tao(l.input_dir / "mau.dxf")
    return l


def test_doc_dung_so_diem(lot: Lot):
    d = dxfio.doc(lot.input_dir / "mau.dxf")
    assert len(d.diem_moc) == 604
    assert len(d.diem_do) == 414          # 413 + 1 điểm cài lỗi
    assert len(d.dut_gay) == 1
    assert len(d.bien_lo) == 1
    assert d.bien_lo[0].khep_kin
    assert d.bien_lo[0].dien_tich_m2 == pytest.approx(154 * 90, rel=1e-9)
    assert len(d.loai_tru) == 1
    assert d.loai_tru[0].dien_tich_m2 == pytest.approx(30 * 25, rel=1e-9)


def test_dut_gay_giu_cao_do(lot: Lot):
    d = dxfio.doc(lot.input_dir / "mau.dxf")
    zs = [z for _, _, z in d.dut_gay[0]]
    assert zs == pytest.approx([2.1, 2.6, 3.4])


def test_bat_duoc_loi_go_cao_do(lot: Lot):
    d = dxfio.doc(lot.input_dir / "mau.dxf")
    ph = qc.kiem_tra(d.diem_do, NGUONG_MAC_DINH, "bề mặt đo")
    assert any(p["loai"] == "cao_do_bat_thuong" for p in ph)


def test_layer_la_thi_dung(lot: Lot, tmp_path: Path):
    import ezdxf
    p = tmp_path / "la.dxf"
    doc = ezdxf.new("R2018")
    doc.layers.add("SN-CAI-GI-DO")
    doc.saveas(p)
    with pytest.raises(dxfio.LayerLa):
        dxfio.doc(p)


def test_khong_duoc_ghi_vao_00_input(lot: Lot):
    import pytest as _p
    with _p.raises(PermissionError):
        lot.guard_write(lot.input_dir / "bay.csv")


def test_cli_nhap_chay_va_ghi_du_file(lot: Lot, capsys):
    ma = cli.main(["nhap", "--lot", str(lot.root), "--preview"])
    assert ma in (0, 1)
    assert "XEM TRƯỚC" in capsys.readouterr().out
    cli.main(["nhap", "--lot", str(lot.root)])
    for ten in ("points_moc.csv", "points_do.csv", "breaklines.geojson",
                "boundary.geojson", "exclude.geojson", "qc_input.json",
                "viec_can_lam.md"):
        assert (lot.process_dir / ten).exists(), ten
    assert list(lot.log_dir.glob("run_*.jsonl"))
