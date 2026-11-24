"""Bố cục bảng và mặt cắt thành danh sách "đối tượng đơn giản" — dùng chung cho mọi backend (DXF, LISP, COM).

Mỗi phần tử là một tuple:
    ("text", chuỗi, x, y, cao_chữ [, màu])     chữ, căn trái
    ("khung", x, y, rộng, cao)                  khung chữ nhật (góc trên-trái)
    ("doan", x1, y1, x2, y2 [, màu])            đoạn thẳng
    ("pl", [(x, y), ...], khép_kín [, màu])      đa tuyến
Bố cục tính ở MỘT chỗ nên bảng/mặt cắt vẽ ra giống hệt nhau dù backend nào.
"""
from __future__ import annotations
import math
from datetime import datetime

# --------------------------------------------------------------------------- bảng
CO_CHU = 1.25


def bang_ent(bang: dict, goc_ve, h: float = CO_CHU) -> list[tuple]:
    """Bảng từng ô theo `bang_in_cad.json` (xuat): tiêu đề, các khối ≤ 40 dòng cạnh nhau, chân."""
    rong_cot = [h * x for x in (9, 12, 12, 12, 12, 14, 14)]
    W = sum(rong_cot)
    ox, oy = goc_ve
    td, chan = bang["tieu_de"], bang["chan"]
    so_dong: list[int] = []
    ent: list[tuple] = []
    y = oy
    ent.append(("text", f"BẢNG KHỐI LƯỢNG SAN NỀN — {td['du_an']} — LÔ {td['lo']} — ĐỢT {td['dot']}", ox, y, h * 1.4))
    ent.append(("text", f"Phương pháp: {td['phuong_phap']}   Ngày: {td['ngay']}", ox, y - h * 2, h))
    for k, nhan in enumerate(td["o_ky"]):
        ent.append(("text", f"{nhan}: …………", ox + W * k / 3, y - h * 4, h))
    y_dau = y - h * 6.5
    for i, kh in enumerate(bang["khoi"]):
        x0 = ox + i * (W + 3 * h)
        ys = y_dau
        cx = x0
        for tcol, w in zip(bang["cot"], rong_cot):
            ent.append(("text", tcol, cx + 0.2 * h, ys - 0.2 * h, h * 0.6))
            cx += w
        rows = [list(r) for r in kh["hang"]]
        for r in rows:
            ys -= h * 1.5
            cx = x0
            for val, w in zip(r, rong_cot):
                txt = val if isinstance(val, str) else ("" if val is None else f"{val:,.3f}")
                ent.append(("text", txt, cx + 0.2 * h, ys - 0.2 * h, h * 0.8))
                cx += w
        if kh.get("co_tong"):
            t = kh["tong"]
            ys -= h * 1.5
            ent.append(("text", "TỔNG", x0 + 0.2 * h, ys - 0.2 * h, h * 0.9))
            ent.append(("text", f"{t['dt_huu_hieu_m2']:,.3f}", x0 + rong_cot[0] + 0.2 * h, ys - 0.2 * h, h * 0.9))
            ent.append(("text", f"{t['kl_dao_m3']:,.3f}", x0 + sum(rong_cot[:5]) + 0.2 * h, ys - 0.2 * h, h * 0.9))
            ent.append(("text", f"{t['kl_dap_m3']:,.3f}", x0 + sum(rong_cot[:6]) + 0.2 * h, ys - 0.2 * h, h * 0.9))
        ent.append(("khung", x0, y_dau, W, y_dau - ys - h * 0.2))
        so_dong.append(len(rows))
    cuoi = y_dau - (max(so_dong or [0]) + 4) * h * 1.5
    ent.append(("text", f"Tổng đào {chan['tong_dao_m3']:,.3f} m³ · Tổng đắp {chan['tong_dap_m3']:,.3f} m³ · "
                        f"Tổng diện tích {chan['tong_dien_tich_m2']:,.3f} m²", ox, cuoi, h))
    ent.append(("text", chan["ghi_chu"], ox, cuoi - 1.5 * h, h * 0.8))
    return ent


def bang_don_gian_ent(tieu_de: str, hang: list[tuple[str, str, str]], goc_ve, h: float = CO_CHU) -> list[tuple]:
    """Bảng 3 cột (Hạng mục | Đơn vị | Khối lượng) như `Bảng tổng`, `Bảng tổng hợp` của SNVN."""
    ox, oy = goc_ve
    w = [h * 22, h * 6, h * 16]
    ent: list[tuple] = [("text", tieu_de, ox, oy, h * 1.2)]
    y = oy - h * 2
    for j, t in enumerate(("Hạng mục", "Đơn vị", "Khối lượng")):
        ent.append(("text", t, ox + sum(w[:j]) + 0.2 * h, y - 0.2 * h, h * 0.8))
    y0 = y
    for ten, dv, gt in hang:
        y -= h * 1.5
        for j, t in enumerate((ten, dv, gt)):
            ent.append(("text", t, ox + sum(w[:j]) + 0.2 * h, y - 0.2 * h, h * 0.8))
    for k in range(len(hang) + 2):                                   # lưới ngang
        yy = y0 + h * 1.5 - k * h * 1.5
        ent.append(("doan", ox, yy, ox + sum(w), yy))
    for j in range(4):                                               # lưới dọc
        xx = ox + sum(w[:j])
        ent.append(("doan", xx, y0 + h * 1.5, xx, y0 + h * 1.5 - (len(hang) + 1) * h * 1.5))
    return ent


def hang_bang_tong(vol: dict, loai: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Các dòng của `Bảng tổng` (chỉ số nộp) hoặc `Bảng tổng hợp` (nộp + kiểm + diện tích)."""
    n, k = vol["so_nop"], vol["so_kiem"]
    f = lambda x: f"{x:,.2f}"
    if loai == "tong":
        return "BẢNG KHỐI LƯỢNG SAN NỀN (SỐ NỘP — LƯỚI Ô VUÔNG)", [
            ("Khối lượng đào", "m³", f(n["dao_m3"])), ("Khối lượng đắp", "m³", f(n["dap_m3"])),
            ("Diện tích đào", "m²", f(n["dt_dao_m2"])), ("Diện tích đắp", "m²", f(n["dt_dap_m2"]))]
    return "BẢNG TỔNG HỢP KHỐI LƯỢNG SAN NỀN", [
        ("Diện tích lô (đã trừ loại trừ)", "m²", f(vol["dt_lo_m2"])),
        ("Diện tích ô thiếu dữ liệu (không tính)", "m²", f(n["dt_thieu_du_lieu_m2"])),
        ("Diện tích đào", "m²", f(n["dt_dao_m2"])), ("Diện tích đắp", "m²", f(n["dt_dap_m2"])),
        ("Khối lượng đào (số nộp — lưới)", "m³", f(n["dao_m3"])), ("Khối lượng đắp (số nộp — lưới)", "m³", f(n["dap_m3"])),
        ("Khối lượng đào (số kiểm — lăng trụ)", "m³", f(k["dao_m3"])), ("Khối lượng đắp (số kiểm — lăng trụ)", "m³", f(k["dap_m3"])),
        ("Chênh nộp − kiểm, đắp", "m³", f(vol["chenh_nop_kiem"]["dap_m3"]))]


# --------------------------------------------------------------------------- hộp bao + chỗ đặt mặc định
DEM_MAT_CAT_M = 30.0        # khoảng đệm tối thiểu giữa kết quả của lô và biểu đồ mặt cắt đặt tự động


def hop_bao_ent(ent: list[tuple]) -> tuple[float, float, float, float] | None:
    """Hộp bao (xmin, ymin, xmax, ymax) của danh sách đối tượng bố cục. Chữ: ước lượng rộng ≈ 0,75 × cao × số ký tự."""
    xs: list[float] = []
    ys: list[float] = []
    for x in ent:
        if x[0] == "text":
            xs += [x[2], x[2] + 0.75 * x[4] * len(str(x[1]))]
            ys += [x[3], x[3] + x[4]]
        elif x[0] == "khung":
            xs += [x[1], x[1] + x[3]]
            ys += [x[2], x[2] - x[4]]
        elif x[0] == "doan":
            xs += [x[1], x[3]]
            ys += [x[2], x[4]]
        elif x[0] == "pl":
            xs += [p[0] for p in x[1]]
            ys += [p[1] for p in x[1]]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def duoi_mac_dinh_lot(hop_bao_lo, bang: dict | None = None) -> tuple[float, float]:
    """(trái x, đáy y) của phần kết quả đã vẽ cho lô khi LISP không đo được bản vẽ: hộp bao lô và bảng in
    (bảng đặt tại góc trên-trái (xmin, ymin − 20) như `ve_ket_qua`)."""
    x0, y0 = float(hop_bao_lo[0]), float(hop_bao_lo[1])
    duoi = y0
    if bang:
        hb = hop_bao_ent(bang_ent(bang, (x0, y0 - 20.0)))
        if hb:
            duoi = min(duoi, hb[1])
    return x0, duoi


def goc_mat_cat_mac_dinh(kq: dict, ty_le_dung: float, trai_x: float, duoi_y: float,
                         dem: float = DEM_MAT_CAT_M) -> tuple[float, float]:
    """Góc gốc (gx, gy) để biểu đồ mặt cắt nằm DƯỚI mọi kết quả của lô: đỉnh biểu đồ (kể cả tiêu đề) thấp hơn `duoi_y`
    ít nhất `dem` m, mép trái (kể cả nhãn cao độ bên trái) thẳng hàng với `trai_x`."""
    ent = mat_cat_ent(kq, (0.0, 0.0), ty_le_dung)
    hb = hop_bao_ent(ent[3:])            # 3 phần tử đầu (tuyến A–B, nhãn A, B) nằm trên MẶT BẰNG, không thuộc biểu đồ
    return trai_x - hb[0], (duoi_y - dem) - hb[3]


# --------------------------------------------------------------------------- mặt cắt
def _buoc_nhan(dai: float) -> float:
    for b in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500):
        if dai / b <= 14:
            return float(b)
    return 1000.0


def _z_tai(tram: list[dict], khoa: str, s: float):
    """Cao độ tại lý trình s: nội suy tuyến tính giữa hai trạm liền kề (đúng vì giữa hai trạm là một tam giác)."""
    for a, b in zip(tram, tram[1:]):
        if a["ly_trinh"] - 1e-9 <= s <= b["ly_trinh"] + 1e-9:
            if a[khoa] is None or b[khoa] is None:
                return None
            d = b["ly_trinh"] - a["ly_trinh"]
            return a[khoa] if d == 0 else a[khoa] + (b[khoa] - a[khoa]) * (s - a["ly_trinh"]) / d
    return None


def mat_cat_ent(kq: dict, goc_ve, ty_le_dung: float = 5.0, h: float | None = None) -> list[tuple]:
    """Mặt cắt: tuyến A–B trên mặt bằng + biểu đồ mặt cắt (ngang 1:1, đứng phóng đại `ty_le_dung`) + bảng số."""
    tram, dai = kq["tram"], kq["chieu_dai_m"]
    h = h or min(3.0, max(0.6, dai / 120.0))
    gx, gy = goc_ve
    zs = [v for s in tram for v in (s["z_moc"], s["z_do"]) if v is not None]
    if not zs:
        raise ValueError("Mặt cắt không có đoạn nào nằm trong TIN")
    zref = math.floor(min(zs)) - 1.0
    Y = lambda z: gy + (z - zref) * ty_le_dung
    ent: list[tuple] = []
    # --- mặt bằng: tuyến cắt + A, B
    ent.append(("pl", [tuple(kq["a"]), tuple(kq["b"])], False, 6))
    ent.append(("text", f"A ({kq['ten']})", kq["a"][0], kq["a"][1], h, 6))
    ent.append(("text", "B", kq["b"][0], kq["b"][1], h, 6))
    # --- khung cao độ
    z_cao = math.ceil(max(zs))
    for k in range(0, int(z_cao - zref) + 1):
        z = zref + k
        ent.append(("doan", gx, Y(z), gx + dai, Y(z), 8))
        ent.append(("text", f"{z:.2f}", gx - h * 6, Y(z) - h * 0.3, h * 0.7))
    # --- hai biên dạng, ngắt tại chỗ thiếu dữ liệu
    for khoa, mau in (("z_moc", 3), ("z_do", 1)):
        doan: list[tuple[float, float]] = []
        for s in tram:
            if s[khoa] is None:
                if len(doan) > 1:
                    ent.append(("pl", doan, False, mau))
                doan = []
            else:
                doan.append((gx + s["ly_trinh"], Y(s[khoa])))
        if len(doan) > 1:
            ent.append(("pl", doan, False, mau))
    # --- lý trình đánh số + bảng số dưới đường chuẩn
    b = _buoc_nhan(dai)
    nhan = [k * b for k in range(int(dai // b) + 1)]
    if dai - nhan[-1] > 1e-6:
        nhan.append(dai)
    hang = [("Lý trình (m)", None, "{:.2f}"), ("Cao độ mốc (m)", "z_moc", "{:.3f}"),
            ("Cao độ đo (m)", "z_do", "{:.3f}"), ("Chênh cao (+đắp/−đào)", "dz", "{:+.3f}")]
    ybang = gy - h * 2
    for r, (ten, khoa, fmt) in enumerate(hang):
        yy = ybang - r * h * 1.6
        ent.append(("text", ten, gx - h * 22, yy - h * 0.3, h * 0.7))
        ent.append(("doan", gx - h * 22, yy + h * 0.9, gx + dai + h * 2, yy + h * 0.9, 8))
    ent.append(("doan", gx - h * 22, ybang - len(hang) * h * 1.6 + h * 0.9, gx + dai + h * 2,
                ybang - len(hang) * h * 1.6 + h * 0.9, 8))
    for s in nhan:
        zm, zd = _z_tai(tram, "z_moc", s), _z_tai(tram, "z_do", s)
        vals = [s, zm, zd, None if zm is None or zd is None else zd - zm]
        ent.append(("doan", gx + s, gy, gx + s, Y(max(v for v in (zm, zd) if v is not None)) if (zm is not None or zd is not None) else gy, 8))
        for r, ((_, _, fmt), v) in enumerate(zip(hang, vals)):
            ent.append(("text", "" if v is None else fmt.format(v), gx + s - h * 1.5, ybang - r * h * 1.6 - h * 0.3, h * 0.6))
    ent.append(("doan", gx, gy, gx + dai, gy, 7))
    # --- tiêu đề + tổng kết
    ytd = Y(z_cao) + h * 3
    ent.append(("text", f"MẶT CẮT {kq['ten']}  —  L = {dai:,.2f} m   ngang 1:1, đứng phóng đại ×{ty_le_dung:g}   "
                        f"(cao độ so sánh {zref:.2f} m)", gx, ytd, h * 1.2))
    ent.append(("text", f"Diện tích đào {kq['dien_tich_dao_m2']:,.3f} m²  ·  diện tích đắp {kq['dien_tich_dap_m2']:,.3f} m²"
                        + (f"  ·  THIẾU DỮ LIỆU {kq['doan_thieu_du_lieu_m']:,.1f} m" if kq["doan_thieu_du_lieu_m"] > 0 else ""),
                gx, ytd - h * 2, h))
    ent.append(("text", "xanh lá = mặt mốc (tự nhiên), đỏ = mặt đo (sau san lấp)", gx, ytd - h * 3.8, h * 0.7))
    return ent
