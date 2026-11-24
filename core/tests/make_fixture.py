"""Sinh DXF mẫu đúng cấu trúc lô 01-CGP để test lõi khi chưa có bản vẽ thật."""
from __future__ import annotations
import random
from pathlib import Path
import ezdxf

E0, N0 = 445000.0, 1113000.0
RONG, CAO = 154.0, 90.0


def tao(duong_dan: Path, so_moc: int = 604, so_do: int = 413, seed: int = 7,
        cai_loi: bool = True) -> Path:
    random.seed(seed)
    doc = ezdxf.new("R2018", setup=True)
    msp = doc.modelspace()
    for ly in ("SN-DIEM-MOC", "SN-DIEM-DO", "SN-DUTGAY",
               "SN-BIENLO", "SN-LOAITRU", "SN-DONGMUC"):
        doc.layers.add(ly)

    msp.add_lwpolyline([(E0, N0), (E0 + RONG, N0), (E0 + RONG, N0 + CAO), (E0, N0 + CAO)],
                       close=True, dxfattribs={"layer": "SN-BIENLO"})
    msp.add_lwpolyline([(E0 + 40, N0 + 30), (E0 + 70, N0 + 30),
                        (E0 + 70, N0 + 55), (E0 + 40, N0 + 55)],
                       close=True, dxfattribs={"layer": "SN-LOAITRU"})
    msp.add_polyline3d([(E0 + 5, N0 + 10, 2.1), (E0 + 60, N0 + 35, 2.6),
                        (E0 + 120, N0 + 70, 3.4)], dxfattribs={"layer": "SN-DUTGAY"})

    for i in range(so_moc):
        x, y = E0 + random.uniform(0, RONG), N0 + random.uniform(0, CAO)
        msp.add_point((x, y, 0.7 + 3.8 * random.random()),
                      dxfattribs={"layer": "SN-DIEM-MOC"})
    for i in range(so_do):
        x, y = E0 + random.uniform(0, RONG), N0 + random.uniform(0, CAO)
        msp.add_point((x, y, 2.8 + random.uniform(-0.05, 0.05)),
                      dxfattribs={"layer": "SN-DIEM-DO"})

    if cai_loi:
        # lỗi gõ 2.85 -> 28.5, phép kiểm MAD phải bắt được
        msp.add_point((E0 + 77, N0 + 45, 28.5), dxfattribs={"layer": "SN-DIEM-DO"})

    msp.add_lwpolyline([(E0 + 10, N0 + 80), (E0 + 90, N0 + 75), (E0 + 150, N0 + 85)],
                       dxfattribs={"layer": "SN-DONGMUC", "elevation": 3.0})
    doc.saveas(duong_dan)
    return duong_dan


TIEU_DE_THAT = ["Tên điểm", "Tọa độ X(m)", "Tọa độ Y(m)", "Cao độ H(m)", "Ghi chú"]
HANG_TIEU_DE = 7          # 6 dòng đầu là tiêu đề trang, hàng 7 là tiêu đề cột


def tao_xlsx(duong_dan: Path, so_diem: int = 200, seed: int = 11, cai_loi: bool = True,
             tieu_de: list[str] | None = None, sheet: str = "Mốc",
             z0: float = 2.8) -> dict:
    """Excel khảo sát đúng khuôn file thật của lô 01-CGP: nhiều dòng tiêu đề trang
    và HAI KHỐI ĐIỂM trên mỗi dòng (cột A-E và F-J). Mặt gần phẳng z0 ± 1 cm.

    Trả về mô tả các lỗi đã cài, để test kiểm tra hệ thống báo ĐÚNG điểm đó.
    """
    from openpyxl import Workbook
    tieu_de = tieu_de or TIEU_DE_THAT
    rng = random.Random(seed)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws["A1"] = "CÔNG TY TNHH KHẢO SÁT ĐỊA HÌNH MẪU"
    ws["A2"] = "BẢNG TỌA ĐỘ VÀ CAO ĐỘ ĐIỂM ĐO"
    ws["A4"] = "Hệ tọa độ VN-2000, kinh tuyến trục 104°30'"
    for k in range(2):
        for c, t in enumerate(tieu_de):
            ws.cell(row=HANG_TIEU_DE, column=k * 5 + c + 1, value=t)

    pts = []
    for i in range(so_diem):
        pts.append([f"P{i:05d}", N0 + rng.uniform(0, CAO), E0 + rng.uniform(0, RONG),
                    z0 + rng.uniform(-0.01, 0.01), ""])
    loi: dict = {}
    if cai_loi and so_diem > 100:
        i = so_diem // 3
        pts[i][3] = 28.5                                    # gõ 2.85 -> 28.5
        loi["cao_do_sai"] = {"id": pts[i][0], "hang": 8 + i // 2}
        pts[11][1] = "n/a"                                  # chữ trong ô tọa độ
        pts[22][3] = None                                   # thiếu cao độ
        loi["hong"] = [8 + 11 // 2, 8 + 22 // 2]
        pts[33][3] = f"{pts[33][3]:.3f}".replace(".", ",")  # "2,805": hợp lệ, kiểu Việt Nam
        loi["dau_phay"] = {"id": pts[33][0], "z": float(pts[33][3].replace(",", "."))}
        pts[44][1], pts[44][2] = pts[45][1], pts[45][2]     # hai điểm cùng chỗ...
        pts[44][3] = pts[45][3] + 0.30                      # ...lệch cao 30 cm
        loi["trung_cho"] = (pts[44][0], pts[45][0])
        pts[55][0] = pts[5][0]                              # lặp tên điểm
        loi["id_lap"] = pts[5][0]
    for i, p in enumerate(pts):
        hang, khoi = HANG_TIEU_DE + 1 + i // 2, i % 2
        for c, v in enumerate(p):
            if v != "":
                ws.cell(row=hang, column=khoi * 5 + c + 1, value=v)
    if cai_loi:
        cuoi = HANG_TIEU_DE + 1 + (so_diem + 1) // 2
        ws.cell(row=cuoi, column=1, value="Tổng cộng")
        # chú giải như file thật: ô easting = "D", ô cao độ = "ĐỈNH TA LUY"
        for k, (ma, ten) in enumerate([("D", "ĐỈNH TA LUY"), ("M", "Mặt bãi ")]):
            ws.cell(row=cuoi + 1 + k, column=3, value=ma)
            ws.cell(row=cuoi + 1 + k, column=4, value=ten)
    wb.save(duong_dan)
    return loi


if __name__ == "__main__":
    import sys
    p = tao(Path(sys.argv[1] if len(sys.argv) > 1 else "mau.dxf"))
    print("đã tạo", p)
