"""Điều kiện qua cửa giai đoạn 1:
   - báo ĐÚNG các điểm lỗi cố ý cài;
   - 11.000 điểm dưới 5 giây;
   - ánh xạ cột Excel nhớ lại được, và đổi khuôn thì tự hỏi lại.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import bang_in, cli, qc                # noqa: E402
from sannen.config import doc_lot, NGUONG_MAC_DINH  # noqa: E402
from sannen.paths import Lot                       # noqa: E402
import make_fixture                                # noqa: E402

ANH_XA = """anh_xa_cot_excel:
  id: Tên điểm
  northing: Tọa độ X(m)
  easting: Tọa độ Y(m)
  z: Cao độ H(m)
  code: Ghi chú
"""


def _lot_yaml(co_anh_xa: bool, dang: str = "excel", he_toa_do: str = "VN-2000") -> str:
    return f"""
ma_lo: XL-01
dot: 1
he_toa_do: {he_toa_do}
don_vi: m
phuong_phap_chinh_thuc: luoi_o_vuong
be_mat_moc: {{nguon: {dang}, file: moc.xlsx}}
be_mat_do:  {{nguon: {dang}, file: do.xlsx}}
luoi: {{kich_thuoc_o_m: 20, goc_xoay_do: 0}}
""" + (ANH_XA if co_anh_xa else "")


def _tao_lot(tmp: Path, n_moc=200, n_do=120, co_anh_xa=True, **kw) -> tuple[Lot, dict]:
    lot = Lot(tmp)
    lot.ensure()
    lot.lot_yaml.write_text(_lot_yaml(co_anh_xa, **kw), encoding="utf-8")
    loi = make_fixture.tao_xlsx(lot.input_dir / "moc.xlsx", n_moc, seed=11)
    make_fixture.tao_xlsx(lot.input_dir / "do.xlsx", n_do, seed=12, cai_loi=False, z0=3.1)
    return lot, loi


def _chay(lot: Lot, *them: str) -> int:
    return cli.main(["nhap", "--lot", str(lot.root), *them])


def _qc(lot: Lot) -> dict:
    return json.loads((lot.process_dir / "qc_input.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ số kiểu Việt Nam
@pytest.mark.parametrize("v, kq", [
    (2.85, 2.85), (3, 3.0), ("2,85", 2.85), ("103,5", 103.5), ("445012.345", 445012.345),
    ("1.113.045,123", 1113045.123), ("1,113,045.5", 1113045.5), ("1.113.045", 1113045.0),
    (" 2,805 ", 2.805), (" 2.8", 2.8), (None, None), ("", None), ("  ", None),
])
def test_doc_so(v, kq):
    assert bang_in.doc_so(v) == pytest.approx(kq) if kq is not None else bang_in.doc_so(v) is None


@pytest.mark.parametrize("v", ["n/a", "2.8m", "abc", "1_000", "nan", "inf", "--1", True])
def test_doc_so_chan_rac(v):
    with pytest.raises(ValueError):
        bang_in.doc_so(v)


# ------------------------------------------------------------------ đọc bảng
def test_doc_bang_dung_so_diem_va_bao_dung_dong_hong(tmp_path):
    lot, loi = _tao_lot(tmp_path)
    cfg = doc_lot(lot.lot_yaml)
    kq = bang_in.doc_bang(lot, cfg["be_mat_moc"], cfg, "moc")

    assert kq.so_khoi == 2 and kq.hang_tieu_de == make_fixture.HANG_TIEU_DE
    assert len(kq.diem) == 200 - 2                 # hai dòng hỏng cài sẵn bị bỏ
    assert kq.so_dong_hong == 2
    assert kq.so_hang_khong_phai_du_lieu == 3      # "Tổng cộng" + 2 dòng chú giải
    # chú giải KHÔNG bị tính là dòng hỏng, nhưng vẫn được liệt kê ở mức thông tin
    chu = [p for p in kq.phat_hien if p["loai"] == "dong_chu"]
    assert len(chu) == 1 and chu[0]["muc"] == "thong_tin"
    assert "hàng 109" in chu[0]["mo_ta"] and "hàng 110" in chu[0]["mo_ta"]
    hong = [p["mo_ta"] for p in kq.phat_hien if p["loai"] == "dong_hong"]
    assert not any("ĐỈNH TA LUY" in m for m in hong)
    for hang in loi["hong"]:
        assert any(f"hàng {hang}" in m for m in hong), (hang, hong)
    assert any("n/a" in m for m in hong) and any("thiếu z" in m for m in hong)
    # dấu phẩy kiểu Việt Nam đọc ĐÚNG, không bị coi là dòng hỏng
    d = next(p for p in kq.diem if p.id == loi["dau_phay"]["id"])
    assert d.z == pytest.approx(loi["dau_phay"]["z"])
    assert d.nguon.startswith("Mốc!hàng ")


def test_hai_khoi_tren_mot_dong_deu_duoc_doc(tmp_path):
    lot, _ = _tao_lot(tmp_path, n_moc=200)
    cfg = doc_lot(lot.lot_yaml)
    kq = bang_in.doc_bang(lot, cfg["be_mat_do"], cfg, "do")     # file sạch, 120 điểm
    assert len(kq.diem) == 120 and kq.so_dong_hong == 0
    assert {p.nguon.endswith("(khối 2)") for p in kq.diem} == {True, False}


def test_dung_khi_tieu_de_khai_khong_co_trong_file(tmp_path):
    lot, _ = _tao_lot(tmp_path)
    lot.lot_yaml.write_text(_lot_yaml(True).replace("Cao độ H(m)", "Cao trình"), encoding="utf-8")
    cfg = doc_lot(lot.lot_yaml)
    with pytest.raises(bang_in.LoiNguon, match="Không thấy tiêu đề"):
        bang_in.doc_bang(lot, cfg["be_mat_moc"], cfg, "moc")


def test_thieu_file_nguon_thi_dung(tmp_path):
    lot, _ = _tao_lot(tmp_path)
    (lot.input_dir / "moc.xlsx").unlink()
    cfg = doc_lot(lot.lot_yaml)
    with pytest.raises(bang_in.LoiNguon, match="Không thấy"):
        bang_in.doc_bang(lot, cfg["be_mat_moc"], cfg, "moc")


def test_csv_cung_khuon(tmp_path):
    lot = Lot(tmp_path)
    lot.ensure()
    (lot.input_dir / "moc.csv").write_text(
        "Tên điểm;Tọa độ X(m);Tọa độ Y(m);Cao độ H(m);Ghi chú\n"
        "A1;1113045,5;445012,25;2,85;tim đường\nA2;1113046;445013;abc;\n",
        encoding="utf-8")
    cfg = {"he_toa_do": "VN-2000", **yaml_anh_xa()}
    kq = bang_in.doc_bang(lot, {"nguon": "csv", "file": "moc.csv"}, cfg, "moc")
    assert len(kq.diem) == 1 and kq.so_dong_hong == 1
    assert kq.diem[0].northing == pytest.approx(1113045.5) and kq.diem[0].code == "tim đường"


def yaml_anh_xa() -> dict:
    import yaml
    return yaml.safe_load(ANH_XA)


# ------------------------------------------------------------------ cổng: báo đúng điểm lỗi
def test_bao_dung_cac_diem_loi_co_y_cai(tmp_path, capsys):
    lot, loi = _tao_lot(tmp_path)
    assert _chay(lot) in (0, 1)
    ph = _qc(lot)["phat_hien"]

    sai = [p for p in ph if p["loai"] == "cao_do_bat_thuong"]
    assert any(loi["cao_do_sai"]["id"] in p["mo_ta"] for p in sai)
    assert any(f"hàng {loi['cao_do_sai']['hang']}" in p["mo_ta"] for p in sai)  # tra ngược được dòng Excel

    a, b = loi["trung_cho"]
    trung = [p for p in ph if p["loai"] == "diem_trung"]
    assert any(a in p["mo_ta"] and b in p["mo_ta"] for p in trung)

    assert any(p["loai"] == "id_trung" and loi["id_lap"] in p["mo_ta"] for p in ph)
    assert sum(p["loai"] == "dong_hong" for p in ph) == 2

    # không có báo động giả trên bảng đo sạch
    do_sach = [p for p in ph if p["muc"] != "thong_tin" and "bề mặt đo" in p["mo_ta"]]
    assert do_sach == [], do_sach


def test_ma_viec_khong_trung_giua_hai_be_mat(tmp_path):
    lot, _ = _tao_lot(tmp_path)
    _tao_loi_o_be_mat_do(lot)
    _chay(lot)
    ma = [p["ma"] for p in _qc(lot)["phat_hien"]]
    assert len(ma) == len(set(ma)) and ma[0] == "V-01"
    assert "V-01" in (lot.process_dir / "viec_can_lam.md").read_text(encoding="utf-8")


def _tao_loi_o_be_mat_do(lot: Lot):
    make_fixture.tao_xlsx(lot.input_dir / "do.xlsx", 200, seed=12, cai_loi=True, z0=3.1)


def test_bat_duoc_dao_xy(tmp_path, capsys):
    lot, _ = _tao_lot(tmp_path)
    lot.lot_yaml.write_text(
        _lot_yaml(True).replace("northing: Tọa độ X(m)", "northing: @@")
                       .replace("easting: Tọa độ Y(m)", "easting: Tọa độ X(m)")
                       .replace("@@", "Tọa độ Y(m)"), encoding="utf-8")
    assert _chay(lot) == 1                                   # có việc chặn
    assert any(p["loai"] == "nghi_dao_xy" and p["muc"] == "chan" for p in _qc(lot)["phat_hien"])


def test_khong_bao_dao_xy_khi_dung_chieu(tmp_path):
    lot, _ = _tao_lot(tmp_path)
    _chay(lot)
    assert not any(p["loai"] == "nghi_dao_xy" for p in _qc(lot)["phat_hien"])


def test_nhieu_dong_hong_thi_chan(tmp_path):
    """Ánh xạ sai cột -> gần hết dòng hỏng -> phải chặn chứ không im lặng bỏ hết."""
    lot, _ = _tao_lot(tmp_path)
    lot.lot_yaml.write_text(_lot_yaml(True).replace("z: Cao độ H(m)", "z: Ghi chú"), encoding="utf-8")
    assert _chay(lot) == 1
    assert any(p["loai"] == "dong_hong_nhieu" for p in _qc(lot)["phat_hien"])


# ------------------------------------------------------------------ ánh xạ cột nhớ lại được
def test_anh_xa_chua_xac_nhan_thi_dung_va_hoi(tmp_path, capsys):
    lot, _ = _tao_lot(tmp_path, co_anh_xa=False)
    assert _chay(lot) == 2
    ra = capsys.readouterr().out
    assert "CẦN NGƯỜI XÁC NHẬN" in ra and "Tọa độ X(m)" in ra and "northing" in ra
    assert not (lot.root / bang_in.FILE_NHO).exists()
    assert not (lot.process_dir / "points_moc.csv").exists()   # chưa xác nhận thì không ghi gì


def test_xem_truoc_khong_luu_anh_xa(tmp_path):
    lot, _ = _tao_lot(tmp_path, co_anh_xa=False)
    assert _chay(lot, "--preview", "--xac-nhan-anh-xa") in (0, 1)
    assert not (lot.root / bang_in.FILE_NHO).exists()          # RULES 4


def test_nho_lai_anh_xa_va_hoi_lai_khi_doi_khuon(tmp_path, capsys):
    lot, _ = _tao_lot(tmp_path, co_anh_xa=False)
    assert _chay(lot, "--xac-nhan-anh-xa") in (0, 1)
    nho = lot.root / bang_in.FILE_NHO
    assert nho.exists()
    assert "Xác nhận ánh xạ cột" in (lot.log_dir / "decisions.md").read_text(encoding="utf-8")
    capsys.readouterr()

    # lần sau không cần cờ: ánh xạ đã nhớ, cả hai bảng cùng khuôn
    assert _chay(lot) in (0, 1)
    assert "anh_xa_cot.yaml" in capsys.readouterr().out
    assert len((__import__("yaml").safe_load(nho.read_text(encoding="utf-8")))["anh_xa"]) == 1

    # khảo sát nộp lại với tiêu đề khác -> dấu vân tay lệch -> không dùng ánh xạ cũ
    make_fixture.tao_xlsx(lot.input_dir / "moc.xlsx", 200,
                          tieu_de=["Tên điểm", "Tọa độ X(m)", "Tọa độ Y(m)", "Cao trình", "Ghi chú"])
    assert _chay(lot) == 2


# ------------------------------------------------------------------ RULES 3, 10
def test_khong_dong_vao_00_input_va_ghi_hash(tmp_path):
    lot, _ = _tao_lot(tmp_path)
    truoc = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in lot.input_dir.iterdir()}
    _chay(lot)
    sau = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in lot.input_dir.iterdir()}
    assert truoc == sau
    q = _qc(lot)
    assert q["nguon"]["be_mat_moc"]["hash_sha256"] == truoc["moc.xlsx"]
    assert len(q["hash_dau_vao"]) == 64
    bl = json.loads(next(lot.log_dir.glob("run_*.jsonl")).read_text(encoding="utf-8").splitlines()[-1])
    assert bl["hash_dau_vao"] == q["hash_dau_vao"]


def test_ket_qua_deterministic_khi_dao_thu_tu_diem(tmp_path):
    """Đảo thứ tự điểm không được làm đổi tập phát hiện (bất biến số 3)."""
    lot, _ = _tao_lot(tmp_path, n_moc=200)
    cfg = doc_lot(lot.lot_yaml)
    diem = bang_in.doc_bang(lot, cfg["be_mat_moc"], cfg, "moc").diem
    a = qc.kiem_tra(diem, NGUONG_MAC_DINH, "x", "VN-2000")
    b = qc.kiem_tra(list(reversed(diem)), NGUONG_MAC_DINH, "x", "VN-2000")
    chon = lambda ds: sorted((p["loai"], p["mo_ta"].split(" và ")[0][:40]) for p in ds
                             if p["loai"] == "cao_do_bat_thuong")
    assert chon(a) == chon(b)


def test_bo_dap_khong_bi_bao_nhung_loi_go_van_bi_bat():
    """Sống bờ đắp cao hơn nền 3 m không phải lỗi nhập; 1 → 10 m giữa nền thì phải bị bắt."""
    from sannen.dxfio import Diem
    diem = []
    for i in range(21):
        for j in range(21):
            x, y = i * 3.0, j * 3.0
            z = 1.0 + 3.0 * max(0.0, 1.0 - abs(x - 30.0) / 6.0)      # sống bờ đắp tại x=30
            diem.append(Diem(f"P{i:02d}_{j:02d}", 1113000 + y, 445000 + x, z))
    loi = next(p for p in diem if p.id == "P04_04")
    loi.z = 10.0
    ph = [p for p in qc.kiem_tra(diem, NGUONG_MAC_DINH, "t", "VN-2000")
          if p["loai"] == "cao_do_bat_thuong"]
    assert any("P04_04" in p["mo_ta"] for p in ph)
    assert not any(f"P10_{j:02d}" in p["mo_ta"] for p in ph for j in range(21)), ph


# ------------------------------------------------------------------ hiệu năng
def test_11000_diem_duoi_5_giay(tmp_path, capsys):
    lot, loi = _tao_lot(tmp_path, n_moc=11_000, n_do=400)
    t0 = time.perf_counter()
    ma = _chay(lot)
    giay = time.perf_counter() - t0
    print(f"\n11.000 điểm mốc + 400 điểm đo: {giay:.2f} s")
    assert ma in (0, 1)
    assert giay < 5.0, f"quá chậm: {giay:.2f} s"
    ph = _qc(lot)["phat_hien"]
    # ở quy mô thật vẫn bắt đúng điểm cài: không bị chìm trong báo động giả
    assert any(p["loai"] == "cao_do_bat_thuong" and loi["cao_do_sai"]["id"] in p["mo_ta"] for p in ph)
    assert sum(p["loai"] == "cao_do_bat_thuong" for p in ph) <= 10
