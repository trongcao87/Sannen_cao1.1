---
name: xem3d
mo_ta: Sinh trình xem 3D (HTML tự chứa) cho hai bề mặt TIN Mốc và Đo để QS kiểm tra trực quan.
giai_doan: 13
---
# xem3d

Verb phụ trợ, chỉ ĐỌC kết quả của `mat` (và `lo`, `luoi`, `tinh` nếu đã chạy). Không đổi số liệu nào.

## Lệnh
    python -m sannen.cli xem3d --lot <thư mục lô> [--ra file.html] [--mo] [--phong-dai-z 2]

Mặc định ghi `20_output/tin3d_view.html`, không tự mở trình duyệt (`--mo` để mở).
Thiếu `surface_moc.json` / `surface_do.json` → báo lỗi, chạy `mat` trước.

## Dùng để làm gì
- Xem bề mặt mốc (xanh lá) và đo (xanh dương) chồng nhau; tách lớp, phóng đại Z 1–10×.
- Tô màu Δz = z đo − z mốc tại từng đỉnh: đắp đỏ, đào hổ phách, ≈ 0 xanh lơ.
- Soát nhanh tam giác thiếu dữ liệu, biên lô, ranh đào–đắp, lưới ô trước khi duyệt cổng.
- Rê chuột lên tam giác/đỉnh để đọc E, N, cao độ.

File chạy offline, không cần mạng, gửi cho người khác xem được. Đây là công cụ nhìn, không
thay cho bảng số của `xuat`.
