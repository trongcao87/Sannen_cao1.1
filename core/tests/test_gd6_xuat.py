"""Giai đoạn 6 — xuat. Điều kiện qua cửa: dòng 3 và dòng 8 bảng tổng khớp = 0."""
from __future__ import annotations
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli                                            # noqa: E402
from lot_giai_tich import E0, N0, chay_het, hcn, tao              # noqa: E402

F_DO = lambda e, n: 10.0 + 0.02 * (e - E0 - 50) + 0.01 * (n - N0 - 30)


# ------------------------------------------------------------------ bộ tính công thức Excel (tập con)
class Excel:
    """Tính lại công thức SUM/ROUND/IF/ABS/AND/OR/MAX + số học, để kiểm file không cần mở Excel."""

    def __init__(self, wb):
        self.wb = wb
        self.nho = {}

    def gia_tri(self, sheet: str, o: str):
        k = (sheet, o)
        if k not in self.nho:
            v = self.wb[sheet][o].value
            self.nho[k] = self.tinh(sheet, v) if isinstance(v, str) and v.startswith("=") else v
        return self.nho[k]

    def _dai(self, sheet, a, b):
        from openpyxl.utils import range_boundaries
        c0, r0, c1, r1 = range_boundaries(f"{a}:{b}")
        from openpyxl.utils import get_column_letter as L
        return [self.gia_tri(sheet, f"{L(c)}{r}") for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]

    def tinh(self, sheet: str, f: str):
        s = f[1:].replace("$", "")
        chuoi: list[str] = []

        def giu(m):
            chuoi.append(m.group(0))
            return f"__S{len(chuoi) - 1}__"
        s = re.sub(r'"[^"]*"', giu, s)
        s = re.sub(r"'([^']+)'!([A-Z]+\d+):([A-Z]+\d+)", lambda m: f"_R({m[1]!r},{m[2]!r},{m[3]!r})", s)
        s = re.sub(r"'([^']+)'!([A-Z]+\d+)", lambda m: f"_C({m[1]!r},{m[2]!r})", s)
        s = re.sub(r"(?<![A-Za-z_'])([A-Z]{1,2}\d+):([A-Z]{1,2}\d+)(?!')",
                   lambda m: f"_R({sheet!r},{m[1]!r},{m[2]!r})", s)
        s = re.sub(r"(?<![A-Za-z_'])\b([A-Z]{1,2}\d+)\b(?!')", lambda m: f"_C({sheet!r},{m[1]!r})", s)
        s = re.sub(r"(?<![<>=!])=(?!=)", "==", s).replace("<>", "!=")
        for i, c in enumerate(chuoi):
            s = s.replace(f"__S{i}__", c)

        def nhan(*a):
            r = []
            for x in a:
                r += x if isinstance(x, list) else [x]
            return r
        env = {"_C": lambda sh, o: self.gia_tri(sh, o) or 0.0 if not isinstance(self.gia_tri(sh, o), str)
               else self.gia_tri(sh, o),
               "_R": lambda sh, a, b: self._dai(sh, a, b),
               "SUM": lambda *a: sum(x for x in nhan(*a) if isinstance(x, (int, float))),
               "ROUND": lambda x, n: round(x, int(n)) + 0.0, "ABS": abs,
               "IF": lambda c, a, b: a if c else b, "AND": lambda *a: all(a), "OR": lambda *a: any(a),
               "MAX": lambda *a: max(nhan(*a))}
        return eval(s, {"__builtins__": {}}, env)          # noqa: S307 — chỉ công thức do chính ta sinh


# ------------------------------------------------------------------ lô dùng chung
@pytest.fixture(scope="module")
def lo_xuat(tmp_path_factory):
    d = tmp_path_factory.mktemp("xuat")
    l = tao(d, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, [hcn(30, 20, 60, 40)], so_diem=2200)
    chay_het(l, "--sweep")
    # hai quyết định của người để thuyết minh phải nêu lại
    cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", "D02-02", "--z", "10.5", "--ly-do", "theo thiết kế"])
    cli.main(["tinh", "--lot", str(l.root), "--sweep"])
    assert cli.main(["xuat", "--lot", str(l.root)]) == 0
    return l


def wb_cua(l):
    return load_workbook(l.output_dir / "KL_GT-01_D01.xlsx")


def test_nam_file_dau_ra_va_ten_sheet(lo_xuat):
    ra = {p.name for p in lo_xuat.output_dir.iterdir()}
    assert {"KL_GT-01_D01.xlsx", "doi_chieu_2pp.xlsx", "bang_in_cad.json", "phieu_truy_vet.json",
            "thuyet_minh_phuong_phap.md"} <= ra
    wb = wb_cua(lo_xuat)
    assert wb.sheetnames == ["00_TONGKHOP", "01_BANG_O", "02_TONGHOP_LO", "03_DOICHIEU",
                            "04_MA_TRAN_PA", "05_QC", "06_TRUYVET"]
    assert wb.active.title == "00_TONGKHOP"                      # mở file thấy đầu tiên


def test_o_tong_la_cong_thuc_khong_phai_so_dan_cung(lo_xuat):
    ws = wb_cua(lo_xuat)["00_TONGKHOP"]
    for r in range(5, 10):
        for c in "CDEF":
            v = ws[f"{c}{r}"].value
            assert isinstance(v, str) and v.startswith("="), (r, c, v)
    assert "SUM('01_BANG_O'!F5:" in ws["C5"].value and "'02_TONGHOP_LO'!B" in ws["C6"].value
    assert ws["E12"].value.startswith("=ROUND(")
    ws1 = wb_cua(lo_xuat)["01_BANG_O"]
    assert ws1.cell(row=ws1.max_row, column=6).value.startswith("=SUM(F5:")


def test_tinh_lai_cong_thuc_dong_3_va_dong_8_bang_0(lo_xuat):
    wb = wb_cua(lo_xuat)
    x = Excel(wb)
    v = json.loads((lo_xuat.process_dir / "volume.json").read_text(encoding="utf-8"))
    T = "00_TONGKHOP"
    assert [x.gia_tri(T, f"{c}7") for c in "CDEF"] == [0, 0, 0, 0]          # dòng 3 = 0
    assert x.gia_tri(T, "E12") == 0                                          # dòng 8 = 0
    assert x.gia_tri(T, "H7") == "ĐẠT" and x.gia_tri(T, "H12") == "ĐẠT"
    # dòng 1 = số nộp của lõi, dòng 4 = số kiểm của lõi
    assert x.gia_tri(T, "C5") == pytest.approx(v["so_nop"]["dao_m3"], rel=1e-12)
    assert x.gia_tri(T, "D5") == pytest.approx(v["so_nop"]["dap_m3"], rel=1e-12)
    assert x.gia_tri(T, "C8") == pytest.approx(v["so_kiem"]["dao_m3"], rel=1e-12)
    # dòng 6 = diện tích đào + đắp = diện tích lô trừ loại trừ (6000 − 600) vì không có ô thiếu dữ liệu
    assert x.gia_tri(T, "E10") == pytest.approx(6000 - 600, rel=1e-9)
    assert x.gia_tri(T, "H9") in ("TRONG NGƯỠNG", "CẦN GIẢI THÍCH — xem 03_DOICHIEU")


def test_chi_tiet_o_cong_lai_dung_tong(lo_xuat):
    wb = wb_cua(lo_xuat)
    x = Excel(wb)
    v = json.loads((lo_xuat.process_dir / "volume.json").read_text(encoding="utf-8"))
    n = len(v["o"])
    assert x.gia_tri("01_BANG_O", f"F{5 + n}") == pytest.approx(sum(o["kl_dao_m3"] for o in v["o"]), rel=1e-12)
    assert x.gia_tri("03_DOICHIEU", f"F{5 + n}") == pytest.approx(
        sum(o["kl_dao_m3"] - o["lang_tru_dao_m3"] for o in v["o"]), abs=1e-9)


def test_ma_tran_phuong_an_co_du_bang_a_va_b(lo_xuat):
    ws = wb_cua(lo_xuat)["04_MA_TRAN_PA"]
    cot_a = [c.value for c in ws["A"] if c.value]
    for ma in [f"A{i}" for i in range(1, 9)] + [f"B{i}" for i in range(1, 6)] + ["B3*"]:
        assert ma in cot_a, ma
    text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "cận dưới" in text and "không đứng được" in text


def test_phieu_truy_vet_dung_schema_va_hash_dau_ra(lo_xuat):
    p = json.loads((lo_xuat.output_dir / "phieu_truy_vet.json").read_text(encoding="utf-8"))
    schema = json.loads((Path(__file__).resolve().parents[2] / "_agent" / "schema" / "truyvet.schema.json")
                        .read_text(encoding="utf-8"))
    for k in schema["required"]:
        assert k in p, k
    assert isinstance(p["dot"], int) and all({"file", "hash_sha256", "so_diem"} <= set(x) for x in p["dau_vao"])
    assert p["dau_vao"] and p["tham_so"]["kich_thuoc_o_m"] == 20
    for x in p["dau_ra"]:
        assert hashlib.sha256((lo_xuat.output_dir / x["file"]).read_bytes()).hexdigest() == x["hash_sha256"]
    assert any("D02-02" in q for q in p["quyet_dinh_cua_nguoi"])


def test_thuyet_minh_nhac_lai_quyet_dinh_cua_nguoi(lo_xuat):
    t = (lo_xuat.output_dir / "thuyet_minh_phuong_phap.md").read_text(encoding="utf-8")
    assert "Đã xử lý gì trên mô hình" in t and "D02-02" in t and "theo thiết kế" in t
    assert "Thông tư 13/2021/TT-BXD" in t or "13/2021" in t
    assert "lưới ô vuông" in t and "lăng trụ" in t and "5. Kết quả" in t


def test_bang_in_cad_chia_khoi_toi_da_40_dong_chi_khoi_cuoi_co_tong(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 100)], lambda e, n: 10.0, F_DO, o=10, so_diem=1800)
    v = chay_het(l)
    assert len(v["o"]) == 100
    assert cli.main(["xuat", "--lot", str(l.root)]) == 0
    b = json.loads((l.output_dir / "bang_in_cad.json").read_text(encoding="utf-8"))
    assert [len(k["hang"]) for k in b["khoi"]] == [40, 40, 20]
    assert [k["co_tong"] for k in b["khoi"]] == [False, False, True]
    tong = b["khoi"][-1]["tong"]
    tay = sum(r[5] for k in b["khoi"] for r in k["hang"])
    assert tong["kl_dao_m3"] == pytest.approx(tay, rel=1e-12)           # TỔNG = cộng các dòng
    assert tong["kl_dao_m3"] == pytest.approx(v["so_nop"]["dao_m3"], rel=1e-12)
    assert b["tieu_de"]["o_ky"] == ["Lập", "Kiểm", "Duyệt"] and b["kho_giay"] == "A3 ngang"
    assert len(b["cot"]) == 7


# ------------------------------------------------------------------ các cổng chặn
def test_xem_truoc_khong_ghi_gi(tmp_path, capsys):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, so_diem=1500)
    chay_het(l)
    assert cli.main(["xuat", "--lot", str(l.root), "--preview"]) == 0
    assert "XEM TRƯỚC" in capsys.readouterr().out
    assert not any(l.output_dir.iterdir())


def test_dung_khi_hieu_chinh_doi_sau_tinh(tmp_path, capsys):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, so_diem=1500)
    chay_het(l)
    cli.main(["hieuchinh", "--lot", str(l.root), "--dinh", "D02-02", "--z", "99"])
    assert cli.main(["xuat", "--lot", str(l.root)]) == 2
    assert "chạy lại `tinh`" in capsys.readouterr().out
    assert not any(l.output_dir.iterdir())
    cli.main(["tinh", "--lot", str(l.root)])
    assert cli.main(["xuat", "--lot", str(l.root)]) == 0


def test_dong_3_khac_0_la_loi_phan_mem_va_khong_ghi(tmp_path, capsys):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, so_diem=1500)
    chay_het(l)
    p = l.process_dir / "volume.json"
    v = json.loads(p.read_text(encoding="utf-8"))
    v["so_nop"]["dao_m3"] += 1.0                          # mô phỏng lỗi phần mềm: tổng hợp ≠ chi tiết
    p.write_text(json.dumps(v), encoding="utf-8")
    assert cli.main(["xuat", "--lot", str(l.root)]) == 1
    ra = capsys.readouterr().out
    assert "Dòng 3 khác 0" in ra and "lỗi phần mềm" in ra and "không làm tròn" in ra
    assert not any(l.output_dir.iterdir())


def test_con_viec_chan_thi_khong_xuat(tmp_path, capsys):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, so_diem=1500)
    chay_het(l)
    p = l.process_dir / "qc_volume.json"
    q = json.loads(p.read_text(encoding="utf-8"))
    q["phat_hien"].append({"ma": "T-99", "loai": "x", "muc": "chan", "mo_ta": "chưa giải quyết"})
    p.write_text(json.dumps(q), encoding="utf-8")
    assert cli.main(["xuat", "--lot", str(l.root)]) == 1
    assert "CHẶN còn tồn" in capsys.readouterr().out and not any(l.output_dir.iterdir())


def test_dung_khi_dau_vao_doi(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, F_DO, so_diem=1500)
    chay_het(l)
    with (l.input_dir / "gt.dxf").open("ab") as f:
        f.write(b"\n")
    assert cli.main(["xuat", "--lot", str(l.root)]) == 2


def test_luy_ke_hai_dot(tmp_path):
    l = tao(tmp_path, [hcn(0, 0, 100, 60)], lambda e, n: 10.0, lambda e, n: 11.0, so_diem=1500)
    v1 = chay_het(l)
    (l.root / "dot0.json").write_text(json.dumps(v1), encoding="utf-8")
    l.lot_yaml.write_text(l.lot_yaml.read_text(encoding="utf-8") + "\ndot_truoc: {volume_json: dot0.json}\n",
                          encoding="utf-8")
    cli.main(["tinh", "--lot", str(l.root)])
    assert cli.main(["xuat", "--lot", str(l.root)]) == 0
    ws = load_workbook(l.output_dir / "KL_GT-01_D01.xlsx")["02_TONGHOP_LO"]
    nhan = [c.value for c in ws["A"] if c.value]
    assert "Đợt trước" in nhan and "Lũy kế các đợt" in nhan
    x = Excel(load_workbook(l.output_dir / "KL_GT-01_D01.xlsx"))
    hang_luy_ke = 7
    assert x.gia_tri("02_TONGHOP_LO", f"C{hang_luy_ke}") == pytest.approx(2 * v1["so_nop"]["dap_m3"], rel=1e-12)
