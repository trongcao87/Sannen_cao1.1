---
name: nhap
mo_ta: Đọc DXF, Excel hoặc CSV, chuẩn hóa điểm đo và hình học, chạy các phép kiểm dữ liệu.
giai_doan: 1
---
# nhap

## Kích hoạt khi
Người nói "nạp dữ liệu lô X", "đọc bản vẽ", "kiểm tra số liệu khảo sát", hoặc đây là
verb đầu tiên của một đợt nghiệm thu mới.

## Lệnh
    python -m sannen.cli nhap --lot <thư mục lô> [--preview] [--xac-nhan-anh-xa]

Mã thoát: `0` sạch · `1` có việc CHẶN (không qua cổng dữ liệu) · `2` dừng vì khai báo
hoặc file nguồn sai / cần người xác nhận · `3` verb chưa cài.

## Vào
- `lot.yaml` khai nguồn từng bề mặt: `nguon: dxf_layer | excel | csv`.
  Với excel/csv phải khai `file:` (tên file trong `00_input/`), tùy chọn `sheet:`.
- `00_input/*.dxf` — biên lô, đứt gãy, vùng loại trừ; và điểm nếu nguồn là `dxf_layer`.
  Không có DXF thì `nhap` vẫn đọc được điểm nhưng ghi cảnh báo thiếu biên lô.
- `00_input/*.xlsx|csv` — khi khảo sát giao bảng số.

## Excel / CSV — ba điều lõi tự xử lý
1. **Hàng tiêu đề nằm giữa trang** — dò trong 40 hàng đầu.
2. **Nhiều khối điểm trên một dòng** (vd cột 1-5 và 6-10) — mỗi khối đọc như một bảng riêng.
3. **Số kiểu Việt Nam** — `103,5` = 103.5; `1.113.045,123` = 1113045.123.

## Ánh xạ cột — lõi KHÔNG đoán (RULES 7)
Thứ tự ưu tiên:
1. `anh_xa_cot` trong `be_mat_*` hoặc `anh_xa_cot_excel` ở lot.yaml → dùng luôn. Không thấy
   tiêu đề đã khai trong file → dừng, in ra các tiêu đề đang có.
2. `anh_xa_cot.yaml` ở thư mục lô, người từng xác nhận, khớp **dấu vân tay hàng tiêu đề** →
   dùng, khỏi hỏi. Khảo sát đổi khuôn bảng thì dấu vân tay lệch và hỏi lại.
3. Chưa có gì → lõi đề xuất từ tiêu đề rồi **dừng (mã 2)**, in kèm một dòng dữ liệu mẫu.

**Agent phải đưa đề xuất cho người xem** (nhất là X↔northing, Y↔easting — đảo là lỗi hay
gặp nhất) rồi mới chạy lại với `--xac-nhan-anh-xa`. Không tự thêm cờ này. Lần xác nhận
ghi vào `anh_xa_cot.yaml` và `90_log/decisions.md`. `--preview` không ghi gì.

## Ra
`10_process/points_moc.csv`, `points_do.csv`, `breaklines.geojson`,
`boundary.geojson`, `exclude.geojson`, `qc_input.json`, `viec_can_lam.md`.

Lưu ý: cả bảy file này đều DẪN XUẤT từ DXF/Excel. Người không chuẩn bị chúng.
Chúng nằm ở `10_process/` vì xóa đi sinh lại được — `00_input/` agent không ghi.
`qc_input.json` và log mang hash từng file nguồn, ánh xạ cột đã dùng, số điểm, số dòng hỏng.

## Các phép kiểm (ngưỡng từ kb/nguong-qc.md)
1. **Dòng hỏng** (Excel/CSV) — ô tọa độ/cao độ không phải số hoặc thiếu → bỏ dòng đó, ghi
   lại đúng `Sheet!hàng N (khối k)`. Quá 5 % dòng hỏng → CHẶN (gần như chắc chắn ánh xạ sai).
   Dòng chữ như "Tổng cộng" và khối trống cuối bảng không tính là hỏng.
2. **Điểm trùng mặt bằng** — cách nhau dưới `trung_mat_bang_mm`. Lệch cao độ đáng kể → báo
   nghi vấn. Trùng cả cao độ → chỉ thông báo, KHÔNG xóa (RULES 2); dựng TIN sẽ gộp.
3. **Cao độ bất thường** — 8 điểm gần nhất, trung vị và MAD (có sàn `mad_san_m`).
   |Z − trung vị| > `mad_he_so` × MAD thì đánh dấu. Bắt rất tốt lỗi gõ 2.85 → 28.5.
4. **Phạm vi toạ độ** — khu đất rộng bất thường (lẫn hệ toạ độ hoặc m/mm).
5. **Nghi đảo X/Y** — với VN-2000, easting trung vị lớn hơn northing trung vị → CHẶN.
6. **Tên điểm lặp** (Excel/CSV) — cảnh báo; không đổi tên.

## Hỏi người trước khi chạy
- File Excel mới: đề xuất ánh xạ cột có đúng không? (xem trên)
- DXF có layer `SN-` lạ: layer đó vai trò gì?
- `be_mat_*.layer` khác quy ước → đổi tên layer trong bản vẽ, không đổi quy ước.

## Cổng duyệt
Sau khi chạy, ghi `viec_can_lam.md`: mã V-01, V-02… **liền mạch cho cả hai bề mặt**, mỗi
việc kèm vị trí (toạ độ hoặc ô Excel). Người quyết giữ hay bỏ. Agent KHÔNG tự sửa cao độ.
