"""Hình học phẳng thuần Python — nền cho TIN, lô, lưới, lăng trụ.

Mọi hàm ở đây làm việc trong hệ toạ độ ĐÃ DỜI GỐC về trọng tâm (xem `Goc`).
VN-2000 có E≈445.000, N≈1.113.000: bình phương những số này trong phép thử
đường tròn ngoại tiếp làm mất gần hết chữ số có nghĩa — lỗi khó tìm nhất của dự án.
Hai lớp phòng vệ: (1) dời gốc, (2) vị từ orient2d/incircle có ngưỡng sai số kiểu
Shewchuk, nghi ngờ thì tính lại bằng phân số chính xác.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Sequence

Diem2 = tuple[float, float]


@dataclass(frozen=True)
class Goc:
    """Gốc toạ độ cục bộ. vao(): VN-2000 -> cục bộ. ra(): cục bộ -> VN-2000."""
    e0: float
    n0: float

    def vao(self, e: float, n: float) -> Diem2:
        return (e - self.e0, n - self.n0)

    def ra(self, x: float, y: float) -> Diem2:
        return (x + self.e0, y + self.n0)

    @staticmethod
    def trong_tam(diem: Iterable[Diem2]) -> "Goc":
        """Trọng tâm làm tròn tới mét: cùng tập điểm -> cùng gốc, không phụ thuộc thứ tự."""
        d = list(diem)
        if not d:
            return Goc(0.0, 0.0)
        e = sum(p[0] for p in d) / len(d)
        n = sum(p[1] for p in d) / len(d)
        return Goc(float(round(e)), float(round(n)))


# --------------------------------------------------------------------------- vị từ
_EPS = 2.220446049250313e-16
_CCW_ERR = (3.0 + 16.0 * _EPS) * _EPS
_ICC_ERR = (10.0 + 96.0 * _EPS) * _EPS


def orient2d(a: Diem2, b: Diem2, c: Diem2) -> float:
    """>0 nếu a,b,c ngược chiều kim đồng hồ; <0 thuận chiều; 0 thẳng hàng (chính xác)."""
    t1 = (b[0] - a[0]) * (c[1] - a[1])
    t2 = (b[1] - a[1]) * (c[0] - a[0])
    det = t1 - t2
    if abs(det) > _CCW_ERR * (abs(t1) + abs(t2)):
        return det
    F = Fraction
    ax, ay, bx, by, cx, cy = F(a[0]), F(a[1]), F(b[0]), F(b[1]), F(c[0]), F(c[1])
    ex = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return float(ex) if ex != 0 else 0.0


def incircle(a: Diem2, b: Diem2, c: Diem2, d: Diem2) -> float:
    """>0 nếu d NẰM TRONG đường tròn qua a,b,c (a,b,c ngược chiều kim đồng hồ)."""
    adx, ady = a[0] - d[0], a[1] - d[1]
    bdx, bdy = b[0] - d[0], b[1] - d[1]
    cdx, cdy = c[0] - d[0], c[1] - d[1]
    al, bl, cl = adx * adx + ady * ady, bdx * bdx + bdy * bdy, cdx * cdx + cdy * cdy
    det = (al * (bdx * cdy - cdx * bdy) + bl * (cdx * ady - adx * cdy)
           + cl * (adx * bdy - bdx * ady))
    perm = ((abs(bdx * cdy) + abs(cdx * bdy)) * al + (abs(cdx * ady) + abs(adx * cdy)) * bl
            + (abs(adx * bdy) + abs(bdx * ady)) * cl)
    if abs(det) > _ICC_ERR * perm:
        return det
    F = Fraction
    adx, ady = F(a[0]) - F(d[0]), F(a[1]) - F(d[1])
    bdx, bdy = F(b[0]) - F(d[0]), F(b[1]) - F(d[1])
    cdx, cdy = F(c[0]) - F(d[0]), F(c[1]) - F(d[1])
    ex = ((adx * adx + ady * ady) * (bdx * cdy - cdx * bdy)
          + (bdx * bdx + bdy * bdy) * (cdx * ady - adx * cdy)
          + (cdx * cdx + cdy * cdy) * (adx * bdy - bdx * ady))
    return float(ex) if ex != 0 else 0.0


# --------------------------------------------------------------------------- đa giác
def dien_tich_co_dau(p: Sequence[Diem2]) -> float:
    """Shoelace. Dương nếu ngược chiều kim đồng hồ."""
    n = len(p)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def cat_nua_mat_phang(p: Sequence[Diem2], a: float, b: float, c: float) -> list[Diem2]:
    """Giữ phần a·x + b·y + c >= 0 (Sutherland–Hodgman với MỘT đường thẳng)."""
    if not p:
        return []
    ra: list[Diem2] = []
    n = len(p)
    f = [a * q[0] + b * q[1] + c for q in p]
    for i in range(n):
        j = (i + 1) % n
        fi, fj = f[i], f[j]
        if fi >= 0:
            ra.append(p[i])
        if (fi > 0 and fj < 0) or (fi < 0 and fj > 0):
            t = fi / (fi - fj)
            ra.append((p[i][0] + t * (p[j][0] - p[i][0]), p[i][1] + t * (p[j][1] - p[i][1])))
    return ra


def cat_hcn(p: Sequence[Diem2], x0: float, y0: float, x1: float, y1: float) -> list[Diem2]:
    q = cat_nua_mat_phang(p, 1.0, 0.0, -x0)
    q = cat_nua_mat_phang(q, -1.0, 0.0, x1)
    q = cat_nua_mat_phang(q, 0.0, 1.0, -y0)
    return cat_nua_mat_phang(q, 0.0, -1.0, y1)


def cat_loi(p: Sequence[Diem2], loi: Sequence[Diem2]) -> list[Diem2]:
    """Cắt đa giác p (tuỳ ý, kể cả lõm) bằng đa giác LỒI `loi` ngược chiều kim đồng hồ.

    Diện tích có dấu của kết quả đúng kể cả khi p lõm (các cạnh suy biến dọc biên cắt
    tự triệt tiêu) — đủ cho mọi phép tích phân ở đây.
    """
    q = list(p)
    n = len(loi)
    for i in range(n):
        if not q:
            break
        (x1, y1), (x2, y2) = loi[i], loi[(i + 1) % n]
        # nửa mặt phẳng bên TRÁI cạnh (x1,y1)->(x2,y2)
        q = cat_nua_mat_phang(q, -(y2 - y1), (x2 - x1), (y2 - y1) * x1 - (x2 - x1) * y1)
    return q


def tich_phan_tuyen_tinh(p: Sequence[Diem2], f) -> float:
    """∫ f dA trên đa giác p với f(x,y) TUYẾN TÍNH, bằng quạt tam giác có dấu.

    Với f tuyến tính, tích phân trên một tam giác = diện tích × f(trọng tâm) — chính xác,
    không xấp xỉ. Đa giác suy biến (từ cat_loi) vẫn đúng nhờ tính có dấu.
    """
    n = len(p)
    if n < 3:
        return 0.0
    x0, y0 = p[0]
    s = 0.0
    for i in range(1, n - 1):
        x1, y1 = p[i]
        x2, y2 = p[i + 1]
        dt = ((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) / 2.0
        if dt != 0.0:
            s += dt * f((x0 + x1 + x2) / 3.0, (y0 + y1 + y2) / 3.0)
    return s


def trong_da_giac(pt: Diem2, vong: Sequence[Diem2]) -> bool:
    """Điểm trong đa giác (quy tắc chẵn–lẻ). Điểm nằm đúng biên: không xác định."""
    x, y = pt
    ben_trong = False
    n = len(vong)
    j = n - 1
    for i in range(n):
        xi, yi = vong[i]
        xj, yj = vong[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ben_trong = not ben_trong
        j = i
    return ben_trong


def giao_doan(p1: Diem2, p2: Diem2, p3: Diem2, p4: Diem2):
    """Giao điểm THỰC SỰ (cắt qua phần trong cả hai đoạn). Trả (t, u) hoặc None.

    P = p1 + t(p2-p1) = p3 + u(p4-p3). Chạm đầu mút / song song / trùng -> None.
    """
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if den == 0.0:
        return None
    ex, ey = p3[0] - p1[0], p3[1] - p1[1]
    t = (ex * d2[1] - ey * d2[0]) / den
    u = (ex * d1[1] - ey * d1[0]) / den
    if 1e-12 < t < 1 - 1e-12 and 1e-12 < u < 1 - 1e-12:
        return t, u
    return None


def tu_cat_nhau(vong: Sequence[Diem2]) -> list[Diem2]:
    """Mọi giao điểm giữa hai cạnh KHÔNG kề nhau của một vòng. Rỗng = đơn giản."""
    n = len(vong)
    ra: list[Diem2] = []
    for i in range(n):
        a, b = vong[i], vong[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = vong[j], vong[(j + 1) % n]
            g = giao_doan(a, b, c, d)
            if g:
                ra.append((a[0] + g[0] * (b[0] - a[0]), a[1] + g[0] * (b[1] - a[1])))
    return ra


def hop_bao_loi(diem: Iterable[Diem2]) -> list[Diem2]:
    """Bao lồi (Andrew), ngược chiều kim đồng hồ."""
    p = sorted(set(diem))
    if len(p) < 3:
        return p

    def nua(pts):
        h: list[Diem2] = []
        for q in pts:
            while len(h) >= 2 and orient2d(h[-2], h[-1], q) <= 0:
                h.pop()
            h.append(q)
        return h
    duoi, tren = nua(p), nua(reversed(p))
    return duoi[:-1] + tren[:-1]


def goc_nho_nhat_do(a: Diem2, b: Diem2, c: Diem2) -> float:
    """Góc nhỏ nhất của tam giác, độ."""
    import math

    def goc(p, q, r):
        v1, v2 = (q[0] - p[0], q[1] - p[1]), (r[0] - p[0], r[1] - p[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        cs = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        return math.degrees(math.acos(cs))
    return min(goc(a, b, c), goc(b, c, a), goc(c, a, b))


def huong_canh_dai(vong: Sequence[Diem2]) -> float:
    """Phương (radian, 0..π) của cạnh dài hộp bao CÓ HƯỚNG nhỏ nhất của đa giác.

    Dùng cho lưới "tự đặt vừa biên lô": quay thước kẹp trên bao lồi, chọn hướng có
    hộp bao diện tích nhỏ nhất, trả phương của cạnh dài hộp đó.
    """
    import math
    h = hop_bao_loi(vong)
    if len(h) < 3:
        return 0.0
    tot, best = None, 0.0
    for i in range(len(h)):
        a, b = h[i], h[(i + 1) % len(h)]
        th = math.atan2(b[1] - a[1], b[0] - a[0])
        c, s = math.cos(-th), math.sin(-th)
        xs = [c * p[0] - s * p[1] for p in h]
        ys = [s * p[0] + c * p[1] for p in h]
        w, hh = max(xs) - min(xs), max(ys) - min(ys)
        if tot is None or w * hh < tot[0] - 1e-9:
            tot = (w * hh, w >= hh)
            best = th if w >= hh else th + math.pi / 2
    return best % math.pi
