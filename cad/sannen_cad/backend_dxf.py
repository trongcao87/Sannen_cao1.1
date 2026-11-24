"""Backend DXF — cài đủ 13 công cụ bằng ezdxf, chạy không cần AutoCAD.

Dùng cho: (1) kiểm thử hợp đồng CAD; (2) xuất kết quả ra DXF khi máy chưa có AutoCAD;
(3) dựng lại bản vẽ để người mở trong AutoCAD 2022 xoay 3D, soi gai nhọn.
KHÔNG BAO GIỜ ghi đè file DXF đầu vào (RULES 3): luôn lưu sang đường dẫn `ra`.
"""
from __future__ import annotations
import math
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

from .backend import (LAYER_KET_QUA, MAU_LAYER, TOI_DA_DINH_POLYFACE, Backend, chia_polyface, kiem_dang_3d,
                      ten_layer)
from .bo_cuc import bang_ent

MAU = MAU_LAYER
APPID = "SANNEN"


class BackendDXF(Backend):
    toi_da_dinh = TOI_DA_DINH_POLYFACE          # số đỉnh tối đa của MỘT polyface (test hạ xuống để thử chia khối)

    def __init__(self, vao: str | Path, ra: str | Path):
        self.vao, self.ra = Path(vao).resolve(), Path(ra).resolve()
        if self.vao == self.ra:
            raise ValueError("RULES 3: không ghi đè DXF đầu vào — cho đường dẫn `ra` khác")
        self.doc = ezdxf.readfile(self.vao)
        self.msp = self.doc.modelspace()

    # ---- tiện ích -----------------------------------------------------------------
    def luu(self) -> None:
        self.ra.parent.mkdir(parents=True, exist_ok=True)
        self.doc.saveas(self.ra)

    def _layer(self, goc: str, dot: int | None) -> str:
        ten = ten_layer(goc, dot)
        if ten not in self.doc.layers:
            lay = self.doc.layers.add(ten, color=MAU.get(goc, 7))
            if goc.startswith("SN-3DF"):
                lay.off()                                   # mặt 3D tắt mặc định (layer-convention)
        return ten

    def _danh_dau(self, e, ma_lo: str, dot: int, hash_tv: str, loai: str, **them) -> None:
        """Xrecord mã lô + đợt + hash truy vết (SPEC mục 8)."""
        xd = e.new_extension_dict()
        xr = xd.add_xrecord(APPID)
        tags = [(1, ma_lo), (1, str(dot)), (1, hash_tv), (1, loai)]
        tags += [(1, f"{k}={v}") for k, v in them.items()]
        xr.reset(tags)

    @staticmethod
    def doc_nhan(e) -> dict | None:
        """Dấu truy vết: Xrecord (backend DXF) hoặc XDATA (đối tượng do file LISP vẽ trong AutoCAD) — cùng nội dung."""
        gt = None
        if e.has_extension_dict:
            xd = e.get_extension_dict()
            if APPID in xd:
                gt = [t.value for t in xd[APPID].tags]
        if gt is None and e.has_xdata(APPID):
            gt = [t.value for t in e.get_xdata(APPID)]
        if gt is None or len(gt) < 4:
            return None
        d = {"ma_lo": gt[0], "dot": int(gt[1]), "hash": gt[2], "loai": gt[3]}
        for x in gt[4:]:
            k, _, v = str(x).partition("=")
            d[k] = v
        return d

    def _la_ket_qua(self, layer: str) -> bool:
        return any(layer == g or layer.startswith(g + "-D") for g in LAYER_KET_QUA)

    def _doi_tuong_ket_qua(self, ma_lo: str, dot: int | None = None, loai: tuple[str, ...] | None = None):
        for e in list(self.msp):
            if not self._la_ket_qua(e.dxf.layer):
                continue
            n = self.doc_nhan(e)
            if n and n["ma_lo"] == ma_lo and (dot is None or n["dot"] == dot) and (loai is None or n["loai"] in loai):
                yield e, n

    def _ket_qua(self, ten: str, xem_truoc: bool, **kq) -> dict:
        if not xem_truoc:
            self.luu()
        return {"cong_cu": ten, "xem_truoc": xem_truoc, "da_ghi": not xem_truoc, **kq}

    # ---- đọc ------------------------------------------------------------------------
    def cad_doc_info(self) -> dict:
        dem: dict[str, int] = {}
        lo: dict[str, int] = {}
        for e in self.msp:
            dem[e.dxf.layer] = dem.get(e.dxf.layer, 0) + 1
            n = self.doc_nhan(e) if self._la_ket_qua(e.dxf.layer) else None
            if n:
                lo[f"{n['ma_lo']}/đợt {n['dot']}"] = lo.get(f"{n['ma_lo']}/đợt {n['dot']}", 0) + 1
        return {"file": str(self.vao), "ra": str(self.ra), "backend": "dxf", "phien_ban_dxf": self.doc.acad_release,
                "layer": sorted(l.dxf.name for l in self.doc.layers),
                "so_doi_tuong_theo_layer": dem,
                "so_doi_tuong_sn": sum(v for k, v in dem.items() if k.upper().startswith("SN-")),
                "lo_da_ve": lo}

    def cad_read_points(self, layer: str) -> list[list[float]]:
        return [[e.dxf.location.x, e.dxf.location.y, e.dxf.location.z]
                for e in self.msp.query(f'POINT[layer=="{layer}"]')]

    def cad_read_polylines(self, layer: str) -> list[dict]:
        ra = []
        for e in self.msp.query(f'LWPOLYLINE[layer=="{layer}"]'):
            ra.append({"khep_kin": bool(e.closed), "elevation": float(e.dxf.elevation),
                       "dinh": [[p[0], p[1], p[2]] for p in e.get_points("xyb")]})
        for e in self.msp.query(f'POLYLINE[layer=="{layer}"]'):
            ra.append({"khep_kin": bool(e.is_closed), "elevation": 0.0,
                       "dinh": [[v.dxf.location.x, v.dxf.location.y, v.dxf.location.z] for v in e.vertices]})
        return ra

    def cad_export_dxf(self, duong_dan: str) -> dict:
        p = Path(duong_dan).resolve()
        if p == self.vao:
            raise ValueError("RULES 3: không ghi đè DXF đầu vào")
        p.parent.mkdir(parents=True, exist_ok=True)
        self.doc.saveas(p)
        return {"da_ghi": str(p)}

    def cad_read_grid_z(self, ma_lo: str, dot: int | None = None) -> list[dict]:
        """Đọc ngược cao độ đỉnh từ NHÃN trong bản vẽ — người có thể đã sửa tay (luoi --resync)."""
        ra = []
        for e, n in self._doi_tuong_ket_qua(ma_lo, dot):
            if n["loai"] != "nhan_dinh" or n.get("be_mat") not in ("moc", "do"):
                continue
            try:
                z = float(str(e.dxf.text).strip().replace(",", "."))
            except ValueError:
                continue
            ra.append({"ma": n["ma"], "be_mat": n["be_mat"], "z": z})
        return sorted(ra, key=lambda x: (x["ma"], x["be_mat"]))

    # ---- ghi ------------------------------------------------------------------------
    def cad_purge_sn(self, ma_lo: str, dot: int | None = None, xem_truoc: bool = True,
                     loai: tuple[str, ...] | None = None) -> dict:
        """Xóa sạch đối tượng kết quả CŨ của đúng lô này (RULES 5); không đụng nguồn, không đụng lô khác.
        `loai` giới hạn theo loại đối tượng (vẽ lại riêng lưới, riêng nhãn...)."""
        ds = list(self._doi_tuong_ket_qua(ma_lo, dot, loai))
        theo = {}
        for e, _ in ds:
            theo[e.dxf.layer] = theo.get(e.dxf.layer, 0) + 1
        if not xem_truoc:
            for e, _ in ds:
                self.msp.delete_entity(e)
        return self._ket_qua("cad_purge_sn", xem_truoc, ma_lo=ma_lo, so_xoa=len(ds), theo_layer=theo)

    def cad_draw_grid(self, ma_lo, dot, hash_tv, luoi, xem_truoc=True) -> dict:
        ox, oy = luoi["goc_luoi"]
        th = math.radians(luoi["goc_xoay_do"])
        c, s = math.cos(th), math.sin(th)
        U, V = [0.0], [0.0]
        for w in luoi["cot_m"]:
            U.append(U[-1] + w)
        for h in luoi["hang_m"]:
            V.append(V[-1] + h)
        P = lambda u, v: (ox + u * c - v * s, oy + u * s + v * c)
        duong = [(P(u, V[0]), P(u, V[-1])) for u in U] + [(P(U[0], v), P(U[-1], v)) for v in V]
        if not xem_truoc:
            ly = self._layer("SN-LUOI", dot)
            for a, b in duong:
                e = self.msp.add_lwpolyline([a, b], dxfattribs={"layer": ly})
                self._danh_dau(e, ma_lo, dot, hash_tv, "luoi")
        return self._ket_qua("cad_draw_grid", xem_truoc, so_duong=len(duong))

    def cad_set_vertex_z(self, ma_lo, dot, hash_tv, nut, xem_truoc=True) -> dict:
        """Đặt (tạo hoặc cập nhật) nhãn cao độ mốc / đo / chênh cao tại từng đỉnh lưới."""
        moi = cap_nhat = 0
        co = {}
        for e, n in self._doi_tuong_ket_qua(ma_lo, dot):
            if n["loai"] == "nhan_dinh":
                co[(n["ma"], n["be_mat"])] = e
        for d in nut:
            dz = None if d.get("z_do") is None or d.get("z_moc") is None else d["z_do"] - d["z_moc"]
            for be, z, dy in (("moc", d.get("z_moc"), 0.0), ("do", d.get("z_do"), -1.0), ("dz", dz, -2.0)):
                if z is None:
                    continue
                txt = f"{z:+.3f}" if be == "dz" else f"{z:.3f}"
                e = co.get((d["ma"], be))
                if e is not None:
                    cap_nhat += 1
                    if not xem_truoc:
                        e.dxf.text = txt
                else:
                    moi += 1
                    if not xem_truoc:
                        ly = self._layer("SN-LUOI-NHAN", dot)
                        t = self.msp.add_text(txt, height=0.5, dxfattribs={"layer": ly})
                        t.set_placement((d["e"] + 0.3, d["n"] + 0.3 + dy * 0.7), align=TextEntityAlignment.LEFT)
                        self._danh_dau(t, ma_lo, dot, hash_tv, "nhan_dinh", ma=d["ma"], be_mat=be)
        return self._ket_qua("cad_set_vertex_z", xem_truoc, nhan_moi=moi, nhan_cap_nhat=cap_nhat)

    def cad_label_cells(self, ma_lo, dot, hash_tv, o, xem_truoc=True) -> dict:
        if not xem_truoc:
            ly = self._layer("SN-LUOI-O", dot)
            for c in o:
                van_ban = f"{c['ma']}\\PĐào {c['kl_dao_m3']:,.1f}\\PĐắp {c['kl_dap_m3']:,.1f}"
                if c.get("thieu_du_lieu"):
                    van_ban = f"{c['ma']}\\PTHIẾU DỮ LIỆU"
                m = self.msp.add_mtext(van_ban, dxfattribs={"layer": ly, "char_height": 0.8,
                                                             "insert": (c["e"], c["n"], 0.0),
                                                             "attachment_point": 5})
                self._danh_dau(m, ma_lo, dot, hash_tv, "nhan_o", ma=c["ma"])
        return self._ket_qua("cad_label_cells", xem_truoc, so_nhan=len(o))

    def cad_draw_cutfill_line(self, ma_lo, dot, hash_tv, doan, xem_truoc=True) -> dict:
        if not xem_truoc:
            ly = self._layer("SN-RANH-DAODAP", dot)
            for a, b in doan:
                e = self.msp.add_lwpolyline([tuple(a), tuple(b)], dxfattribs={"layer": ly})
                self._danh_dau(e, ma_lo, dot, hash_tv, "ranh_dao_dap")
        return self._ket_qua("cad_draw_cutfill_line", xem_truoc, so_doan=len(doan))

    def cad_draw_3dface(self, ma_lo, dot, hash_tv, be_mat, tam_giac, loai="mat", xem_truoc=True, dang="3dface") -> dict:
        kiem_dang_3d(dang)
        goc = "SN-QC" if loai == "qc" else ("SN-3DF-MOC" if be_mat == "moc" else "SN-3DF-DO")
        loai_tv = "mat_3d" if loai != "qc" else "qc"
        kq: dict = {}
        if dang == "polyface":
            khoi = chia_polyface(tam_giac, self.toi_da_dinh)
            kq = {"dang": "polyface", "so_polyface": len(khoi), "so_dinh": sum(len(d) for d, _ in khoi)}
            if len(khoi) > 1:
                kq["ghi_chu"] = (f"Bề mặt có {kq['so_dinh']} đỉnh — vượt giới hạn một polyface của AutoCAD, "
                                 f"đã chia thành {len(khoi)} khối liên tiếp (mỗi khối ≤ {self.toi_da_dinh} đỉnh)")
            if not xem_truoc:
                ly = self._layer(goc, dot)
                for i, (dinh, mat) in enumerate(khoi, 1):
                    pf = self.msp.add_polyface(dxfattribs={"layer": ly})
                    pf.append_faces([[dinh[k] for k in m] for m in mat])
                    self._danh_dau(pf, ma_lo, dot, hash_tv, loai_tv, be_mat=be_mat, so_mat=len(mat), khoi=f"{i}/{len(khoi)}")
        elif not xem_truoc:
            ly = self._layer(goc, dot)
            for t in tam_giac:
                f = self.msp.add_3dface([tuple(p) for p in t], dxfattribs={"layer": ly})
                self._danh_dau(f, ma_lo, dot, hash_tv, loai_tv, be_mat=be_mat)
        return self._ket_qua("cad_draw_3dface", xem_truoc, layer=ten_layer(goc, dot), so_mat=len(tam_giac), **kq)

    def cad_draw_table(self, ma_lo, dot, hash_tv, bang, goc_ve, chieu_cao_chu=1.25, xem_truoc=True) -> dict:
        """Bảng in: tiêu đề + các khối cạnh nhau (≤ 40 dòng/khối) + chân. Bố cục dùng chung (bo_cuc.bang_ent)."""
        ent = bang_ent(bang, goc_ve, chieu_cao_chu)
        kq = self.ve_ent(ma_lo, dot, hash_tv, "bang", "SN-BANG", ent, xem_truoc)
        return {**kq, "cong_cu": "cad_draw_table", "so_khoi": len(bang["khoi"])}

    def ve_ent(self, ma_lo, dot, hash_tv, loai, layer, ent, xem_truoc=True, **them) -> dict:
        """Vẽ danh sách đối tượng đơn giản (bo_cuc): chữ, khung, đoạn, đa tuyến — mỗi cái mang dấu truy vết."""
        if not xem_truoc:
            ly = self._layer(layer, dot)
            for x in ent:
                if x[0] == "text":
                    e = self.msp.add_text(str(x[1]), height=x[4], dxfattribs={"layer": ly, "color": x[5] if len(x) > 5 else 256})
                    e.set_placement((x[2], x[3]), align=TextEntityAlignment.LEFT)
                elif x[0] == "khung":
                    _, fx, fy, fw, fh = x
                    e = self.msp.add_lwpolyline([(fx, fy), (fx + fw, fy), (fx + fw, fy - fh), (fx, fy - fh)],
                                                close=True, dxfattribs={"layer": ly})
                elif x[0] == "doan":
                    e = self.msp.add_lwpolyline([(x[1], x[2]), (x[3], x[4])],
                                                dxfattribs={"layer": ly, "color": x[5] if len(x) > 5 else 256})
                elif x[0] == "pl":
                    e = self.msp.add_lwpolyline([tuple(p) for p in x[1]], close=bool(x[2]),
                                                dxfattribs={"layer": ly, "color": x[3] if len(x) > 3 else 256})
                else:
                    raise ValueError(f"Phần tử bố cục lạ: {x[0]}")
                self._danh_dau(e, ma_lo, dot, hash_tv, loai, **them)
        return self._ket_qua("ve_ent", xem_truoc, loai=loai, so_doi_tuong=len(ent))

    # ---- điều hướng -------------------------------------------------------------------
    def cad_zoom_to(self, e: float, n: float, kich_thuoc: float = 50.0) -> dict:
        self.doc.set_modelspace_vport(height=kich_thuoc, center=(e, n))
        self.luu()
        return {"e": e, "n": n, "chieu_cao_khung_nhin": kich_thuoc}
