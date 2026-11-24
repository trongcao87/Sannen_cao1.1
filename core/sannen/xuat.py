"""Verb `xuat` (giai đoạn 6): workbook 7 sheet, bảng in CAD, phiếu truy vết, thuyết minh.

Quy tắc cứng (kb/mau-bieu.md, RULES 4): dòng 3 và dòng 8 của bảng tổng khớp phải BẰNG 0.
Khác 0 là lỗi phần mềm — DỪNG, không làm tròn cho khớp. Mọi ô tổng trong 00_TONGKHOP là
CÔNG THỨC tham chiếu sang sheet chi tiết, không phải số dán cứng.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, io_out
from .bang_in import bam_sha256
from .config import nguong
from .luoi import doc_hieu_chinh
from .mat import DauVaoDaDoi, kiem_hash_dau_vao
from .paths import Lot
from .tinh import hash_hieu_chinh

TONG_KHOP, BANG_O, TONG_LO, DOI_CHIEU, MA_TRAN, QC, TRUY_VET = (
    "00_TONGKHOP", "01_BANG_O", "02_TONGHOP_LO", "03_DOICHIEU", "04_MA_TRAN_PA", "05_QC", "06_TRUYVET")
KB = Path(__file__).resolve().parents[2] / "_agent" / "kb"
TOI_DA_DONG_KHOI_CAD = 40
FILE_QC = (("nhap", "qc_input.json"), ("mat", "qc_surface.json"), ("lo", "qc_lo.json"),
           ("luoi", "qc_luoi.json"), ("tinh", "qc_volume.json"))


# =========================================================================== số liệu & kiểm khớp
def _qc_tat_ca(lot: Lot) -> list[tuple[str, dict]]:
    ra = []
    for verb, ten in FILE_QC:
        p = lot.process_dir / ten
        if p.exists():
            ra += [(verb, f) for f in io_out.doc_json(p).get("phat_hien", [])]
    return ra


def _dot_truoc(lot: Lot, cfg: dict) -> dict | None:
    ch = (cfg.get("dot_truoc") or {}).get("volume_json")
    if not ch:
        return None
    p = Path(ch) if Path(ch).is_absolute() else lot.root / ch
    return io_out.doc_json(p) if p.exists() else None


def kiem_khop(v: dict, ng: dict) -> dict:
    """Ba điều kiện khớp, tính bằng Python TRƯỚC khi ghi — cùng phép với công thức trong Excel."""
    o = v["o"]
    s = lambda k: sum(c.get(k, 0.0) for c in o)
    d1 = [s("kl_dao_m3"), s("kl_dap_m3"), s("dt_dao_m2"), s("dt_dap_m2")]
    n, k = v["so_nop"], v["so_kiem"]
    d2 = [n["dao_m3"], n["dap_m3"], n["dt_dao_m2"], n["dt_dap_m2"]]
    d3 = [round(a - b, 6) + 0.0 for a, b in zip(d1, d2)]
    d4 = [k["dao_m3"], k["dap_m3"], k["dt_dao_m2"], k["dt_dap_m2"]]
    c_dao, c_dap = d1[0] - d4[0], d1[1] - d4[1]
    p_dao = 100 * c_dao / d4[0] if d4[0] else 0.0
    p_dap = 100 * c_dap / d4[1] if d4[1] else 0.0
    d6 = d1[2] + d1[3]
    d7 = v["dt_lo_m2"] - n["dt_thieu_du_lieu_m2"]
    d8 = round(d6 - d7, 6) + 0.0
    trong_nguong = ((abs(c_dao) <= ng["o_lech_lon_m3"] or abs(p_dao) <= ng["o_lech_lon_pct"])
                    and (abs(c_dap) <= ng["o_lech_lon_m3"] or abs(p_dap) <= ng["o_lech_lon_pct"]))
    return {"dong1": d1, "dong2": d2, "dong3": d3, "dong4": d4, "dong5_m3": [c_dao, c_dap],
            "dong5_pct": [p_dao, p_dap], "dong6": d6, "dong7": d7, "dong8": d8,
            "dong3_dat": all(x == 0 for x in d3), "dong8_dat": d8 == 0,
            "dong5_trong_nguong": trong_nguong}


# =========================================================================== workbook
def _styles():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    mong = Side(style="thin", color="999999")
    return {"dam": Font(bold=True), "tieu_de": Font(bold=True, size=13),
            "nen": PatternFill("solid", fgColor="DDE6F0"), "tong": PatternFill("solid", fgColor="F2F2F2"),
            "vien": Border(left=mong, right=mong, top=mong, bottom=mong),
            "giua": Alignment(horizontal="center", vertical="center", wrap_text=True),
            "xuong": Alignment(wrap_text=True, vertical="top")}


def _dau_bang(ws, hang: int, cot: list[str], st) -> None:
    for c, t in enumerate(cot, 1):
        x = ws.cell(row=hang, column=c, value=t)
        x.font, x.fill, x.alignment, x.border = st["dam"], st["nen"], st["giua"], st["vien"]


def _rong_cot(ws, rong: list[float]) -> None:
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(rong, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _tieu_de(ws, cfg: dict, du_an: dict, ten: str, st) -> None:
    ws["A1"] = f"{ten} — {du_an.get('ten_du_an', '')} — Lô {cfg['ma_lo']} — Đợt {cfg['dot']}"
    ws["A1"].font = st["tieu_de"]
    ws["A2"] = (f"Phương pháp nộp: lưới ô vuông · lõi {__version__} · "
                f"lập {datetime.now():%d/%m/%Y %H:%M}")


def tao_workbook(lot: Lot, cfg: dict, du_an: dict, v: dict, kt: dict, qc_all, qi: dict, ng: dict,
                 grid: dict, ghi_de: list, quyet_dinh: list[str], truoc: dict | None, ten_file: str):
    from openpyxl import Workbook
    st = _styles()
    wb = Workbook()
    ws0 = wb.active
    ws0.title = TONG_KHOP
    ws1, ws2, ws3, ws4, ws5, ws6 = (wb.create_sheet(t) for t in (BANG_O, TONG_LO, DOI_CHIEU, MA_TRAN, QC, TRUY_VET))
    f3, f2 = "#,##0.000", "#,##0.00"
    cells = v["o"]

    # ---- 01_BANG_O -----------------------------------------------------------
    _tieu_de(ws1, cfg, du_an, "Bảng khối lượng từng ô", st)
    _dau_bang(ws1, 4, ["Ô", "DT hữu hiệu (m²)", "Cao độ TB mốc (m)", "Cao độ TB đo (m)", "Chênh cao TB (m)",
                       "KL đào (m³)", "KL đắp (m³)", "DT đào (m²)", "DT đắp (m²)", "Ghi chú"], st)
    for r, c in enumerate(cells, 5):
        ws1.cell(row=r, column=1, value=c["ma"])
        ws1.cell(row=r, column=2, value=c["dt_huu_hieu_m2"])
        if c["thieu_du_lieu"]:
            for col in range(3, 10):
                ws1.cell(row=r, column=col, value=None if col < 6 else 0.0)
            ws1.cell(row=r, column=10, value="THIẾU DỮ LIỆU — không tính khối lượng (RULES 8)")
        else:
            for col, key in ((3, "z_tb_moc"), (4, "z_tb_do"), (5, "dz_tb"), (6, "kl_dao_m3"),
                             (7, "kl_dap_m3"), (8, "dt_dao_m2"), (9, "dt_dap_m2")):
                ws1.cell(row=r, column=col, value=c[key])
            if c["vat_ranh_lo"]:
                ws1.cell(row=r, column=10, value="ô vắt ranh lô")
        for col in (2, 3, 4, 5, 6, 7, 8, 9):
            ws1.cell(row=r, column=col).number_format = f3
    r1 = 4 + len(cells)
    tong_r = r1 + 1
    ws1.cell(row=tong_r, column=1, value="TỔNG").font = st["dam"]
    for col in (2, 6, 7, 8, 9):
        L = chr(64 + col)
        x = ws1.cell(row=tong_r, column=col, value=f"=SUM({L}5:{L}{r1})")
        x.number_format, x.font, x.fill = f3, st["dam"], st["tong"]
    ws1.freeze_panes = "B5"
    _rong_cot(ws1, [11, 16, 16, 16, 15, 15, 15, 14, 14, 44])

    # ---- 02_TONGHOP_LO ---------------------------------------------------------
    _tieu_de(ws2, cfg, du_an, "Tổng hợp theo lô và theo đợt", st)
    _dau_bang(ws2, 4, ["Hạng mục", "Đào (m³)", "Đắp (m³)", "DT đào (m²)", "DT đắp (m²)",
                       "DT thiếu dữ liệu (m²)", "DT lô, đã trừ loại trừ (m²)"], st)
    n = v["so_nop"]
    r = 5
    cur = 5
    if truoc:
        tn = truoc["so_nop"]
        ws2.append([])
        for col, val in enumerate(["Đợt trước", tn["dao_m3"], tn["dap_m3"], tn["dt_dao_m2"], tn["dt_dap_m2"],
                                   tn["dt_thieu_du_lieu_m2"], truoc.get("dt_lo_m2")], 1):
            ws2.cell(row=5, column=col, value=val)
        cur = 6
    for col, val in enumerate([f"Đợt {cfg['dot']} (đợt này)", n["dao_m3"], n["dap_m3"], n["dt_dao_m2"],
                               n["dt_dap_m2"], n["dt_thieu_du_lieu_m2"], v["dt_lo_m2"]], 1):
        ws2.cell(row=cur, column=col, value=val)
    if truoc:
        ws2.cell(row=cur + 1, column=1, value="Lũy kế các đợt").font = st["dam"]
        for col in range(2, 6):
            L = chr(64 + col)
            ws2.cell(row=cur + 1, column=col, value=f"=SUM({L}5:{L}{cur})").font = st["dam"]
    for row in ws2.iter_rows(min_row=5, max_row=cur + 1, min_col=2, max_col=7):
        for x in row:
            x.number_format = f3
    _rong_cot(ws2, [24, 16, 16, 16, 16, 20, 26])

    # ---- 03_DOICHIEU -----------------------------------------------------------
    _tieu_de(ws3, cfg, du_an, "Đối chiếu hai phương pháp theo từng ô", st)
    _dau_bang(ws3, 4, ["Ô", "Lưới: đào (m³)", "Lưới: đắp (m³)", "Lăng trụ: đào (m³)", "Lăng trụ: đắp (m³)",
                       "Chênh đào (m³)", "Chênh đắp (m³)", "Chênh lớn nhất (%)", "Cờ", "Ghi chú"], st)
    for r, c in enumerate(cells, 5):
        ws3.cell(row=r, column=1, value=c["ma"])
        ws3.cell(row=r, column=2, value=c["kl_dao_m3"]); ws3.cell(row=r, column=3, value=c["kl_dap_m3"])
        ws3.cell(row=r, column=4, value=c["lang_tru_dao_m3"]); ws3.cell(row=r, column=5, value=c["lang_tru_dap_m3"])
        ws3.cell(row=r, column=6, value=f"=B{r}-D{r}"); ws3.cell(row=r, column=7, value=f"=C{r}-E{r}")
        ws3.cell(row=r, column=8, value=f"=IF(MAX(D{r},E{r})=0,0,100*MAX(ABS(F{r}),ABS(G{r}))/MAX(D{r},E{r}))")
        if c["thieu_du_lieu"]:
            ws3.cell(row=r, column=9, value="THIẾU DỮ LIỆU")
        elif c.get("o_lech_lon"):
            ws3.cell(row=r, column=9, value="LỆCH LỚN")
            ws3.cell(row=r, column=10, value="ô vắt ranh đào–đắp / vắt biên lô" if c["vat_ranh_lo"] or
                     (c["kl_dao_m3"] * c["kl_dap_m3"] == 0) else "địa hình trong ô")
        for col in range(2, 9):
            ws3.cell(row=r, column=col).number_format = f3 if col < 8 else f2
    r3 = 4 + len(cells)
    ws3.cell(row=r3 + 1, column=1, value="TỔNG").font = st["dam"]
    for col in range(2, 8):
        L = chr(64 + col)
        x = ws3.cell(row=r3 + 1, column=col, value=f"=SUM({L}5:{L}{r3})")
        x.number_format, x.font, x.fill = f3, st["dam"], st["tong"]
    ws3.freeze_panes = "B5"
    _rong_cot(ws3, [11, 15, 15, 17, 17, 15, 15, 16, 16, 36])

    # ---- 04_MA_TRAN_PA ---------------------------------------------------------
    _tieu_de(ws4, cfg, du_an, "Ma trận phương án", st)
    cot = ["Mã", "Mô tả", "Đào (m³)", "Đắp (m³)", "Ròng (m³)", "DT đào (m²)", "DT đắp (m²)",
           "Số ô vắt ranh", "Số ô thiếu DL", "Ghi chú"]
    _dau_bang(ws4, 4, cot, st)
    k = v["so_kiem"]
    for col, val in enumerate(["B3*", "Lăng trụ có đứt gãy, đã lọc tam giác rác (SỐ KIỂM)", k["dao_m3"],
                               k["dap_m3"], "=D5-C5", k["dt_dao_m2"], k["dt_dap_m2"]], 1):
        ws4.cell(row=5, column=col, value=val)
    sw = v.get("sweep")
    r = 7
    if not sw:
        ws4.cell(row=r, column=1, value="Chưa quét ma trận phương án. Chạy `tinh --sweep` để có bảng A và B.")
    else:
        for ten, ds in (("BẢNG A — quét cách đặt lưới, giữ nguyên kích thước ô", sw["A"]),
                        ("BẢNG B — quét phương pháp, giữ cách đặt lưới A1", sw["B"])):
            ws4.cell(row=r, column=1, value=ten).font = st["dam"]
            r += 1
            for p in ds:
                ws4.cell(row=r, column=1, value=p["ma"]); ws4.cell(row=r, column=2, value=p["mo_ta"])
                if "bo_qua" in p:
                    ws4.cell(row=r, column=10, value="bỏ qua: " + p["bo_qua"])
                elif p["ma"] == "A8":
                    for col, key in ((3, "dao"), (4, "dap"), (5, "rong")):
                        ws4.cell(row=r, column=col, value=f"{p[key]['min']:,.1f} … {p[key]['max']:,.1f}")
                    ws4.cell(row=r, column=10, value=f"{p['so_to_hop']} tổ hợp: khoảng min…max của đào / đắp / ròng")
                else:
                    for col, key in ((3, "dao"), (4, "dap"), (5, "rong"), (6, "dt_dao"), (7, "dt_dap"),
                                     (8, "so_o_vat_ranh"), (9, "so_o_thieu")):
                        if key in p:
                            ws4.cell(row=r, column=col, value=p[key])
                    if "ghi_chu" in p:
                        ws4.cell(row=r, column=10, value=p["ghi_chu"])
                r += 1
            r += 1
        d = sw["doc"]
        ws4.cell(row=r, column=1, value="Quy tắc đọc").font = st["dam"]
        ws4.cell(row=r + 1, column=1, value=d["cau"]).alignment = st["xuong"]
        ws4.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=10)
        ws4.row_dimensions[r + 1].height = 48
        ws4.cell(row=r + 2, column=1, value=(
            f"Cận dưới (đào+đắp) = {d['can_duoi_tong_dao_dap_m3']:,.3f} m³ tại {d['phuong_an_can_duoi']}; "
            f"B3 = {d['b3_tong_dao_dap_m3']:,.3f} m³; phần bị triệt tiêu = {d['phan_bi_trieu_tiet_m3']:,.3f} m³."))
    for row in ws4.iter_rows(min_row=5, max_row=ws4.max_row, min_col=3, max_col=7):
        for x in row:
            if isinstance(x.value, (int, float)):
                x.number_format = f3
    _rong_cot(ws4, [9, 54, 17, 17, 17, 14, 14, 13, 13, 46])

    # ---- 05_QC -------------------------------------------------------------------
    _tieu_de(ws5, cfg, du_an, "Kiểm soát chất lượng số liệu", st)
    _dau_bang(ws5, 4, ["Mã", "Verb", "Loại", "Mức", "Mô tả", "E (VN-2000)", "N (VN-2000)", "Hệ quả nếu bỏ qua"], st)
    for r, (verb, f) in enumerate(qc_all, 5):
        vt = f.get("vi_tri") or [None, None]
        for col, val in enumerate([f.get("ma"), verb, f.get("loai"), f.get("muc"), f.get("mo_ta"),
                                   vt[0], vt[1], f.get("he_qua_neu_bo_qua")], 1):
            x = ws5.cell(row=r, column=col, value=val)
            if col in (5, 8):
                x.alignment = st["xuong"]
    if not qc_all:
        ws5.cell(row=5, column=1, value="Không có phát hiện nào.")
    ws5.freeze_panes = "A5"
    _rong_cot(ws5, [8, 8, 24, 11, 80, 14, 14, 40])

    # ---- 06_TRUYVET ----------------------------------------------------------------
    _tieu_de(ws6, cfg, du_an, "Truy vết", st)
    dong = [("Mã lô", cfg["ma_lo"]), ("Đợt", cfg["dot"]), ("Hệ toạ độ", cfg["he_toa_do"]),
            ("Phiên bản lõi", __version__), ("Thời điểm lập", datetime.now(timezone.utc).isoformat()),
            ("Hash bộ đầu vào", qi.get("hash_dau_vao"))]
    for ten, nguon in (qi.get("nguon") or {}).items():
        if nguon:
            dong.append((f"Đầu vào · {ten}", f"{nguon['file']}  sha256={nguon['hash_sha256']}"
                         + (f"  sheet={nguon['sheet']}  {nguon.get('so_diem', '')} điểm" if "sheet" in nguon else "")))
    ts = grid["tham_so"]
    dong += [("Kích thước ô (m)", ts["kich_thuoc_o_m"]), ("Góc xoay lưới (độ)", ts["goc_xoay_do"]),
             ("Gốc lưới (E, N)", f"{ts['goc_luoi'][0]}, {ts['goc_luoi'][1]}"), ("Số cột × hàng", f"{ts['nx']} × {ts['ny']}"),
             ("Số đỉnh hiệu chỉnh tay", len(ghi_de))]
    for g in ghi_de:
        dong.append((f"  Hiệu chỉnh {g['ma']} ({g['be_mat']})", f"{g['z_goc']} → {g['z_moi']} m  {g.get('ly_do', '')}"))
    for q in quyet_dinh:
        dong.append(("Quyết định của người", q))
    for r, (a, b) in enumerate(dong, 4):
        ws6.cell(row=r, column=1, value=a).font = st["dam"]
        ws6.cell(row=r, column=2, value=b).alignment = st["xuong"]
    _rong_cot(ws6, [32, 120])

    # ---- 00_TONGKHOP (cuối cùng vì tham chiếu mọi sheet) -----------------------------
    ws = ws0
    _tieu_de(ws, cfg, du_an, "Bảng tổng khớp", st)
    _dau_bang(ws, 4, ["#", "Chỉ tiêu", "Đào (m³)", "Đắp (m³)", "DT đào (m²)", "DT đắp (m²)", "Điều kiện khớp", "Kết quả"], st)
    q = lambda s: f"'{s}'!"
    cur2 = cur
    ws.append([])
    chi_tieu = {
        5: ("1", "Cộng từ bảng chi tiết từng ô", [f"=SUM({q(BANG_O)}F5:F{r1})", f"=SUM({q(BANG_O)}G5:G{r1})",
                                                 f"=SUM({q(BANG_O)}H5:H{r1})", f"=SUM({q(BANG_O)}I5:I{r1})"], "—"),
        6: ("2", "Bảng tổng hợp lô", [f"={q(TONG_LO)}B{cur2}", f"={q(TONG_LO)}C{cur2}",
                                       f"={q(TONG_LO)}D{cur2}", f"={q(TONG_LO)}E{cur2}"], "(2) = (1)"),
        7: ("3", "Chênh lệch (1) − (2)", ["=ROUND(C5-C6,6)", "=ROUND(D5-D6,6)", "=ROUND(E5-E6,6)", "=ROUND(F5-F6,6)"],
            "PHẢI BẰNG 0"),
        8: ("4", "Số kiểm theo lăng trụ (PA B3)", [f"={q(MA_TRAN)}C5", f"={q(MA_TRAN)}D5",
                                                    f"={q(MA_TRAN)}F5", f"={q(MA_TRAN)}G5"], "—"),
        9: ("5", "Chênh lệch (1) − (4): m³ (cột C, D) và % so với lăng trụ (cột E, F)",
            ["=C5-C8", "=D5-D8", "=IF(C8=0,0,100*C9/C8)", "=IF(D8=0,0,100*D9/D8)"],
            f"≤ ngưỡng ô lệch lớn ({ng['o_lech_lon_pct']} % hoặc {ng['o_lech_lon_m3']} m³, lấy lớn hơn) hoặc giải thích bằng {DOI_CHIEU}"),
        10: ("6", "Tổng diện tích đào + đắp (m²)", [None, None, "=E5+F5", None], "—"),
        11: ("7", "Diện tích lô theo AREA, đã trừ vùng loại trừ và vùng thiếu dữ liệu (m²)",
             [None, None, f"={q(TONG_LO)}G{cur2}-{q(TONG_LO)}F{cur2}", None], "(7) = (6)"),
        12: ("8", "Chênh lệch (6) − (7)", [None, None, "=ROUND(E10-E11,6)", None], "PHẢI BẰNG 0"),
    }
    for r, (so, ten, cong, dk) in chi_tieu.items():
        ws.cell(row=r, column=1, value=so); ws.cell(row=r, column=2, value=ten).alignment = st["xuong"]
        for col, ct in enumerate(cong, 3):
            if ct is not None:
                ws.cell(row=r, column=col, value=ct).number_format = f3
        ws.cell(row=r, column=7, value=dk).alignment = st["xuong"]
    ws["H7"] = '=IF(AND(C7=0,D7=0,E7=0,F7=0),"ĐẠT","LỖI PHẦN MỀM — DỪNG")'
    ws["H12"] = '=IF(E12=0,"ĐẠT","LỖI PHẦN MỀM — DỪNG")'
    ws["H9"] = ('=IF(AND(OR(ABS(C9)<=$C$15,ABS(E9)<=$C$14),OR(ABS(D9)<=$C$15,ABS(F9)<=$C$14)),'
                '"TRONG NGƯỠNG","CẦN GIẢI THÍCH — xem 03_DOICHIEU")')
    ws["B14"] = "Ngưỡng ô lệch lớn — %"; ws["C14"] = ng["o_lech_lon_pct"]
    ws["B15"] = "Ngưỡng ô lệch lớn — m³"; ws["C15"] = ng["o_lech_lon_m3"]
    ws["B17"] = ("Dòng 3 hoặc 8 khác 0 là LỖI PHẦN MỀM: dừng, tìm nguyên nhân, không làm tròn cho khớp. "
                 "Dòng 5 vượt ngưỡng không phải lỗi — là chuyện phải giải thích.")
    ws["B17"].alignment = st["xuong"]
    ws.merge_cells("B17:H17")
    ws.row_dimensions[17].height = 34
    for r in range(5, 13):
        ws.cell(row=r, column=2).border = st["vien"]
    _rong_cot(ws, [5, 52, 16, 16, 16, 16, 44, 30])
    ws.sheet_view.tabSelected = True
    wb.active = 0
    return wb


def tao_doi_chieu_2pp(v: dict, cfg: dict):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "DOICHIEU"
    ws.append(["Ô", "Lưới đào", "Lưới đắp", "Lăng trụ đào", "Lăng trụ đắp", "Chênh đào", "Chênh đắp", "Cờ"])
    for c in v["o"]:
        ws.append([c["ma"], c["kl_dao_m3"], c["kl_dap_m3"], c["lang_tru_dao_m3"], c["lang_tru_dap_m3"],
                   c["kl_dao_m3"] - c["lang_tru_dao_m3"], c["kl_dap_m3"] - c["lang_tru_dap_m3"],
                   "THIẾU DL" if c["thieu_du_lieu"] else ("LỆCH LỚN" if c.get("o_lech_lon") else "")])
    ws2 = wb.create_sheet("TONG")
    n, k = v["so_nop"], v["so_kiem"]
    ws2.append(["", "Đào (m³)", "Đắp (m³)", "Ròng (m³)"])
    ws2.append(["Số nộp — lưới ô vuông", n["dao_m3"], n["dap_m3"], n["rong_m3"]])
    ws2.append(["Số kiểm — lăng trụ", k["dao_m3"], k["dap_m3"], k["rong_m3"]])
    ws2.append(["Chênh (nộp − kiểm)", "=B2-B3", "=C2-C3", "=D2-D3"])
    return wb


# =========================================================================== bảng in CAD, phiếu, thuyết minh
def tao_bang_in_cad(cfg: dict, du_an: dict, v: dict, kt: dict) -> dict:
    cells = v["o"]
    hang = [[c["ma"], c["dt_huu_hieu_m2"], c.get("z_tb_moc"), c.get("z_tb_do"), c.get("dz_tb"),
             c["kl_dao_m3"], c["kl_dap_m3"]] for c in cells]
    khoi = []
    for i in range(0, len(hang), TOI_DA_DONG_KHOI_CAD):
        khoi.append({"hang": hang[i:i + TOI_DA_DONG_KHOI_CAD], "co_tong": False})
    if not khoi:
        khoi = [{"hang": [], "co_tong": False}]
    d1 = kt["dong1"]
    khoi[-1]["co_tong"] = True          # CHỈ khối cuối mang dòng TỔNG, và bằng đúng dòng 1 bảng tổng khớp
    khoi[-1]["tong"] = {"dt_huu_hieu_m2": sum(c["dt_huu_hieu_m2"] for c in cells),
                        "kl_dao_m3": d1[0], "kl_dap_m3": d1[1]}
    return {
        "kho_giay": "A3 ngang",
        "tieu_de": {"du_an": du_an.get("ten_du_an"), "lo": cfg["ma_lo"], "dot": cfg["dot"],
                    "phuong_phap": "Lưới ô vuông (trung bình 4 góc) — số nộp",
                    "ngay": datetime.now().strftime("%d/%m/%Y"),
                    "o_ky": ["Lập", "Kiểm", "Duyệt"]},
        "cot": ["Tên ô", "Diện tích (m²)", "Cao độ TB mốc (m)", "Cao độ TB đo (m)", "Chênh cao TB (m)",
                "KL đào (m³)", "KL đắp (m³)"],
        "toi_da_dong_moi_khoi": TOI_DA_DONG_KHOI_CAD, "khoi": khoi,
        "chan": {"tong_dao_m3": d1[0], "tong_dap_m3": d1[1], "tong_dien_tich_m2": d1[2] + d1[3],
                 "ghi_chu": "Bề mặt mốc và đo: TIN Delaunay từ điểm khảo sát; ô thiếu dữ liệu không tính (RULES 8). "
                            "Số lăng trụ chỉ là số kiểm."},
    }


def _doc_quyet_dinh(lot: Lot) -> list[str]:
    p = lot.log_dir / "decisions.md"
    if not p.exists():
        return []
    return [l.strip()[2:].strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip().startswith("- ")]


def tao_thuyet_minh(lot: Lot, cfg: dict, du_an: dict, v: dict, kt: dict, qi: dict, grid: dict,
                    ghi_de: list, quyet_dinh: list[str], qc_all, lo: dict, surf: dict) -> str:
    n, k = v["so_nop"], v["so_kiem"]
    ts = grid["tham_so"]
    L = [f"# Thuyết minh phương pháp đo bóc khối lượng san nền", "",
         f"**Dự án:** {du_an.get('ten_du_an', '')}  ", f"**Lô:** {cfg.get('ten_lo', cfg['ma_lo'])} — đợt nghiệm thu {cfg['dot']}  ",
         f"**Hệ toạ độ:** {cfg['he_toa_do']}  ", f"**Lập:** {datetime.now():%d/%m/%Y}  ",
         f"**Phiên bản lõi tính:** sannen-core {__version__}", "",
         "## 1. Căn cứ", ""]
    cc = KB / "can-cu-phap-ly.md"
    if cc.exists():
        # Căn cứ pháp lý lấy NGUYÊN VĂN từ kb/can-cu-phap-ly.md (SKILL xuat); bỏ dòng hướng dẫn
        # cho agent ở đầu file và mục "Ngoài phạm vi" (đã có ở mục 8 của thuyết minh).
        for dong in cc.read_text(encoding="utf-8").splitlines()[1:]:
            if dong.startswith("## Ngoài phạm vi"):
                break
            if dong.startswith("Agent tra file này"):
                continue
            L.append("###" + dong[2:] if dong.startswith("## ") else dong)
    for c in du_an.get("can_cu", []):
        if not any(c[:25] in x for x in L):
            L.append(f"- {c}")
    L += ["", "## 2. Phương pháp đo bóc", "",
          "Khối lượng đào/đắp là chênh lệch giữa **bề mặt mốc** (trước thi công) và **bề mặt đo** (sau thi công).",
          f"- **Số nộp — lưới ô vuông:** lô được chia ô {ts['kich_thuoc_o_m']:g} × {ts['kich_thuoc_o_m']:g} m "
          f"({ts['nx']} cột × {ts['ny']} hàng, góc xoay {ts['goc_xoay_do']:g}°, gốc lưới E = {ts['goc_luoi'][0]:,.3f}, "
          f"N = {ts['goc_luoi'][1]:,.3f}). Khối lượng mỗi ô = chênh cao trung bình bốn đỉnh × diện tích hữu hiệu của ô "
          "(sau khi cắt theo biên lô và trừ vùng loại trừ). Chênh cao dương là đắp, âm là đào.",
          "- **Số kiểm — lăng trụ tam giác:** chồng chính xác hai mặt TIN; trên mỗi mảnh chồng cả hai mặt đều là mặt phẳng "
          "nên khối lượng là tích phân đúng; mảnh vắt đường chênh cao bằng 0 được cắt và tách đào/đắp. "
          "Số này chỉ dùng để kiểm tra và đàm phán, không thay thế số nộp.", "",
          "## 3. Nguồn số liệu", ""]
    for ten, nguon in (qi.get("nguon") or {}).items():
        if nguon:
            L.append(f"- `{nguon['file']}` (sha256 `{nguon['hash_sha256'][:16]}…`)"
                     + (f", sheet «{nguon['sheet']}», {nguon.get('so_diem')} điểm" if "sheet" in nguon else ""))
    ts_mat = surf.get("thong_ke", {})
    L += ["", "### Bề mặt TIN", ""]
    for nhan, ten in (("moc", "Mốc"), ("do", "Đo")):
        t = ts_mat.get(nhan)
        if t:
            L.append(f"- **{ten}:** {t['so_diem_vao']} điểm khảo sát → {t['so_diem']} đỉnh, {t['so_tam_giac']} tam giác; "
                     f"ép {t['so_doan_ep']} đoạn đứt gãy; gộp {t['so_gop']} điểm trùng; loại {t['so_tam_giac_rac_loai']} "
                     f"tam giác rác ở mép; {t['so_tam_giac_det']} tam giác dẹt trong vùng; "
                     f"{t['so_tam_giac_thieu_du_lieu']} tam giác thiếu dữ liệu.")
    L += ["", "## 4. Biên lô", ""]
    L.append(f"- Biên lô: {len(lo['bien_lo'])} vòng, {lo['tong']['dt_bien_lo_m2']:,.3f} m². "
             f"Vùng loại trừ: {len(lo['loai_tru'])}, {lo['tong']['dt_loai_tru_m2']:,.3f} m². "
             f"Diện tích hữu dụng {lo['tong']['dt_hieu_dung_m2']:,.3f} m².")
    L += ["", "## 5. Kết quả", "",
          "| | Đào (m³) | Đắp (m³) | Ròng (m³) |", "|---|---:|---:|---:|",
          f"| **Số nộp — lưới ô vuông** | {n['dao_m3']:,.3f} | {n['dap_m3']:,.3f} | {n['rong_m3']:+,.3f} |",
          f"| Số kiểm — lăng trụ | {k['dao_m3']:,.3f} | {k['dap_m3']:,.3f} | {k['rong_m3']:+,.3f} |",
          f"| Chênh (nộp − kiểm) | {kt['dong5_m3'][0]:+,.3f} | {kt['dong5_m3'][1]:+,.3f} | |", "",
          f"Diện tích đào {n['dt_dao_m2']:,.3f} m², diện tích đắp {n['dt_dap_m2']:,.3f} m²; "
          f"{n['so_o']} ô, trong đó {n['so_o_vat_ranh']} ô vắt biên lô."]
    if n["so_o_thieu"]:
        L.append(f"\n**Lưu ý:** {n['so_o_thieu']} ô ({n['dt_thieu_du_lieu_m2']:,.3f} m²) nằm trên vùng thiếu dữ liệu "
                 "nên KHÔNG tính khối lượng — cần đo bổ sung hoặc người có thẩm quyền xác nhận cách xử lý.")
    L += ["", "### Kiểm tra khớp", "",
          f"- (1) = (2): chênh {max(abs(x) for x in kt['dong3']):.0e} — "
          f"{'đạt' if kt['dong3_dat'] else 'KHÔNG ĐẠT'}.",
          f"- Diện tích đào + đắp so với diện tích lô trừ loại trừ: chênh {kt['dong8']:.0e} — "
          f"{'đạt' if kt['dong8_dat'] else 'KHÔNG ĐẠT'}.",
          f"- Chênh giữa số nộp và số kiểm: {'trong ngưỡng' if kt['dong5_trong_nguong'] else 'vượt ngưỡng, xem sheet 03_DOICHIEU'}.",
          "", "## 6. Đã xử lý gì trên mô hình", ""]
    if quyet_dinh:
        L += [f"- {q}" for q in quyet_dinh]
    else:
        L.append("Không có quyết định nào của người được ghi vào `90_log/decisions.md` trong đợt này.")
    if ghi_de:
        L += ["", "Cao độ đỉnh lưới do người hiệu chỉnh:", ""]
        L += [f"- {g['ma']} ({'mốc' if g['be_mat'] == 'moc' else 'đo'}): {g['z_goc']} → {g['z_moi']} m"
              f"{' — ' + g['ly_do'] if g.get('ly_do') else ''}" for g in ghi_de]
    canh_bao = [f for _, f in qc_all if f.get("muc") in ("chan", "canh_bao")]
    L += ["", "## 7. Các điểm cần lưu ý", ""]
    if canh_bao:
        L += [f"- {f.get('ma')}: {f.get('mo_ta')}" for f in canh_bao[:30]]
        if len(canh_bao) > 30:
            L.append(f"- … và {len(canh_bao) - 30} mục nữa (xem sheet 05_QC).")
    else:
        L.append("Không có.")
    L += ["", "## 8. Ngoài phạm vi", "",
          "Hệ số đầm chặt, phân loại cấp đất, cự ly vận chuyển và đơn giá thuộc bước lập dự toán; "
          "tài liệu này chỉ cho ra khối lượng đào/đắp (m³) và diện tích giữa hai bề mặt.", "",
          "Nhà thầu / Tư vấn giám sát / Chủ đầu tư: Lập ………… · Kiểm ………… · Duyệt …………", ""]
    return "\n".join(L)


# =========================================================================== verb
def chay(lot: Lot, cfg: dict, preview: bool) -> int:
    ng = nguong(cfg)
    qi = kiem_hash_dau_vao(lot)
    vp = lot.process_dir / "volume.json"
    if not vp.exists():
        raise DauVaoDaDoi("Chưa có volume.json — chạy `tinh` trước.")
    v = io_out.doc_json(vp)
    ghi_de = doc_hieu_chinh(lot)
    if v["hash_dau_vao"] != qi.get("hash_dau_vao"):
        raise DauVaoDaDoi("volume.json sinh từ đầu vào khác — chạy lại `tinh`.")
    if v["tham_so"].get("hieu_chinh_hash") != hash_hieu_chinh(ghi_de):
        raise DauVaoDaDoi("Cao độ đỉnh lưới đã đổi (grid_adjusted.json) sau lần `tinh` cuối — chạy lại `tinh` "
                          "(không bao giờ xuất số cũ).")
    grid = io_out.doc_json(lot.process_dir / "grid.json")
    for k in ("cot_m", "hang_m", "goc_luoi", "goc_xoay_do"):          # lưới đổi (vd chỉnh trong CAD) mà chưa tính lại
        if v["tham_so"].get(k) != grid["tham_so"].get(k):
            raise DauVaoDaDoi("Lưới (grid.json) đã đổi sau lần `tinh` cuối — chạy lại `tinh` (không bao giờ xuất số cũ).")
    lo = io_out.doc_json(lot.process_dir / "lo.json")
    surf = io_out.doc_json(lot.process_dir / "qc_surface.json")
    qc_all = _qc_tat_ca(lot)

    chan = [(vb, f) for vb, f in qc_all if f.get("muc") == "chan"]
    kt = kiem_khop(v, ng)
    print("BẢNG TỔNG KHỚP")
    print(f"  1 Chi tiết từng ô : đào {kt['dong1'][0]:>14,.3f}  đắp {kt['dong1'][1]:>14,.3f}  "
          f"DT đào {kt['dong1'][2]:>12,.3f}  DT đắp {kt['dong1'][3]:>12,.3f}")
    print(f"  2 Tổng hợp lô     : đào {kt['dong2'][0]:>14,.3f}  đắp {kt['dong2'][1]:>14,.3f}")
    print(f"  3 Chênh (1)-(2)   : {kt['dong3']}   → {'ĐẠT' if kt['dong3_dat'] else 'LỖI PHẦN MỀM'}")
    print(f"  4 Lăng trụ (B3)   : đào {kt['dong4'][0]:>14,.3f}  đắp {kt['dong4'][1]:>14,.3f}")
    print(f"  5 Chênh (1)-(4)   : {kt['dong5_m3'][0]:+,.3f} / {kt['dong5_m3'][1]:+,.3f} m³  "
          f"({kt['dong5_pct'][0]:+.2f} % / {kt['dong5_pct'][1]:+.2f} %) → "
          f"{'trong ngưỡng' if kt['dong5_trong_nguong'] else 'CẦN GIẢI THÍCH (xem 03_DOICHIEU)'}")
    print(f"  6 DT đào + đắp    : {kt['dong6']:,.6f} m²    7 DT lô (trừ loại trừ, thiếu DL): {kt['dong7']:,.6f} m²")
    print(f"  8 Chênh (6)-(7)   : {kt['dong8']}   → {'ĐẠT' if kt['dong8_dat'] else 'LỖI PHẦN MỀM'}")
    loi = []
    if not kt["dong3_dat"]:
        loi.append("Dòng 3 khác 0: tổng bảng chi tiết ≠ tổng hợp — lỗi phần mềm")
    if not kt["dong8_dat"]:
        loi.append("Dòng 8 khác 0: DT đào + đắp ≠ DT lô trừ loại trừ — lỗi phần mềm")
    for vb, f in chan:
        loi.append(f"CHẶN còn tồn ({vb}) {f.get('ma')}: {f.get('mo_ta')}")
    if loi:
        print("\nDỪNG — không ghi file (RULES 4/7, không làm tròn cho khớp):")
        for x in loi:
            print("  •", x)
        return 1
    ten = f"KL_{cfg['ma_lo']}_D{int(cfg['dot']):02d}.xlsx"
    files = [ten, "doi_chieu_2pp.xlsx", "bang_in_cad.json", "phieu_truy_vet.json", "thuyet_minh_phuong_phap.md"]
    if preview:
        print(f"\n-- XEM TRƯỚC (RULES 4). Sẽ ghi vào {lot.output_dir}: " + ", ".join(files))
        print("-- Người duyệt nội dung rồi chạy lại không có --preview.")
        return 0

    pj = lot.root.parent.parent / "project.yaml"
    du_an = {}
    if pj.exists():
        import yaml
        du_an = yaml.safe_load(pj.read_text(encoding="utf-8")) or {}
    quyet_dinh = _doc_quyet_dinh(lot)
    truoc = _dot_truoc(lot, cfg)
    lot.ensure()
    out = lot.output_dir
    wb = tao_workbook(lot, cfg, du_an, v, kt, qc_all, qi, ng, grid, ghi_de, quyet_dinh, truoc, ten)
    for t in (out / ten, out / "doi_chieu_2pp.xlsx", out / "bang_in_cad.json",
              out / "phieu_truy_vet.json", out / "thuyet_minh_phuong_phap.md"):
        lot.guard_write(t)
    wb.save(out / ten)
    tao_doi_chieu_2pp(v, cfg).save(out / "doi_chieu_2pp.xlsx")
    (out / "bang_in_cad.json").write_text(
        json.dumps(tao_bang_in_cad(cfg, du_an, v, kt), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "thuyet_minh_phuong_phap.md").write_text(
        tao_thuyet_minh(lot, cfg, du_an, v, kt, qi, grid, ghi_de, quyet_dinh, qc_all, lo, surf), encoding="utf-8")
    ts = grid["tham_so"]
    dau_vao = []
    for nhan, nguon in (qi.get("nguon") or {}).items():
        if not nguon:
            continue
        so = nguon.get("so_diem")
        if so is None:
            so = sum(surf["thong_ke"][b]["so_diem_vao"] for b in ("moc", "do")
                     if cfg[f"be_mat_{b}"].get("nguon", "dxf_layer") == "dxf_layer")
        dau_vao.append({"file": nguon["file"], "hash_sha256": nguon["hash_sha256"], "so_diem": int(so)})
    phieu = {
        "ma_lo": cfg["ma_lo"], "dot": int(cfg["dot"]), "thoi_diem": datetime.now(timezone.utc).isoformat(),
        "phien_ban_loi": __version__, "dau_vao": dau_vao, "hash_dau_vao": qi.get("hash_dau_vao"),
        "tham_so": {"phuong_phap": cfg["phuong_phap_chinh_thuc"], "kich_thuoc_o_m": ts["kich_thuoc_o_m"],
                    "goc_xoay_do": ts["goc_xoay_do"], "goc_luoi": ts["goc_luoi"],
                    "so_hieu_chinh_dinh": len(ghi_de)},
        "quyet_dinh_cua_nguoi": quyet_dinh,
        "ket_qua": {"dao_m3": v["so_nop"]["dao_m3"], "dap_m3": v["so_nop"]["dap_m3"],
                    "lang_tru_dao_m3": v["so_kiem"]["dao_m3"], "lang_tru_dap_m3": v["so_kiem"]["dap_m3"]},
        "kiem_tra_khop": {"dong3": kt["dong3"], "dong8": kt["dong8"], "dong5_trong_nguong": kt["dong5_trong_nguong"]},
        "dau_ra": [{"file": f, "hash_sha256": bam_sha256(out / f)} for f in files if f != "phieu_truy_vet.json"],
    }
    (out / "phieu_truy_vet.json").write_text(json.dumps(phieu, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {len(files)} file vào {out}")
    return 0
