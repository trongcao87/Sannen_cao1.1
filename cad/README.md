# cad/ — cầu nối AutoCAD 2022

Trống tới giai đoạn 8. Khi làm, phơi đúng 13 tool trong SPEC mục 9:

Đọc: `cad_doc_info`, `cad_read_points`, `cad_read_polylines`, `cad_export_dxf`,
`cad_read_grid_z`.
Ghi (cần duyệt): `cad_purge_sn`, `cad_draw_grid`, `cad_set_vertex_z`,
`cad_label_cells`, `cad_draw_cutfill_line`, `cad_draw_3dface`, `cad_draw_table`.
Điều hướng: `cad_zoom_to`.

Bản đầu viết bằng Python qua COM/ActiveX (pywin32). Khi cần vẽ hàng trăm nghìn
entity thì thay tầng COM bằng add-in .NET phơi đúng những tên tool này — agent
không phải đổi gì.

Lưu ý: phần ĐỌC đầu vào KHÔNG đi qua đây. Đầu vào là DXF đọc headless bằng ezdxf
(SPEC mục 13). `cad_export_dxf` chỉ để xuất lại DXF mỗi khi biên lô hay đứt gãy đổi.
