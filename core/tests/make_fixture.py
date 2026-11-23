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


if __name__ == "__main__":
    import sys
    p = tao(Path(sys.argv[1] if len(sys.argv) > 1 else "mau.dxf"))
    print("đã tạo", p)
