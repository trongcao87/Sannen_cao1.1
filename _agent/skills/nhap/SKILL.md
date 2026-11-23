---
name: nhap
mo_ta: Đọc DXF hoặc Excel, chuẩn hóa điểm đo và hình học, chạy 4 phép kiểm dữ liệu.
giai_doan: 1
---
# nhap

## Kích hoạt khi
Người nói "nạp dữ liệu lô X", "đọc bản vẽ", "kiểm tra số liệu khảo sát", hoặc đây là
verb đầu tiên của một đợt nghiệm thu mới.

## Lệnh
    python -m sannen.cli nhap --lot <thư mục lô> [--preview]

## Vào
- `00_input/*.dxf` — nguồn chính. Layer theo `kb/layer-convention.md`.
- `00_input/*.xlsx` — khi khảo sát giao Excel. Ánh xạ cột lấy từ `lot.yaml`.
- `lot.yaml` — khai báo nguồn của từng bề mặt.

## Ra
`10_process/points_moc.csv`, `points_do.csv`, `breaklines.geojson`,
`boundary.geojson`, `exclude.geojson`, `qc_input.json`.

Lưu ý: cả năm file này đều DẪN XUẤT từ DXF/Excel. Người không chuẩn bị chúng.
Chúng nằm ở `10_process/` vì xóa đi sinh lại được — `00_input/` agent không ghi.

## Bốn phép kiểm (ngưỡng từ kb/nguong-qc.md)
1. **Dòng hỏng** — thiếu toạ độ hoặc không phải số → bỏ qua, ghi lại số dòng.
2. **Điểm trùng mặt bằng** — cách nhau dưới `trung_mat_bang_mm`. Cao độ gần nhau thì
   giữ một; lệch đáng kể thì báo nghi vấn.
3. **Cao độ bất thường** — với mỗi điểm lấy 8 điểm gần nhất, tính trung vị và MAD.
   |Z − trung vị| > `mad_he_so` × MAD thì đánh dấu. Bắt rất tốt lỗi gõ 103.5 → 1035.
4. **Phạm vi toạ độ** — cảnh báo nếu khu đất rộng bất thường (lẫn hệ toạ độ hoặc m/mm).

## Hỏi người trước khi chạy
- File Excel: ánh xạ cột có đúng không? Nhớ lại cho lần sau.
- DXF có layer `SN-` lạ: layer đó vai trò gì?

## Cổng duyệt
Sau khi chạy, ghi `viec_can_lam.md` với từng điểm nghi vấn kèm toạ độ. Người quyết
giữ hay bỏ. Agent KHÔNG tự sửa cao độ — dữ liệu đo là bằng chứng (RULES 2).
