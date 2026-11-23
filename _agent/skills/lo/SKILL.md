---
name: lo
mo_ta: Chuẩn hóa biên lô và vùng loại trừ, đối chiếu diện tích với lệnh AREA.
giai_doan: 3
---
# lo

## Lệnh
    python -m sannen.cli lo --lot <thư mục lô>

Chạy song song với `mat`.

## Chuẩn hóa hình học — làm trước, một lần
1. **Khép kín và tự cắt** — biên tự cắt làm mọi phép tính diện tích sai dấu.
   Báo lỗi và chỉ đúng vị trí giao điểm.
2. **Chia nhỏ cung tròn** — LWPolyline có thể chứa bulge. Bung thành đoạn thẳng với
   sai số đỉnh cung dưới `cung_tron_sai_so_mm`. BẮT BUỘC: bỏ qua bulge gây lệch tới
   9,5 % diện tích (đã đo 23/11/2026).
3. **Chuẩn chiều** — biên ngoài ngược chiều kim đồng hồ, vùng loại trừ thuận chiều,
   để công thức diện tích tự trừ phần lỗ.
4. **Đối chiếu AREA** — so diện tích tính được với lệnh AREA của AutoCAD, hiện cả hai
   số. Lệch quá `area_lech_pct` thì DỪNG và hỏi.

## Ra
`boundary.geojson`, `exclude.geojson` (cùng với `nhap`), phần `properties` mang
`dien_tich_m2` và `dien_tich_area_cad_m2`.

## Cổng 2
Người xác nhận ranh giới lô và vùng loại trừ trước khi đặt lưới.
