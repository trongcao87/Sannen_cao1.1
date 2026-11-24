"""Sinh lô thử có nghiệm giải tích: biên + loại trừ tuỳ ý, hai bề mặt có công thức đã biết.

Điểm đo phủ THỪA RA NGOÀI biên một dải `le` mét để TIN bao kín lô, đúng như khảo sát thật.
Chạy nhap → mat → lo bằng chính CLI, nên test đi qua toàn bộ đường ống.
"""
from __future__ import annotations
import math
import random
import sys
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sannen import cli                       # noqa: E402
from sannen.paths import Lot                 # noqa: E402

E0, N0 = 445000.0, 1113000.0
YAML = """
ma_lo: GT-01
dot: 1
he_toa_do: VN-2000
don_vi: m
phuong_phap_chinh_thuc: luoi_o_vuong
be_mat_moc: {{nguon: dxf_layer, layer: SN-DIEM-MOC}}
be_mat_do:  {{nguon: dxf_layer, layer: SN-DIEM-DO}}
luoi: {{kich_thuoc_o_m: {o}, goc_xoay_do: {goc}}}
"""


def hcn(x0, y0, x1, y1):
    return [(E0 + x0, N0 + y0), (E0 + x1, N0 + y0), (E0 + x1, N0 + y1), (E0 + x0, N0 + y1)]


def tao(tmp: Path, bien, f_moc, f_do, loai_tru=(), so_diem=1500, le=8.0, seed=1,
        o=20, goc=0, extra_yaml="", khoang_trong=None, dut_gay=()) -> Lot:
    """f_moc, f_do: hàm (e, n) -> z. khoang_trong: (x0,y0,x1,y1) tương đối E0,N0 — không đo."""
    l = Lot(tmp)
    l.ensure()
    l.lot_yaml.write_text(YAML.format(o=o, goc=goc) + extra_yaml, encoding="utf-8")
    doc = ezdxf.new("R2018")
    for ly in ("SN-DIEM-MOC", "SN-DIEM-DO", "SN-BIENLO", "SN-LOAITRU", "SN-DUTGAY"):
        doc.layers.add(ly)
    msp = doc.modelspace()
    for b in bien:
        msp.add_lwpolyline([(p[0], p[1], 0, 0, p[2] if len(p) > 2 else 0) for p in b],
                           format="xyseb", close=True, dxfattribs={"layer": "SN-BIENLO"})
    for b in loai_tru:
        msp.add_lwpolyline([(p[0], p[1], 0, 0, p[2] if len(p) > 2 else 0) for p in b],
                           format="xyseb", close=True, dxfattribs={"layer": "SN-LOAITRU"})
    for dg in dut_gay:
        msp.add_polyline3d(dg, dxfattribs={"layer": "SN-DUTGAY"})
    xs = [p[0] for b in bien for p in b]
    ys = [p[1] for b in bien for p in b]
    x0, x1, y0, y1 = min(xs) - le, max(xs) + le, min(ys) - le, max(ys) + le
    # Lưới điểm lắc ±30 % bước — giống khảo sát thật hơn điểm ngẫu nhiên Poisson (vốn tự sinh ra
    # những lỗ hổng 10× diện tích tam giác trung bình, bị `mat` đánh dấu đúng là thiếu dữ liệu).
    r = random.Random(seed)
    h = math.sqrt((x1 - x0) * (y1 - y0) / so_diem)
    nx, ny = max(2, round((x1 - x0) / h)), max(2, round((y1 - y0) / h))
    hx, hy = (x1 - x0) / nx, (y1 - y0) / ny
    pts = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            jx = 0.0 if i in (0, nx) else r.uniform(-0.3, 0.3) * hx
            jy = 0.0 if j in (0, ny) else r.uniform(-0.3, 0.3) * hy
            e, n = x0 + i * hx + jx, y0 + j * hy + jy
            if khoang_trong:
                kx0, ky0, kx1, ky1 = khoang_trong
                if kx0 <= e - E0 <= kx1 and ky0 <= n - N0 <= ky1:
                    continue
            pts.append((e, n))
    for e, n in pts:
        msp.add_point((e, n, f_moc(e, n)), dxfattribs={"layer": "SN-DIEM-MOC"})
        msp.add_point((e, n, f_do(e, n)), dxfattribs={"layer": "SN-DIEM-DO"})
    doc.saveas(l.input_dir / "gt.dxf")
    return l


def chay_het(l: Lot, *tinh_args: str) -> dict:
    """nhap → mat → lo → luoi → tinh. Trả về volume.json."""
    import json
    chay_den(l, "luoi")
    cli.main(["tinh", "--lot", str(l.root), *tinh_args])
    return json.loads((l.process_dir / "volume.json").read_text(encoding="utf-8"))


def chay_den(l: Lot, den: str = "lo") -> None:
    """Chạy nhap → mat → lo (→ luoi). Không đòi mã thoát 0: test nào cần thì tự kiểm."""
    cli.main(["nhap", "--lot", str(l.root)])
    cli.main(["mat", "--lot", str(l.root)])
    cli.main(["lo", "--lot", str(l.root)])
    if den == "luoi":
        cli.main(["luoi", "--lot", str(l.root)])
