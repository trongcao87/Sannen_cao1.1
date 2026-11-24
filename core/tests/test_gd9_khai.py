"""Quyết định của người ghi trong lot.yaml: biên lô là một đa tuyến cụ thể; vùng thiếu dữ liệu bù bằng điểm đo gần nhất."""
from __future__ import annotations
import csv
import json
import math
import sys
from pathlib import Path

import ezdxf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, dxfio                                        # noqa: E402
from sannen.paths import Lot                                         # noqa: E402
import make_fixture                                                  # noqa: E402
from lot_giai_tich import E0, N0, chay_den, hcn, tao                 # noqa: E402

f_moc = lambda e, n: 1.0 + 0.010 * (e - E0) + 0.004 * (n - N0)
f_do = lambda e, n: 3.0 + 0.002 * (e - E0)


def dxf_tho(duong_dan: Path, cac_da_giac: dict[str, list]) -> Path:
    """Bản vẽ NHÀ THẦU: chưa có layer SN-, biên nằm trên layer '0'."""
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    for ten, ring in cac_da_giac.items():
        msp.add_lwpolyline([(p[0], p[1], 0, 0, p[2] if len(p) > 2 else 0) for p in ring], format="xyseb",
                           close=True, dxfattribs={"layer": "0"})
    doc.saveas(duong_dan)
    return duong_dan


def test_doc_bien_polyline_chon_dung_mot_da_tuyen(tmp_path):
    p = dxf_tho(tmp_path / "t.dxf", {"a": hcn(0, 0, 100, 60),                       # 4 đỉnh
                                     "b": [(E0, N0), (E0 + 50, N0), (E0 + 50, N0 + 30), (E0 + 25, N0 + 40), (E0, N0 + 30)]})
    b = dxfio.doc_bien_polyline(p, "0", 5)
    assert len(b.dinh) == 5 and b.khep_kin and b.dien_tich_m2 == pytest.approx(50 * 30 + 0.5 * 50 * 10)
    with pytest.raises(dxfio.LoiBien, match="tìm thấy 0 đa tuyến.*4 đỉnh khép kín.*5 đỉnh khép kín"):
        dxfio.doc_bien_polyline(p, "0", 7)                   # không có: liệt kê ứng viên cho người chọn
    q = dxf_tho(tmp_path / "hai.dxf", {"a": hcn(0, 0, 10, 10), "b": hcn(20, 0, 30, 10)})
    with pytest.raises(dxfio.LoiBien, match="tìm thấy 2"):   # mơ hồ thì dừng, không đoán
        dxfio.doc_bien_polyline(q, "0", 4)


def _lot_excel_bien_khai(tmp_path) -> Lot:
    l = Lot(tmp_path)
    l.ensure()
    dxf_tho(l.input_dir / "ban_ve_nha_thau.dxf", {"khung": hcn(-50, -50, 400, 300), "lo": hcn(0, 0, 100, 60)})
    make_fixture.tao_xlsx(l.input_dir / "moc.xlsx", 400, seed=1, cai_loi=False)
    make_fixture.tao_xlsx(l.input_dir / "do.xlsx", 400, seed=2, cai_loi=False, z0=3.1)
    l.lot_yaml.write_text("""ma_lo: KHAI-01
dot: 1
he_toa_do: VN-2000
phuong_phap_chinh_thuc: luoi_o_vuong
be_mat_moc: {nguon: excel, file: moc.xlsx}
be_mat_do: {nguon: excel, file: do.xlsx}
bien_lo: {nguon: dxf_polyline, file: ban_ve_nha_thau.dxf, layer: "0", so_dinh: 4}
luoi: {kich_thuoc_o_m: 20, goc_xoay_do: 0}
""", encoding="utf-8")
    return l


def test_nhap_dung_bien_nguoi_khai_va_ghi_hash(tmp_path):
    l = _lot_excel_bien_khai(tmp_path)
    # có HAI đa tuyến 4 đỉnh trên layer 0 → mơ hồ → dừng, nói rõ
    assert cli.main(["nhap", "--lot", str(l.root), "--xac-nhan-anh-xa"]) == 2
    dxf_tho(l.input_dir / "ban_ve_nha_thau.dxf", {"khung": hcn(-50, -50, 400, 300)[:3] + [(E0 + 399, N0 + 301), (E0, N0 + 5)],
                                                  "lo": hcn(0, 0, 100, 60)})
    assert cli.main(["nhap", "--lot", str(l.root), "--xac-nhan-anh-xa"]) in (0, 1)
    b = json.loads((l.process_dir / "boundary.geojson").read_text(encoding="utf-8"))
    assert len(b["features"]) == 1 and b["features"][0]["properties"]["dien_tich_m2"] == pytest.approx(6000)
    q = json.loads((l.process_dir / "qc_input.json").read_text(encoding="utf-8"))
    assert q["nguon"]["bien_lo"]["file"] == "ban_ve_nha_thau.dxf" and q["nguon"]["bien_lo"]["so_dinh"] == 4
    assert not any(p["loai"] == "thieu_dxf" for p in q["phat_hien"])
    # đổi bản vẽ sau nhap → mat dừng (hash bao gồm cả file biên)
    with (l.input_dir / "ban_ve_nha_thau.dxf").open("ab") as f:
        f.write(b"\n")
    assert cli.main(["mat", "--lot", str(l.root)]) == 2


# ------------------------------------------------------------------ bù bằng điểm đo gần nhất
def _doc_diem(l: Lot, ten: str):
    with (l.process_dir / ten).open(encoding="utf-8") as f:
        return [(float(r["easting"]), float(r["northing"]), float(r["z"])) for r in csv.DictReader(f)]


def test_diem_gan_nhat_bu_dinh_ngoai_vung_do(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do, o=30, le=0.0, so_diem=1500,
            extra_yaml="\nnguong: {goc_tam_giac_det_do: 0}\n")
    chay_den(l)
    assert cli.main(["luoi", "--lot", str(l.root)]) == 0
    assert any(o["thieu_du_lieu"] for o in json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))["o"])
    # đỉnh góc xa nhất của lưới 30 m cách điểm đo gần nhất √(20²+30²) = 36 m → cho bù trong 45 m
    assert cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "45", "--ngoai-suy-kieu", "diem_gan_nhat"]) == 0
    g = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert g["tham_so"]["ngoai_suy_kieu"] == "diem_gan_nhat"
    assert not any(o["thieu_du_lieu"] for o in g["o"])
    do = _doc_diem(l, "points_do.csv")
    bu = [n for n in g["nut"].values() if not (E0 - 1e-6 <= n["e"] <= E0 + 100 + 1e-6 and N0 - 1e-6 <= n["n"] <= N0 + 60 + 1e-6)]
    assert bu, "phải có đỉnh nằm ngoài vùng đo"
    for n in bu:      # cao độ đỉnh bù PHẢI đúng bằng cao độ của một điểm đo thật, là điểm gần nhất
        gan = min(do, key=lambda p: math.hypot(p[0] - n["e"], p[1] - n["n"]))
        assert n["z_do"] == pytest.approx(gan[2], abs=2e-4)
    q = json.loads((l.process_dir / "qc_luoi.json").read_text(encoding="utf-8"))
    cb = next(p for p in q["phat_hien"] if p["loai"] == "o_ngoai_suy")
    assert "ĐIỂM ĐO gần nhất" in cb["mo_ta"]


def test_diem_gan_nhat_bu_ca_lo_hong_giua_lo(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 100)], f_moc, f_do, so_diem=1400, khoang_trong=(30, 30, 70, 70))
    chay_den(l)
    cli.main(["luoi", "--lot", str(l.root)])
    g0 = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert any(o["thieu_du_lieu"] for o in g0["o"])                       # mặc định: lỗ hổng làm ô bị loại
    assert cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "30", "--ngoai-suy-kieu", "diem_gan_nhat"]) == 0
    g = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert not any(o["thieu_du_lieu"] for o in g["o"])
    bu = [o for o in g["o"] if o["ngoai_suy"]]
    assert bu and len(bu) >= sum(1 for o in g0["o"] if o["thieu_du_lieu"])  # ô từng bị loại giờ mang cờ "đã bù"
    assert cli.main(["tinh", "--lot", str(l.root), "--sweep"]) == 0
    v = json.loads((l.process_dir / "volume.json").read_text(encoding="utf-8"))
    assert v["so_nop"]["so_o_thieu"] == 0 and v["dt_dao_dap_thieu_tru_dt_lo_m2"] == pytest.approx(0, abs=1e-6)
    assert v["tham_so"]["ngoai_suy_kieu"] == "diem_gan_nhat"


def test_xa_hon_ban_kinh_thi_van_thieu(tmp_path):
    """Người chỉ cho bù trong 3 m thì ô cách vùng đo xa hơn vẫn bị loại — không tự nới."""
    l = tao(tmp_path, [hcn(0, 0, 100, 100)], f_moc, f_do, so_diem=1400, khoang_trong=(20, 20, 80, 80))
    chay_den(l)
    cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "3", "--ngoai-suy-kieu", "diem_gan_nhat"])
    g = json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))
    assert any(o["thieu_du_lieu"] for o in g["o"])
