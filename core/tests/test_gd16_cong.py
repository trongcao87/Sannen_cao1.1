"""Chốt chặn cổng ở tầng CLI (cong.py): mọi lối vào — dòng lệnh, MCP, menu AutoCAD — đều qua `cli.main`.

Chạy với chốt THẬT (marker `cong_that` tắt phần tắt-chốt của conftest). Test dùng thẳng `cli.main`, không qua MCP,
để chứng minh CLI tự chặn chứ không nhờ lớp MCP.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, cong                                   # noqa: E402
from lot_giai_tich import E0, N0, hcn, tao                     # noqa: E402

pytestmark = pytest.mark.cong_that

F_DO = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)


def lot_moi(tmp_path):
    return tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, [hcn(30, 20, 60, 40)], so_diem=1500)


def chay(l, verb, *them):
    return cli.main([verb, "--lot", str(l.root), *them])


def duyet(l, c):
    van_ban, loi = cong.duyet_cong({"lot": str(l.root), "cong": c, "nguoi_duyet": "QS", "bang_chung": "ok"})
    assert not loi, van_ban


def test_chot_that_dang_bat(tmp_path):
    """Bảo hiểm cho conftest: nếu marker không bật được chốt thật thì mọi test dưới đây vô nghĩa."""
    l = lot_moi(tmp_path)
    ok, ly = cong.kiem_cong(l, "mat", False)
    assert ok is False and "Cổng 1" in ly


def test_cli_tu_choi_ghi_khi_chua_duyet_va_khong_tao_file(tmp_path, capsys):
    l = lot_moi(tmp_path)
    assert chay(l, "nhap") == 0                                 # nhap không cần cổng
    capsys.readouterr()
    assert chay(l, "mat") == 2
    ra = capsys.readouterr().out
    assert "TỪ CHỐI ghi `mat`" in ra and "Cổng 1" in ra
    assert not (l.process_dir / "surface_moc.json").exists()    # bị chặn TRƯỚC khi ghi, không phải phát hiện sau
    assert chay(l, "lo") == 2 and not (l.process_dir / "lo.json").exists()


def test_xem_truoc_luon_chay_khong_can_duyet(tmp_path, capsys):
    l = lot_moi(tmp_path)
    chay(l, "nhap")
    capsys.readouterr()
    assert chay(l, "mat", "--preview") < 2
    assert "TỪ CHỐI" not in capsys.readouterr().out
    assert not (l.process_dir / "surface_moc.json").exists()    # preview không ghi


def test_ba_cong_chan_dung_verb_cua_no(tmp_path, capsys):
    l = lot_moi(tmp_path)
    chay(l, "nhap")
    duyet(l, 1)
    assert chay(l, "mat") < 2 and chay(l, "lo") < 2
    capsys.readouterr()
    for verb in ("luoi", "tinh", "hieuchinh"):                  # cổng 2 chưa duyệt
        assert chay(l, verb) == 2, verb
        assert "Cổng 2" in capsys.readouterr().out
    duyet(l, 2)
    assert chay(l, "luoi") < 2 and chay(l, "tinh") < 2
    capsys.readouterr()
    assert chay(l, "xuat") == 2                                 # cổng 3 chưa duyệt
    assert "Cổng 3" in capsys.readouterr().out
    assert not (l.output_dir / "phieu_truy_vet.json").exists()
    duyet(l, 3)
    assert chay(l, "xuat") < 2 and (l.output_dir / "phieu_truy_vet.json").exists()


def test_ket_qua_doi_sau_khi_duyet_thi_cli_chan_lai(tmp_path, capsys):
    l = lot_moi(tmp_path)
    chay(l, "nhap")
    duyet(l, 1)
    chay(l, "mat"); chay(l, "lo")
    duyet(l, 2)
    with (l.process_dir / "surface_moc.json").open("a", encoding="utf-8") as f:
        f.write(" ")
    capsys.readouterr()
    assert chay(l, "luoi") == 2
    assert "mất hiệu lực" in capsys.readouterr().out


def test_cong_json_hong_thi_coi_la_chua_duyet(tmp_path, capsys):
    l = lot_moi(tmp_path)
    chay(l, "nhap")
    l.log_dir.mkdir(parents=True, exist_ok=True)
    (l.log_dir / "cong.json").write_text("{ không phải json", encoding="utf-8")
    capsys.readouterr()
    assert chay(l, "mat") == 2                                  # không bao giờ coi cong.json hỏng là "đã duyệt"
    assert not (l.process_dir / "surface_moc.json").exists()


def test_nhap_va_xem3d_khong_bi_chan(tmp_path, capsys):
    l = lot_moi(tmp_path)
    assert chay(l, "nhap") == 0
    ra = capsys.readouterr().out
    assert "TỪ CHỐI" not in ra
    assert cong.CONG_CAN == {"mat": 1, "lo": 1, "luoi": 2, "hieuchinh": 2, "tinh": 2, "xuat": 3}
    assert cong.kiem_cong(l, "nhap", False) == (True, "") and cong.kiem_cong(l, "xem3d", False) == (True, "")


def test_ba_lo_vao_dung_chung_mot_ham():
    """Chặn không lệch giữa các lối vào: MCP dùng đúng hàm của cong.py chứ không bản sao."""
    from sannen import mcp_server
    assert mcp_server.kiem_cong.__module__ == "sannen.cong" and mcp_server.cong_da_duyet is cong.cong_da_duyet
    assert mcp_server.duyet_cong is cong.duyet_cong
