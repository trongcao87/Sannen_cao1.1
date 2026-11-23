# Quy ước layer

Mọi layer của hệ thống mang tiền tố `SN-`. Layer không có tiền tố này agent không đụng tới.
Gặp layer `SN-` không có trong bảng → HỎI, không đoán.
Nhiều đợt trong cùng bản vẽ: thêm hậu tố đợt, ví dụ `SN-DIEM-DO-D03`, `SN-LUOI-D03`.

## Nguồn — agent chỉ đọc

| Layer | Đối tượng CAD | Agent làm gì |
|---|---|---|
| `SN-DIEM-MOC` | Point 3D, Block, Text cao độ | → `10_process/points_moc.csv` |
| `SN-DIEM-DO` | Point 3D, Block, Text cao độ | → `10_process/points_do.csv` |
| `SN-DUTGAY` | Polyline 3D | → `breaklines.geojson`, ép thành cạnh ràng buộc TIN |
| `SN-DONGMUC` | Polyline 2D có elevation | Bẻ thành chuỗi điểm theo bước khai báo |
| `SN-BIENLO` | LWPolyline khép kín | → `boundary.geojson`; kiểm khép kín, tự cắt, đối chiếu AREA |
| `SN-LOAITRU` | LWPolyline khép kín | → `exclude.geojson`; trừ khỏi diện tích và khối lượng |

## Kết quả — agent vẽ lại, purge trước khi vẽ

| Layer | Đối tượng CAD | Nội dung |
|---|---|---|
| `SN-LUOI` | Line, LWPolyline | Lưới ô vuông |
| `SN-LUOI-NHAN` | Block có thuộc tính | Cao độ mốc / đo / chênh cao tại đỉnh lưới |
| `SN-LUOI-O` | Text | Khối lượng đào · đắp từng ô |
| `SN-RANH-DAODAP` | LWPolyline | Đường ranh giới đào–đắp |
| `SN-3DF-MOC`, `SN-3DF-DO` | 3DFACE | Mặt 3D hai bề mặt TIN, tắt mặc định |
| `SN-QC` | 3DFACE, Circle | Tam giác dẹt · quá lớn · điểm nghi vấn, màu cảnh báo |
| `SN-BANG` | Table, Mtext | Bảng khối lượng in trong bản vẽ |
