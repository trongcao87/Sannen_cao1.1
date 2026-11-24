"""Giai đoạn 13 — xem3d: trình xem 3D HTML tự chứa cho hai bề mặt TIN."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, xem3d                                     # noqa: E402
from lot_giai_tich import E0, N0, chay_den, hcn, tao              # noqa: E402

F_MOC = lambda e, n: 10.0 + 0.01 * (e - E0)
F_DO = lambda e, n: 10.5 + 0.01 * (e - E0)


@pytest.fixture
def lo(tmp_path):
    l = tao(tmp_path / "lot", [hcn(0, 0, 100, 60)], F_MOC, F_DO, so_diem=800)
    chay_den(l, "luoi")
    return l


def nhung(p: Path) -> dict:
    m = re.search(r'<script type="application/json" id="du-lieu">(.*?)</script>',
                  p.read_text(encoding="utf-8"), re.S)
    assert m, "không thấy khối JSON nhúng"
    return json.loads(m.group(1))


def test_tao_file_mac_dinh_va_noi_dung(lo, capsys):
    assert cli.main(["xem3d", "--lot", str(lo.root)]) == 0
    p = lo.output_dir / "tin3d_view.html"
    assert p.exists() and str(p) in capsys.readouterr().out
    txt = p.read_bytes().decode("utf-8")                       # UTF-8 hợp lệ
    assert '<meta charset="utf-8">' in txt and "Phối cảnh" in txt and "Đào / Đắp" in txt
    for ngoai in ("http://", "https://", "<script src", "cdn"):
        assert ngoai not in txt, "file phải tự chứa, chạy offline"
    d = nhung(p)
    sm = json.loads((lo.process_dir / "surface_moc.json").read_text(encoding="utf-8"))
    sd = json.loads((lo.process_dir / "surface_do.json").read_text(encoding="utf-8"))
    assert len(d["moc"]["p"]) == len(sm["diem"]) and len(d["moc"]["t"]) == len(sm["tam_giac"])
    assert len(d["do"]["p"]) == len(sd["diem"]) and len(d["do"]["t"]) == len(sd["tam_giac"])
    assert len(d["do"]["dz"]) == len(sd["diem"])
    # toạ độ đã dời về trọng tâm: số nhỏ
    assert max(abs(v) for p_ in d["moc"]["p"] for v in p_[:2]) < 200
    assert abs(d["goc"][0] - E0) < 200 and abs(d["goc"][1] - N0) < 200
    # Δz = z_đo − z_mốc = 0,5 m trên mặt phẳng giải tích (đỉnh nằm trong TIN mốc)
    dz = [v for v in d["do"]["dz"] if v is not None]
    assert len(dz) > 0.9 * len(d["do"]["dz"])
    assert all(abs(v - 0.5) < 0.01 for v in dz)
    assert d["bien"] and d["luoi"] and d["phong_dai_z"] == 2.0


def test_hai_lan_cung_byte_va_ra_tuy_chon(lo, tmp_path):
    p1 = xem3d.tao_html(lo.root)
    b1 = p1.read_bytes()
    assert xem3d.tao_html(lo.root).read_bytes() == b1
    khac = tmp_path / "ra" / "xem.html"
    p2 = xem3d.tao_html(lo.root, khac, phong_dai_z=4)
    assert p2 == khac and nhung(khac)["phong_dai_z"] == 4.0
    assert not list(lo.input_dir.glob("*.html"))               # không đụng 00_input


def test_khong_ghi_vao_00_input(lo):
    with pytest.raises(PermissionError):
        xem3d.tao_html(lo.root, lo.input_dir / "x.html")


def test_thieu_surface_bao_loi_tieng_viet(lo, capsys):
    (lo.process_dir / "surface_do.json").unlink()
    assert cli.main(["xem3d", "--lot", str(lo.root)]) == 2
    out = capsys.readouterr().out
    assert "surface_do.json" in out and "mat" in out
    with pytest.raises(xem3d.ThieuBeMat):
        xem3d.tao_html(lo.root)
