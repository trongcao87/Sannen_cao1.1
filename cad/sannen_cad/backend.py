"""Hợp đồng của lớp CAD — đúng 13 công cụ (SPEC mục 9, cad/README.md).

Mọi backend (DXF để kiểm thử/đầu ra thay thế, COM cho AutoCAD 2022 thật) phải cài đúng giao
diện này; agent và bộ điều phối `ve.py` chỉ biết giao diện, không biết backend.

Quy ước chung:
  - Toạ độ truyền vào/ra luôn là VN-2000 tuyệt đối (E, N, Z). Dời gốc là việc của lõi tính.
  - Mọi đối tượng KẾT QUẢ mang Xrecord "SANNEN" ghi: mã lô, đợt, hash truy vết, loại [, mã đỉnh, bề mặt].
  - Công cụ ghi nhận cờ `xem_truoc` (RULES 4): True thì chỉ trả về điều SẼ làm, không ghi.
"""
from __future__ import annotations
from abc import ABC, abstractmethod

# Các layer kết quả — agent vẽ lại, purge trước khi vẽ (kb/layer-convention.md)
LAYER_KET_QUA = ("SN-LUOI", "SN-LUOI-NHAN", "SN-LUOI-O", "SN-RANH-DAODAP",
                 "SN-3DF-MOC", "SN-3DF-DO", "SN-QC", "SN-BANG", "SN-MATCAT")
# Loại đối tượng ghi trong dấu truy vết (Xrecord/XDATA). `cad_purge_sn(loai=...)` xóa theo loại để vẽ lại từng phần.
LOAI = ("luoi", "nhan_dinh", "nhan_o", "ranh_dao_dap", "mat_3d", "qc", "bang", "mat_cat", "cong_o")
NHOM_LOP = {"luoi": ("luoi",), "nhan": ("nhan_dinh",), "o": ("nhan_o", "cong_o"), "ranh": ("ranh_dao_dap",),
            "3d": ("mat_3d", "qc"), "bang": ("bang",), "mat_cat": ("mat_cat",)}
TEN_CONG_CU = ("cad_doc_info", "cad_read_points", "cad_read_polylines", "cad_export_dxf", "cad_read_grid_z",
               "cad_purge_sn", "cad_draw_grid", "cad_set_vertex_z", "cad_label_cells",
               "cad_draw_cutfill_line", "cad_draw_3dface", "cad_draw_table", "cad_zoom_to")
CONG_CU_GHI = ("cad_purge_sn", "cad_draw_grid", "cad_set_vertex_z", "cad_label_cells",
               "cad_draw_cutfill_line", "cad_draw_3dface", "cad_draw_table")


def ten_layer(goc: str, dot: int | None) -> str:
    """SN-LUOI cho đợt 1; SN-LUOI-D03 cho đợt 3 (nhiều đợt cùng một bản vẽ)."""
    return goc if not dot or dot <= 1 else f"{goc}-D{dot:02d}"


# ---- mặt 3D: POLYFACE MESH (một đối tượng/bề mặt) hoặc 3DFACE rời (lối cũ) -------------------------------
DANG_3D = ("polyface", "3dface")
TOI_DA_DINH_POLYFACE = 30000          # AutoCAD: một polyface ≤ 32767 đỉnh; chừa dư cho mặt mốc/đo lớn
MAU_LAYER = {"SN-LUOI": 8, "SN-LUOI-NHAN": 3, "SN-LUOI-O": 2, "SN-RANH-DAODAP": 1, "SN-3DF-MOC": 3,
             "SN-3DF-DO": 2, "SN-QC": 6, "SN-BANG": 7, "SN-MATCAT": 6}       # mốc xanh lá, đo vàng


def kiem_dang_3d(dang: str) -> str:
    if dang not in DANG_3D:
        raise ValueError(f"dang phải là một trong {DANG_3D} — nhận được «{dang}»")
    return dang


def chia_polyface(tam_giac: list, toi_da: int = TOI_DA_DINH_POLYFACE) -> list[tuple[list[tuple], list[tuple]]]:
    """Tam giác [[p,p,p],...] → các khối polyface [(đỉnh, mặt)], đỉnh dùng chung theo toạ độ, mặt là chỉ số 0-based.

    Một polyface chứa tối đa `toi_da` đỉnh: vượt thì chia thành nhiều khối LIÊN TIẾP theo thứ tự tam giác."""
    khoi: list[tuple[list[tuple], list[tuple]]] = []
    dinh: list[tuple] = []
    chi_so: dict[tuple, int] = {}
    mat: list[tuple] = []
    for t in tam_giac:
        p = [tuple(round(float(v), 6) for v in q) for q in t[:3]]
        moi = len({q for q in p if q not in chi_so})
        if mat and len(dinh) + moi > toi_da:
            khoi.append((dinh, mat))
            dinh, chi_so, mat = [], {}, []
        ids = []
        for q in p:
            if q not in chi_so:
                chi_so[q] = len(dinh)
                dinh.append(q)
            ids.append(chi_so[q])
        mat.append(tuple(ids))
    if mat:
        khoi.append((dinh, mat))
    return khoi


class Backend(ABC):
    # ---- đọc ---------------------------------------------------------------------
    @abstractmethod
    def cad_doc_info(self) -> dict: ...

    @abstractmethod
    def cad_read_points(self, layer: str) -> list[list[float]]: ...

    @abstractmethod
    def cad_read_polylines(self, layer: str) -> list[dict]: ...

    @abstractmethod
    def cad_export_dxf(self, duong_dan: str) -> dict: ...

    @abstractmethod
    def cad_read_grid_z(self, ma_lo: str, dot: int | None = None) -> list[dict]: ...

    # ---- ghi (cần duyệt) -------------------------------------------------------------
    @abstractmethod
    def cad_purge_sn(self, ma_lo: str, dot: int | None = None, xem_truoc: bool = True,
                     loai: tuple[str, ...] | None = None) -> dict: ...

    def ve_ent(self, ma_lo: str, dot: int, hash_tv: str, loai: str, layer: str, ent: list,
               xem_truoc: bool = True, **them) -> dict:
        """Mở rộng (ngoài 13 công cụ): vẽ danh sách đối tượng đơn giản của `bo_cuc` — bảng tổng, mặt cắt, cộng ô."""
        raise NotImplementedError("Backend này chưa hỗ trợ ve_ent")

    @abstractmethod
    def cad_draw_grid(self, ma_lo: str, dot: int, hash_tv: str, luoi: dict, xem_truoc: bool = True) -> dict: ...

    @abstractmethod
    def cad_set_vertex_z(self, ma_lo: str, dot: int, hash_tv: str, nut: list[dict], xem_truoc: bool = True) -> dict: ...

    @abstractmethod
    def cad_label_cells(self, ma_lo: str, dot: int, hash_tv: str, o: list[dict], xem_truoc: bool = True) -> dict: ...

    @abstractmethod
    def cad_draw_cutfill_line(self, ma_lo: str, dot: int, hash_tv: str, doan: list, xem_truoc: bool = True) -> dict: ...

    @abstractmethod
    def cad_draw_3dface(self, ma_lo: str, dot: int, hash_tv: str, be_mat: str, tam_giac: list,
                        loai: str = "mat", xem_truoc: bool = True, dang: str = "3dface") -> dict:
        """`dang="polyface"`: MỘT đối tượng POLYLINE polyface/bề mặt (≤ 30000 đỉnh/khối — vượt thì chia khối liên tiếp);
        `dang="3dface"`: mỗi tam giác một 3DFACE rời (lối cũ, giữ để tương thích)."""
        ...

    @abstractmethod
    def cad_draw_table(self, ma_lo: str, dot: int, hash_tv: str, bang: dict, goc_ve: list,
                       chieu_cao_chu: float = 1.25, xem_truoc: bool = True) -> dict: ...

    # ---- điều hướng ------------------------------------------------------------------
    @abstractmethod
    def cad_zoom_to(self, e: float, n: float, kich_thuoc: float = 50.0) -> dict: ...
