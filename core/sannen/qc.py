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


def _o_bang(diem: list[Diem], canh: float):
    luoi: dict[tuple[int, int], list[int]] = {}
    for i, p in enumerate(diem):
        luoi.setdefault((int(p.easting // canh), int(p.northing // canh)), []).append(i)
    return luoi


def kiem_tra(diem: list[Diem], nguong: dict[str, float], nhan: str) -> list[dict]:
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

    # 2. Điểm trùng mặt bằng
    nguong_m = nguong["trung_mat_bang_mm"] / 1000.0
    canh = max(nguong_m * 10, 1.0)
    luoi = _o_bang(diem, canh)
    da_bao: set[int] = set()
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
                    else:
                        da_bao.add(j)
                        ra.append(_phat_hien(
                            ma(), "diem_trung", "canh_bao",
                            f"{nhan}: {a.id} và {b.id} trùng mặt bằng nhưng lệch cao độ {dz:.3f} m",
                            vi_tri=(a.easting, a.northing),
                            lua_chon=["(a) giữ điểm đo sau", "(b) giữ điểm đo trước",
                                      "(c) hỏi lại đơn vị khảo sát"],
                            he_qua="TIN lấy một trong hai một cách tuỳ tiện"))

    # 3. Cao độ bất thường theo MAD trên 8 điểm gần nhất
    k = nguong["mad_he_so"]
    buoc = max((rong * cao / max(len(diem), 1)) ** 0.5 * 3, 1.0)
    luoi2 = _o_bang(diem, buoc)
    nghi_van = 0
    for i, p in enumerate(diem):
        gx, gy = int(p.easting // buoc), int(p.northing // buoc)
        lan_can = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   for j in luoi2.get((gx + dx, gy + dy), []) if j != i]
        if len(lan_can) < 4:
            continue
        lan_can.sort(key=lambda j: (diem[j].easting - p.easting) ** 2
                     + (diem[j].northing - p.northing) ** 2)
        zs = [diem[j].z for j in lan_can[:LANG_GIENG]]
        tv = median(zs)
        mad = max(median([abs(z - tv) for z in zs]), nguong.get("mad_san_m", 0.02))
        if abs(p.z - tv) > k * mad:
            nghi_van += 1
            if nghi_van <= 20:
                ra.append(_phat_hien(
                    ma(), "cao_do_bat_thuong", "canh_bao",
                    f"{nhan}: {p.id} cao độ {p.z:.3f} m, trung vị lân cận {tv:.3f} m "
                    f"(lệch {abs(p.z - tv) / mad:.1f}×MAD)",
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
