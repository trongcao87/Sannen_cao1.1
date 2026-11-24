"""TIN Delaunay có ràng buộc đứt gãy (giai đoạn 2) — thuần Python.

Hai pha, đúng như skills/mat/SKILL.md:
  1. Delaunay thuần bằng Bowyer–Watson, điểm chèn theo thứ tự CHÍNH TẮC (không phụ thuộc
     thứ tự file) nên cùng tập điểm luôn ra cùng một tam giác phân.
  2. Ép từng đoạn đứt gãy: lật cạnh cắt qua đoạn (Sloan 1993), rồi khôi phục Delaunay
     quanh vùng nhưng không bao giờ lật cạnh đã ràng buộc.

Toàn bộ chạy trong hệ toạ độ đã dời gốc về trọng tâm (geom.Goc).
"""
from __future__ import annotations
import math
from collections import deque
from dataclasses import dataclass, field

from .geom import Goc, orient2d, incircle, goc_nho_nhat_do, giao_doan


class TinLoi(Exception):
    """Không dựng được TIN hoặc dữ liệu mâu thuẫn. DỪNG, không vá (RULES 7)."""


LOAI_TOT, LOAI_THIEU_DU_LIEU = 0, 2     # nhãn tam giác: 2 = quá lớn, vùng thiếu dữ liệu


# =========================================================================== bộ dựng
class _Dung:
    def __init__(self, xs: list[float], ys: list[float]):
        n = len(xs)
        self.n = n
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        d = max(maxx - minx, maxy - miny, 1.0)
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        self.P = [(x, y) for x, y in zip(xs, ys)]
        # Tam giác siêu lớn chứa mọi điểm; dựng xong thì bỏ các tam giác dính nó. Phải RẤT xa:
        # tam giác sát biên gần thẳng hàng có đường tròn ngoại tiếp bán kính ~L²/(8h); nếu đỉnh
        # siêu lớn lọt vào đó thì tam giác biên bị "cướp" và bao lồi hụt. 1e7·d chịu được độ
        # lệch khỏi thẳng hàng tới ~d·1e-5; vị từ chính xác lo phần số lớn.
        M = 1e7 * d
        self.P += [(cx - 2 * M, cy - M), (cx + 2 * M, cy - M), (cx, cy + 2 * M)]
        self.V: list[list[int]] = [[n, n + 1, n + 2]]
        self.N: list[list[int]] = [[-1, -1, -1]]
        self.song: list[bool] = [True]
        self.vt = [-1] * (n + 3)
        for i in (n, n + 1, n + 2):
            self.vt[i] = 0
        self.cuoi = 0

    # ---- định vị & chèn ----------------------------------------------------
    def _o(self, a: int, b: int, p) -> float:
        return orient2d(self.P[a], self.P[b], p)

    def dinh_vi(self, p, t: int) -> int:
        V, N = self.V, self.N
        if not self.song[t]:
            t = next(i for i in range(len(V) - 1, -1, -1) if self.song[i])
        for _ in range(4 * len(V) + 16):
            vt = V[t]
            for k in range(3):
                if self._o(vt[(k + 1) % 3], vt[(k + 2) % 3], p) < 0:
                    nt = N[t][k]
                    if nt < 0:
                        return t
                    t = nt
                    break
            else:
                return t
        raise TinLoi("Không định vị được điểm khi dựng TIN (dữ liệu suy biến)")

    def chen(self, i: int) -> None:
        V, N, P = self.V, self.N, self.P
        p = P[i]
        t0 = self.dinh_vi(p, self.cuoi)
        cav = [t0]
        trong = {t0}
        ngoai: set[int] = set()
        ngan_xep = [t0]
        while ngan_xep:
            u = ngan_xep.pop()
            for k in range(3):
                nb = N[u][k]
                if nb < 0 or nb in trong or nb in ngoai:
                    continue
                a, b, c = V[nb]
                if incircle(P[a], P[b], P[c], p) > 0:
                    trong.add(nb)
                    cav.append(nb)
                    ngan_xep.append(nb)
                else:
                    ngoai.add(nb)
        theo_dau: dict[int, int] = {}
        theo_cuoi: dict[int, int] = {}
        moi: list[int] = []
        for u in cav:
            for k in range(3):
                nb = N[u][k]
                if nb in trong:
                    continue
                a, b = V[u][(k + 1) % 3], V[u][(k + 2) % 3]
                t = len(V)
                V.append([i, a, b])
                N.append([nb, -1, -1])
                self.song.append(True)
                if nb >= 0:
                    N[nb][N[nb].index(u)] = t
                theo_dau[a] = t
                theo_cuoi[b] = t
                moi.append(t)
        for t in moi:
            _, a, b = V[t]
            N[t][1] = theo_dau[b]
            N[t][2] = theo_cuoi[a]
            self.vt[a] = t
            self.vt[b] = t
        self.vt[i] = moi[-1]
        for u in cav:
            self.song[u] = False
        self.cuoi = moi[-1]

    # ---- thao tác cục bộ ---------------------------------------------------
    def quanh(self, u: int) -> list[int]:
        V, N = self.V, self.N
        t0 = self.vt[u]
        thay, ds, st = {t0}, [t0], [t0]
        while st:
            t = st.pop()
            for k in range(3):
                if V[t][k] == u:
                    continue
                nb = N[t][k]
                if nb >= 0 and nb not in thay:
                    thay.add(nb)
                    ds.append(nb)
                    st.append(nb)
        return ds

    def tim_canh(self, a: int, b: int):
        """(t, k): tam giác chứa cạnh a–b, k = chỉ số đỉnh thứ ba. None nếu không có cạnh."""
        for t in self.quanh(a):
            vt = self.V[t]
            if b in vt:
                return t, next(k for k in range(3) if vt[k] != a and vt[k] != b)
        return None

    def _rp(self, n: int, cu: int, moi: int) -> None:
        if n >= 0:
            self.N[n][self.N[n].index(cu)] = moi

    def lat(self, t: int, k: int) -> tuple[int, int]:
        """Lật cạnh đối diện đỉnh k của t. Trả về đường chéo mới (a, d)."""
        V, N = self.V, self.N
        o = N[t][k]
        a, b, c = V[t][k], V[t][(k + 1) % 3], V[t][(k + 2) % 3]
        j = N[o].index(t)
        d = V[o][j]
        n_ca, n_ab = N[t][(k + 1) % 3], N[t][(k + 2) % 3]
        n_bd, n_dc = N[o][(j + 1) % 3], N[o][(j + 2) % 3]
        V[t], N[t] = [a, b, d], [n_bd, o, n_ab]
        V[o], N[o] = [a, d, c], [n_dc, n_ca, t]
        self._rp(n_bd, o, t)
        self._rp(n_ca, t, o)
        for v_, tt in ((a, t), (b, t), (d, o), (c, o)):
            self.vt[v_] = tt
        return a, d

    # ---- ép đứt gãy --------------------------------------------------------
    def ep(self, u: int, v: int, rb: set[tuple[int, int]]) -> None:
        if u == v:
            return
        khoa = (u, v) if u < v else (v, u)
        if khoa in rb:
            return
        if self.tim_canh(u, v):
            rb.add(khoa)
            return
        P, V, N = self.P, self.V, self.N
        bat_dau = None
        for t in self.quanh(u):
            k = V[t].index(u)
            a, b = V[t][(k + 1) % 3], V[t][(k + 2) % 3]
            oa = orient2d(P[u], P[a], P[v])
            ob = orient2d(P[u], P[v], P[b])
            if oa >= 0 and ob >= 0:
                if oa == 0:                    # đỉnh a nằm đúng trên đoạn: tách đôi
                    self.ep(u, a, rb); self.ep(a, v, rb); return
                if ob == 0:
                    self.ep(u, b, rb); self.ep(b, v, rb); return
                bat_dau = (t, a, b)
                break
        if bat_dau is None:
            raise TinLoi(f"Đứt gãy đi ra ngoài vùng có điểm đo (đỉnh {u}→{v})")
        cur, r, l = bat_dau[0], bat_dau[1], bat_dau[2]      # a bên phải, b bên trái đoạn u→v
        cat = [(r, l)]
        for _ in range(len(V) + 8):
            vc = V[cur]
            kk = next(k for k in range(3) if vc[k] != r and vc[k] != l)
            nxt = N[cur][kk]
            if nxt < 0:
                raise TinLoi("Đứt gãy cắt ra ngoài biên TIN")
            c = next(x for x in V[nxt] if x != r and x != l)
            if c == v:
                break
            oc = orient2d(P[u], P[v], P[c])
            if oc == 0:
                self.ep(u, c, rb); self.ep(c, v, rb); return
            if oc > 0:
                l = c
            else:
                r = c
            cat.append((r, l))
            cur = nxt
        else:
            raise TinLoi("Không lần theo được đứt gãy (vòng lặp)")

        cola = deque(cat)
        moi: list[tuple[int, int]] = []
        gioi_han = 60 * len(cat) + 2000
        while cola:
            gioi_han -= 1
            if gioi_han < 0:
                raise TinLoi(f"Ép đứt gãy {u}→{v} không hội tụ")
            p, q = cola.popleft()
            if ((p, q) if p < q else (q, p)) in rb:
                raise TinLoi("Hai đứt gãy cắt nhau mà chưa được tách giao điểm")
            e = self.tim_canh(p, q)
            if e is None:
                continue
            t, k = e
            o = N[t][k]
            c = V[t][k]
            d = V[o][N[o].index(t)]
            if not (orient2d(P[c], P[d], P[p]) * orient2d(P[c], P[d], P[q]) < 0):
                cola.append((p, q))
                continue
            self.lat(t, k)
            if (orient2d(P[u], P[v], P[c]) * orient2d(P[u], P[v], P[d]) < 0
                    and orient2d(P[c], P[d], P[u]) * orient2d(P[c], P[d], P[v]) < 0):
                cola.append((c, d))
            else:
                moi.append((c, d))
        rb.add(khoa)
        for _ in range(200):
            doi = False
            for idx, (c, d) in enumerate(moi):
                if ((c, d) if c < d else (d, c)) in rb:
                    continue
                e = self.tim_canh(c, d)
                if e is None:
                    continue
                t, k = e
                o = N[t][k]
                if o < 0:
                    continue
                dd = V[o][N[o].index(t)]
                a_, b_, c_ = V[t]
                if incircle(P[a_], P[b_], P[c_], P[dd]) > 0:
                    moi[idx] = self.lat(t, k)
                    doi = True
            if not doi:
                break

    def ket_qua(self) -> list[tuple[int, int, int]]:
        n = self.n
        return [tuple(v) for v, s in zip(self.V, self.song)
                if s and v[0] < n and v[1] < n and v[2] < n]


def _gan_nhat_tam_giac(p, tri):
    """(khoảng cách, điểm gần nhất) từ điểm tới tam giác; (0, p) nếu nằm trong."""
    a, b, c = tri
    if (orient2d(a, b, p) >= 0 and orient2d(b, c, p) >= 0 and orient2d(c, a, p) >= 0):
        return 0.0, p
    tot = None
    for u, v in ((a, b), (b, c), (c, a)):
        dx, dy = v[0] - u[0], v[1] - u[1]
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - u[0]) * dx + (p[1] - u[1]) * dy) / l2))
        q = (u[0] + t * dx, u[1] + t * dy)
        d = math.hypot(p[0] - q[0], p[1] - q[1])
        if tot is None or d < tot[0]:
            tot = (d, q)
    return tot


# =========================================================================== TIN
class Tin:
    """TIN bất biến để truy vấn: nội suy cao độ, định vị tam giác."""

    def __init__(self, goc: Goc, x, y, z, tris, loai=None, rang_buoc=()):
        self.goc = goc
        self.x, self.y, self.z = list(x), list(y), list(z)
        self.tris: list[tuple[int, int, int]] = [tuple(t) for t in tris]
        self.loai: list[int] = list(loai) if loai is not None else [LOAI_TOT] * len(self.tris)
        self.rang_buoc: set[tuple[int, int]] = {tuple(sorted(e)) for e in rang_buoc}
        self._ban_do = None
        self._canh_ban_do = 1.0

    # ---- tạo / lưu ----------------------------------------------------------
    def la_tot(self, i: int) -> bool:
        return self.loai[i] == LOAI_TOT

    def toa_do(self, i: int):
        a, b, c = self.tris[i]
        return ((self.x[a], self.y[a], self.z[a]), (self.x[b], self.y[b], self.z[b]),
                (self.x[c], self.y[c], self.z[c]))

    def mat_phang(self, i: int) -> tuple[float, float, float]:
        """z = A·x + B·y + C trong toạ độ cục bộ của tam giác i."""
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = self.toa_do(i)
        det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        A = ((z2 - z1) * (y3 - y1) - (z3 - z1) * (y2 - y1)) / det
        B = ((x2 - x1) * (z3 - z1) - (x3 - x1) * (z2 - z1)) / det
        return A, B, z1 - A * x1 - B * y1

    def _lap_ban_do(self) -> None:
        if not self.tris:
            self._ban_do = {}
            return
        canh = [math.sqrt(abs(self._dt(i))) for i in range(len(self.tris))]
        self._canh_ban_do = max(2.0 * sum(canh) / len(canh), 1e-6)
        h = self._canh_ban_do
        bd: dict[tuple[int, int], list[int]] = {}
        for i, (a, b, c) in enumerate(self.tris):
            xs = (self.x[a], self.x[b], self.x[c])
            ys = (self.y[a], self.y[b], self.y[c])
            for gx in range(int(math.floor(min(xs) / h)), int(math.floor(max(xs) / h)) + 1):
                for gy in range(int(math.floor(min(ys) / h)), int(math.floor(max(ys) / h)) + 1):
                    bd.setdefault((gx, gy), []).append(i)
        self._ban_do = bd

    def _dt(self, i: int) -> float:
        a, b, c = self.tris[i]
        return ((self.x[b] - self.x[a]) * (self.y[c] - self.y[a])
                - (self.x[c] - self.x[a]) * (self.y[b] - self.y[a])) / 2.0

    def dien_tich_tam_giac(self, i: int) -> float:
        return abs(self._dt(i))

    def chua(self, x: float, y: float) -> int | None:
        """Chỉ số tam giác chứa điểm cục bộ (x,y); None nếu ngoài TIN."""
        if self._ban_do is None:
            self._lap_ban_do()
        h = self._canh_ban_do
        p = (x, y)
        for i in self._ban_do.get((int(math.floor(x / h)), int(math.floor(y / h))), ()):
            a, b, c = self.tris[i]
            pa, pb, pc = (self.x[a], self.y[a]), (self.x[b], self.y[b]), (self.x[c], self.y[c])
            if (orient2d(pa, pb, p) >= 0 and orient2d(pb, pc, p) >= 0
                    and orient2d(pc, pa, p) >= 0):
                return i
        return None

    def da_giac(self, i: int) -> list[tuple[float, float]]:
        a, b, c = self.tris[i]
        return [(self.x[a], self.y[a]), (self.x[b], self.y[b]), (self.x[c], self.y[c])]

    def tam_giac_gan(self, x0: float, y0: float, x1: float, y1: float) -> list[int]:
        """Các tam giác có hộp bao giao với hộp (x0,y0)-(x1,y1), theo thứ tự chỉ số."""
        if self._ban_do is None:
            self._lap_ban_do()
        if getattr(self, "_bb", None) is None:
            self._bb = [(min(self.x[a], self.x[b], self.x[c]), min(self.y[a], self.y[b], self.y[c]),
                         max(self.x[a], self.x[b], self.x[c]), max(self.y[a], self.y[b], self.y[c]))
                        for a, b, c in self.tris]
        h = self._canh_ban_do
        ids: set[int] = set()
        for gx in range(int(math.floor(x0 / h)), int(math.floor(x1 / h)) + 1):
            for gy in range(int(math.floor(y0 / h)), int(math.floor(y1 / h)) + 1):
                ids.update(self._ban_do.get((gx, gy), ()))
        bb = self._bb
        return sorted(i for i in ids if bb[i][0] <= x1 and bb[i][2] >= x0
                      and bb[i][1] <= y1 and bb[i][3] >= y0)

    def tra_xy(self, x: float, y: float):
        """(z, loại tam giác) tại toạ độ CỤC BỘ, hoặc None nếu ngoài TIN."""
        i = self.chua(x, y)
        if i is None:
            return None
        A, B, C = self.mat_phang(i)
        return A * x + B * y + C, self.loai[i]

    def dinh_gan_nhat(self, x: float, y: float, r: float):
        """Điểm ĐO gần nhất (đỉnh TIN) trong bán kính r → (z, khoảng cách) hoặc None.

        Hòa khoảng cách thì lấy chỉ số đỉnh nhỏ hơn: kết quả không phụ thuộc thứ tự duyệt.
        """
        best = None
        for i in self.tam_giac_gan(x - r, y - r, x + r, y + r):
            for k in self.tris[i]:
                d = math.hypot(self.x[k] - x, self.y[k] - y)
                if d <= r and (best is None or d < best[0] - 1e-12 or (abs(d - best[0]) <= 1e-12 and k < best[1])):
                    best = (d, k)
        return None if best is None else (self.z[best[1]], best[0])

    def tra_ngoai_suy(self, x: float, y: float, r: float, kieu: str = "gan_nhat"):
        """Điểm NGOÀI TIN, trong bán kính r của tam giác gần nhất. Trả (z, loại, khoảng cách) hoặc None.

        kieu="gan_nhat" (mặc định, THẬN TRỌNG): cao độ tại ĐIỂM GẦN NHẤT trên mép vùng đo — không kéo
        dài độ dốc. kieu="mat_phang": kéo dài mặt phẳng tam giác; trên ta luy/bờ đắp dốc, kéo 20 m ra
        ngoài cho cao độ vô lý (đo trên lô 01-CGP: đào 4.521 m³ so với 68 m³ của lăng trụ).
        Chỉ dùng khi NGƯỜI đã chấp nhận (lot.yaml luoi.ngoai_suy_m) — RULES 8 mặc định cấm.
        """
        best = None
        for i in self.tam_giac_gan(x - r, y - r, x + r, y + r):
            d, q = _gan_nhat_tam_giac((x, y), self.da_giac(i))
            if d <= r and (best is None or d < best[0] - 1e-12):
                best = (d, i, q)
        if best is None:
            return None
        A, B, C = self.mat_phang(best[1])
        px, py = (x, y) if kieu == "mat_phang" else best[2]
        return A * px + B * py + C, self.loai[best[1]], best[0]

    def tra(self, e: float, n: float):
        """(z, loại tam giác) tại toạ độ VN-2000, hoặc None nếu ngoài TIN."""
        x, y = self.goc.vao(e, n)
        return self.tra_xy(x, y)

    def z_tai(self, e: float, n: float) -> float | None:
        r = self.tra(e, n)
        return None if r is None else r[0]

    def to_dict(self) -> dict:
        e = [self.goc.ra(x, y) for x, y in zip(self.x, self.y)]
        return {"goc": [self.goc.e0, self.goc.n0],
                "diem": [[round(a, 4), round(b, 4), round(z, 4)] for (a, b), z in zip(e, self.z)],
                "tam_giac": [list(t) for t in self.tris],
                "loai_tam_giac": self.loai,
                "canh_rang_buoc": sorted([list(e_) for e_ in self.rang_buoc])}

    @classmethod
    def from_dict(cls, d: dict) -> "Tin":
        goc = Goc(d["goc"][0], d["goc"][1])
        xy = [goc.vao(e, n) for e, n, _ in d["diem"]]
        return cls(goc, [p[0] for p in xy], [p[1] for p in xy], [p[2] for p in d["diem"]],
                   d["tam_giac"], d.get("loai_tam_giac"), d.get("canh_rang_buoc", []))


# =========================================================================== dựng từ điểm
@dataclass
class BaoCaoTin:
    so_diem_vao: int = 0
    so_diem: int = 0
    so_gop: int = 0
    lech_gop_max_m: float = 0.0
    xung_dot: list[dict] = field(default_factory=list)
    rac: list[dict] = field(default_factory=list)
    thieu_du_lieu: list[dict] = field(default_factory=list)
    det_trong: list[dict] = field(default_factory=list)
    khoang_cach_tb_m: float = 0.0
    so_dut_gay: int = 0
    so_doan_ep: int = 0


def _khoa_chinh_tac(x: float, y: float, h: float, z: float):
    band = int(math.floor(y / h))
    return (band, x if band % 2 == 0 else -x, y, z)


def dung_tin(goc: Goc, diem: list[tuple[float, float, float]],
             dut_gay: list[list[tuple[float, float, float]]] | None = None, *,
             tol_trung_m: float = 0.001, giao_dutgay_cm: float = 1.0,
             goc_det_do: float = 5.0, lon_boi: float = 3.0) -> tuple[Tin, BaoCaoTin]:
    """Dựng TIN từ điểm (E,N,Z VN-2000) và đứt gãy 3D. Deterministic: không phụ thuộc
    thứ tự điểm đầu vào."""
    bc = BaoCaoTin(so_diem_vao=len(diem), so_dut_gay=len(dut_gay or []))
    nguon: list[tuple[float, float, float, int]] = []     # x, y, z, loại (0 đo, 1 dứt gãy)
    for e, n, z in diem:
        x, y = goc.vao(e, n)
        nguon.append((x, y, z, 0))
    dg_idx: list[list[int]] = []
    for line in dut_gay or []:
        ids = []
        for e, n, z in line:
            x, y = goc.vao(e, n)
            ids.append(len(nguon))
            nguon.append((x, y, z, 1))
        dg_idx.append(ids)
    if len({(round(s[0], 3), round(s[1], 3)) for s in nguon}) < 3:
        raise TinLoi("Cần ít nhất 3 điểm khác nhau để dựng TIN")

    xs_ = [s[0] for s in nguon]
    ys_ = [s[1] for s in nguon]
    rong = max(max(xs_) - min(xs_), max(ys_) - min(ys_), 1.0)
    h_band = max(rong / max(math.sqrt(len(nguon) / 2.0), 1.0), 1e-3)
    thu_tu = sorted(range(len(nguon)),
                    key=lambda i: _khoa_chinh_tac(nguon[i][0], nguon[i][1], h_band, nguon[i][2]))

    # gộp điểm trùng (cách nhau dưới tol_trung_m) — z lấy TRUNG BÌNH, không phụ thuộc thứ tự
    nhom: list[list[int]] = []
    o_luoi: dict[tuple[int, int], int] = {}
    ve_nhom = [0] * len(nguon)
    for i in thu_tu:
        x, y = nguon[i][0], nguon[i][1]
        gx, gy = int(math.floor(x / tol_trung_m)), int(math.floor(y / tol_trung_m))
        tim = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                g = o_luoi.get((gx + dx, gy + dy))
                if g is not None:
                    q = nguon[nhom[g][0]]
                    if abs(q[0] - x) < tol_trung_m and abs(q[1] - y) < tol_trung_m:
                        tim = g
        if tim is None:
            tim = len(nhom)
            nhom.append([])
            o_luoi[(gx, gy)] = tim
        nhom[tim].append(i)
        ve_nhom[i] = tim

    px, py, pz = [], [], []
    for g in nhom:
        do = [nguon[i][2] for i in g if nguon[i][3] == 0]
        dg = [nguon[i][2] for i in g if nguon[i][3] == 1]
        zs = do or dg
        px.append(sum(nguon[i][0] for i in g) / len(g))
        py.append(sum(nguon[i][1] for i in g) / len(g))
        pz.append(sum(zs) / len(zs))
        if len(g) > 1:
            bc.so_gop += len(g) - 1
            bc.lech_gop_max_m = max(bc.lech_gop_max_m, max(nguon[i][2] for i in g)
                                    - min(nguon[i][2] for i in g))
        if do and dg and abs(sum(do) / len(do) - sum(dg) / len(dg)) * 100 > giao_dutgay_cm:
            e, n = goc.ra(px[-1], py[-1])
            bc.xung_dot.append({"loai": "dut_gay_lech_diem_do", "vi_tri": [round(e, 3), round(n, 3)],
                                "z_diem_do": round(sum(do) / len(do), 4),
                                "z_dut_gay": round(sum(dg) / len(dg), 4)})

    # đoạn đứt gãy theo đỉnh đã gộp; tách tại giao điểm
    doan: list[tuple[int, int]] = []
    for ids in dg_idx:
        for a, b in zip(ids, ids[1:]):
            ga, gb = ve_nhom[a], ve_nhom[b]
            if ga != gb:
                doan.append((ga, gb) if ga < gb else (gb, ga))
    doan = sorted(set(doan))
    cat: dict[int, list[tuple[float, int]]] = {}
    for i in range(len(doan)):
        a1, b1 = doan[i]
        for j in range(i + 1, len(doan)):
            a2, b2 = doan[j]
            if len({a1, b1, a2, b2}) < 4:
                continue
            if (max(px[a1], px[b1]) < min(px[a2], px[b2]) or max(px[a2], px[b2]) < min(px[a1], px[b1])
                    or max(py[a1], py[b1]) < min(py[a2], py[b2]) or max(py[a2], py[b2]) < min(py[a1], py[b1])):
                continue
            g = giao_doan((px[a1], py[a1]), (px[b1], py[b1]), (px[a2], py[a2]), (px[b2], py[b2]))
            if not g:
                continue
            t, u = g
            z1 = pz[a1] + t * (pz[b1] - pz[a1])
            z2 = pz[a2] + u * (pz[b2] - pz[a2])
            xi, yi = px[a1] + t * (px[b1] - px[a1]), py[a1] + t * (py[b1] - py[a1])
            if abs(z1 - z2) * 100 > giao_dutgay_cm:
                e, n = goc.ra(xi, yi)
                bc.xung_dot.append({"loai": "dut_gay_cat_nhau_lech_cao",
                                    "vi_tri": [round(e, 3), round(n, 3)],
                                    "z_duong_1": round(z1, 4), "z_duong_2": round(z2, 4)})
            k = len(px)
            px.append(xi); py.append(yi); pz.append((z1 + z2) / 2)
            cat.setdefault(i, []).append((t, k))
            cat.setdefault(j, []).append((u, k))
    doan_ep: list[tuple[int, int]] = []
    for i, (a, b) in enumerate(doan):
        chuoi = [a] + [k for _, k in sorted(cat.get(i, []))] + [b]
        doan_ep += [(p, q) for p, q in zip(chuoi, chuoi[1:]) if p != q]
    bc.so_doan_ep = len(doan_ep)
    bc.so_diem = len(px)
    if bc.so_diem < 3:
        raise TinLoi("Sau khi gộp điểm trùng còn dưới 3 điểm")

    d = _Dung(px, py)
    for i in range(len(px)):
        d.chen(i)
    rb: set[tuple[int, int]] = set()
    for u, v in doan_ep:
        d.ep(u, v, rb)
    tris = d.ket_qua()
    if not tris:
        raise TinLoi("Không tạo được tam giác nào (điểm thẳng hàng?)")

    # ---- QC: tam giác rác ở mép (loại), tam giác dẹt trong vùng (cảnh báo), quá lớn (đánh dấu)
    def goc_min(t):
        a, b, c = t
        return goc_nho_nhat_do((px[a], py[a]), (px[b], py[b]), (px[c], py[c]))
    giu = list(tris)
    for _ in range(50):
        dem: dict[tuple[int, int], int] = {}
        for a, b, c in giu:
            for e in ((a, b), (b, c), (c, a)):
                k = (e[0], e[1]) if e[0] < e[1] else (e[1], e[0])
                dem[k] = dem.get(k, 0) + 1
        bo = []
        for t in giu:
            a, b, c = t
            tren_mep = any(dem[(e[0], e[1]) if e[0] < e[1] else (e[1], e[0])] == 1
                           for e in ((a, b), (b, c), (c, a)))
            if tren_mep and goc_min(t) < goc_det_do:
                bo.append(t)
        if not bo:
            break
        boset = set(bo)
        for t in bo:
            cx = sum(px[i] for i in t) / 3
            cy = sum(py[i] for i in t) / 3
            e, n = goc.ra(cx, cy)
            bc.rac.append({"vi_tri": [round(e, 3), round(n, 3)], "goc_min_do": round(goc_min(t), 2)})
        giu = [t for t in giu if t not in boset]
    if not giu:
        raise TinLoi("Mọi tam giác đều bị loại là rác — dữ liệu quá thưa hoặc thẳng hàng")

    dt = lambda t: abs((px[t[1]] - px[t[0]]) * (py[t[2]] - py[t[0]])
                       - (px[t[2]] - px[t[0]]) * (py[t[1]] - py[t[0]])) / 2
    tong_dt = sum(dt(t) for t in giu)
    used = {i for t in giu for i in t}
    bc.khoang_cach_tb_m = math.sqrt(tong_dt / max(len(used), 1))
    nguong_lon = lon_boi * bc.khoang_cach_tb_m
    loai = []
    for t in sorted(giu):
        a, b, c = t
        canh = max(math.hypot(px[a] - px[b], py[a] - py[b]), math.hypot(px[b] - px[c], py[b] - py[c]),
                   math.hypot(px[c] - px[a], py[c] - py[a]))
        cx, cy = goc.ra(sum(px[i] for i in t) / 3, sum(py[i] for i in t) / 3)
        # "Quá lớn" = cạnh dài hơn k·d VÀ diện tích hơn tam giác đều cạnh k·d. Chỉ xét cạnh
        # thì tam giác mảnh ở nơi điểm đo thưa ngẫu nhiên bị báo oan (đo 23/11/2026 trên
        # điểm ngẫu nhiên: ~2 % tam giác có cạnh >3d mà không hề có lỗ hổng dữ liệu).
        if canh > nguong_lon and dt(t) > (math.sqrt(3.0) / 4.0) * nguong_lon ** 2:
            loai.append(LOAI_THIEU_DU_LIEU)
            bc.thieu_du_lieu.append({"vi_tri": [round(cx, 3), round(cy, 3)],
                                     "canh_dai_m": round(canh, 2), "dien_tich_m2": round(dt(t), 2)})
        else:
            loai.append(LOAI_TOT)
            if goc_min(t) < goc_det_do:
                bc.det_trong.append({"vi_tri": [round(cx, 3), round(cy, 3)],
                                     "goc_min_do": round(goc_min(t), 2)})
    # đánh lại chỉ số đỉnh: chỉ giữ đỉnh còn dùng, thứ tự ổn định
    giu = sorted(giu)
    ds = sorted(used)
    moi = {o: k for k, o in enumerate(ds)}
    rb2 = [(moi[a], moi[b]) for a, b in rb if a in moi and b in moi]
    tin = Tin(goc, [px[i] for i in ds], [py[i] for i in ds], [pz[i] for i in ds],
              [(moi[a], moi[b], moi[c]) for a, b, c in giu], loai, rb2)
    return tin, bc
