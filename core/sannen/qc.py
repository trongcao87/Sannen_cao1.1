"""Bốn phép kiểm dữ liệu đầu vào (SPEC mục 5, skill nhap).

Một điểm nhập sai cao độ có thể làm sai hàng nghìn mét khối mà nhìn bản vẽ không ra.
Agent KHÔNG tự sửa — chỉ liệt kê để người quyết (RULES 2).
"""
from __future__ import annotations
from statistics import median
from .dxfio import Diem

LANG_GIENG = 8


def _phat_hien(ma, loai, muc, mo_ta, vi_tri=None, lua_chon=None, he_qua=""):
    d = {"ma": ma, "loai": loai, "muc": muc, "mo_ta": mo_ta}
    if vi_tri:
        d["vi_tri"] = [round(v, 3) for v in vi_tri]
    if lua_chon:
        d["lua_chon"] = lua_chon
    if he_qua:
        d["he_qua_neu_bo_qua"] = he_qua
    return d


def danh_ma(phat_hien: list[dict], tien_to: str = "V") -> list[dict]:
    """Đánh lại V-01, V-02... liền mạch cho TOÀN BỘ phát hiện của một lần nhập.

    kiem_tra() chạy riêng từng bề mặt nên mỗi lần đều bắt đầu từ V-01; gộp lại mà
    không đánh số lại thì "V-01 a" trên phiếu việc là mơ hồ.
    """
    for i, p in enumerate(phat_hien, 1):
        p["ma"] = f"{tien_to}-{i:02d}"
    return phat_hien


def _ref(p: Diem) -> str:
    """Tên điểm kèm vị trí trong file gốc (nếu có) để QS mở Excel là thấy ngay."""
    return f"{p.id} [{p.nguon}]" if p.nguon else p.id


def _mat_phang_tai(p: Diem, lan_can: list[Diem]) -> tuple[float, float] | None:
    """Khớp z = a + b·dx + c·dy bình phương tối thiểu trên các điểm lân cận (tọa độ
    dời về p nên a chính là cao độ dự đoán tại p). Trả về (dự đoán, thang đo sai số)
    hoặc None nếu lân cận thẳng hàng. Thang đo = độ lệch chuẩn dư có bậc tự do."""
    n = len(lan_can)
    sx = sy = sz = sxx = sxy = syy = sxz = syz = 0.0
    for q in lan_can:
        x, y, z = q.easting - p.easting, q.northing - p.northing, q.z
        sx += x; sy += y; sz += z
        sxx += x * x; sxy += x * y; syy += y * y
        sxz += x * z; syz += y * z
    # hệ [n sx sy; sx sxx sxy; sy sxy syy]·[a b c] = [sz sxz syz], giải bằng Cramer
    def det3(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    A = [[n, sx, sy], [sx, sxx, sxy], [sy, sxy, syy]]
    d = det3(A)
    chuan = n * (sxx + syy) ** 2 + 1e-300
    if abs(d) < 1e-9 * chuan:
        return None
    r = [sz, sxz, syz]
    def thay(c):
        return [[r[i] if j == c else A[i][j] for j in range(3)] for i in range(3)]
    a, b, c = det3(thay(0)) / d, det3(thay(1)) / d, det3(thay(2)) / d
    ss = sum((q.z - (a + b * (q.easting - p.easting) + c * (q.northing - p.northing))) ** 2
             for q in lan_can)
    return a, (ss / max(n - 3, 1)) ** 0.5


def _o_bang(diem: list[Diem], canh: float):
    luoi: dict[tuple[int, int], list[int]] = {}
    for i, p in enumerate(diem):
        luoi.setdefault((int(p.easting // canh), int(p.northing // canh)), []).append(i)
    return luoi


def kiem_tra(diem: list[Diem], nguong: dict[str, float], nhan: str,
             he_toa_do: str = "") -> list[dict]:
    """Trả về danh sách phát hiện, đánh mã V-01, V-02... để người trả lời gọn."""
    ra: list[dict] = []
    stt = 0

    def ma() -> str:
        nonlocal stt
        stt += 1
        return f"V-{stt:02d}"

    if not diem:
        return [_phat_hien(ma(), "dong_hong", "chan",
                           f"{nhan}: không đọc được điểm nào")]

    # 4. Phạm vi toạ độ — lẫn hệ toạ độ hoặc lẫn đơn vị m/mm
    es = [p.easting for p in diem]
    ns = [p.northing for p in diem]
    rong, cao = max(es) - min(es), max(ns) - min(ns)
    if rong > 50_000 or cao > 50_000:
        ra.append(_phat_hien(
            ma(), "pham_vi_toa_do", "chan",
            f"{nhan}: khu đất {rong:.0f} × {cao:.0f} m — rộng bất thường",
            lua_chon=["(a) kiểm lại hệ toạ độ", "(b) kiểm lại đơn vị m/mm"],
            he_qua="mọi phép nội suy và diện tích sai theo"))

    # 4b. Đảo X/Y — lỗi hay gặp nhất khi nhận Excel. Mọi múi VN-2000 đều có
    # northing (~0,9–2,4 triệu) lớn hơn easting (~0,3–0,7 triệu), nên trung vị
    # easting > trung vị northing gần như chắc chắn là cột đã bị đảo.
    if he_toa_do.upper().replace(" ", "").replace("-", "") == "VN2000":
        if median(es) > median(ns):
            ra.append(_phat_hien(
                ma(), "nghi_dao_xy", "chan",
                f"{nhan}: easting trung vị {median(es):,.0f} lớn hơn northing trung vị "
                f"{median(ns):,.0f} — nghi hai cột X/Y bị đảo",
                lua_chon=["(a) đảo lại ánh xạ cột northing/easting",
                          "(b) khảo sát xác nhận đúng như vậy"],
                he_qua="toàn bộ hình học bị phản chiếu qua đường chéo; diện tích vẫn "
                       "ra số nhưng không khớp biên lô"))

    # 2. Điểm trùng mặt bằng
    nguong_m = nguong["trung_mat_bang_mm"] / 1000.0
    canh = max(nguong_m * 10, 1.0)
    luoi = _o_bang(diem, canh)
    da_bao: set[int] = set()
    trung_cung_cao_do: list[str] = []
    for (gx, gy), idxs in luoi.items():
        lan_can = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   for j in luoi.get((gx + dx, gy + dy), [])]
        for i in idxs:
            if i in da_bao:
                continue
            for j in lan_can:
                if j <= i or j in da_bao:
                    continue
                a, b = diem[i], diem[j]
                if abs(a.easting - b.easting) < nguong_m and abs(a.northing - b.northing) < nguong_m:
                    dz = abs(a.z - b.z)
                    if dz < nguong_m:
                        da_bao.add(j)
                        trung_cung_cao_do.append(f"{_ref(a)} = {_ref(b)}")
                    else:
                        da_bao.add(j)
                        ra.append(_phat_hien(
                            ma(), "diem_trung", "canh_bao",
                            f"{nhan}: {_ref(a)} và {_ref(b)} trùng mặt bằng nhưng lệch cao độ {dz:.3f} m",
                            vi_tri=(a.easting, a.northing),
                            lua_chon=["(a) giữ điểm đo sau", "(b) giữ điểm đo trước",
                                      "(c) hỏi lại đơn vị khảo sát"],
                            he_qua="TIN lấy một trong hai một cách tuỳ tiện"))
    if trung_cung_cao_do:
        # Không xóa điểm nào (RULES 2): chỉ thông báo. Bước dựng TIN gộp điểm trùng.
        ra.append(_phat_hien(
            ma(), "diem_trung_cung_cao_do", "thong_tin",
            f"{nhan}: {len(trung_cung_cao_do)} cặp điểm trùng cả mặt bằng lẫn cao độ, "
            f"vd {'; '.join(trung_cung_cao_do[:3])}. Giữ nguyên trong dữ liệu."))

    # 3. Cao độ bất thường theo MAD trên 8 điểm gần nhất
    k = nguong["mad_he_so"]
    buoc = max((rong * cao / max(len(diem), 1)) ** 0.5 * 3, 1.0)
    luoi2 = _o_bang(diem, buoc)
    san = nguong.get("mad_san_m", 0.02)
    # Vòng 1 — lệch khỏi TRUNG VỊ lân cận (bền vững với một điểm gõ sai bên cạnh).
    ung_vien: dict[int, tuple[float, float, list[int]]] = {}
    for i, p in enumerate(diem):
        gx, gy = int(p.easting // buoc), int(p.northing // buoc)
        lan_can = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   for j in luoi2.get((gx + dx, gy + dy), []) if j != i]
        if len(lan_can) < 4:
            continue
        lan_can.sort(key=lambda j: (diem[j].easting - p.easting) ** 2
                     + (diem[j].northing - p.northing) ** 2)
        gieng = lan_can[:LANG_GIENG]
        zs = [diem[j].z for j in gieng]
        tv = median(zs)
        mad = max(median([abs(z - tv) for z in zs]), san)
        if abs(p.z - tv) > k * mad:
            ung_vien[i] = (tv, mad, gieng)

    # Vòng 2 — trung vị coi bờ đắp, đỉnh/chân ta luy là "bất thường" vì lân cận là nền
    # thấp (đo 23/11/2026 trên lô 01-CGP). Điểm nằm trên MẶT DỐC thì khớp mặt phẳng
    # của các điểm lân cận BÌNH THƯỜNG; lỗi gõ thì không. Chỉ giữ cờ nếu trượt cả hai.
    nghi: list[tuple[int, float, float]] = []
    for i, (tv, mad, gieng) in ung_vien.items():
        p = diem[i]
        # Dùng CẢ tám lân cận: độ phân tán của chính chúng (vd sống bờ đắp cùng cao)
        # nới thang đo cho đúng; lỗi gõ nằm giữa nền sạch thì thang đo vẫn nhỏ.
        du_doan = _mat_phang_tai(p, [diem[j] for j in gieng])
        if du_doan is None:
            nghi.append((i, tv, abs(p.z - tv) / mad))
            continue
        pred, thang_du = du_doan
        t = max(san, thang_du)
        if abs(p.z - pred) > k * t:
            nghi.append((i, pred, abs(p.z - pred) / t))

    nghi_van = len(nghi)
    for n_, (i, ref, so_lan) in enumerate(sorted(nghi), 1):
        if n_ > 20:
            break
        p = diem[i]
        ra.append(_phat_hien(
            ma(), "cao_do_bat_thuong", "canh_bao",
            f"{nhan}: {_ref(p)} cao độ {p.z:.3f} m, dự đoán từ lân cận {ref:.3f} m "
            f"(lệch {so_lan:.1f}× thang đo)",
            vi_tri=(p.easting, p.northing),
            lua_chon=["(a) giữ — địa hình thật", "(b) bỏ điểm",
                      "(c) hỏi lại đơn vị khảo sát"],
            he_qua="một điểm sai cao độ kéo theo cả vùng tam giác quanh nó"))
    if nghi_van > 20:
        ra.append(_phat_hien(
            ma(), "cao_do_bat_thuong", "chan",
            f"{nhan}: còn {nghi_van - 20} điểm nghi vấn nữa chưa liệt kê — "
            "số lượng bất thường, nên soát lại cả bộ số liệu"))
    return ra
