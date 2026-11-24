"""Giai đoạn 4 — luoi + hieuchinh. Điều kiện qua cửa: tổng diện tích các ô = diện tích lô."""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli, luoi as L4                          # noqa: E402
from lot_giai_tich import E0, N0, chay_den, hcn, tao        # noqa: E402

f_moc = lambda e, n: 1.0 + 0.010 * (e - E0) + 0.004 * (n - N0)
f_do = lambda e, n: 3.0 + 0.002 * (e - E0)


def grid(l) -> dict:
    return json.loads((l.process_dir / "grid.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("goc", [0, 17.5, "auto"])
def test_tong_dien_tich_cac_o_bang_dien_tich_lo(tmp_path, goc):
    l = tao(tmp_path, [hcn(0, 0, 154, 90)], f_moc, f_do, [hcn(40, 30, 70, 55)], goc=goc)
    chay_den(l)
    assert cli.main(["luoi", "--lot", str(l.root)]) == 0
    g = grid(l)
    assert g["tong"]["dt_o_m2"] == pytest.approx(154 * 90 - 750, abs=1e-6)
    assert g["tong"]["dt_o_m2"] == pytest.approx(g["tong"]["dt_lo_m2"], abs=1e-9)
    assert sum(o["dt_huu_hieu_m2"] for o in g["o"]) == pytest.approx(154 * 90 - 750, abs=1e-5)


def test_luoi_lo_hinh_chu_l_xoay_tu_dong(tmp_path):
    chu_l = [(0, 0), (100, 0), (100, 40), (40, 40), (40, 100), (0, 100)]
    xoay = lambda p: (E0 + 0.8660254 * p[0] - 0.5 * p[1] + 50, N0 + 0.5 * p[0] + 0.8660254 * p[1] + 20)
    l = tao(tmp_path, [[xoay(p) for p in chu_l]], f_moc, f_do, goc="auto", so_diem=3000, le=16)
    chay_den(l)
    assert cli.main(["luoi", "--lot", str(l.root)]) == 0
    g = grid(l)
    # biên lưu ở độ chính xác 0,1 mm nên diện tích lô xoay lệch ~1e-6 tương đối, không hơn
    assert g["tong"]["dt_o_m2"] == pytest.approx(100 * 40 + 40 * 60, rel=2e-6)
    assert g["tong"]["dt_o_m2"] == pytest.approx(g["tong"]["dt_lo_m2"], abs=1e-9)
    # lưới tự bám theo cạnh dài: góc xoay là 30° hoặc 120° (mod 180)
    assert (g["tham_so"]["goc_xoay_do"] % 90) == pytest.approx(30.0, abs=1e-3)
    assert any(o["vat_ranh_lo"] for o in g["o"])


def test_cao_do_dinh_noi_suy_dung_mat_phang(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do, goc=0)
    chay_den(l, "luoi")
    for k, n in list(grid(l)["nut"].items())[:25]:
        assert n["z_moc"] == pytest.approx(f_moc(n["e"], n["n"]), abs=2e-4)   # JSON làm tròn 0,1 mm
        assert n["z_do"] == pytest.approx(f_do(n["e"], n["n"]), abs=2e-4)


def test_luoi_khong_deu_cot_hang_tuy_chinh(tmp_path):
    y = "\nluoi_khac: 1\n"
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do)
    l.lot_yaml.write_text(l.lot_yaml.read_text(encoding="utf-8").replace(
        "luoi: {kich_thuoc_o_m: 20, goc_xoay_do: 0}",
        "luoi: {kich_thuoc_o_m: 20, goc_xoay_do: 0, cot_m: [10, 30, 30, 30], hang_m: [20, 40]}"),
        encoding="utf-8")
    chay_den(l, "luoi")
    g = grid(l)
    assert (g["tham_so"]["nx"], g["tham_so"]["ny"]) == (4, 2)
    assert g["tong"]["dt_o_m2"] == pytest.approx(100 * 60, abs=1e-6)
    areas = sorted(o["dt_day_du_m2"] for o in g["o"])
    assert areas[0] == pytest.approx(10 * 20) and areas[-1] == pytest.approx(30 * 40)


def test_goc_luoi_cho_truoc_phu_kin_lo(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do)
    chay_den(l)
    assert cli.main(["luoi", "--lot", str(l.root), "--goc-luoi", f"{E0 + 7},{N0 + 3}"]) == 0
    g = grid(l)
    assert g["tong"]["dt_o_m2"] == pytest.approx(6000, abs=1e-6)
    assert g["tham_so"]["goc_luoi"][0] <= E0 + 1e-6 and g["tham_so"]["goc_luoi"][1] <= N0 + 1e-6


def test_vung_thieu_du_lieu_danh_dau_o_va_khong_tinh(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 100)], f_moc, f_do, so_diem=1400,
            khoang_trong=(30, 30, 70, 70))
    chay_den(l)
    cli.main(["luoi", "--lot", str(l.root)])
    g = grid(l)
    thieu = [o for o in g["o"] if o["thieu_du_lieu"]]
    assert thieu, "khoảng trống đo giữa lô phải làm vài ô bị đánh dấu"
    assert all(2 <= o["i"] <= 3 or 1 <= o["i"] <= 3 for o in thieu)
    q = json.loads((l.process_dir / "qc_luoi.json").read_text(encoding="utf-8"))
    assert any(p["loai"] == "o_thieu_du_lieu" for p in q["phat_hien"])


# ------------------------------------------------------------------ ngoại suy (RULES 8: người chấp nhận)
def _lo_do_vua_biên(tmp_path):
    """Khảo sát chỉ đo TRỌN BÊN TRONG biên (không phủ thừa); ô 30 m làm đỉnh biên rơi ra ngoài vùng đo."""
    return tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do, o=30, le=0.0, so_diem=1500,
               extra_yaml="\nnguong: {goc_tam_giac_det_do: 0}\n")


def test_mac_dinh_cam_ngoai_suy_o_sat_bien_bi_loai_va_bao(tmp_path):
    l = _lo_do_vua_biên(tmp_path)
    chay_den(l)
    assert cli.main(["luoi", "--lot", str(l.root)]) == 0
    g = grid(l)
    assert g["tham_so"]["ngoai_suy_m"] == 0
    thieu = [o for o in g["o"] if o["thieu_du_lieu"]]
    assert thieu and all(not o["ngoai_suy"] for o in g["o"])
    assert g["tong"]["dt_o_m2"] == pytest.approx(6000, abs=1e-5)        # ô vẫn phủ lô; chỉ không tính khối lượng
    q = json.loads((l.process_dir / "qc_luoi.json").read_text(encoding="utf-8"))
    assert any(p["loai"] == "o_thieu_du_lieu" for p in q["phat_hien"])
    assert not any(p["loai"] == "o_ngoai_suy" for p in q["phat_hien"])


def test_ngoai_suy_mac_dinh_la_diem_gan_nhat_khong_keo_dai_do_doc(tmp_path):
    """Trên lô thật 01-CGP, kéo dài mặt phẳng 20 m ở chân bờ đắp cho đào 4.521 m³ (lăng trụ: 68 m³)."""
    l = _lo_do_vua_biên(tmp_path)
    chay_den(l)
    assert cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "40"]) == 0
    gn = grid(l)
    assert gn["tham_so"]["ngoai_suy_kieu"] == "gan_nhat"
    assert cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "40", "--ngoai-suy-kieu", "mat_phang"]) == 0
    mp = grid(l)
    assert mp["tham_so"]["ngoai_suy_kieu"] == "mat_phang"
    # ở đỉnh ngoài vùng đo, hai cách cho cao độ khác nhau (mặt nghiêng thì kéo dài mới đổi theo vị trí)
    khac = [k for k, n in gn["nut"].items()
            if n["z_do"] is not None and abs(n["z_do"] - mp["nut"][k]["z_do"]) > 1e-3]
    assert khac
    # kiểu lạ thì bị từ chối ngay ở dòng lệnh, không tự đoán
    with pytest.raises(SystemExit) as e:
        cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "40", "--ngoai-suy-kieu", "sai"])
    assert e.value.code == 2


def test_nguoi_chap_nhan_ngoai_suy_thi_tinh_duoc_nhung_van_bi_co(tmp_path, capsys):
    l = _lo_do_vua_biên(tmp_path)
    chay_den(l)
    # kiểu mặt phẳng: mặt phẳng nghiêng thì kéo dài là CHÍNH XÁC (chỉ dùng được khi địa hình thật là phẳng)
    assert cli.main(["luoi", "--lot", str(l.root), "--ngoai-suy", "40", "--ngoai-suy-kieu", "mat_phang"]) == 0
    g = grid(l)
    assert g["tham_so"]["ngoai_suy_m"] == 40
    assert not any(o["thieu_du_lieu"] for o in g["o"])
    ns = [o for o in g["o"] if o["ngoai_suy"]]
    assert ns and all(o["vat_ranh_lo"] for o in ns)                       # chỉ ô sát biên mới cần ngoại suy
    q = json.loads((l.process_dir / "qc_luoi.json").read_text(encoding="utf-8"))
    cb = next(p for p in q["phat_hien"] if p["loai"] == "o_ngoai_suy")
    assert cb["muc"] == "canh_bao" and "RULES 8" in cb["he_qua_neu_bo_qua"]
    assert cli.main(["tinh", "--lot", str(l.root), "--sweep"]) == 0
    v = vol(l)
    assert v["so_nop"]["so_o_thieu"] == 0 and v["tham_so"]["ngoai_suy_m"] == 40
    # mặt phẳng nên ngoại suy chính xác; lưới (4 góc) và lăng trụ (đúng hình học) lệch nhau ≪ 5 %
    assert v["so_nop"]["rong_m3"] == pytest.approx(v["so_kiem"]["rong_m3"], rel=0.05)
    a1 = next(r for r in v["sweep"]["A"] if r["ma"] == "A1")
    assert a1["so_o_thieu"] == 0 and v["sweep"]["doc"]["dt_thieu_du_lieu_m2"]["min"] == 0
    # các phương án đặt lưới xoay xa (A6, A8) có đỉnh rơi xa hơn 40 m khỏi vùng đo nên vẫn loại vài ô:
    # sweep phải NÓI RA điều đó, không để người đọc ma trận tưởng chênh lệch do ô vắt ranh
    if v["sweep"]["doc"]["dt_thieu_du_lieu_m2"]["max"] > 0:
        assert "KHÔNG chỉ do ô vắt ranh" in v["sweep"]["doc"]["canh_bao_thieu_du_lieu"]


def test_sweep_canh_bao_khi_cac_phuong_an_loai_dien_tich_thieu_khac_nhau(tmp_path):
    l = _lo_do_vua_biên(tmp_path)
    chay_den(l, "luoi")
    cli.main(["tinh", "--lot", str(l.root), "--sweep"])
    d = vol(l)["sweep"]["doc"]
    assert d["dt_thieu_du_lieu_m2"]["max"] > 0
    assert "KHÔNG chỉ do ô vắt ranh" in d["canh_bao_thieu_du_lieu"]


def vol(l) -> dict:
    return json.loads((l.process_dir / "volume.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ hieuchinh
def _chuan_bi(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], f_moc, f_do, goc=0)
    chay_den(l, "luoi")
    return l


def test_hieuchinh_tu_cap_nhat_chenh_cao_dung_giai_tich(tmp_path, capsys):
    l = _chuan_bi(tmp_path)
    g = grid(l)
    ok = {o["ma"] for o in g["o"] if not o["thieu_du_lieu"]}
    # đỉnh trong chung 4 ô, cả 4 ô đều có đủ dữ liệu (điểm đo ngẫu nhiên có thể có 1-2 lỗ hổng thật)
    ma = next(m for m in sorted(g["nut"])
              if sum(1 for o in g["o"] if m in o["nut"] and o["ma"] in ok) == 4)
    z0 = g["nut"][ma]["z_do"]
    capsys.readouterr()
    assert cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", ma, "--z", str(z0 + 0.4),
                     "--ly-do", "thiết kế nâng"]) == 0
    ra = capsys.readouterr().out
    cung = [o for o in g["o"] if ma in o["nut"]]
    assert len(cung) == 4
    mong = sum(0.4 / 4 * o["dt_huu_hieu_m2"] for o in cung)       # mỗi ô: Δ(dz_tb) = Δz/4
    assert "Cộng các ô trên" in ra and "tự tính lại chênh cao" in ra
    adj = json.loads((l.process_dir / "grid_adjusted.json").read_text(encoding="utf-8"))
    assert adj["ghi_de"][0]["ma"] == ma and adj["ghi_de"][0]["z_moi"] == pytest.approx(z0 + 0.4)
    assert adj["ghi_de"][0]["z_goc"] == pytest.approx(z0)
    dec = (l.log_dir / "decisions.md").read_text(encoding="utf-8")
    assert ma in dec and "thiết kế nâng" in dec
    # tính độc lập: KL cộng các ô trước/sau
    nut = L4.nut_hieu_luc(g, L4.doc_hieu_chinh(l))
    sau = sum(L4.khoi_luong_o(o, nut)["kl_m3"] for o in cung)
    truoc = sum(L4.khoi_luong_o(o, g["nut"])["kl_m3"] for o in cung)
    assert sau - truoc == pytest.approx(mong, rel=1e-9)


def test_hieuchinh_xem_truoc_khong_ghi_va_bo_hoan_tac(tmp_path):
    l = _chuan_bi(tmp_path)
    assert cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", "D02-02", "--z", "9",
                     "--preview"]) == 0
    assert not (l.process_dir / "grid_adjusted.json").exists()
    cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", "D02-02", "--z", "9"])
    assert len(L4.doc_hieu_chinh(l)) == 1
    cli.main(["hieuchinh", "--lot", str(l.root), "--bo", "D02-02"])
    assert L4.doc_hieu_chinh(l) == []


def test_hieuchinh_ma_dinh_sai_thi_dung(tmp_path, capsys):
    l = _chuan_bi(tmp_path)
    assert cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", "D99-99", "--z", "1"]) == 2
    assert "Không có đỉnh" in capsys.readouterr().out


def test_hieuchinh_tu_file_csv(tmp_path):
    l = _chuan_bi(tmp_path)
    f = tmp_path / "sua.csv"
    f.write_text("ma,z,be_mat,ly_do\nD02-02,2.5,do,sửa A\nD03-03,2,5,moc,sửa B\n".replace("2,5,moc", '"2,5",moc'),
                 encoding="utf-8")
    assert cli.main(["hieuchinh", "--lot", str(l.root), "--tu-file", str(f)]) == 0
    adj = {(g["ma"], g["be_mat"]): g["z_moi"] for g in L4.doc_hieu_chinh(l)}
    assert adj[("D02-02", "do")] == 2.5 and adj[("D03-03", "moc")] == 2.5          # "2,5" kiểu Việt Nam


# ------------------------------------------------------------------ --resync
def test_resync_bao_chenh_lech_truoc_khi_nhan(tmp_path, capsys):
    l = _chuan_bi(tmp_path)
    g = grid(l)
    ma = "D02-03"
    f = tmp_path / "cad.json"
    f.write_text(json.dumps([{"ma": ma, "z": g["nut"][ma]["z_do"] + 0.1},
                             {"ma": "D01-01", "z": g["nut"]["D01-01"]["z_do"]}]), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["luoi", "--lot", str(l.root), "--resync", "--tu-file", str(f)]) == 1
    ra = capsys.readouterr().out
    assert ma in ra and "Chưa nhận" in ra and "D01-01" not in ra
    assert not (l.process_dir / "grid_adjusted.json").exists()          # chưa nhận thì không ghi
    assert cli.main(["luoi", "--lot", str(l.root), "--resync", "--tu-file", str(f), "--chap-nhan"]) == 0
    adj = L4.doc_hieu_chinh(l)
    assert len(adj) == 1 and adj[0]["z_moi"] == pytest.approx(g["nut"][ma]["z_do"] + 0.1)
    assert cli.main(["luoi", "--lot", str(l.root), "--resync", "--tu-file", str(f)]) == 0   # giờ khớp
