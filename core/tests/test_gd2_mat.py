"""Giai đoạn 2 — verb `mat` chạy trọn từ DXF mẫu."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, mat                      # noqa: E402
from sannen.paths import Lot                     # noqa: E402
from sannen.tin import Tin                       # noqa: E402
import make_fixture                              # noqa: E402
from test_smoke import LOT_YAML                  # noqa: E402


@pytest.fixture
def lot_nhap(tmp_path) -> Lot:
    l = Lot(tmp_path)
    l.ensure()
    l.lot_yaml.write_text(LOT_YAML, encoding="utf-8")
    make_fixture.tao(l.input_dir / "mau.dxf")
    cli.main(["nhap", "--lot", str(l.root)])
    return l


def test_mat_ghi_du_file_va_tin_phu_kin_vung_do(lot_nhap, capsys):
    ma = cli.main(["mat", "--lot", str(lot_nhap.root)])
    assert ma in (0, 1)
    for ten in ("surface_moc.json", "surface_do.json", "qc_surface.json"):
        assert (lot_nhap.process_dir / ten).exists(), ten
    moc = Tin.from_dict(json.loads((lot_nhap.process_dir / "surface_moc.json").read_text(encoding="utf-8")))
    do = Tin.from_dict(json.loads((lot_nhap.process_dir / "surface_do.json").read_text(encoding="utf-8")))
    assert moc.goc == do.goc                       # một gốc chung cho hai bề mặt
    # giữa khu đất có điểm đo thì nội suy ra số
    assert moc.z_tai(make_fixture.E0 + 100, make_fixture.N0 + 30) is not None
    assert do.z_tai(make_fixture.E0 + 100, make_fixture.N0 + 30) is not None


def test_mat_ep_dut_gay_tu_dxf(lot_nhap):
    cli.main(["mat", "--lot", str(lot_nhap.root), "--be-mat", "moc"])
    d = json.loads((lot_nhap.process_dir / "surface_moc.json").read_text(encoding="utf-8"))
    assert d["thong_ke"]["so_doan_ep"] == 2         # polyline 3 đỉnh = 2 đoạn
    assert len(d["canh_rang_buoc"]) >= 2


def test_mat_dung_khi_dau_vao_doi_sau_nhap(lot_nhap, capsys):
    with (lot_nhap.input_dir / "mau.dxf").open("ab") as f:
        f.write(b"\n")                              # đổi hash mà không hỏng DXF
    assert cli.main(["mat", "--lot", str(lot_nhap.root)]) == 2
    assert "đã thay đổi" in capsys.readouterr().out
    assert not (lot_nhap.process_dir / "surface_moc.json").exists()


def test_mat_xem_truoc_khong_ghi(lot_nhap, capsys):
    cli.main(["mat", "--lot", str(lot_nhap.root), "--preview"])
    assert "XEM TRƯỚC" in capsys.readouterr().out
    assert not (lot_nhap.process_dir / "surface_moc.json").exists()


def test_mat_chua_nhap_thi_bao(tmp_path, capsys):
    l = Lot(tmp_path)
    l.ensure()
    l.lot_yaml.write_text(LOT_YAML, encoding="utf-8")
    assert cli.main(["mat", "--lot", str(l.root)]) == 2
    assert "nhap" in capsys.readouterr().out


def test_mat_deterministic_hai_lan_chay(lot_nhap):
    cli.main(["mat", "--lot", str(lot_nhap.root)])
    a = (lot_nhap.process_dir / "surface_moc.json").read_bytes()
    cli.main(["mat", "--lot", str(lot_nhap.root)])
    assert a == (lot_nhap.process_dir / "surface_moc.json").read_bytes()
