"""Backend COM cho AutoCAD 2022 — KHUNG, chưa cài và chưa kiểm thử.

Máy phát triển không có AutoCAD nên phần này CỐ Ý không viết thân hàm: viết mà không chạy
thử được trên AutoCAD thật thì chỉ là đoán, và bản vẽ này đi vào hồ sơ thanh toán.

Việc cần làm khi có AutoCAD 2022 (pywin32: `win32com.client.Dispatch("AutoCAD.Application")`):

  cad_doc_info           doc = acad.ActiveDocument; duyệt doc.Layers, doc.ModelSpace.Count
  cad_read_points        ModelSpace, lọc ObjectName == "AcDbPoint" && Layer == layer
  cad_read_polylines     "AcDbPolyline" / "AcDb3dPolyline"; Coordinates, Closed, Elevation
  cad_export_dxf         doc.SaveAs(path, ac2018_dxf)   (đầu vào của lõi là DXF)
  cad_read_grid_z        đọc Text của đối tượng trên SN-LUOI-NHAN, mã đỉnh/bề mặt lấy từ Xrecord
  cad_purge_sn           quét ModelSpace, lọc layer SN-* + Xrecord "SANNEN" (mã lô khớp) → Delete()
  cad_draw_grid          AddLightWeightPolyline
  cad_set_vertex_z       AddText / sửa TextString; Xrecord qua doc.Dictionaries + AddXRecord
  cad_label_cells        AddMText
  cad_draw_cutfill_line  AddLightWeightPolyline
  cad_draw_3dface        Add3DFace — chia lô lớn thành nhiều đợt (hàng trăm nghìn entity
                         thì thay lớp COM bằng add-in .NET phơi đúng những tên tool này)
  cad_draw_table         AddTable (thật) — khác backend DXF chỉ có đường + chữ
  cad_zoom_to            acad.ZoomWindow / ZoomCenter

Khi cài: chạy lại bộ test hợp đồng (core/tests/test_gd8_cad.py) với backend này trên một bản vẽ
thật, rồi purge sạch, vẽ hai lần, so số đối tượng — đúng điều kiện qua cửa giai đoạn 8.
"""
from __future__ import annotations

from .backend import Backend, TEN_CONG_CU

_THONG_BAO = ("Backend COM chưa cài đặt — cần AutoCAD 2022 để viết và kiểm thử (xem docstring). "
              "Dùng backend DXF: --backend dxf")


class BackendCOM(Backend):
    def __init__(self, *a, **kw):
        raise NotImplementedError(_THONG_BAO)


def _khong_cai(ten):
    def f(self, *a, **kw):
        raise NotImplementedError(_THONG_BAO)
    f.__name__ = ten
    return f


for _ten in TEN_CONG_CU:
    setattr(BackendCOM, _ten, _khong_cai(_ten))
BackendCOM.__abstractmethods__ = frozenset()
