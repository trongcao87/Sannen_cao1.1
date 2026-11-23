---
name: luoi
mo_ta: Đặt lưới ô vuông vừa biên lô, nội suy cao độ hai bề mặt lên từng đỉnh lưới.
giai_doan: 4
---
# luoi

## Lệnh
    python -m sannen.cli luoi --lot <thư mục lô> [--o 20] [--goc 0] [--goc-luoi E,N]
    python -m sannen.cli luoi --lot <thư mục lô> --resync

## Đặt lưới
Định nghĩa bằng: điểm gốc, góc xoay, kích thước ô (cho phép mỗi hàng/cột một kích
thước). Khác SNVN: chọn biên lô trước, tool tự tính hộp bao xoay theo cạnh dài của lô
và đặt lưới vừa khít — không phải chỉnh tay từng hàng cột.

Sửa lưới: đổi kích thước từng hàng/cột, chèn/xóa hàng cột, di chuyển và xoay toàn
lưới. Lưới bám sát biên làm giảm số ô vắt ranh đào–đắp — nguồn sai số chính của
phương pháp lưới ô vuông.

## Cắt mảnh theo ô — cách làm rẻ
Đừng dùng thư viện cắt đa giác tổng quát. Đổi toạ độ mọi mảnh về hệ của lưới (dời gốc,
xoay ngược góc lưới) thì đường lưới thành đường song song trục → chỉ cần
Sutherland–Hodgman cắt bằng đường thẳng, lặp theo số đường lưới đi qua hộp bao của
mảnh, thường chỉ một hoặc hai đường.

## --resync
Đọc ngược cao độ đỉnh lưới từ nhãn trong bản vẽ (`cad_read_grid_z`) khi người sửa
thẳng trong CAD thay vì ra lệnh cho agent. Agent BÁO chênh lệch trước khi nhận —
nếu không, bảng Excel và bản vẽ sẽ nói hai con số khác nhau mà không ai biết.

## Ra
`grid.json` — nút lưới với cao độ nội suy từ hai TIN, danh sách ô và diện tích hữu
hiệu sau cắt biên. Layer `SN-LUOI`, `SN-LUOI-NHAN`.

## Hỏi người trước khi chạy
Kích thước ô, góc và gốc lưới — theo yêu cầu hồ sơ. Nếu chỉ dẫn đo bóc đã chốt thì
dùng đúng, không tự chọn.
