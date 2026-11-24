# cad/ — cầu nối AutoCAD 2022 (giai đoạn 8)

Phơi đúng 13 công cụ của SPEC mục 9:

| Nhóm | Công cụ |
|---|---|
| Đọc | `cad_doc_info`, `cad_read_points`, `cad_read_polylines`, `cad_export_dxf`, `cad_read_grid_z` |
| Ghi (cần duyệt, mặc định `xem_truoc=true`) | `cad_purge_sn`, `cad_draw_grid`, `cad_set_vertex_z`, `cad_label_cells`, `cad_draw_cutfill_line`, `cad_draw_3dface`, `cad_draw_table` |
| Điều hướng | `cad_zoom_to` |

## Hai backend

| Backend | Trạng thái | Dùng để |
|---|---|---|
| `dxf` (`sannen_cad/backend_dxf.py`) | **Đã cài và kiểm thử** (`core/tests/test_gd8_cad.py`) | Vẽ kết quả ra DXF mà người mở trong AutoCAD 2022; kiểm thử hợp đồng; máy không có AutoCAD |
| `com` (`sannen_cad/backend_com.py`) | **KHUNG, chưa cài** — cần AutoCAD 2022 | Ghi thẳng vào bản vẽ đang mở (pywin32). Docstring liệt kê ánh xạ từng công cụ sang lệnh COM |

Backend COM cố ý không có thân hàm: viết mà không chạy thử được trên AutoCAD thật thì chỉ là đoán, trong khi bản vẽ
này đi vào hồ sơ thanh toán. Khi cài, chạy lại đúng bộ test hợp đồng với backend đó trên bản vẽ thật.

## Cách chạy

    cd core && pip install -e ".[dev]"
    set PYTHONPATH=..\cad
    python -m sannen_cad.ve --lot ..\projects\<dự án>\lots\<lô> --vao <dxf nhà thầu> --ra <dxf kết quả> [--preview]
    python -m sannen_cad.mcp_cad_server --vao <dxf nhà thầu> --ra <dxf kết quả>

## Quy ước

- **Không bao giờ ghi đè DXF đầu vào** (RULES 3): `--ra` phải khác `--vao`.
- Mọi đối tượng kết quả mang **Xrecord `SANNEN`**: mã lô, đợt, hash truy vết (`volume.json.hash_dau_vao`), loại
  [, mã đỉnh, bề mặt]. `cad_purge_sn` chỉ xóa đối tượng có Xrecord khớp mã lô (và đợt) — không đụng nguồn, không đụng lô khác.
- Nhiều đợt cùng bản vẽ: đợt ≥ 2 dùng hậu tố layer (`SN-LUOI-D03`). Đợt 1 không hậu tố.
- Layer `SN-3DF-MOC` (xanh lá) / `SN-3DF-DO` (vàng) tắt mặc định; `SN-QC` bật. Mặt 3D vẽ dạng POLYFACE mesh (một đối tượng/bề mặt, ≤ 30000 đỉnh/khối, vượt thì chia khối) khi `dang=polyface` (menu CAD); `dang=3dface` giữ lối 3DFACE rời. Xem `MENU.md`.
- Nhãn đỉnh (`SN-LUOI-NHAN`) là TEXT có Xrecord mã đỉnh + bề mặt; người sửa chữ trực tiếp trong CAD rồi
  `cad_read_grid_z` → `luoi --resync` đưa số về hệ thống (hệ thống báo chênh lệch trước khi nhận).
- Phần ĐỌC đầu vào của lõi KHÔNG đi qua đây: đầu vào là DXF đọc headless (SPEC mục 8).

## Menu SAN NỀN trong AutoCAD

Giao diện menu/hộp thoại, lệnh SN_*, cầu nối và checklist kiểm: xem [MENU.md](MENU.md). Backend LISP (ackend_lisp.py) sinh file entmake nạp thẳng vào bản vẽ đang mở — thay cho phần COM chưa thể kiểm thử.
